"""Kafka EventBus adapter (production path, integration-tested only).

Per docs/LENS_IMPLEMENTATION.md §3.3 (Public Interfaces) and §3.6 (aiokafka,
ndjson local buffer). Phase-0 scope (§3.7): basic send + local buffer
fallback; basic consumer loop + handler dispatch; DLQ via stderr only.

This module touches aiokafka and is omitted from CI coverage per the
no-Docker decision. It is validated manually via `pytest -m integration`
against an env-provided broker before deploy. The pure ndjson buffer logic
lives in `kafka_buffer.py` and is fully unit-tested.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore[import-untyped]
from aiokafka.errors import KafkaError  # type: ignore[import-untyped]

from lens.backbone.bus import EventConsumer, EventHandler, EventProducer
from lens.backbone.kafka_buffer import NDJSONLocalBuffer
from lens.events.schema import EventEnvelope

logger = logging.getLogger(__name__)


class _KafkaProducer:
    """Wrap AIOKafkaProducer with local-buffer fallback on send failure."""

    def __init__(
        self,
        bootstrap_servers: list[str],
        topic: str,
        local_buffer_path: Path | None,
    ) -> None:
        self._bootstrap = bootstrap_servers
        self._topic = topic
        self._buffer = (
            NDJSONLocalBuffer(local_buffer_path) if local_buffer_path is not None else None
        )
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap)
        await self._producer.start()
        if self._buffer is not None and not self._buffer.is_empty():
            for payload in self._buffer.drain():
                await self._send_payload(payload)

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def send(self, event: EventEnvelope) -> None:
        await self._send_payload(event.model_dump(mode="json"))

    async def _send_payload(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        try:
            assert self._producer is not None, "producer not started"
            await self._producer.send_and_wait(self._topic, body)
        except (KafkaError, ConnectionError, OSError):
            if self._buffer is None:
                raise
            self._buffer.append(payload)


class _KafkaConsumer:
    """Wrap AIOKafkaConsumer with handler dispatch + manual offset commit."""

    def __init__(
        self,
        bootstrap_servers: list[str],
        topic: str,
        group_id: str,
        handler: EventHandler,
        dlq_topic: str | None,
    ) -> None:
        self._bootstrap = bootstrap_servers
        self._topic = topic
        self._group_id = group_id
        self._handler = handler
        self._dlq_topic = dlq_topic  # logged only in Phase 0; topic wiring is Phase 1
        self._consumer: AIOKafkaConsumer | None = None
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap,
            group_id=self._group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await self._consumer.start()
        try:
            while not self._stopped.is_set():
                try:
                    batch = await self._consumer.getmany(timeout_ms=200, max_records=10)
                except KafkaError:
                    logger.exception("kafka poll failed; retrying")
                    await asyncio.sleep(0.5)
                    continue
                for tp, messages in batch.items():
                    for msg in messages:
                        try:
                            payload = json.loads(msg.value.decode("utf-8"))
                            await self._handler.handle(payload)
                        except Exception:
                            logger.exception(
                                "handler raised on offset %s; skipping (DLQ deferred to Phase 1)",
                                msg.offset,
                            )
                        # Phase 0: commit even on handler failure (log + skip per spec §3.7)
                        await self._consumer.commit({tp: msg.offset + 1})
        finally:
            await self._consumer.stop()
            self._consumer = None

    async def stop(self) -> None:
        self._stopped.set()


class KafkaEventBus:
    """Factory for producers and consumers wired to a real Kafka broker."""

    def __init__(self, bootstrap_servers: list[str]) -> None:
        self._bootstrap = bootstrap_servers

    def producer(self, topic: str, *, local_buffer_path: Path | None = None) -> EventProducer:
        return _KafkaProducer(self._bootstrap, topic, local_buffer_path)

    def consumer(
        self,
        topic: str,
        *,
        group_id: str,
        handler: EventHandler,
        dlq_topic: str | None = None,
    ) -> EventConsumer:
        return _KafkaConsumer(self._bootstrap, topic, group_id, handler, dlq_topic)
