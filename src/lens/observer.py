"""Observer layer (L0) for emitting events into backbone/projections."""

from collections.abc import Callable
from typing import Any


class Observer:
    def __init__(self, subscribers: list[Callable[[Any], None]]) -> None:
        self._subscribers = subscribers

    def emit(self, event: Any) -> None:
        for subscriber in self._subscribers:
            subscriber(event)
