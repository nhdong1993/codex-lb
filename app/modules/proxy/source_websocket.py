"""One source session with bounded sequential Responses turns.

The route supplies policy/preparation; this owner alone reads the upstream,
serializes downstream writes, and finalizes each dispatch before reuse. A
source with native Responses WebSocket keeps one upstream connection; any
other streaming source is bridged with one HTTP/SSE request per turn, the
session rebuilding full input for continuations of its own last response.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

import anyio
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from app.core import shutdown
from app.core.clock import Clock, Scheduler
from app.core.errors import is_previous_response_not_found_error, is_previous_response_not_found_public_shape
from app.core.types import JsonValue
from app.core.utils.shared_future import _await_cleanup_deferring_cancellation, _await_result_deferring_cancellation
from app.core.utils.sse import extract_sse_data
from app.db.session import get_background_session
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.api_keys.service import ApiKeysService, ApiKeyUsageReservationData
from app.modules.model_sources.aliases import source_request_payload
from app.modules.model_sources.catalog import source_model_upstream_id
from app.modules.model_sources.forwarding import (
    SOURCE_FIRST_FRAME_DEADLINE_SECONDS,
    ModelSourceForwardingError,
    SourceStreamUsageParser,
    SourceUsageHolder,
    classify_responses_frame,
)
from app.modules.model_sources.websocket import open_source_websocket, parse_source_event, source_ws_error
from app.modules.proxy._service.api_key_usage import _api_key_reservation_heartbeat_seconds
from app.modules.proxy._service.websocket.helpers import (
    _parse_websocket_payload,
    _websocket_continuity_error_fields,
    _websocket_event_error_code,
    _websocket_event_error_message,
    _websocket_event_error_param,
    _websocket_event_error_type,
    _WebSocketJsonObject,
)
from app.modules.proxy.helpers import _normalize_error_code
from app.modules.proxy.source_dispatch import CleanupScheduler, SourceDispatch, error_code_from_payload
from app.modules.proxy.source_ownership import SourceOwnershipError, source_revision
from app.modules.proxy.source_pool import MAX_SOURCE_ATTEMPTS, get_source_pool, retryable_source_error
from app.modules.proxy.websocket_input import WebSocketInputBuffer, WebSocketInputOverflow

logger = logging.getLogger(__name__)

_TRANSPORT_CLOSE_TIMEOUT_SECONDS = 2.0
_SESSION_CLEANUP_TIMEOUT_SECONDS = 5.0
# WebSocket-only envelope fields an HTTP Responses source must not receive.
_BRIDGE_DROPPED_FIELDS = frozenset({"type", "generate"})

type SourceUpstream = Literal["websocket", "http"]


@dataclass(frozen=True, slots=True)
class SourceSocketIdentity:
    source_id: str
    revision: str
    model: str
    upstream: SourceUpstream


@dataclass(slots=True)
class SourceWebSocketTurn:
    owner: SourceDispatch
    payload: dict[str, JsonValue]
    portable: bool
    deadline: float
    reserve: Callable[[], Awaitable[ApiKeyUsageReservationData | None]]
    upstream: SourceUpstream
    # Client input the turn was prepared from; a bridged session's transcript.
    client_input: JsonValue = None
    upstream_status_code: int = 101
    terminal_handed_off: bool = False
    terminal_error: ModelSourceForwardingError | None = None

    @property
    def identity(self) -> SourceSocketIdentity:
        return SourceSocketIdentity(
            self.owner.source.id, source_revision(self.owner.source, self.owner.model), self.owner.model, self.upstream
        )

    @property
    def local_warmup(self) -> bool:
        """HTTP Responses has no ``generate:false``; the bridge answers it itself."""
        return self.upstream == "http" and self.owner.warmup


@dataclass(frozen=True, slots=True)
class BridgedSourceEvents:
    """The open HTTP/SSE response of one bridged turn.

    ``blocks`` is consumed and closed by the relaying task only;
    ``close_transport`` is the stream's close latch and is safe from any task.
    """

    blocks: AsyncGenerator[str, None]
    upstream_status_code: int
    close_transport: Callable[[], Awaitable[None]]


class OpenBridgedSourceEvents(Protocol):
    async def __call__(self, owner: SourceDispatch, payload: dict[str, JsonValue], /) -> BridgedSourceEvents: ...


@dataclass(frozen=True, slots=True)
class _BridgeTranscript:
    """Full input plus delivered output items of the session's last completed bridged response."""

    response_id: str
    items_json: str
    size: int


def _bridge_input_items(value: JsonValue) -> list[JsonValue] | None:
    if value is None:
        return []
    if isinstance(value, str):
        return [{"role": "user", "content": value}]
    if isinstance(value, list):
        return value
    return None


def _json_text(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_size(value: JsonValue) -> int:
    return len(_json_text(value).encode("utf-8"))


def _resend_size(transcript: _BridgeTranscript, delta: list[JsonValue], rest: dict[str, JsonValue]) -> int:
    """Exact compact UTF-8 size of ``{**rest, "input": [*transcript items, *delta]}`` without reserializing history."""
    items = transcript.size + _json_size(delta) - 2 + (1 if transcript.size > 2 and delta else 0)
    rest_size = _json_size(rest)
    return rest_size - 1 + (1 if rest else 0) + len('"input":') + items + 1


class PrepareSourceTurn(Protocol):
    async def __call__(
        self,
        payload: dict[str, JsonValue],
        /,
        *,
        bound: SourceSocketIdentity | None,
        excluded: set[str],
        received_at: float,
    ) -> SourceWebSocketTurn | None: ...


@dataclass(frozen=True, slots=True)
class _QueuedTurn:
    payload: dict[str, JsonValue]
    received_at: float


class SourceWebSocketSession:
    def __init__(
        self,
        websocket: WebSocket,
        prepare: PrepareSourceTurn,
        *,
        client_send_lock: anyio.Lock,
        clock: Clock,
        scheduler: Scheduler,
        request_timeout: float,
        connect_timeout: float,
        idle_timeout: float,
        stream_idle_timeout: float,
        cleanup_scheduler: CleanupScheduler,
        expose_stale_previous_response_classifier: bool,
        input_buffer: WebSocketInputBuffer,
        open_http: OpenBridgedSourceEvents,
        transcript_limit: int,
    ) -> None:
        self.websocket = websocket
        self.prepare = prepare
        self.clock = clock
        self.scheduler = scheduler
        self.request_timeout = request_timeout
        self.connect_timeout = connect_timeout
        self.idle_timeout = idle_timeout
        self.stream_idle_timeout = stream_idle_timeout
        self.cleanup_scheduler = cleanup_scheduler
        self.expose_stale_previous_response_classifier = expose_stale_previous_response_classifier
        self.input_buffer = input_buffer
        self.open_http = open_http
        self.transcript_limit = transcript_limit
        self.upstream: ClientConnection | None = None
        self._http: BridgedSourceEvents | None = None
        self._http_close_task: asyncio.Task[None] | None = None
        self._transcript: _BridgeTranscript | None = None
        self._upstream_close_task: asyncio.Task[None] | None = None
        self.identity: SourceSocketIdentity | None = None
        self.queue: asyncio.Queue[_QueuedTurn] = asyncio.Queue(maxsize=1)
        self.send_lock = client_send_lock
        self.active = True
        self.last_activity = clock.monotonic()
        self.deadline: float | None = None
        self.turn: SourceWebSocketTurn | None = None
        self.deadline_expired = False

    def limit_preparation_deadline(self, deadline: float) -> float:
        """Apply a selected source's shorter budget before its policy awaits."""
        self.deadline = deadline if self.deadline is None else min(self.deadline, deadline)
        return self.deadline

    async def send(self, event: dict[str, JsonValue], *, turn: SourceWebSocketTurn | None = None) -> None:
        async with self.send_lock:
            if turn is not None:
                holder = turn.owner.usage_holder
                # Mark the transport handoff only after obtaining the write
                # lock: cancellation while queued has not delivered a frame.
                turn.terminal_handed_off = holder is not None and holder.terminal_kind is not None
                if (
                    classify_responses_frame(str(event["type"])) in {"content", "success_terminal"}
                    and not turn.owner.warmup
                ):
                    turn.owner.content_delivered = True
            await self.scheduler.wait_for(
                self.websocket.send_text(json.dumps(event, ensure_ascii=True, separators=(",", ":"))),
                timeout=min(self.stream_idle_timeout, self.request_timeout, self.idle_timeout),
            )

    async def send_error(self, error: ModelSourceForwardingError) -> None:
        await self.send({"type": "error", "status": error.status_code, **error.payload})

    def _terminal_error(self, event: dict[str, JsonValue], event_type: str) -> ModelSourceForwardingError:
        code = _normalize_error_code(
            _websocket_event_error_code(event_type, event), _websocket_event_error_type(event_type, event)
        )
        param = _websocket_event_error_param(event_type, event)
        message = _websocket_event_error_message(event_type, event)
        if is_previous_response_not_found_public_shape(code=code, param=param, message=message):
            recoverable = is_previous_response_not_found_error(code=code, param=param, message=message)
            safe_code, safe_message = _websocket_continuity_error_fields(
                reason="previous_response_not_found" if recoverable else "malformed_previous_response",
                expose_stale_previous_response_classifier=self.expose_stale_previous_response_classifier,
            )
            return source_ws_error(safe_code, safe_message, status=502)
        return source_ws_error("model_source_response_failed", "Model source failed the response", status=502)

    async def _close_http(self) -> None:
        events = self._http
        if events is None:
            return
        if self._http_close_task is None:

            async def close() -> None:
                try:
                    await events.close_transport()
                except Exception:
                    logger.warning("source_bridge_close_failed")

            # Every closer joins one task: none may finish the turn, and so
            # return its admission, while the HTTP response is still open.
            self._http_close_task = self.scheduler.create_task(close(), name="source-bridge-close")
        await _await_cleanup_deferring_cancellation(self._http_close_task, scheduler=self.scheduler)

    async def _close_upstream(self) -> None:
        await self._close_http()
        upstream = self.upstream
        if upstream is None:
            return
        if self._upstream_close_task is None:

            async def close() -> None:
                try:
                    await self.scheduler.wait_for(upstream.close(), timeout=_TRANSPORT_CLOSE_TIMEOUT_SECONDS)
                except Exception:
                    logger.warning("source_websocket_close_failed")
                finally:
                    # Even a peer that never acknowledges close must stop
                    # consuming this source's admission before it is released.
                    upstream.transport.abort()

            self._upstream_close_task = self.scheduler.create_task(close(), name="source-ws-upstream-close")
        await _await_cleanup_deferring_cancellation(self._upstream_close_task, scheduler=self.scheduler)

    async def _close_downstream(self) -> None:
        async def close() -> None:
            async with self.send_lock:
                await self.websocket.close(code=1012 if shutdown.is_draining() else 1000)

        try:
            await self.scheduler.wait_for(close(), timeout=_TRANSPORT_CLOSE_TIMEOUT_SECONDS)
        except (TimeoutError, OSError, RuntimeError, WebSocketDisconnect):
            pass

    async def _finish_interrupted(self, turn: SourceWebSocketTurn) -> None:
        if turn.local_warmup:
            # Reached on every exit, including before the worker ran it.
            await turn.owner.discard()
            return
        await self._close_upstream()
        holder = turn.owner.usage_holder
        if holder is not None and holder.terminal_kind in {"failed", "error"}:
            await turn.owner.finish_with_forwarding_error(
                turn.terminal_error
                or source_ws_error("model_source_response_failed", "Model source failed the response", status=502)
            )
        elif turn.terminal_handed_off and holder is not None and holder.terminal_kind in {"completed", "incomplete"}:
            await turn.owner.finish(
                status="success", upstream_status_code=turn.upstream_status_code, trial_result="success"
            )
        elif self.deadline_expired:
            await turn.owner.finish_with_forwarding_error(
                source_ws_error("model_source_timeout", "Model source WebSocket response timed out", status=504)
            )
        else:
            await turn.owner.finish(status="cancelled", error_code="client_disconnected")

    async def _receive(self) -> None:
        while True:
            message = await self.input_buffer.receive()
            if message["type"] == "websocket.disconnect":
                return
            self.last_activity = self.input_buffer.received_at
            value = message.get("text")
            payload = parse_source_event(value) if isinstance(value, str) else None
            if payload is not None and isinstance(value, str):
                # Preserve duplicate capability carriers for the same strict
                # security intent parser used by subscription sessions.
                payload = _parse_websocket_payload(value)
            if payload is None:
                await self.send_error(source_ws_error("invalid_request_error", "Expected a bounded JSON text object"))
                continue
            event_type = payload.get("type")
            if event_type != "response.create" or "stream_id" in payload:
                await self.send_error(
                    source_ws_error(
                        "unsupported_operation", "Source sessions support sequential response.create events only"
                    )
                )
                continue
            if payload.get("background") is True or (
                "generate" in payload and not isinstance(payload["generate"], bool)
            ):
                await self.send_error(source_ws_error("unsupported_operation", "Invalid source generation controls"))
                continue
            if shutdown.is_draining():
                await self.send_error(source_ws_error("server_draining", "Server is draining; reconnect", status=503))
                continue
            try:
                self.queue.put_nowait(_QueuedTurn(payload, self.last_activity))
            except asyncio.QueueFull:
                await self.send_error(
                    source_ws_error(
                        "websocket_queue_full", "One response is active and one is already queued", status=429
                    )
                )

    async def _lifecycle(self) -> None:
        while True:
            await self.scheduler.sleep(0.25)
            if self.deadline is not None and self.clock.monotonic() >= self.deadline:
                self.deadline_expired = True
                return
            if shutdown.is_draining():
                remaining = shutdown.remaining_drain_timeout_seconds()
                if not self.active or (remaining is not None and remaining <= 0):
                    return
            elif (
                not self.active
                and self.queue.empty()
                and self.clock.monotonic() - self.last_activity >= self.idle_timeout
            ):
                return

    def _observe(self, turn: SourceWebSocketTurn) -> tuple[SourceUsageHolder, SourceStreamUsageParser]:
        owner = turn.owner
        holder = SourceUsageHolder()
        owner.event_usage = holder
        parser = SourceStreamUsageParser(
            holder,
            response_shape="responses",
            model=owner.model,
            upstream_model=source_model_upstream_id(owner.source, owner.model),
        )
        return holder, parser

    async def _relay(self, turn: SourceWebSocketTurn) -> None:
        assert self.upstream is not None
        owner = turn.owner
        holder, parser = self._observe(turn)
        payload = source_request_payload(owner.source, turn.payload)
        payload.pop("stream", None)
        payload.pop("background", None)
        payload.pop("stream_options", None)
        payload["type"] = "response.create"
        owner.sent_at = self.clock.monotonic()
        # From this await onwards delivery may be ambiguous: never replay.
        await self.upstream.send(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
        while True:
            receive_timeout = self.stream_idle_timeout
            if holder.first_frame_at is None:
                receive_timeout = min(receive_timeout, SOURCE_FIRST_FRAME_DEADLINE_SECONDS)
            value = await self.scheduler.wait_for(self.upstream.recv(), timeout=receive_timeout)
            event: dict[str, JsonValue] | None = parse_source_event(value)
            if event is None or not isinstance(event.get("type"), str) or "stream_id" in event:
                raise source_ws_error(
                    "model_source_invalid_event", "Model source returned an unsupported event", status=502
                )
            event_type = str(event["type"])
            if event_type != "error" and not event_type.startswith("response."):
                raise source_ws_error(
                    "model_source_invalid_event", "Model source returned an unsupported event", status=502
                )
            await self._relay_event(turn, holder, parser, event)
            if holder.terminal_kind is not None:
                await self._finish_relayed(turn)
                return

    async def _relay_http(self, turn: SourceWebSocketTurn) -> None:
        events = self._http
        assert events is not None
        holder, parser = self._observe(turn)
        output_items: list[JsonValue] = []
        try:
            async for block in events.blocks:
                data = extract_sse_data(block)
                if data is None:
                    # Comments, keepalives and ``[DONE]`` carry nothing to relay.
                    continue
                event = parse_source_event(data)
                if event is None or not isinstance(event.get("type"), str) or "stream_id" in event:
                    raise source_ws_error(
                        "model_source_invalid_event", "Model source returned an unsupported event", status=502
                    )
                event_type = str(event["type"])
                if event_type != "error" and not event_type.startswith("response."):
                    # Vendor events such as ``codex.rate_limits`` describe the
                    # source's own upstream, not this client's session.
                    continue
                delivered = await self._relay_event(turn, holder, parser, event)
                item = delivered.get("item")
                if event_type == "response.output_item.done" and isinstance(item, dict):
                    output_items.append(item)
                if holder.terminal_kind is not None:
                    self._remember(turn, delivered, output_items)
                    # Close the response before finishing returns admission.
                    await self._close_http()
                    await self._finish_relayed(turn)
                    return
        finally:
            await _await_cleanup_deferring_cancellation(events.blocks.aclose(), scheduler=self.scheduler)
        raise source_ws_error(
            "model_source_stream_truncated", "Model source disconnected before completing the response", status=502
        )

    async def _relay_event(
        self,
        turn: SourceWebSocketTurn,
        holder: SourceUsageHolder,
        parser: SourceStreamUsageParser,
        event: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Validate, observe, publish and deliver one upstream event; returns the event as delivered."""
        owner = turn.owner
        event_type = str(event["type"])
        if event_type in {"response.created", "response.completed", "response.incomplete", "response.failed"}:
            if not isinstance(event.get("response"), dict):
                raise source_ws_error(
                    "model_source_invalid_event", "Model source returned an invalid response envelope", status=502
                )
            response = event["response"]
            if isinstance(response, dict) and "output" in response:
                output = response["output"]
                if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
                    raise source_ws_error(
                        "model_source_invalid_event", "Model source returned invalid response output", status=502
                    )
        if holder.first_frame_at is None:
            holder.first_frame_at = self.clock.monotonic()
        parser.observe_event(event)
        response = event.get("response")
        if owner.warmup and (
            classify_responses_frame(event_type) == "content"
            or (isinstance(response, dict) and bool(response.get("output")))
            or (holder.usage is not None and holder.usage.output_tokens > 0)
        ):
            raise source_ws_error(
                "model_source_warmup_invalid", "Model source generated output during warmup", status=502
            )
        if event_type in {"error", "response.failed"}:
            # Do not echo provider errors containing source secrets/URLs.
            error = self._terminal_error(event, event_type)
            error.upstream_status_code = turn.upstream_status_code
            turn.terminal_error = error
            if event_type == "response.failed" and isinstance(response, dict):
                event = {
                    "type": event_type,
                    "response": {
                        "id": response.get("id"),
                        "object": "response",
                        "status": "failed",
                        "model": owner.model,
                        "error": error.payload["error"],
                    },
                }
            else:
                event = {"type": "error", "status": 502, **error.payload}
        if owner.ownership is not None:
            await owner.ownership.record_event(event)
        owner.observe_stream()
        await self.send(event, turn=turn)
        return event

    async def _finish_relayed(self, turn: SourceWebSocketTurn) -> None:
        owner = turn.owner
        holder = owner.usage_holder
        assert holder is not None and holder.terminal_kind is not None
        if holder.terminal_kind in {"completed", "incomplete"}:
            await owner.finish(status="success", upstream_status_code=turn.upstream_status_code, trial_result="success")
        else:
            assert turn.terminal_error is not None
            await owner.finish_with_forwarding_error(turn.terminal_error)
        if owner.settlement_failed or owner.reservation_release_failed:
            raise source_ws_error("usage_settlement_failed", "Unable to finalize source usage; reconnect", status=502)

    def _remember(
        self, turn: SourceWebSocketTurn, terminal: dict[str, JsonValue], output_items: list[JsonValue]
    ) -> None:
        """Keep only a completed response continuable, as Codex does."""
        self._transcript = None
        response = terminal.get("response")
        if terminal.get("type") != "response.completed" or not isinstance(response, dict):
            return
        response_id = response.get("id")
        if isinstance(response_id, str) and response_id:
            self._store_transcript(response_id, turn.client_input, output_items)

    def _store_transcript(self, response_id: str, client_input: JsonValue, output_items: list[JsonValue]) -> None:
        items = _bridge_input_items(client_input)
        if items is None:
            return
        text = _json_text([*items, *output_items])
        size = len(text.encode("utf-8"))
        # Bounded like the equivalent HTTP full resend; a larger one is dropped.
        if size <= self.transcript_limit:
            self._transcript = _BridgeTranscript(response_id, text, size)

    def _expand_continuation(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Replace a continuation of the last bridged response by the full input Codex would resend over HTTP.

        Other ``previous_response_id`` values pass through: preparation keeps
        subscription-anchor and ownership precedence, then fails them closed.
        """
        transcript = self._transcript
        if transcript is None or payload.get("previous_response_id") != transcript.response_id:
            return payload
        delta = _bridge_input_items(payload.get("input"))
        if delta is None:
            raise source_ws_error("invalid_request_error", "input must be a string or an array of input items")
        # Bound the whole HTTP-equivalent resend, not only its input.
        rest = {
            key: value
            for key, value in payload.items()
            if key not in {"type", "generate", "previous_response_id", "input"}
        }
        if _resend_size(transcript, delta, rest) > self.transcript_limit:
            raise source_ws_error(
                "invalid_request_error", "The reconstructed request exceeds the Responses request size limit"
            )
        # Keep the frame's raw key pairs: security routing inspects duplicated
        # capability carriers that a plain dict copy would collapse.
        pairs = payload.raw_pairs if isinstance(payload, _WebSocketJsonObject) else tuple(payload.items())
        return _WebSocketJsonObject(
            [(key, value) for key, value in pairs if key not in {"previous_response_id", "input"}]
            + [("input", [*json.loads(transcript.items_json), *delta])]
        )

    async def _answer_local_warmup(self, turn: SourceWebSocketTurn) -> None:
        owner = turn.owner
        # The warmup's equivalent of a successful open: bind before the
        # completion so an immediate continuation stays on this source.
        self.identity = turn.identity
        response_id = f"resp_{uuid4().hex}"
        self._transcript = None
        self._store_transcript(response_id, turn.client_input, [])
        envelope: dict[str, JsonValue] = {
            "id": response_id,
            "object": "response",
            "created_at": int(self.clock.time()),
            "model": owner.model,
            "output": [],
        }
        await self.send({"type": "response.created", "response": {**envelope, "status": "in_progress"}})
        await self.send({"type": "response.completed", "response": {**envelope, "status": "completed"}})
        await owner.discard()

    async def _open_http(self, turn: SourceWebSocketTurn) -> None:
        # Its continuation, if any, was expanded before preparation; only this
        # turn's completion can make the session continuable again.
        self._transcript = None
        payload = {key: value for key, value in turn.payload.items() if key not in _BRIDGE_DROPPED_FIELDS}
        payload["stream"] = True
        turn.owner.sent_at = self.clock.monotonic()
        # The previous turn finished only after its response was closed.
        self._http, self._http_close_task = None, None
        try:
            self._http = await self.scheduler.wait_for(
                self.open_http(turn.owner, payload), timeout=max(0, turn.deadline - self.clock.monotonic())
            )
        except TimeoutError:
            # The open converts its own phase timeouts; this is the turn
            # deadline. The request may have been sent, so it is never retried.
            raise source_ws_error("model_source_timeout", "Model source response timed out", status=504) from None
        turn.upstream_status_code = self._http.upstream_status_code

    async def _heartbeat(self, owner: SourceDispatch) -> None:
        while owner.reservation is not None and not owner.finished:
            await self.scheduler.sleep(_api_key_reservation_heartbeat_seconds())
            if owner.finished:
                return
            try:
                async with get_background_session() as session:
                    await ApiKeysService(ApiKeysRepository(session)).touch_usage_reservation(
                        owner.reservation.reservation_id
                    )
            except Exception:
                # A failed touch must not permanently remove protection from
                # the stale-reservation reaper while this turn is still live.
                logger.warning(
                    "source_websocket_reservation_touch_failed request_id=%s",
                    owner.request_id,
                    exc_info=True,
                )

    async def _generation(self, turn: SourceWebSocketTurn) -> bool:
        heartbeat = self.scheduler.create_task(self._heartbeat(turn.owner), name="source-ws-reservation")
        relay = self._relay(turn) if turn.upstream == "websocket" else self._relay_http(turn)
        try:
            await self.scheduler.wait_for(relay, timeout=max(0, turn.deadline - self.clock.monotonic()))
        except TimeoutError:
            error = source_ws_error("model_source_timeout", "Model source WebSocket response timed out", status=504)
            await self._close_upstream()
            if turn.terminal_handed_off:
                await self._finish_interrupted(turn)
                return False
            await turn.owner.finish_with_forwarding_error(error)
            raise error from None
        except (ConnectionClosed, OSError):
            error = source_ws_error(
                "model_source_stream_truncated", "Model source disconnected before completing the response", status=502
            )
            await self._close_upstream()
            if turn.terminal_handed_off:
                await self._finish_interrupted(turn)
                return False
            await turn.owner.finish_with_forwarding_error(error)
            raise error from None
        except SourceOwnershipError:
            error = source_ws_error(
                "model_source_ownership_unavailable", "Unable to record model source continuity", status=502
            )
            await self._close_upstream()
            await turn.owner.finish_with_forwarding_error(error)
            raise error from None
        except ModelSourceForwardingError as error:
            await self._close_upstream()
            await turn.owner.finish_with_forwarding_error(error)
            raise
        finally:
            heartbeat.cancel()
            await _await_cleanup_deferring_cancellation(
                asyncio.gather(heartbeat, return_exceptions=True), scheduler=self.scheduler
            )
            if not turn.owner.finished:
                await self._finish_interrupted(turn)
        return True

    async def _reserve(self, turn: SourceWebSocketTurn) -> None:
        async def acquire() -> None:
            reservation, cancellation = await _await_result_deferring_cancellation(
                turn.reserve(), scheduler=self.scheduler
            )
            turn.owner.reservation = reservation
            if cancellation is not None:
                raise cancellation

        try:
            await self.scheduler.wait_for(acquire(), timeout=max(0, turn.deadline - self.clock.monotonic()))
        except TimeoutError:
            raise source_ws_error("model_source_timeout", "Source reservation timed out", status=504) from None

    async def _worker(
        self, first: SourceWebSocketTurn, first_payload: dict[str, JsonValue], received_at: float
    ) -> None:
        turn = first
        raw = _QueuedTurn(first_payload, received_at)
        while True:
            self.active = True
            self.turn = turn
            self.deadline = turn.deadline
            attempted: set[str] = set()
            try:
                if turn.local_warmup:
                    await self._answer_local_warmup(turn)
                else:
                    await self._reserve(turn)
                    # Only an unbound portable initial turn may try another
                    # source after a retryable open failure. Bound sessions never move.
                    while True:
                        attempted.add(turn.owner.source.id)
                        try:
                            if turn.upstream == "http":
                                await self._open_http(turn)
                            elif self.upstream is None:
                                self.upstream = await open_source_websocket(
                                    turn.owner.source,
                                    timeout=max(
                                        0.001, min(self.connect_timeout, turn.deadline - self.clock.monotonic())
                                    ),
                                )
                            break
                        except ModelSourceForwardingError as error:
                            await turn.owner.finish_with_forwarding_error(error)
                            task = asyncio.current_task()
                            if task is not None and task.cancelling():
                                raise asyncio.CancelledError
                            if turn.owner.settlement_failed or turn.owner.reservation_release_failed:
                                raise source_ws_error(
                                    "usage_settlement_failed", "Unable to finalize source usage; reconnect", status=502
                                ) from None
                            get_source_pool().failed(turn.owner.source, error)
                            if (
                                self.identity is not None
                                or not turn.portable
                                or not retryable_source_error(error)
                                or len(attempted) >= MAX_SOURCE_ATTEMPTS
                            ):
                                raise
                            try:
                                prepared = await self.scheduler.wait_for(
                                    self.prepare(
                                        raw.payload, bound=None, excluded=attempted, received_at=raw.received_at
                                    ),
                                    timeout=max(0, raw.received_at + self.request_timeout - self.clock.monotonic()),
                                )
                            except TimeoutError:
                                raise source_ws_error(
                                    "model_source_timeout", "Source retry preparation timed out", status=504
                                ) from None
                            except ModelSourceForwardingError as retry_error:
                                # Like the HTTP pool, report the source's own
                                # failure when no replacement is selectable.
                                if (
                                    turn.upstream == "http"
                                    and error_code_from_payload(retry_error.payload) == "model_source_busy"
                                ):
                                    raise error from None
                                raise
                            if prepared is None:
                                raise error
                            turn = prepared
                            self.turn = turn
                            self.deadline = turn.deadline
                            await self._reserve(turn)
                    self.identity = turn.identity
                    if not await self._generation(turn):
                        return
            except ModelSourceForwardingError as error:
                if not turn.owner.finished:
                    await self._close_upstream()
                    await turn.owner.finish_with_forwarding_error(error)
                raise
            finally:
                if not turn.owner.finished:
                    await self._finish_interrupted(turn)
            # Dispatch finalization defers cancellation until settlement is
            # durable. Do not enter another queue wait after that cancellation.
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError
            self.active = False
            self.deadline = None
            self.turn = None
            self.last_activity = self.clock.monotonic()
            raw = await self.queue.get()
            self.active = True
            self.deadline = raw.received_at + self.request_timeout
            if shutdown.is_draining():
                return
            try:
                # Waiting in the queue spends the same request budget; policy
                # and ownership are read again only when the turn can dispatch.
                remaining = self.request_timeout - (self.clock.monotonic() - raw.received_at)
                turn_or_none = await self.scheduler.wait_for(
                    self.prepare(
                        self._expand_continuation(raw.payload),
                        bound=self.identity,
                        excluded=set(),
                        received_at=raw.received_at,
                    ),
                    timeout=max(0, remaining),
                )
                if turn_or_none is None:
                    raise source_ws_error(
                        "websocket_reconnect_required", "Reconnect to change the session model or backend", status=409
                    )
                turn = turn_or_none
            except TimeoutError:
                raise source_ws_error(
                    "model_source_timeout", "Queued response expired before dispatch", status=504
                ) from None

    async def run(
        self, first_payload: dict[str, JsonValue], received_at: float
    ) -> Literal["subscription", "handled", "closed"]:
        first: SourceWebSocketTurn | None = None
        handoff = False
        self.deadline = received_at + self.request_timeout

        async def prepare_first() -> None:
            nonlocal first
            # Retain a late result for cleanup even if persistence deferred
            # cancellation after it claimed admission.
            first = await self.prepare(first_payload, bound=None, excluded=set(), received_at=received_at)

        preparation = self.scheduler.create_task(prepare_first(), name="source-ws-prepare")
        reader = self.scheduler.create_task(self.input_buffer.observe_disconnect(), name="source-ws-preflight-client")
        lifecycle = self.scheduler.create_task(self._lifecycle(), name="source-ws-lifecycle")
        tasks = [preparation, reader, lifecycle]
        worker: asyncio.Task[None] | None = None

        async def stop_preparation_reader() -> bool:
            reader.cancel()
            cancellation = await _await_cleanup_deferring_cancellation(
                asyncio.gather(reader, return_exceptions=True), scheduler=self.scheduler
            )
            if cancellation is not None:
                raise cancellation
            if not reader.cancelled():
                # A disconnect/overflow may have won just as preparation
                # completed. Its consumed ASGI message cannot be handed back.
                reader.result()
                return True
            return False

        async def send_session_error(error: ModelSourceForwardingError) -> bool:
            send_task = self.scheduler.create_task(self.send_error(error), name="source-ws-error")
            tasks.append(send_task)
            watchers = {send_task, reader}
            if not self.deadline_expired:
                watchers.add(lifecycle)
            done, _ = await self.scheduler.wait(
                watchers, timeout=_TRANSPORT_CLOSE_TIMEOUT_SECONDS, return_when=asyncio.FIRST_COMPLETED
            )
            if send_task in done:
                try:
                    send_task.result()
                except (TimeoutError, OSError, RuntimeError, WebSocketDisconnect):
                    return False
                return True
            return False

        def observe_end(done: set[asyncio.Future[None]]) -> bool:
            if reader in done:
                reader.result()
                return True
            if lifecycle in done:
                lifecycle.result()
                (worker if worker is not None else preparation).cancel()
                if self.deadline_expired and (self.turn is None or not self.turn.terminal_handed_off):
                    raise source_ws_error(
                        "model_source_timeout", "Model source WebSocket response timed out", status=504
                    )
                return True
            return False

        try:
            done, _ = await self.scheduler.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if observe_end(done):
                return "closed"
            try:
                preparation.result()
            except ModelSourceForwardingError as error:
                delivered = await send_session_error(error)
                ended = await stop_preparation_reader()
                handoff = delivered and not ended and not lifecycle.done()
                return "handled" if handoff else "closed"
            # Stop read-ahead before giving receive ownership back to the
            # subscription loop or to the source's regular reader. Buffered
            # messages and their original timestamps survive this transition.
            if await stop_preparation_reader():
                return "closed"
            if lifecycle.done():
                if observe_end({lifecycle}):
                    return "closed"
            if first is None:
                handoff = True
                return "subscription"
            self.turn = first
            self.deadline = first.deadline
            reader = self.scheduler.create_task(self._receive(), name="source-ws-client")
            worker = self.scheduler.create_task(self._worker(first, first_payload, received_at), name="source-ws-turn")
            tasks.extend((reader, worker))
            done, _ = await self.scheduler.wait({reader, worker, lifecycle}, return_when=asyncio.FIRST_COMPLETED)
            if not observe_end(done):
                worker.result()
        except WebSocketInputOverflow:
            await send_session_error(
                source_ws_error(
                    "websocket_queue_full", "Too many frames while resolving the session backend", status=429
                )
            )
        except ModelSourceForwardingError as error:
            await send_session_error(error)
        except (WebSocketDisconnect, ConnectionClosed):
            pass
        except Exception as error:
            logger.error("source_websocket_failure kind=%s", type(error).__name__)
            await send_session_error(
                source_ws_error("model_source_websocket_failed", "Source session failed", status=502)
            )
        finally:

            async def cleanup() -> None:
                for task in tasks:
                    task.cancel()
                if handoff:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    return
                remaining = shutdown.remaining_post_drain_cleanup_timeout_seconds()
                if remaining is None:
                    remaining = shutdown.remaining_drain_timeout_seconds()
                budget = (
                    _SESSION_CLEANUP_TIMEOUT_SECONDS
                    if remaining is None
                    else min(_SESSION_CLEANUP_TIMEOUT_SECONDS, max(0, remaining))
                )
                cleanup_deadline = self.clock.monotonic() + budget
                await asyncio.gather(self._close_upstream(), self._close_downstream())

                async def finalize() -> None:
                    await _await_cleanup_deferring_cancellation(
                        asyncio.gather(*tasks, return_exceptions=True), scheduler=self.scheduler
                    )
                    if first is not None and not first.owner.finished:
                        await self._finish_interrupted(first)

                cleanup_task = self.cleanup_scheduler._schedule_cancel_safe_cleanup(
                    finalize(),
                    action="source_websocket_finalize",
                    request_id=first.owner.request_id if first is not None and first.owner.request_id else "source-ws",
                )
                done, _ = await self.scheduler.wait(
                    {cleanup_task}, timeout=max(0, cleanup_deadline - self.clock.monotonic())
                )
                if not done:
                    logger.warning("source_websocket_cleanup_deferred")

            cancellation = await _await_cleanup_deferring_cancellation(cleanup(), scheduler=self.scheduler)
            if cancellation is not None:
                raise cancellation
        return "closed"
