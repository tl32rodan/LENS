"""Unit tests for APEventBridge — the polling loop that ties source → bus.

Per docs/LENS_IMPLEMENTATION.md §4.3 / §4.6 and docs/LENS_TEST_REFERENCE.md §3.1
(bridge cases).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from itertools import count
from typing import Any

from lens.events.schema import EventEnvelope


class _FakeSource:
    def __init__(self, snapshots: list[dict[str, dict[str, Any]]]) -> None:
        self._snapshots = list(snapshots)
        self.calls = 0

    async def fetch_snapshot(self) -> dict[str, dict[str, Any]]:
        self.calls += 1
        if self._snapshots:
            return self._snapshots.pop(0)
        return self._snapshots[-1] if self._snapshots else {}


class _RecordingProducer:
    def __init__(self) -> None:
        self.sent: list[EventEnvelope] = []

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, event: EventEnvelope) -> None:
        self.sent.append(event)


def _id_gen() -> str:
    n = next(_id_gen.counter)  # type: ignore[attr-defined]
    return f"00000000-0000-0000-0000-{n:012d}"


_id_gen.counter = count()  # type: ignore[attr-defined]
_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)


async def test_bridge_run_polls_source_and_publishes_events() -> None:
    """The bridge's run loop fetches snapshots and sends diffed events to the producer."""
    from lens.observer.ap_bridge import APEventBridge

    source = _FakeSource([
        {"f1": {"state": "RUNNING", "library": "L", "owner": "o"}},
        {"f1": {"state": "COMPLETED", "library": "L", "owner": "o"}},
    ])
    producer = _RecordingProducer()
    bridge = APEventBridge(
        source=source,
        producer=producer,
        build_id="b1",
        poll_interval_sec=0.01,
        now=lambda: _NOW,
        id_gen=_id_gen,
    )
    run_task = asyncio.create_task(bridge.run())
    for _ in range(50):
        if len(producer.sent) >= 2:
            break
        await asyncio.sleep(0.01)
    await bridge.stop()
    await run_task

    assert [e.event_type for e in producer.sent[:2]] == ["FlowStarted", "FlowCompleted"]
