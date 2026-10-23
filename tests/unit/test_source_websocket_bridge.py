from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import anyio
import pytest

from app.core.clock import REAL_CLOCK, REAL_SCHEDULER
from app.modules.proxy.source_websocket import BridgedSourceEvents, SourceWebSocketSession


def _session() -> SourceWebSocketSession:
    unused = cast(Any, None)
    return SourceWebSocketSession(
        unused,
        unused,
        client_send_lock=anyio.Lock(),
        clock=REAL_CLOCK,
        scheduler=REAL_SCHEDULER,
        request_timeout=60,
        connect_timeout=5,
        idle_timeout=60,
        stream_idle_timeout=60,
        cleanup_scheduler=unused,
        expose_stale_previous_response_classifier=False,
        input_buffer=unused,
        open_http=unused,
        transcript_limit=1024,
    )


@pytest.mark.asyncio
async def test_concurrent_bridge_closers_wait_for_one_transport_close() -> None:
    release = asyncio.Event()
    closes = 0

    async def close_transport() -> None:
        nonlocal closes
        closes += 1
        await release.wait()

    async def blocks():
        if False:
            yield ""

    session = _session()
    session._http = BridgedSourceEvents(blocks(), 200, close_transport)
    # Teardown starts closing; a turn timeout then finishes through the same path.
    teardown = asyncio.create_task(session._close_upstream())
    await asyncio.sleep(0)
    timeout_path = asyncio.create_task(session._close_upstream())
    await asyncio.sleep(0.05)

    # Neither closer may proceed to finalization while the response is open.
    assert not teardown.done() and not timeout_path.done()
    release.set()
    await asyncio.gather(teardown, timeout_path)
    assert closes == 1


class _ObservingOwner:
    """The slice of ``SourceDispatch`` that ``SourceWebSocketSession.send`` touches."""

    def __init__(self) -> None:
        self.observed: list[str | None] = []
        self.usage_holder = None
        self.warmup = False
        self.content_delivered = False

    def observe_relayed_event(self, event_type: str | None, payload: dict[str, Any] | None) -> None:
        del payload
        self.observed.append(event_type)


class _RecordingWebSocket:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def send_text(self, text: str) -> None:
        self.texts.append(text)


@pytest.mark.asyncio
async def test_send_observes_timing_only_after_taking_the_send_lock() -> None:
    session = _session()
    websocket = _RecordingWebSocket()
    session.websocket = cast(Any, websocket)
    owner = _ObservingOwner()
    turn = cast(Any, SimpleNamespace(owner=owner, terminal_handed_off=False, trace=None))
    delta: dict[str, Any] = {"type": "response.output_text.delta", "delta": "hi"}

    async with session.send_lock:
        queued = asyncio.create_task(session.send(delta, turn=turn))
        await asyncio.sleep(0.01)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued

    # Cancelled while queued for the lock: never handed off, never timed.
    assert owner.observed == [] and websocket.texts == []

    await session.send(delta, turn=turn)
    assert owner.observed == ["response.output_text.delta"]
    assert len(websocket.texts) == 1
