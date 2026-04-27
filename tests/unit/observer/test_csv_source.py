"""Unit tests for CSVStatusSource.

Per docs/LENS_IMPLEMENTATION.md §4.3 / §4.7 and docs/LENS_TEST_REFERENCE.md §3.1.

The CSV column schema is documented in `lens.observer.ap_bridge.CSVStatusSource`'s
docstring; it is the assumed-shape default per the no-Docker MVP plan.
"""

from __future__ import annotations

from pathlib import Path


async def test_csv_source_parses_typical_dashboard_file(tmp_path: Path) -> None:
    """A well-formed CSV yields a {flow_id: state-fields} dict."""
    from lens.observer.ap_bridge import CSVStatusSource

    csv = tmp_path / "ap.csv"
    csv.write_text(
        "flow_id,library,owner,state,started_at,completed_at,error_message\n"
        "f1,libA,brian,RUNNING,2026-04-27T10:00:00+00:00,,\n"
        "f2,libA,brian,COMPLETED,2026-04-27T09:00:00+00:00,2026-04-27T09:30:00+00:00,\n"
    )

    snapshot = await CSVStatusSource(csv).fetch_snapshot()
    assert set(snapshot) == {"f1", "f2"}
    assert snapshot["f1"]["state"] == "RUNNING"
    assert snapshot["f1"]["library"] == "libA"
    assert snapshot["f2"]["state"] == "COMPLETED"
