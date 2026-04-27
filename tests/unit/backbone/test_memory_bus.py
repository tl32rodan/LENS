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
