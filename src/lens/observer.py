"""Observer layer (L0) for emitting events into backbone/projections."""

from collections.abc import Callable, Iterable

from lens.events import EventEnvelope, SchemaRegistry

Subscriber = Callable[[EventEnvelope], None]


class Observer:
    def __init__(
        self,
        subscribers: Iterable[Subscriber],
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self._subscribers = tuple(subscribers)
        self._schema_registry = schema_registry or SchemaRegistry()

    def emit(self, event: EventEnvelope) -> None:
        self._schema_registry.validate(event)
        for subscriber in self._subscribers:
            subscriber(event)
