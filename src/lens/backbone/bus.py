"""Event-bus Protocol definitions (L2 infra contract).

Per docs/LENS_IMPLEMENTATION.md §3.3. All adapters (KafkaEventBus, the
in-memory fake, future test doubles) implement these Protocols. Code targets
the Protocol — never the concrete adapter (DP-8 Replaceable Adapters).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from lens.events.schema import EventEnvelope


@runtime_checkable
class EventProducer(Protocol):
    """Sends events. Fire-and-forget; never blocks on broker availability."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, event: EventEnvelope) -> None: ...


@runtime_checkable
class EventHandler(Protocol):
    """Callable that processes one event. Implemented by Projection consumers."""

    async def handle(self, event: dict[str, Any]) -> None: ...


@runtime_checkable
class EventConsumer(Protocol):
    """Long-running loop that pulls events and dispatches to a handler."""

    async def run(self) -> None: ...
    async def stop(self) -> None: ...


@runtime_checkable
class EventBus(Protocol):
    """Factory for producers and consumers; hides Kafka-specific concepts."""

    def producer(
        self, topic: str, *, local_buffer_path: Path | None = None
    ) -> EventProducer: ...

    def consumer(
        self,
        topic: str,
        *,
        group_id: str,
        handler: EventHandler,
        dlq_topic: str | None = None,
    ) -> EventConsumer: ...
