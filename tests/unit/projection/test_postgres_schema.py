"""Unit tests for the Phase-0 projection DDL.

These verify the DDL strings exist with the expected shape — actual
table creation against a real Postgres lives in
`pytest -m integration` per the no-Docker plan.
"""

from __future__ import annotations


def test_all_ddl_includes_both_phase0_tables() -> None:
    from lens.projection.postgres_schema import all_ddl

    statements = all_ddl()
    joined = "\n".join(statements)
    assert "projection_applied_events" in joined
    assert "dashboard_kg_state" in joined


def test_dedup_table_uses_composite_primary_key() -> None:
    """Per plan decision #9: (projection_name, event_id) must be the PK."""
    from lens.projection.postgres_schema import PROJECTION_APPLIED_EVENTS_DDL

    assert "PRIMARY KEY (projection_name, event_id)" in PROJECTION_APPLIED_EVENTS_DDL


def test_dashboard_indexes_cover_filterable_columns() -> None:
    """API filters by status and library — both must be indexed."""
    from lens.projection.postgres_schema import DASHBOARD_KG_STATE_INDEXES

    joined = "\n".join(DASHBOARD_KG_STATE_INDEXES)
    assert "idx_dashboard_kg_state_library" in joined
    assert "idx_dashboard_kg_state_status" in joined


def test_ddl_is_idempotent() -> None:
    """init_db() must be safe to re-run; every CREATE uses IF NOT EXISTS."""
    from lens.projection.postgres_schema import all_ddl

    for stmt in all_ddl():
        assert "IF NOT EXISTS" in stmt, f"non-idempotent DDL: {stmt!r}"
