"""Unit tests for lens.backbone.memory_bus — InMemoryEventBus.

Per docs/LENS_IMPLEMENTATION.md §3.3 and docs/LENS_TEST_REFERENCE.md §2.1
(InMemoryEventBus block). Phase-0 semantics: fan-out — every consumer
registered on a topic receives every event sent to that topic.

These tests are now load-bearing for CI given the no-Docker decision: the
fake stands in for the real Kafka adapter in unit/integration suites.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from lens.events.schema import NodeStarted


def _sample_event() -> NodeStarted:
    return NodeStarted(
        event_id="550e8400-e29b-41d4-a716-446655440000",  # type: ignore[arg-type]
        schema_version="1.0",
        timestamp=datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC),
        build_id="build_42",
        node_id="n1",
        level="flow",
        entity_id="flow_a",
    )


def test_in_memory_bus_implements_event_bus_protocol() -> None:
    from lens.backbone.bus import EventBus
    from lens.backbone.memory_bus import InMemoryEventBus

    assert isinstance(InMemoryEventBus(), EventBus)


async def test_producer_send_delivers_event_to_consumer_handler() -> None:
    """An event published via producer.send reaches the consumer's handler."""
    from lens.backbone.memory_bus import InMemoryEventBus

    bus = InMemoryEventBus()
    received: list[dict[str, Any]] = []

    class _Handler:
        async def handle(self, event: dict[str, Any]) -> None:
            received.append(event)

    consumer = bus.consumer("build.events", group_id="g", handler=_Handler())
    producer = bus.producer("build.events")
    await producer.start()

    await producer.send(_sample_event())

    run_task = asyncio.create_task(consumer.run())
    # let the consumer drain the queue
    for _ in range(20):
        if received:
            break
        await asyncio.sleep(0.01)
    await consumer.stop()
    await run_task
    await producer.stop()

    assert len(received) == 1
    assert received[0]["event_type"] == "NodeStarted"
    assert received[0]["node_id"] == "n1"


async def _drain_until(
    consumer: Any, predicate: Any, *, max_iters: int = 50, sleep: float = 0.01
) -> None:
    """Run a consumer until `predicate()` is truthy, then stop it cleanly."""
    run_task = asyncio.create_task(consumer.run())
    try:
        for _ in range(max_iters):
            if predicate():
                break
            await asyncio.sleep(sleep)
    finally:
        await consumer.stop()
        await run_task


async def test_two_consumers_on_same_topic_both_receive_events() -> None:
    """Fan-out semantics: every consumer registered on the topic sees every event."""
    from lens.backbone.memory_bus import InMemoryEventBus

    bus = InMemoryEventBus()
    a: list[dict[str, Any]] = []
    b: list[dict[str, Any]] = []

    class _Recorder:
        def __init__(self, bucket: list[dict[str, Any]]) -> None:
            self.bucket = bucket

        async def handle(self, event: dict[str, Any]) -> None:
            self.bucket.append(event)

    consumer_a = bus.consumer("topic", group_id="ga", handler=_Recorder(a))
    consumer_b = bus.consumer("topic", group_id="gb", handler=_Recorder(b))
    producer = bus.producer("topic")
    await producer.send(_sample_event())

    run_a = asyncio.create_task(consumer_a.run())
    run_b = asyncio.create_task(consumer_b.run())
    for _ in range(50):
        if a and b:
            break
        await asyncio.sleep(0.01)
    await consumer_a.stop()
    await consumer_b.stop()
    await run_a
    await run_b

    assert len(a) == 1
    assert len(b) == 1


async def test_event_on_topic_a_does_not_reach_consumer_of_topic_b() -> None:
    """Topics are isolated — events on one topic do not bleed into another."""
    from lens.backbone.memory_bus import InMemoryEventBus

    bus = InMemoryEventBus()
    received_b: list[dict[str, Any]] = []

    class _Recorder:
        async def handle(self, event: dict[str, Any]) -> None:
            received_b.append(event)

    consumer_b = bus.consumer("topic.b", group_id="g", handler=_Recorder())
    producer_a = bus.producer("topic.a")
    await producer_a.send(_sample_event())

    run_task = asyncio.create_task(consumer_b.run())
    await asyncio.sleep(0.05)  # plenty of time to wrongly receive
    await consumer_b.stop()
    await run_task

    assert received_b == []


async def test_handler_exception_does_not_crash_consumer_loop() -> None:
    """Per spec §2.1 #3: a handler that raises must not kill the consumer loop."""
    from lens.backbone.memory_bus import InMemoryEventBus

    bus = InMemoryEventBus()
    successes: list[dict[str, Any]] = []

    class _FlakyHandler:
        def __init__(self) -> None:
            self.calls = 0

        async def handle(self, event: dict[str, Any]) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("boom on first event")
            successes.append(event)

    handler = _FlakyHandler()
    consumer = bus.consumer("topic", group_id="g", handler=handler)
    producer = bus.producer("topic")
    await producer.send(_sample_event())
    await producer.send(_sample_event())

    run_task = asyncio.create_task(consumer.run())
    for _ in range(50):
        if successes:
            break
        await asyncio.sleep(0.01)
    await consumer.stop()
    await run_task

    assert handler.calls == 2  # the loop survived the first failure
    assert len(successes) == 1  # only the second event made it through


async def test_consumer_stop_causes_run_to_return() -> None:
    """Calling stop() on an idle consumer makes run() return promptly."""
    from lens.backbone.memory_bus import InMemoryEventBus

    bus = InMemoryEventBus()

    class _Noop:
        async def handle(self, event: dict[str, Any]) -> None: ...

    consumer = bus.consumer("topic", group_id="g", handler=_Noop())
    run_task = asyncio.create_task(consumer.run())
    await asyncio.sleep(0.02)
    await consumer.stop()
    await asyncio.wait_for(run_task, timeout=0.5)  # must return, not hang


async def test_producer_start_and_stop_are_callable_noops() -> None:
    """Lifecycle methods exist and can be called without state setup."""
    from lens.backbone.memory_bus import InMemoryEventBus

    bus = InMemoryEventBus()
    producer = bus.producer("topic")
    await producer.start()
    await producer.start()  # idempotent
    await producer.stop()
    await producer.stop()
