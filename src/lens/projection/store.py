"""Projection store Protocols (L3 contracts).

Per docs/LENS_IMPLEMENTATION.md §5.3. Adapters: in-memory (load-bearing for
CI) and PostgreSQL (production). Code targets these Protocols, never the
concrete adapter (DP-8).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DedupTracker(Protocol):
    """Tracks which (projection_name, event_id) pairs have been applied."""

    async def has_applied(self, projection_name: str, event_id: str) -> bool: ...

    async def mark_applied(self, projection_name: str, event_id: str) -> None: ...


@runtime_checkable
class ProjectionTransaction(Protocol):
    """A transactional scope; concrete adapters control isolation level."""

    async def __aenter__(self) -> ProjectionTransaction: ...

    async def __aexit__(self, *exc_info: Any) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


@runtime_checkable
class ProjectionStore(Protocol):
    """Storage substrate for a projection — provides transactions and dedup."""

    @property
    def dedup(self) -> DedupTracker: ...

    def transaction(self) -> ProjectionTransaction: ...


@runtime_checkable
class DashboardStateStore(ProjectionStore, Protocol):
    """Storage operations for the dashboard_kg_state projection.

    Spec §5.3 enumerates only write operations; the read methods below are an
    additive extension required by the API layer (§6.3). They do not require
    an active transaction — concrete adapters take a read snapshot.
    """

    # writes (spec §5.3) ----------------------------------------------
    async def upsert_kg(self, build_id: str, fields: dict[str, Any]) -> None: ...

    async def increment_counter(self, build_id: str, field: str, delta: int = 1) -> None: ...

    async def truncate_all(self) -> None: ...

    # reads (additive for L5 API) -------------------------------------
    async def get_kg(self, build_id: str) -> dict[str, Any] | None: ...

    async def list_kgs(
        self, *, status: str | None = None, library: str | None = None
    ) -> list[dict[str, Any]]: ...

    async def list_libraries(self) -> list[dict[str, Any]]: ...

    async def get_library_health(self, library: str) -> list[dict[str, Any]]: ...
