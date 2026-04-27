"""End-to-end walking-skeleton test (Recipe B from the plan).

Drives the full pipeline through in-memory adapters:

    CSV file → CSVStatusSource → APEventBridge → InMemoryEventBus
            → DashboardStateProjection (consumer)
            → InMemoryDashboardStateStore
            → FastAPI (TestClient)
            → assert KG visible at /api/kgs

This is the architectural validation point per the plan: if this test
passes, the rest of MVP is fan-out (real adapters in Sprint C, deploy
package in Sprint D).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from lens.api.app import create_app
from lens.backbone.memory_bus import InMemoryEventBus
from lens.observer.ap_bridge import APEventBridge, CSVStatusSource
from lens.projection.dashboard_state import DashboardStateProjection
from lens.projection.memory_adapter import InMemoryDashboardStateStore


def _id_gen() -> UUID:
    n = next(_id_gen.counter)  # type: ignore[attr-defined]
    return UUID(f"00000000-0000-0000-0000-{n:012d}")


_id_gen.counter = count()  # type: ignore[attr-defined]


async def test_walking_skeleton_csv_to_api_in_memory(tmp_path: Path) -> None:
    """A flow seeded in CSV reaches the API after one observer tick + projection drain."""
    csv_path = tmp_path / "ap.csv"
    csv_path.write_text(
        "flow_id,library,owner,state,started_at,completed_at,error_message\n"
        "f1,libA,brian,RUNNING,2026-04-27T10:00:00+00:00,,\n"
        "f2,libA,brian,COMPLETED,2026-04-27T09:00:00+00:00,2026-04-27T09:30:00+00:00,\n"
    )

    bus = InMemoryEventBus()
    store = InMemoryDashboardStateStore()
    projection = DashboardStateProjection(store)

    # Adapter that bridges the bus consumer's `handle(dict)` → projection.handle(dict)
    class _ProjectionHandler:
        async def handle(self, event: dict[str, Any]) -> None:
            await projection.handle(event)

    consumer = bus.consumer(
        "build.events", group_id="dashboard_state", handler=_ProjectionHandler()
    )
    producer = bus.producer("build.events")
    bridge = APEventBridge(
        source=CSVStatusSource(csv_path),
        producer=producer,
        build_id="build_42",
        poll_interval_sec=0.01,
        now=lambda: datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC),
        id_gen=_id_gen,
    )

    consumer_task = asyncio.create_task(consumer.run())
    bridge_task = asyncio.create_task(bridge.run())

    # wait until projection has both flows reflected (f1 + f2 → total_flows=2)
    deadline = 100
    while deadline > 0:
        kg = await store.get_kg("build_42")
        if kg is not None and kg.get("total_flows", 0) >= 2:
            break
        await asyncio.sleep(0.01)
        deadline -= 1

    await bridge.stop()
    await consumer.stop()
    await bridge_task
    await consumer_task

    # Now query via the API.
    client = TestClient(create_app(dashboard_store=store))
    response = client.get("/api/kgs")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    kg_row = body[0]
    assert kg_row["build_id"] == "build_42"
    assert kg_row["library"] == "libA"
    assert kg_row["total_flows"] == 2
    assert kg_row["completed_flows"] == 1  # f2 was COMPLETED on first sight (catch-up)
