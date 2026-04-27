"""DDL constants for the projection layer.

Per docs/LENS_IMPLEMENTATION.md §5.4. Phase-0 ships these via an idempotent
`init_db()` script (decision #6 — no Alembic until Phase 1). Lives in its
own module so the strings are unit-testable without an asyncpg dependency.
"""

from __future__ import annotations

PROJECTION_APPLIED_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS projection_applied_events (
    projection_name VARCHAR(64) NOT NULL,
    event_id VARCHAR(64) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (projection_name, event_id)
);
""".strip()


DASHBOARD_KG_STATE_DDL = """
CREATE TABLE IF NOT EXISTS dashboard_kg_state (
    build_id VARCHAR(64) PRIMARY KEY,
    library VARCHAR(128),
    owner VARCHAR(64),
    status VARCHAR(32) NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_flows INT DEFAULT 0,
    completed_flows INT DEFAULT 0,
    failed_flows INT DEFAULT 0,
    last_event_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);
""".strip()


DASHBOARD_KG_STATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_dashboard_kg_state_library ON dashboard_kg_state(library);",
    "CREATE INDEX IF NOT EXISTS idx_dashboard_kg_state_status ON dashboard_kg_state(status);",
)


def all_ddl() -> list[str]:
    """Return every DDL statement needed to bootstrap a fresh Postgres."""
    return [
        PROJECTION_APPLIED_EVENTS_DDL,
        DASHBOARD_KG_STATE_DDL,
        *DASHBOARD_KG_STATE_INDEXES,
    ]
