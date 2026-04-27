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

import pytest

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
