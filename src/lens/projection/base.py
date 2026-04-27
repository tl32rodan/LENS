"""ProjectionConsumer base class.

Per docs/LENS_IMPLEMENTATION.md §5.3 / §5.7. Subclasses set `name` (used as
the dedup namespace) and implement `apply()`. The base provides `handle()`,
which wraps apply in a transaction with event-id deduplication.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from lens.projection.store import ProjectionStore, ProjectionTransaction


class ProjectionConsumer(ABC):
    """One projection. Subclasses must set `name` and implement `apply`."""

    name: ClassVar[str]

    def __init__(self, store: ProjectionStore) -> None:
        self._store = store

    @abstractmethod
    async def apply(self, event: dict[str, Any], txn: ProjectionTransaction) -> None:
        """Mutate the store in response to one event. Called inside a transaction."""

    async def handle(self, event: dict[str, Any]) -> None:
        """Idempotently apply one event.

        Per spec §5.3: dedup → apply → mark applied → commit, all in one txn.
        """
        async with self._store.transaction() as txn:
            if await self._store.dedup.has_applied(self.name, event["event_id"]):
                return
            await self.apply(event, txn)
            await self._store.dedup.mark_applied(self.name, event["event_id"])
            await txn.commit()
