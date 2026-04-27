"""In-memory EventBus — pure-Python pub/sub for tests and demo runs.

Implements `lens.backbone.bus.EventBus` with asyncio.Queue. Fan-out semantics:
every consumer registered on a topic receives every event sent to that topic.

Per docs/LENS_IMPLEMENTATION.md §3.3 and the no-Docker MVP decision, this
adapter is load-bearing for CI — it stands in for the real Kafka bus during
unit and end-to-end tests.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from lens.backbone.bus import EventBus, EventConsumer, EventHandler, EventProducer
from lens.events.schema import EventEnvelope

logger = logging.getLogger(__name__)


class _InMemoryProducer:
    """Fans an event out to every queue registered for the topic."""

    def __init__(self, queues: list[asyncio.Queue[dict[str, Any]]]) -> None:
        self._queues = queues

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send(self, event: EventEnvelope) -> None:
        payload: dict[str, Any] = event.model_dump(mode="json")
        for queue in self._queues:
            await queue.put(payload)


class _InMemoryConsumer:
    """Pulls events off its private queue and dispatches to a handler."""

    def __init__(
        self, queue: asyncio.Queue[dict[str, Any]], handler: EventHandler
    ) -> None:
        self._queue = queue
        self._handler = handler
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        while not self._stopped.is_set():
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.05)
            except TimeoutError:
                continue
            try:
                await self._handler.handle(event)
            except Exception:
                logger.exception(
                    "in-memory consumer handler raised; continuing loop"
                )

    async def stop(self) -> None:
        self._stopped.set()


class InMemoryEventBus:
    """Process-local EventBus. One bus per test; stateful across producer/consumer pairs."""

    def __init__(self) -> None:
        self._consumer_queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def producer(
        self, topic: str, *, local_buffer_path: Path | None = None
    ) -> EventProducer:
        # local_buffer_path is irrelevant in-memory; accepted for Protocol parity.
        del local_buffer_path
        queues = self._consumer_queues.setdefault(topic, [])
        return _InMemoryProducer(queues)

    def consumer(
        self,
        topic: str,
        *,
        group_id: str,
        handler: EventHandler,
        dlq_topic: str | None = None,
    ) -> EventConsumer:
        del group_id, dlq_topic  # decorative for the in-memory fan-out fake
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._consumer_queues.setdefault(topic, []).append(queue)
        return _InMemoryConsumer(queue, handler)
