"""Postgres-backed DashboardStateStore (production path, integration-tested only).

Per docs/LENS_IMPLEMENTATION.md §5.3 (Protocols) and §5.4 (DDL). Async via
SQLAlchemy 2.x's `AsyncEngine` + asyncpg. Phase-0 deploys with a one-shot
`init_db()` instead of Alembic (plan decision #6).

This module is omitted from CI coverage per the no-Docker decision; it is
validated via `pytest -m integration` against an env-provided Postgres
before deploy.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    create_async_engine,
)

from lens.projection.postgres_schema import all_ddl
from lens.projection.store import (
    DedupTracker,
    ProjectionTransaction,
)


async def init_db(dsn: str) -> None:
    """Apply every DDL statement; safe to re-run (all DDL uses IF NOT EXISTS)."""
    engine = create_async_engine(dsn)
    try:
        async with engine.begin() as conn:
            for stmt in all_ddl():
                await conn.execute(text(stmt))
    finally:
        await engine.dispose()


class _PgDedup:
    def __init__(self, store: PostgresDashboardStateStore) -> None:
        self._store = store

    async def has_applied(self, projection_name: str, event_id: str) -> bool:
        async with self._store._engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT 1 FROM projection_applied_events "
                    "WHERE projection_name = :pn AND event_id = :eid"
                ),
                {"pn": projection_name, "eid": event_id},
            )
            return result.first() is not None

    async def mark_applied(self, projection_name: str, event_id: str) -> None:
        async with self._store._engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO projection_applied_events "
                    "(projection_name, event_id) VALUES (:pn, :eid) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"pn": projection_name, "eid": event_id},
            )


class _PgTransaction:
    """Thin wrapper around an AsyncConnection's transactional scope."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._conn: AsyncConnection | None = None
        self._committed = False

    async def __aenter__(self) -> _PgTransaction:
        self._conn = await self._engine.connect().__aenter__()
        await self._conn.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._conn is not None
        try:
            if exc_type is None and self._committed:
                await self._conn.commit()
            else:
                await self._conn.rollback()
        finally:
            await self._conn.close()

    async def commit(self) -> None:
        self._committed = True

    async def rollback(self) -> None:
        if self._conn is not None:
            await self._conn.rollback()
        self._committed = False


class PostgresDashboardStateStore:
    """DashboardStateStore implemented against PostgreSQL.

    Constructor accepts the asyncpg DSN (validated by lens.config). Use
    `init_db(dsn)` once on deploy to bootstrap the schema.
    """

    def __init__(self, dsn: str) -> None:
        self._engine: AsyncEngine = create_async_engine(dsn)
        self._dedup = _PgDedup(self)

    async def aclose(self) -> None:
        await self._engine.dispose()

    @property
    def dedup(self) -> DedupTracker:
        return self._dedup

    def transaction(self) -> ProjectionTransaction:
        return _PgTransaction(self._engine)

    @asynccontextmanager
    async def _begin(self) -> AsyncIterator[AsyncConnection]:
        async with self._engine.begin() as conn:
            yield conn

    async def upsert_kg(self, build_id: str, fields: dict[str, Any]) -> None:
        cols = ["build_id", *fields.keys()]
        placeholders = [":build_id", *(f":{k}" for k in fields)]
        update_pairs = ", ".join(f"{k} = EXCLUDED.{k}" for k in fields)
        sql = (
            f"INSERT INTO dashboard_kg_state ({', '.join(cols)}) "
            f"VALUES ({', '.join(placeholders)}) "
            f"ON CONFLICT (build_id) DO UPDATE SET "
            f"{update_pairs}, updated_at = NOW()"
            if fields
            else (
                "INSERT INTO dashboard_kg_state (build_id, status) "
                "VALUES (:build_id, 'RUNNING') ON CONFLICT DO NOTHING"
            )
        )
        async with self._begin() as conn:
            await conn.execute(text(sql), {"build_id": build_id, **fields})

    async def increment_counter(self, build_id: str, field: str, delta: int = 1) -> None:
        # Whitelist column names since `field` is interpolated into SQL.
        if field not in {"total_flows", "completed_flows", "failed_flows"}:
            raise ValueError(f"increment_counter: unsupported field {field!r}")
        sql = text(
            f"INSERT INTO dashboard_kg_state (build_id, status, {field}) "
            f"VALUES (:build_id, 'RUNNING', :delta) "
            f"ON CONFLICT (build_id) DO UPDATE SET "
            f"{field} = dashboard_kg_state.{field} + :delta, updated_at = NOW()"
        )
        async with self._begin() as conn:
            await conn.execute(sql, {"build_id": build_id, "delta": delta})

    async def truncate_all(self) -> None:
        async with self._begin() as conn:
            await conn.execute(text("TRUNCATE TABLE dashboard_kg_state"))
            await conn.execute(text("TRUNCATE TABLE projection_applied_events"))

    async def get_kg(self, build_id: str) -> dict[str, Any] | None:
        async with self._engine.connect() as conn:
            result = await conn.execute(
                text("SELECT * FROM dashboard_kg_state WHERE build_id = :bid"),
                {"bid": build_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def list_kgs(
        self, *, status: str | None = None, library: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if status is not None:
            clauses.append("status = :status")
            params["status"] = status
        if library is not None:
            clauses.append("library = :library")
            params["library"] = library
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        async with self._engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT * FROM dashboard_kg_state{where} ORDER BY build_id"),
                params,
            )
            return [dict(row) for row in result.mappings().all()]

    async def list_libraries(self) -> list[dict[str, Any]]:
        sql = text(
            "SELECT library, "
            "COUNT(*) AS total_kgs, "
            "SUM(CASE WHEN status='RUNNING' THEN 1 ELSE 0 END) AS running, "
            "SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) AS completed, "
            "SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed "
            "FROM dashboard_kg_state "
            "WHERE library IS NOT NULL "
            "GROUP BY library "
            "ORDER BY library"
        )
        async with self._engine.connect() as conn:
            result = await conn.execute(sql)
            return [dict(row) for row in result.mappings().all()]

    async def get_library_health(self, library: str) -> list[dict[str, Any]]:
        sql = text(
            "SELECT build_id, status, started_at, completed_at "
            "FROM dashboard_kg_state "
            "WHERE library = :library "
            "ORDER BY started_at"
        )
        async with self._engine.connect() as conn:
            result = await conn.execute(sql, {"library": library})
            return [dict(row) for row in result.mappings().all()]
