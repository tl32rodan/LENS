"""In-memory ProjectionStore + DashboardStateStore.

Per docs/LENS_IMPLEMENTATION.md §5.3 (Protocols) plus the no-Docker MVP
plan: this adapter is the runtime store under `LENS_PROJECTION_STORE=memory`
and the unit-test fake everywhere else. Transactional semantics use
deep-copy snapshots so rollback is exact.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from types import TracebackType
from typing import Any

from lens.projection.store import (
    DedupTracker,
    ProjectionTransaction,
)


class _MemDedup:
    def __init__(self, store: InMemoryDashboardStateStore) -> None:
        self._store = store

    async def has_applied(self, projection_name: str, event_id: str) -> bool:
        return (projection_name, event_id) in self._store._dedup_applied

    async def mark_applied(self, projection_name: str, event_id: str) -> None:
        self._store._dedup_applied.add((projection_name, event_id))


class _MemTransaction:
    """Snapshot-based transaction. On exit without commit (or on exception),
    restores the store's state and dedup set to their pre-`__aenter__` values.
    """

    def __init__(self, store: InMemoryDashboardStateStore) -> None:
        self._store = store
        self._snapshot_state: dict[str, dict[str, Any]] | None = None
        self._snapshot_dedup: set[tuple[str, str]] | None = None
        self._committed = False

    async def __aenter__(self) -> _MemTransaction:
        self._snapshot_state = copy.deepcopy(self._store._state)
        self._snapshot_dedup = set(self._store._dedup_applied)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None or not self._committed:
            await self.rollback()

    async def commit(self) -> None:
        self._committed = True

    async def rollback(self) -> None:
        if self._snapshot_state is not None:
            self._store._state = self._snapshot_state
        if self._snapshot_dedup is not None:
            self._store._dedup_applied = self._snapshot_dedup
        self._committed = False


class InMemoryDashboardStateStore:
    """Process-local DashboardStateStore. One instance per worker."""

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}
        self._dedup_applied: set[tuple[str, str]] = set()
        self._dedup_tracker = _MemDedup(self)

    # ProjectionStore -----------------------------------------------------
    @property
    def dedup(self) -> DedupTracker:
        return self._dedup_tracker

    def transaction(self) -> ProjectionTransaction:
        return _MemTransaction(self)

    # DashboardStateStore writes -----------------------------------------
    async def upsert_kg(self, build_id: str, fields: dict[str, Any]) -> None:
        if build_id in self._state:
            self._state[build_id].update(fields)
        else:
            self._state[build_id] = {"build_id": build_id, **fields}

    async def increment_counter(self, build_id: str, field: str, delta: int = 1) -> None:
        kg = self._state.setdefault(build_id, {"build_id": build_id})
        kg[field] = kg.get(field, 0) + delta

    async def truncate_all(self) -> None:
        self._state.clear()
        self._dedup_applied.clear()

    # DashboardStateStore reads ------------------------------------------
    async def get_kg(self, build_id: str) -> dict[str, Any] | None:
        record = self._state.get(build_id)
        return copy.deepcopy(record) if record is not None else None

    async def list_kgs(
        self,
        *,
        status: str | None = None,
        library: str | None = None,
    ) -> list[dict[str, Any]]:
        rows: Sequence[dict[str, Any]] = list(self._state.values())
        if status is not None:
            rows = [r for r in rows if r.get("status") == status]
        if library is not None:
            rows = [r for r in rows if r.get("library") == library]
        return [copy.deepcopy(r) for r in rows]

    async def list_libraries(self) -> list[dict[str, Any]]:
        agg: dict[str, dict[str, Any]] = {}
        for kg in self._state.values():
            lib = kg.get("library")
            if lib is None:
                continue
            row = agg.setdefault(
                lib,
                {
                    "library": lib,
                    "total_kgs": 0,
                    "running": 0,
                    "completed": 0,
                    "failed": 0,
                },
            )
            row["total_kgs"] += 1
            status = (kg.get("status") or "").lower()
            if status in ("running", "completed", "failed"):
                row[status] += 1
        return list(agg.values())

    async def get_library_health(self, library: str) -> list[dict[str, Any]]:
        return [
            {
                "build_id": kg["build_id"],
                "status": kg.get("status"),
                "started_at": kg.get("started_at"),
                "completed_at": kg.get("completed_at"),
            }
            for kg in self._state.values()
            if kg.get("library") == library
        ]


