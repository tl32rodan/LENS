"""Unit tests for lens.backbone.bus — Protocol definitions.

Per docs/LENS_IMPLEMENTATION.md §3.3 (Public Interfaces).

Protocols are checked at runtime via @runtime_checkable so any concrete
adapter (KafkaEventBus, InMemoryEventBus, …) can be verified shape-wise
without inheritance.
"""

from __future__ import annotations


def test_module_exports_all_four_protocols() -> None:
    """Spec §3.3 names exactly four Protocols; the module must export each."""
    from lens.backbone import bus

    for name in ("EventProducer", "EventHandler", "EventConsumer", "EventBus"):
        assert hasattr(bus, name), f"missing Protocol: {name}"


def test_event_producer_runtime_check_accepts_conforming_stub() -> None:
    """A class with start/stop/send (all async) is recognised as EventProducer."""
    from lens.backbone.bus import EventProducer
    from lens.events.schema import EventEnvelope

    class _Stub:
        async def start(self) -> None: ...
        async def stop(self) -> None: ...
        async def send(self, event: EventEnvelope) -> None: ...

    assert isinstance(_Stub(), EventProducer)


def test_event_producer_runtime_check_rejects_missing_method() -> None:
    """A class missing `send()` does NOT satisfy EventProducer."""
    from lens.backbone.bus import EventProducer

    class _Incomplete:
        async def start(self) -> None: ...
        async def stop(self) -> None: ...

    assert not isinstance(_Incomplete(), EventProducer)


def test_event_handler_runtime_check_accepts_conforming_stub() -> None:
    """Any object with `async def handle(event)` is an EventHandler."""
    from typing import Any

    from lens.backbone.bus import EventHandler

    class _Stub:
        async def handle(self, event: dict[str, Any]) -> None: ...

    assert isinstance(_Stub(), EventHandler)


def test_event_consumer_runtime_check_accepts_conforming_stub() -> None:
    """A class with `run()` and `stop()` (both async) is recognised as EventConsumer."""
    from lens.backbone.bus import EventConsumer

    class _Stub:
        async def run(self) -> None: ...
        async def stop(self) -> None: ...

    assert isinstance(_Stub(), EventConsumer)


def test_event_bus_runtime_check_accepts_conforming_stub() -> None:
    """A class with the producer/consumer factory methods is an EventBus."""
    from pathlib import Path
    from typing import cast

    from lens.backbone.bus import EventBus, EventConsumer, EventHandler, EventProducer

    class _Stub:
        def producer(
            self, topic: str, *, local_buffer_path: Path | None = None
        ) -> EventProducer:
            return cast(EventProducer, object())

        def consumer(
            self,
            topic: str,
            *,
            group_id: str,
            handler: EventHandler,
            dlq_topic: str | None = None,
        ) -> EventConsumer:
            return cast(EventConsumer, object())

    assert isinstance(_Stub(), EventBus)
