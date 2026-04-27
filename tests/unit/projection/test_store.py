"""Unit tests for lens.projection.store — Protocol definitions for L3.

Per docs/LENS_IMPLEMENTATION.md §5.3 (Public Interfaces).
"""

from __future__ import annotations

from typing import Any


def test_module_exports_all_required_protocols() -> None:
    from lens.projection import store

    for name in (
        "DedupTracker",
        "ProjectionTransaction",
        "ProjectionStore",
        "DashboardStateStore",
    ):
        assert hasattr(store, name), f"missing Protocol: {name}"


def test_dedup_tracker_runtime_check_accepts_conforming_stub() -> None:
    from lens.projection.store import DedupTracker

    class _Stub:
        async def has_applied(self, projection_name: str, event_id: str) -> bool:
            return False

        async def mark_applied(self, projection_name: str, event_id: str) -> None: ...

    assert isinstance(_Stub(), DedupTracker)


def test_projection_transaction_runtime_check_accepts_conforming_stub() -> None:
    from lens.projection.store import ProjectionTransaction

    class _Stub:
        async def __aenter__(self) -> _Stub:
            return self

        async def __aexit__(self, *exc_info: Any) -> None: ...
        async def commit(self) -> None: ...
        async def rollback(self) -> None: ...

    assert isinstance(_Stub(), ProjectionTransaction)


def test_dashboard_state_store_runtime_check_accepts_conforming_stub() -> None:
    from lens.projection.store import (
        DashboardStateStore,
        DedupTracker,
        ProjectionTransaction,
    )

    class _DummyDedup:
        async def has_applied(self, projection_name: str, event_id: str) -> bool:
            return False

        async def mark_applied(self, projection_name: str, event_id: str) -> None: ...

    class _DummyTxn:
        async def __aenter__(self) -> _DummyTxn:
            return self

        async def __aexit__(self, *exc_info: Any) -> None: ...
        async def commit(self) -> None: ...
        async def rollback(self) -> None: ...

    class _Stub:
        @property
        def dedup(self) -> DedupTracker:
            return _DummyDedup()

        def transaction(self) -> ProjectionTransaction:
            return _DummyTxn()

        async def upsert_kg(self, build_id: str, fields: dict[str, Any]) -> None: ...
        async def increment_counter(self, build_id: str, field: str, delta: int = 1) -> None: ...

        async def truncate_all(self) -> None: ...
        async def get_kg(self, build_id: str) -> dict[str, Any] | None:
            return None

        async def list_kgs(
            self, *, status: str | None = None, library: str | None = None
        ) -> list[dict[str, Any]]:
            return []

        async def list_libraries(self) -> list[dict[str, Any]]:
            return []

        async def get_library_health(self, library: str) -> list[dict[str, Any]]:
            return []

    assert isinstance(_Stub(), DashboardStateStore)
