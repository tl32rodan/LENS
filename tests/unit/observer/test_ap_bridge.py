"""Unit tests for APEventBridge — the polling loop that ties source → bus.

Per docs/LENS_IMPLEMENTATION.md §4.3 / §4.6 and docs/LENS_TEST_REFERENCE.md §3.1
(bridge cases).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from itertools import count
from typing import Any
from uuid import UUID

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


def _id_gen() -> UUID:
    n = next(_id_gen.counter)  # type: ignore[attr-defined]
    return UUID(f"00000000-0000-0000-0000-{n:012d}")


_id_gen.counter = count()  # type: ignore[attr-defined]
_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)


async def test_bridge_run_polls_source_and_publishes_events() -> None:
    """The bridge's run loop fetches snapshots and sends diffed events to the producer."""
    from lens.observer.ap_bridge import APEventBridge

    source = _FakeSource(
        [
            {"f1": {"state": "RUNNING", "library": "L", "owner": "o"}},
            {"f1": {"state": "COMPLETED", "library": "L", "owner": "o"}},
        ]
    )
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

    assert [e.model_dump()["event_type"] for e in producer.sent[:2]] == [
        "FlowStarted",
        "FlowCompleted",
    ]


async def test_bridge_survives_source_fetch_failure() -> None:
    """A raising source does not crash the bridge — next tick recovers."""
    from lens.observer.ap_bridge import APEventBridge

    class _FlakySource:
        def __init__(self) -> None:
            self.calls = 0

        async def fetch_snapshot(self) -> dict[str, dict[str, Any]]:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("AP service down")
            return {"f1": {"state": "RUNNING", "library": "L", "owner": "o"}}

    source = _FlakySource()
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
        if producer.sent:
            break
        await asyncio.sleep(0.01)
    await bridge.stop()
    await run_task

    assert len(producer.sent) == 1
    assert producer.sent[0].model_dump()["event_type"] == "FlowStarted"


async def test_bridge_survives_producer_send_failure() -> None:
    """If producer.send raises, the bridge logs and continues; later events still get through."""
    from lens.observer.ap_bridge import APEventBridge

    class _FlakyProducer:
        def __init__(self) -> None:
            self.calls = 0
            self.successful: list[EventEnvelope] = []

        async def start(self) -> None: ...
        async def stop(self) -> None: ...
        async def send(self, event: EventEnvelope) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("kafka unavailable")
            self.successful.append(event)

    source = _FakeSource(
        [
            {"f1": {"state": "RUNNING", "library": "L", "owner": "o"}},
            {
                "f1": {"state": "RUNNING", "library": "L", "owner": "o"},
                "f2": {"state": "RUNNING", "library": "L", "owner": "o"},
            },
        ]
    )
    producer = _FlakyProducer()
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
        if producer.successful:
            break
        await asyncio.sleep(0.01)
    await bridge.stop()
    await run_task

    assert producer.calls >= 2
    assert any(e.model_dump()["entity_id"] == "f2" for e in producer.successful)


async def test_bridge_run_returns_when_stop_called() -> None:
    """Calling stop() ends run() promptly."""
    from lens.observer.ap_bridge import APEventBridge

    source = _FakeSource([{}])
    producer = _RecordingProducer()
    bridge = APEventBridge(
        source=source,
        producer=producer,
        build_id="b1",
        poll_interval_sec=10.0,  # long; stop should still return fast
        now=lambda: _NOW,
        id_gen=_id_gen,
    )
    run_task = asyncio.create_task(bridge.run())
    await asyncio.sleep(0.02)
    await bridge.stop()
    await asyncio.wait_for(run_task, timeout=0.5)
