from __future__ import annotations

import asyncio
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
