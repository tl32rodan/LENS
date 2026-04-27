"""Unit tests for DashboardStateProjection (and the ProjectionConsumer base).

Per docs/LENS_IMPLEMENTATION.md §5.3 / §5.7 and docs/LENS_TEST_REFERENCE.md §4.1.
"""

from __future__ import annotations

from typing import Any

import pytest

from lens.projection.memory_adapter import InMemoryDashboardStateStore


def _flow_started(
    event_id: str, build_id: str = "b1", entity_id: str = "f1", **kw: Any
) -> dict[str, Any]:
    return {
        "event_type": "FlowStarted",
        "event_id": event_id,
        "schema_version": "1.0",
        "timestamp": "2026-04-27T10:00:00+00:00",
        "build_id": build_id,
        "entity_id": entity_id,
        "library": "L",
        "owner": "brian",
        **kw,
    }


def _flow_completed(
    event_id: str, build_id: str = "b1", entity_id: str = "f1", **kw: Any
) -> dict[str, Any]:
    return {
        "event_type": "FlowCompleted",
        "event_id": event_id,
        "schema_version": "1.0",
        "timestamp": "2026-04-27T10:30:00+00:00",
        "build_id": build_id,
        "entity_id": entity_id,
        "library": "L",
        "owner": "brian",
        "exit_code": 0,
        "duration_seconds": 1.0,
        **kw,
    }


def _flow_failed(
    event_id: str, build_id: str = "b1", entity_id: str = "f1", **kw: Any
) -> dict[str, Any]:
    return {
        "event_type": "FlowFailed",
        "event_id": event_id,
        "schema_version": "1.0",
        "timestamp": "2026-04-27T10:30:00+00:00",
        "build_id": build_id,
        "entity_id": entity_id,
        "library": "L",
        "owner": "brian",
        "exit_code": 1,
        "duration_seconds": 0.5,
        "error_message": "boom",
        **kw,
    }


# --- ProjectionConsumer base behavior -------------------------------


async def test_projection_skips_already_applied_event() -> None:
    """Per spec §5.3 handle() — the dedup check short-circuits a re-applied event."""
    from lens.projection.dashboard_state import DashboardStateProjection

    store = InMemoryDashboardStateStore()
    proj = DashboardStateProjection(store)

    await proj.handle(_flow_started("evt-1"))
    record_first = await store.get_kg("b1")
    assert record_first is not None
    total_after_first = record_first["total_flows"]

    await proj.handle(_flow_started("evt-1"))  # duplicate — must be ignored
    record_after = await store.get_kg("b1")
    assert record_after is not None
    assert record_after["total_flows"] == total_after_first  # unchanged


async def test_projection_marks_event_as_applied_after_success() -> None:
    from lens.projection.dashboard_state import DashboardStateProjection

    store = InMemoryDashboardStateStore()
    proj = DashboardStateProjection(store)

    await proj.handle(_flow_started("evt-1"))
    assert await store.dedup.has_applied(proj.name, "evt-1") is True


async def test_projection_does_not_mark_applied_on_failure() -> None:
    """If apply() raises, the event must remain un-marked so it can be retried."""
    from lens.projection.dashboard_state import DashboardStateProjection

    class _Boom(DashboardStateProjection):
        async def apply(self, event: Any, txn: Any) -> None:
            raise RuntimeError("apply boom")

    store = InMemoryDashboardStateStore()
    proj = _Boom(store)
    with pytest.raises(RuntimeError):
        await proj.handle(_flow_started("evt-1"))

    assert await store.dedup.has_applied(proj.name, "evt-1") is False


async def test_projection_transaction_rolls_back_on_apply_exception() -> None:
    """Per DP-2: failed apply must restore prior state."""
    from lens.projection.dashboard_state import DashboardStateProjection

    class _Boom(DashboardStateProjection):
        async def apply(self, event: Any, txn: Any) -> None:
            await self._store.upsert_kg("b1", {"status": "POISONED"})
            raise RuntimeError("apply boom")

    store = InMemoryDashboardStateStore()
    await store.upsert_kg("b1", {"status": "RUNNING"})
    proj = _Boom(store)

    with pytest.raises(RuntimeError):
        await proj.handle(_flow_started("evt-1"))

    record = await store.get_kg("b1")
    assert record is not None
    assert record["status"] == "RUNNING"  # rolled back


# --- DashboardStateProjection apply rules ---------------------------


async def test_flow_started_creates_kg_row() -> None:
    from lens.projection.dashboard_state import DashboardStateProjection

    store = InMemoryDashboardStateStore()
    proj = DashboardStateProjection(store)
    await proj.handle(_flow_started("evt-1"))

    record = await store.get_kg("b1")
    assert record is not None
    assert record["status"] == "RUNNING"
    assert record["library"] == "L"
    assert record["owner"] == "brian"
    assert record["total_flows"] == 1


async def test_flow_started_increments_total_flows_for_existing_kg() -> None:
    from lens.projection.dashboard_state import DashboardStateProjection

    store = InMemoryDashboardStateStore()
    proj = DashboardStateProjection(store)

    await proj.handle(_flow_started("evt-1", entity_id="f1"))
    await proj.handle(_flow_started("evt-2", entity_id="f2"))

    record = await store.get_kg("b1")
    assert record is not None
    assert record["total_flows"] == 2


async def test_flow_completed_increments_completed_flows() -> None:
    from lens.projection.dashboard_state import DashboardStateProjection

    store = InMemoryDashboardStateStore()
    proj = DashboardStateProjection(store)
    await proj.handle(_flow_started("evt-1"))
    await proj.handle(_flow_completed("evt-2"))

    record = await store.get_kg("b1")
    assert record is not None
    assert record["completed_flows"] == 1


async def test_flow_failed_increments_failed_flows_and_sets_failed_status() -> None:
    from lens.projection.dashboard_state import DashboardStateProjection

    store = InMemoryDashboardStateStore()
    proj = DashboardStateProjection(store)
    await proj.handle(_flow_started("evt-1"))
    await proj.handle(_flow_failed("evt-2"))

    record = await store.get_kg("b1")
    assert record is not None
    assert record["failed_flows"] == 1
    assert record["status"] == "FAILED"


async def test_kg_status_becomes_completed_when_all_flows_complete() -> None:
    from lens.projection.dashboard_state import DashboardStateProjection

    store = InMemoryDashboardStateStore()
    proj = DashboardStateProjection(store)
    await proj.handle(_flow_started("evt-1", entity_id="f1"))
    await proj.handle(_flow_started("evt-2", entity_id="f2"))
    await proj.handle(_flow_completed("evt-3", entity_id="f1"))
    await proj.handle(_flow_completed("evt-4", entity_id="f2"))

    record = await store.get_kg("b1")
    assert record is not None
    assert record["status"] == "COMPLETED"


async def test_unrelated_event_types_are_ignored() -> None:
    from lens.projection.dashboard_state import DashboardStateProjection

    store = InMemoryDashboardStateStore()
    proj = DashboardStateProjection(store)
    await proj.handle(
        {
            "event_type": "NodeStarted",
            "event_id": "evt-1",
            "schema_version": "1.0",
            "timestamp": "2026-04-27T10:00:00+00:00",
            "build_id": "b1",
            "node_id": "n1",
            "level": "flow",
            "entity_id": "f1",
        }
    )
    assert await store.get_kg("b1") is None


async def test_rebuild_from_empty_state_reproduces_same_result() -> None:
    """Per DP-2: replaying the event log against an empty store yields the same state."""
    from lens.projection.dashboard_state import DashboardStateProjection

    events = [
        _flow_started("evt-1", entity_id="f1"),
        _flow_started("evt-2", entity_id="f2"),
        _flow_completed("evt-3", entity_id="f1"),
        _flow_failed("evt-4", entity_id="f2"),
    ]

    store_a = InMemoryDashboardStateStore()
    proj_a = DashboardStateProjection(store_a)
    for e in events:
        await proj_a.handle(e)

    store_b = InMemoryDashboardStateStore()
    proj_b = DashboardStateProjection(store_b)
    for e in events:
        await proj_b.handle(e)

    assert await store_a.get_kg("b1") == await store_b.get_kg("b1")
