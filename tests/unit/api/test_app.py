"""Unit tests for the L5 REST API.

Per docs/LENS_IMPLEMENTATION.md §6.3 / §6.6 and docs/LENS_TEST_REFERENCE.md §5.1.

Tests use FastAPI's TestClient (requires httpx) and inject an
InMemoryDashboardStateStore as the read-side store. This is the same
adapter the e2e walking-skeleton test will wire up.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from lens.projection.memory_adapter import InMemoryDashboardStateStore


@pytest.fixture
def store() -> InMemoryDashboardStateStore:
    return InMemoryDashboardStateStore()


@pytest.fixture
def client(store: InMemoryDashboardStateStore) -> TestClient:
    from lens.api.app import create_app

    return TestClient(create_app(dashboard_store=store))


async def _seed(
    store: InMemoryDashboardStateStore,
    *,
    build_id: str,
    library: str = "L",
    status: str = "RUNNING",
    **extra: Any,
) -> None:
    await store.upsert_kg(
        build_id,
        {
            "library": library,
            "owner": "brian",
            "status": status,
            "started_at": "2026-04-27T10:00:00+00:00",
            "total_flows": 1,
            "completed_flows": 0,
            "failed_flows": 0,
            **extra,
        },
    )


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_kgs_returns_empty_when_no_data(client: TestClient) -> None:
    response = client.get("/api/kgs")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_kgs_returns_all_active_kgs(
    client: TestClient, store: InMemoryDashboardStateStore
) -> None:
    await _seed(store, build_id="b1", library="L1", status="RUNNING")
    await _seed(store, build_id="b2", library="L2", status="COMPLETED")

    response = client.get("/api/kgs")
    assert response.status_code == 200
    body = response.json()
    assert {row["build_id"] for row in body} == {"b1", "b2"}


async def test_list_kgs_filters_by_status(
    client: TestClient, store: InMemoryDashboardStateStore
) -> None:
    await _seed(store, build_id="b1", status="RUNNING")
    await _seed(store, build_id="b2", status="COMPLETED")

    response = client.get("/api/kgs?status=RUNNING")
    assert response.status_code == 200
    assert [r["build_id"] for r in response.json()] == ["b1"]


async def test_list_kgs_filters_by_library(
    client: TestClient, store: InMemoryDashboardStateStore
) -> None:
    await _seed(store, build_id="b1", library="L1")
    await _seed(store, build_id="b2", library="L2")

    response = client.get("/api/kgs?library=L1")
    assert response.status_code == 200
    assert [r["build_id"] for r in response.json()] == ["b1"]


def test_get_kg_returns_404_for_unknown_build_id(client: TestClient) -> None:
    response = client.get("/api/kgs/does-not-exist")
    assert response.status_code == 404


async def test_get_kg_returns_full_details(
    client: TestClient, store: InMemoryDashboardStateStore
) -> None:
    await _seed(store, build_id="b1", library="L", status="COMPLETED")

    response = client.get("/api/kgs/b1")
    assert response.status_code == 200
    body = response.json()
    assert body["build_id"] == "b1"
    assert body["status"] == "COMPLETED"
    assert body["library"] == "L"


async def test_list_libraries_aggregates_correctly(
    client: TestClient, store: InMemoryDashboardStateStore
) -> None:
    await _seed(store, build_id="b1", library="L", status="RUNNING")
    await _seed(store, build_id="b2", library="L", status="COMPLETED")
    await _seed(store, build_id="b3", library="L", status="FAILED")

    response = client.get("/api/libraries")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["library"] == "L"
    assert row["total_kgs"] == 3
    assert row["running"] == 1
    assert row["completed"] == 1
    assert row["failed"] == 1


async def test_library_health_returns_trend_over_time(
    client: TestClient, store: InMemoryDashboardStateStore
) -> None:
    await _seed(
        store,
        build_id="b1",
        library="L",
        status="COMPLETED",
        completed_at="2026-04-27T11:00:00+00:00",
    )
    await _seed(
        store,
        build_id="b2",
        library="L",
        status="FAILED",
        completed_at="2026-04-27T12:00:00+00:00",
    )
    await _seed(store, build_id="b3", library="OTHER", status="COMPLETED")

    response = client.get("/api/libraries/L/health")
    assert response.status_code == 200
    body = response.json()
    assert {row["build_id"] for row in body} == {"b1", "b2"}
