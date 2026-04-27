"""L5 REST API.

Per docs/LENS_IMPLEMENTATION.md §6.3 / §6.6 — read-only Phase-0 endpoints
backed by a `DashboardStateStore`. No auth, no WebSocket. The app is built
via `create_app(dashboard_store=...)` so tests and the composition root
inject whichever adapter is appropriate (in-memory or PostgreSQL).
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from lens.projection.store import DashboardStateStore


def create_app(*, dashboard_store: DashboardStateStore) -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(title="LENS", version="0.0.0")

    def get_store() -> DashboardStateStore:
        return dashboard_store

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/kgs")
    async def list_kgs(
        store: Annotated[DashboardStateStore, Depends(get_store)],
        status: str | None = None,
        library: str | None = None,
    ) -> list[dict[str, Any]]:
        return await store.list_kgs(status=status, library=library)

    @app.get("/api/kgs/{build_id}")
    async def get_kg(
        build_id: str,
        store: Annotated[DashboardStateStore, Depends(get_store)],
    ) -> dict[str, Any]:
        record = await store.get_kg(build_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"unknown build_id: {build_id}")
        return record

    @app.get("/api/libraries")
    async def list_libraries(
        store: Annotated[DashboardStateStore, Depends(get_store)],
    ) -> list[dict[str, Any]]:
        return await store.list_libraries()

    @app.get("/api/libraries/{library}/health")
    async def library_health(
        library: str,
        store: Annotated[DashboardStateStore, Depends(get_store)],
    ) -> list[dict[str, Any]]:
        return await store.get_library_health(library)

    return app
