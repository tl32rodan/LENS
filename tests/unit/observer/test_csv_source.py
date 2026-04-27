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


async def test_csv_source_returns_empty_when_file_missing(tmp_path: Path) -> None:
    """A non-existent CSV yields an empty snapshot rather than raising.

    Rationale: Observer must keep polling even if AP hasn't written its first
    CSV yet (boot-time race). DP-6 says fail loud, but here "no data" is a
    legitimate state, not a failure — the bridge keeps trying on next tick.
    """
    from lens.observer.ap_bridge import CSVStatusSource

    snapshot = await CSVStatusSource(tmp_path / "missing.csv").fetch_snapshot()
    assert snapshot == {}


async def test_csv_source_handles_partially_written_file(tmp_path: Path) -> None:
    """A CSV in mid-write (header only, or trailing partial row) yields what's parseable.

    AP could be writing the file when we read it. We accept "best-effort
    parse" and rely on the next poll tick to catch up — events will be
    deduplicated downstream by event_id (spec §5.7).
    """
    from lens.observer.ap_bridge import CSVStatusSource

    csv_path = tmp_path / "ap.csv"
    # Header + one good row + one truncated row (no newline at end, missing fields)
    csv_path.write_text(
        "flow_id,library,owner,state,started_at,completed_at,error_message\n"
        "f1,libA,brian,RUNNING,2026-04-27T10:00:00+00:00,,\n"
        "f2,libA,brian,RUN"  # truncated mid-write
    )

    snapshot = await CSVStatusSource(csv_path).fetch_snapshot()
    # f1 must be present; f2 is "best effort" — either parsed with garbage state
    # or missing entirely. We don't assert about f2.
    assert "f1" in snapshot
    assert snapshot["f1"]["state"] == "RUNNING"
