from __future__ import annotations

import json
from collections.abc import AsyncIterator

import aiohttp
import pytest

from app.modules.proxy._service.streaming.capacity_replay import (
    CapacityReplayPrelude,
    hold_capacity_replay_prelude,
    is_output_free_capacity_terminal,
    raise_if_capacity_replay,
)
from app.modules.proxy._service.support import _RetryableStreamError
from app.modules.proxy.work_admission import AdmissionLease

pytestmark = pytest.mark.unit

_OVERLOADED = "Our servers are currently overloaded. Please try again later."
_SELECTED_MODEL_CAPACITY = "Selected model is at capacity. Please try a different model."


def _line(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _created(response_id: str = "resp_1") -> str:
    return _line({"type": "response.created", "response": {"id": response_id, "status": "in_progress"}})


def _in_progress(response_id: str = "resp_1") -> str:
    return _line({"type": "response.in_progress", "response": {"id": response_id, "status": "in_progress"}})


def _failed(code: str | None = "server_is_overloaded", message: str = _OVERLOADED, **response: object) -> str:
    error: dict[str, object] = {"message": message}
    if code is not None:
        error["code"] = code
    return _line({"type": "response.failed", "response": {"id": "resp_1", "error": error, **response}})


def _output_item_added() -> str:
    return _line(
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {"id": "msg_1", "type": "message", "role": "assistant", "content": []},
        }
    )


class _Upstream:
    def __init__(self, lines: list[str], error: Exception | None = None) -> None:
        self._lines = list(lines)
        self._error = error
        self.reads = 0

    def __aiter__(self) -> _Upstream:
        return self

    async def __anext__(self) -> str:
        self.reads += 1
        if self._lines:
            return self._lines.pop(0)
        if self._error is not None:
            raise self._error
        raise StopAsyncIteration


class _LoadBalancer:
    def __init__(self) -> None:
        self.released: list[object] = []

    async def release_account_lease(self, lease: object) -> None:
        self.released.append(lease)


def _prelude(upstream: _Upstream, load_balancer: _LoadBalancer | None = None) -> CapacityReplayPrelude:
    iterator = hold_capacity_replay_prelude(
        upstream,
        True,
        load_balancer or _LoadBalancer(),
        AdmissionLease(None, stage="response_create"),
        None,
    )
    assert isinstance(iterator, CapacityReplayPrelude)
    return iterator


async def _drain(iterator: AsyncIterator[str]) -> list[str]:
    return [line async for line in iterator]


@pytest.mark.asyncio
async def test_disabled_hold_returns_the_upstream_iterator_unchanged() -> None:
    upstream = _Upstream([_created()])

    iterator = hold_capacity_replay_prelude(
        upstream, False, _LoadBalancer(), AdmissionLease(None, stage="response_create"), None
    )

    assert iterator is upstream


@pytest.mark.asyncio
async def test_output_flushes_the_held_prelude_in_order() -> None:
    lines = [_created(), _in_progress(), _output_item_added(), _line({"type": "response.completed"})]
    iterator = _prelude(_Upstream(lines))

    assert await _drain(iterator) == lines
    assert iterator.capacity_terminal is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("server_is_overloaded", _OVERLOADED),
        ("overloaded_error", _OVERLOADED),
        ("model_at_capacity", "Model is at capacity."),
        ("invalid_request_error", _SELECTED_MODEL_CAPACITY),
    ],
)
async def test_output_free_capacity_terminal_drops_the_prelude(code: str, message: str) -> None:
    terminal = _failed(code, message)
    iterator = _prelude(_Upstream([_created(), _in_progress(), terminal]))

    assert await _drain(iterator) == [terminal]
    assert iterator.capacity_terminal is True
    with pytest.raises(_RetryableStreamError) as exc_info:
        raise_if_capacity_replay(iterator, code, {"message": message})
    assert exc_info.value.capacity_replay is True
    assert exc_info.value.exclude_account is True


@pytest.mark.asyncio
async def test_first_event_capacity_terminal_is_flagged() -> None:
    terminal = _failed()
    iterator = _prelude(_Upstream([terminal]))

    assert await _drain(iterator) == [terminal]
    assert iterator.capacity_terminal is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal",
    [
        _failed(usage={"input_tokens": 3, "output_tokens": 1}),
        _failed(usage={"output_tokens": 0, "output_tokens_details": {"reasoning_tokens": 2}}),
        _failed(output=[{"id": "msg_1", "type": "message"}]),
        _failed("server_error", "An error occurred while processing your request."),
        _failed("usage_limit_reached", _SELECTED_MODEL_CAPACITY),
        _failed("rate_limit_exceeded", _SELECTED_MODEL_CAPACITY),
    ],
    ids=["output-tokens", "reasoning-tokens", "output-items", "server-error", "usage-limit", "rate-limit"],
)
async def test_terminals_without_the_output_free_capacity_proof_flush_unchanged(terminal: str) -> None:
    lines = [_created(), _in_progress(), terminal]
    iterator = _prelude(_Upstream(lines))

    assert await _drain(iterator) == lines
    assert iterator.capacity_terminal is False
    raise_if_capacity_replay(iterator, "server_is_overloaded", {"message": _OVERLOADED})


@pytest.mark.asyncio
async def test_eof_while_holding_hands_out_the_prelude_before_ending() -> None:
    lines = [_created(), _in_progress()]
    iterator = _prelude(_Upstream(lines))

    assert await _drain(iterator) == lines


@pytest.mark.asyncio
async def test_transport_error_while_holding_hands_out_the_prelude_then_raises() -> None:
    error = aiohttp.ClientPayloadError("connection reset")
    iterator = _prelude(_Upstream([_created()], error=error))

    assert await iterator.__anext__() == _created()
    with pytest.raises(aiohttp.ClientPayloadError):
        await iterator.__anext__()


@pytest.mark.asyncio
async def test_transport_error_before_any_frame_raises_immediately() -> None:
    iterator = _prelude(_Upstream([], error=aiohttp.ClientPayloadError("reset")))

    with pytest.raises(aiohttp.ClientPayloadError):
        await iterator.__anext__()


@pytest.mark.asyncio
async def test_response_create_admission_is_released_on_the_first_frame() -> None:
    load_balancer = _LoadBalancer()
    upstream = _Upstream([_created(), _in_progress(), _output_item_added()])
    iterator = _prelude(upstream, load_balancer)

    await iterator.__anext__()

    assert load_balancer.released == [None]


@pytest.mark.asyncio
async def test_a_prelude_that_never_ends_stops_being_held() -> None:
    metadata = [_line({"type": "codex.rate_limits", "index": index}) for index in range(12)]
    upstream = _Upstream([*metadata, _failed()])
    iterator = _prelude(upstream)

    first = await iterator.__anext__()

    assert first == metadata[0]
    assert upstream.reads == 9
    assert iterator.capacity_terminal is False


def test_capacity_terminal_classifier_requires_a_terminal_event() -> None:
    assert is_output_free_capacity_terminal("response.created", {"type": "response.created"}) is False
    assert (
        is_output_free_capacity_terminal(
            "error", {"type": "error", "error": {"code": "server_is_overloaded", "message": _OVERLOADED}}
        )
        is True
    )
