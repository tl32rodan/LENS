"""DashboardStateProjection — derives `dashboard_kg_state` rows from Flow events.

Per docs/LENS_IMPLEMENTATION.md §5.4 (schema) and §5.7 (rules).

Apply rules (Phase 0):
    FlowStarted    → upsert KG (status=RUNNING on first sight); total_flows++
    FlowCompleted  → completed_flows++; if all flows done & no failures → COMPLETED
    FlowFailed     → failed_flows++; status = FAILED (any failure is terminal)
    other types    → ignored

Status precedence: any failed_flows > 0 ⇒ FAILED; else completed >= total ⇒
COMPLETED; else RUNNING.
"""

from __future__ import annotations

from typing import Any, ClassVar

from lens.projection.base import ProjectionConsumer
from lens.projection.store import DashboardStateStore, ProjectionTransaction


class DashboardStateProjection(ProjectionConsumer):
    name: ClassVar[str] = "dashboard_state"

    def __init__(self, store: DashboardStateStore) -> None:
        super().__init__(store)
        self._store: DashboardStateStore = store

    async def apply(self, event: dict[str, Any], txn: ProjectionTransaction) -> None:
        del txn  # in-memory store mutates directly; PG adapter will use it
        event_type = event.get("event_type")
        if event_type == "FlowStarted":
            await self._on_flow_started(event)
        elif event_type == "FlowCompleted":
            await self._on_flow_completed(event)
        elif event_type == "FlowFailed":
            await self._on_flow_failed(event)
        # else: silently ignore (NodeStarted/NodeCompleted etc.)

    async def _on_flow_started(self, event: dict[str, Any]) -> None:
        build_id = event["build_id"]
        existing = await self._store.get_kg(build_id)
        if existing is None:
            await self._store.upsert_kg(
                build_id,
                {
                    "library": event.get("library"),
                    "owner": event.get("owner"),
                    "status": "RUNNING",
                    "started_at": event.get("timestamp"),
                    "total_flows": 0,
                    "completed_flows": 0,
                    "failed_flows": 0,
                },
            )
        await self._store.increment_counter(build_id, "total_flows", delta=1)
        await self._store.upsert_kg(build_id, {"last_event_at": event.get("timestamp")})

    async def _on_flow_completed(self, event: dict[str, Any]) -> None:
        build_id = event["build_id"]
        await self._store.increment_counter(build_id, "completed_flows", delta=1)
        await self._store.upsert_kg(build_id, {"last_event_at": event.get("timestamp")})
        await self._recompute_status(build_id, event.get("timestamp"))

    async def _on_flow_failed(self, event: dict[str, Any]) -> None:
        build_id = event["build_id"]
        await self._store.increment_counter(build_id, "failed_flows", delta=1)
        await self._store.upsert_kg(
            build_id,
            {
                "status": "FAILED",
                "completed_at": event.get("timestamp"),
                "last_event_at": event.get("timestamp"),
            },
        )

    async def _recompute_status(self, build_id: str, completed_timestamp: str | None) -> None:
        kg = await self._store.get_kg(build_id)
        if kg is None:
            return
        if kg.get("failed_flows", 0) > 0:
            return  # already terminal
        if kg.get("completed_flows", 0) >= kg.get("total_flows", 0) > 0:
            await self._store.upsert_kg(
                build_id,
                {"status": "COMPLETED", "completed_at": completed_timestamp},
            )
