"""Unit tests for InMemoryDashboardStateStore.

Per docs/LENS_IMPLEMENTATION.md §5.3 (Protocol shapes) and the no-Docker
MVP plan: this adapter is load-bearing for CI and stands in for the
PostgresDashboardStateStore during all unit / e2e tests.

Test layout: dedup, writes, reads, transaction semantics.
"""

from __future__ import annotations

import pytest


def test_in_memory_store_implements_dashboard_state_store_protocol() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore
    from lens.projection.store import DashboardStateStore

    assert isinstance(InMemoryDashboardStateStore(), DashboardStateStore)


# --- dedup ----------------------------------------------------------


async def test_dedup_unseen_event_returns_false() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    assert await store.dedup.has_applied("p1", "evt-1") is False


async def test_dedup_seen_event_returns_true() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.dedup.mark_applied("p1", "evt-1")
    assert await store.dedup.has_applied("p1", "evt-1") is True


async def test_dedup_isolated_per_projection_name() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.dedup.mark_applied("projection_A", "evt-1")
    assert await store.dedup.has_applied("projection_B", "evt-1") is False


# --- writes ---------------------------------------------------------


async def test_upsert_kg_creates_new_record() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"library": "L", "status": "RUNNING"})

    record = await store.get_kg("b1")
    assert record is not None
    assert record["library"] == "L"
    assert record["status"] == "RUNNING"
    assert record["build_id"] == "b1"


async def test_upsert_kg_updates_existing_record_fields() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"library": "L", "status": "RUNNING"})
    await store.upsert_kg("b1", {"status": "COMPLETED"})

    record = await store.get_kg("b1")
    assert record is not None
    assert record["status"] == "COMPLETED"
    assert record["library"] == "L"  # preserved


async def test_increment_counter_starts_at_zero_and_adds_delta() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.increment_counter("b1", "total_flows", delta=2)
    await store.increment_counter("b1", "total_flows")  # default delta=1

    record = await store.get_kg("b1")
    assert record is not None
    assert record["total_flows"] == 3


async def test_truncate_all_clears_state() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"library": "L"})
    await store.dedup.mark_applied("p", "evt-1")

    await store.truncate_all()

    assert await store.get_kg("b1") is None
    assert await store.dedup.has_applied("p", "evt-1") is False


# --- reads ----------------------------------------------------------


async def test_get_kg_returns_none_for_missing_build() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    assert await store.get_kg("does-not-exist") is None


async def test_list_kgs_returns_all_when_no_filter() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"library": "L1", "status": "RUNNING"})
    await store.upsert_kg("b2", {"library": "L2", "status": "COMPLETED"})

    kgs = await store.list_kgs()
    assert {k["build_id"] for k in kgs} == {"b1", "b2"}


async def test_list_kgs_filters_by_status() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"library": "L", "status": "RUNNING"})
    await store.upsert_kg("b2", {"library": "L", "status": "COMPLETED"})

    running = await store.list_kgs(status="RUNNING")
    assert [k["build_id"] for k in running] == ["b1"]


async def test_list_kgs_filters_by_library() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"library": "L1"})
    await store.upsert_kg("b2", {"library": "L2"})

    only_l1 = await store.list_kgs(library="L1")
    assert [k["build_id"] for k in only_l1] == ["b1"]


async def test_list_libraries_aggregates_kgs_by_library() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"library": "L", "status": "RUNNING"})
    await store.upsert_kg("b2", {"library": "L", "status": "COMPLETED"})
    await store.upsert_kg("b3", {"library": "L", "status": "FAILED"})

    libs = await store.list_libraries()
    assert len(libs) == 1
    row = libs[0]
    assert row["library"] == "L"
    assert row["total_kgs"] == 3
    assert row["running"] == 1
    assert row["completed"] == 1
    assert row["failed"] == 1


async def test_get_library_health_returns_kgs_for_library() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"library": "L", "status": "COMPLETED"})
    await store.upsert_kg("b2", {"library": "OTHER", "status": "COMPLETED"})

    rows = await store.get_library_health("L")
    assert [r["build_id"] for r in rows] == ["b1"]


# --- transactions ---------------------------------------------------


async def test_transaction_commit_persists_changes() -> None:
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    async with store.transaction() as txn:
        await store.upsert_kg("b1", {"status": "RUNNING"})
        await txn.commit()

    assert (await store.get_kg("b1")) is not None


async def test_transaction_rollback_on_exception_restores_state() -> None:
    """Per DP-2: failed apply must not leave half-applied state behind."""
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"status": "RUNNING"})

    with pytest.raises(RuntimeError):
        async with store.transaction():
            await store.upsert_kg("b1", {"status": "POISONED"})
            await store.upsert_kg("b2", {"status": "RUNNING"})
            raise RuntimeError("apply boom")

    record_b1 = await store.get_kg("b1")
    assert record_b1 is not None
    assert record_b1["status"] == "RUNNING"  # rolled back
    assert (await store.get_kg("b2")) is None  # never created


async def test_transaction_aexit_without_commit_rolls_back() -> None:
    """If the body completes without calling commit, treat as implicit rollback."""
    from lens.projection.memory_adapter import InMemoryDashboardStateStore

    store = InMemoryDashboardStateStore()
    async with store.transaction():
        await store.upsert_kg("b1", {"status": "RUNNING"})
        # no commit() call

    assert (await store.get_kg("b1")) is None
