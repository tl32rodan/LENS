"""Unit tests for the composition root.

Verify that the env-driven switches select the right adapter type. Real
Kafka / Postgres adapters are constructed but never connected to (tests
don't call `start()`), so no broker / DB is required.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in list(os.environ):
        if key.startswith("LENS_"):
            monkeypatch.delenv(key, raising=False)


def test_build_event_bus_returns_in_memory_when_lens_bus_is_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lens.backbone.memory_bus import InMemoryEventBus
    from lens.composition import build_event_bus
    from lens.config import Settings

    monkeypatch.setenv("LENS_BUS", "memory")
    bus = build_event_bus(Settings())
    assert isinstance(bus, InMemoryEventBus)


def test_build_event_bus_returns_kafka_when_lens_bus_is_kafka(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lens.backbone.kafka_bus import KafkaEventBus
    from lens.composition import build_event_bus
    from lens.config import Settings

    monkeypatch.setenv("LENS_BUS", "kafka")
    bus = build_event_bus(Settings())
    assert isinstance(bus, KafkaEventBus)


def test_build_dashboard_store_returns_memory_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lens.composition import build_dashboard_store
    from lens.config import Settings
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    monkeypatch.setenv("LENS_PROJECTION_STORE", "memory")
    store = build_dashboard_store(Settings())
    assert isinstance(store, InMemoryDashboardStateStore)


def test_build_dashboard_store_returns_postgres_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lens.composition import build_dashboard_store
    from lens.config import Settings
    from lens.projection.postgres_adapter import PostgresDashboardStateStore

    monkeypatch.setenv("LENS_PROJECTION_STORE", "postgres")
    store = build_dashboard_store(Settings())
    assert isinstance(store, PostgresDashboardStateStore)


def test_build_app_uses_injected_store(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from lens.composition import build_app
    from lens.config import Settings
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    monkeypatch.setenv("LENS_BUS", "memory")
    monkeypatch.setenv("LENS_PROJECTION_STORE", "memory")
    store = InMemoryDashboardStateStore()
    app = build_app(Settings(), store=store)

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_build_observer_bridge_uses_injected_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    from lens.backbone.memory_bus import InMemoryEventBus
    from lens.composition import build_observer_bridge
    from lens.config import Settings
    from lens.observer.ap_bridge import APEventBridge

    monkeypatch.setenv("LENS_BUS", "memory")
    bus = InMemoryEventBus()
    bridge = build_observer_bridge(Settings(), bus=bus)
    assert isinstance(bridge, APEventBridge)


def test_build_projection_consumer_returns_projection_and_consumer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lens.backbone.bus import EventConsumer
    from lens.backbone.memory_bus import InMemoryEventBus
    from lens.composition import build_projection_consumer
    from lens.config import Settings
    from lens.projection.dashboard_state import DashboardStateProjection
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    monkeypatch.setenv("LENS_BUS", "memory")
    monkeypatch.setenv("LENS_PROJECTION_STORE", "memory")

    bus = InMemoryEventBus()
    store = InMemoryDashboardStateStore()
    projection, consumer = build_projection_consumer(Settings(), bus=bus, store=store)
    assert isinstance(projection, DashboardStateProjection)
    assert isinstance(consumer, EventConsumer)
