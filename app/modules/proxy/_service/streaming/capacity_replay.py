"""One cross-account replay for output-free capacity rejections on direct SSE.

Upstream can accept a Responses POST -- ``response.created`` and usually
``response.in_progress`` arrive -- and then reject it with
``server_is_overloaded`` (or another capacity terminal) before producing
anything. Every side effect of a Responses turn is reported as an output item
or as billed output tokens, so such a terminal is as replay-safe as a rejection
before acceptance: the same proof the HTTP bridge and WebSocket accepted replay
rely on (``http_bridge/accepted_replay.py``).

For a stream whose request may move to another account, ``_stream_once`` reads
upstream through ``CapacityReplayPrelude``, which holds the lifecycle prelude
back. When an output-free capacity terminal follows, the prelude is dropped and
the terminal reaches ``_stream_once`` as its first frame, which hands it to the
pre-visible failover (``raise_if_capacity_replay``). Anything else flushes the
held frames in order, so a turn that produces output is forwarded unchanged.
openspec: retry-http-accepted-overload-on-another-account.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.core.balancer.types import UpstreamError
from app.core.openai.parsing import classify_event_type, parse_sse_event_payload
from app.core.types import JsonValue
from app.core.utils.sse import parse_sse_data_json
from app.modules.proxy._load_balancer.types import AccountLease
from app.modules.proxy._service.http_bridge.accepted_replay import (
    _ACCEPTED_CAPACITY_REPLAY_ERROR_CODES,
    _ACCEPTED_REPLAY_FAIL_CLOSED_ERROR_CODES,
    _terminal_payload_reports_output,
)
from app.modules.proxy._service.streaming.helpers import _raw_stream_error_fields
from app.modules.proxy._service.support import _RetryableStreamError
from app.modules.proxy.helpers import is_upstream_model_capacity_error
from app.modules.proxy.work_admission import AdmissionLease

_PRELUDE_EVENT_TYPES = frozenset({"response.created", "response.in_progress", "response.queued"})
_TERMINAL_EVENT_TYPES = frozenset({"response.failed", "error"})
# The prelude is two or three lifecycle frames plus the odd metadata frame; a
# stream that keeps sending non-output frames stops being held instead of
# buffering without bound.
_MAX_HELD_FRAMES = 8


def is_output_free_capacity_terminal(event_type: str | None, payload: dict[str, JsonValue] | None) -> bool:
    """Return whether a terminal frame is a capacity rejection that proves no output.

    Capacity means ``server_is_overloaded``, ``overloaded_error``,
    ``model_at_capacity`` or the selected-model capacity message. Quota and
    rate-limit codes keep their stronger classification even with that message,
    and a terminal reporting output items or billed output/reasoning tokens is
    never replayable.
    """
    if event_type not in _TERMINAL_EVENT_TYPES or _terminal_payload_reports_output(payload):
        return False
    # ``_stream_once`` only reaches its retry branch for a frame that parses as a
    # lifecycle event; requiring the same here keeps both sides in agreement.
    if parse_sse_event_payload(payload) is None:
        return False
    _error_type, message, _param, code = _raw_stream_error_fields(event_type, payload)
    if code in _ACCEPTED_REPLAY_FAIL_CLOSED_ERROR_CODES:
        return False
    return code in _ACCEPTED_CAPACITY_REPLAY_ERROR_CODES or is_upstream_model_capacity_error(message)


class _AccountLeaseReleaser(Protocol):
    async def release_account_lease(self, lease: AccountLease | None) -> None: ...


def _is_prelude_frame(event_type: str | None) -> bool:
    if event_type in _PRELUDE_EVENT_TYPES:
        return True
    return event_type not in _TERMINAL_EVENT_TYPES and not (event_type or "").startswith("response.")


class CapacityReplayPrelude:
    """Upstream line iterator that holds the lifecycle prelude (see module docstring)."""

    def __init__(
        self,
        upstream: AsyncIterator[str],
        load_balancer: _AccountLeaseReleaser,
        admission_lease: AdmissionLease,
        account_lease: AccountLease | None,
    ) -> None:
        self._upstream = upstream
        self._load_balancer = load_balancer
        self._admission_lease = admission_lease
        self._account_lease = account_lease
        self._ready: list[str] = []
        self._deferred_error: Exception | None = None
        self._resolved = False
        # True once the held prelude was dropped for an output-free capacity
        # terminal; that terminal is then the only frame handed out.
        self.capacity_terminal = False

    def __aiter__(self) -> CapacityReplayPrelude:
        return self

    async def __anext__(self) -> str:
        if not self._resolved:
            self._resolved = True
            await self._resolve_prelude()
        if self._ready:
            return self._ready.pop(0)
        if self._deferred_error is not None:
            error, self._deferred_error = self._deferred_error, None
            raise error
        return await self._upstream.__anext__()

    async def _close_upstream(self) -> None:
        close = getattr(self._upstream, "aclose", None)
        if close is not None:
            await close()

    async def _resolve_prelude(self) -> None:
        held: list[str] = []
        while True:
            try:
                line = await self._upstream.__anext__()
            except Exception as exc:
                # EOF or a transport failure while holding: hand out the held
                # frames first, then the original failure, exactly as without
                # the hold.
                if not held:
                    raise
                self._ready = held
                self._deferred_error = exc
                return
            if not held:
                # Admission covers response creation only; release it when the
                # first frame arrives, as the unheld stream does. Both releases
                # are idempotent, so ``_stream_once`` releasing again is a no-op.
                self._admission_lease.release()
                await self._load_balancer.release_account_lease(self._account_lease)
            payload = parse_sse_data_json(line)
            event_type = classify_event_type(payload)
            if _is_prelude_frame(event_type) and len(held) < _MAX_HELD_FRAMES:
                held.append(line)
                continue
            if is_output_free_capacity_terminal(event_type, payload):
                self.capacity_terminal = True
                self._ready = [line]
                # ``_stream_once`` hands this terminal to the failover and never
                # reads again; close upstream now so its teardown runs here
                # instead of in the async-generator finalizer.
                await self._close_upstream()
                return
            self._ready = [*held, line]
            return


def hold_capacity_replay_prelude(
    upstream: AsyncIterator[str],
    enabled: bool,
    load_balancer: _AccountLeaseReleaser,
    admission_lease: AdmissionLease,
    account_lease: AccountLease | None,
) -> AsyncIterator[str]:
    """Wrap ``upstream`` in ``CapacityReplayPrelude`` only when the request may move accounts."""
    if not enabled:
        return upstream
    return CapacityReplayPrelude(upstream, load_balancer, admission_lease, account_lease)


def raise_if_capacity_replay(iterator: AsyncIterator[str], code: str, error: UpstreamError) -> None:
    """Hand an output-free capacity terminal to the pre-visible failover path."""
    if isinstance(iterator, CapacityReplayPrelude) and iterator.capacity_terminal:
        raise _RetryableStreamError(code, error, exclude_account=True, capacity_replay=True)
