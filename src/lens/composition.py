"""Composition root — wires Settings → adapters → application.

Per plan decision #13 (DP-8 Replaceable Adapters): the choice of bus and
store is config, not code. Tests inject `Settings` directly; the CLI entry
points read environment variables and pass the resulting `Settings`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from lens.api.app import create_app
from lens.backbone.bus import EventBus, EventConsumer
from lens.config import Settings
from lens.projection.store import DashboardStateStore

if TYPE_CHECKING:
    from lens.observer.ap_bridge import APEventBridge
    from lens.projection.dashboard_state import DashboardStateProjection


def build_event_bus(settings: Settings) -> EventBus:
    """Return the EventBus implementation selected by `settings.bus`."""
    if settings.bus == "memory":
        from lens.backbone.memory_bus import InMemoryEventBus

        return InMemoryEventBus()
    if settings.bus == "kafka":
        from lens.backbone.kafka_bus import KafkaEventBus

        return KafkaEventBus(settings.kafka_bootstrap_servers)
    raise ValueError(f"unknown LENS_BUS value: {settings.bus!r}")


def build_dashboard_store(settings: Settings) -> DashboardStateStore:
    """Return the DashboardStateStore selected by `settings.projection_store`."""
    if settings.projection_store == "memory":
        from lens.projection.memory_adapter import InMemoryDashboardStateStore

        return InMemoryDashboardStateStore()
    if settings.projection_store == "postgres":
        from lens.projection.postgres_adapter import PostgresDashboardStateStore

        return PostgresDashboardStateStore(settings.pg_dsn)
    raise ValueError(f"unknown LENS_PROJECTION_STORE value: {settings.projection_store!r}")


def build_app(settings: Settings, *, store: DashboardStateStore | None = None) -> FastAPI:
    """Build the FastAPI app, wiring in either an injected store or one from settings."""
    if store is None:
        store = build_dashboard_store(settings)
    return create_app(dashboard_store=store)


def build_observer_bridge(
    settings: Settings,
    *,
    bus: EventBus | None = None,
) -> APEventBridge:
    """Build an APEventBridge wired to a CSV source and the configured bus."""
    from lens.observer.ap_bridge import APEventBridge, CSVStatusSource

    if bus is None:
        bus = build_event_bus(settings)
    producer = bus.producer(
        settings.kafka_topic_events,
        local_buffer_path=settings.producer_local_buffer_path if settings.bus == "kafka" else None,
    )
    return APEventBridge(
        source=CSVStatusSource(settings.observer_csv_path),
        producer=producer,
        build_id=settings.observer_build_id,
        poll_interval_sec=settings.observer_poll_interval_sec,
    )


def build_projection_consumer(
    settings: Settings,
    *,
    bus: EventBus | None = None,
    store: DashboardStateStore | None = None,
) -> tuple[DashboardStateProjection, EventConsumer]:
    """Wire the DashboardStateProjection into a bus consumer.

    Returns (projection, consumer) so the caller can `consumer.run()` and
    `consumer.stop()` directly. The bus and store can be reused across
    other components by passing them in.
    """
    from lens.projection.dashboard_state import DashboardStateProjection

    if bus is None:
        bus = build_event_bus(settings)
    if store is None:
        store = build_dashboard_store(settings)

    projection = DashboardStateProjection(store)

    class _Adapter:
        async def handle(self, event: dict[str, object]) -> None:
            await projection.handle(event)

    consumer = bus.consumer(
        settings.kafka_topic_events,
        group_id="dashboard_state",
        handler=_Adapter(),
        dlq_topic=settings.kafka_topic_dlq,
    )
    return projection, consumer
