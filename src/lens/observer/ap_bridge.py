"""Observer (L0) — bridges AP's status output into LENS event stream.

Per docs/LENS_IMPLEMENTATION.md §4.3, §4.6, §4.7. Phase-0 scope: CSV source +
APEventBridge polling loop, emitting FlowStarted / FlowCompleted / FlowFailed.

The CSV schema below is the **assumed default** (per the no-Docker MVP plan,
decision #16 in the plan file). When AP's real CSV format is confirmed, swap
the decoder by either editing `CSVStatusSource._row_to_state` or shipping an
alternative `APStatusSource` implementation — everything downstream targets
the Protocol, not the parser.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Protocol


class APStatusSource(Protocol):
    """Pluggable source of AP's current state. Returns a dict keyed by flow_id."""

    async def fetch_snapshot(self) -> dict[str, dict[str, Any]]: ...


class CSVStatusSource:
    """Read AP's CSV dashboard.

    Assumed schema (column order is irrelevant; column names are):
        flow_id        (required)
        library        (optional)
        owner          (optional)
        state          (required; one of RUNNING / COMPLETED / FAILED)
        started_at     (optional; ISO-8601)
        completed_at   (optional; ISO-8601)
        error_message  (optional)
    """

    def __init__(self, csv_path: Path) -> None:
        self._path = csv_path

    async def fetch_snapshot(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        with self._path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            return {
                row["flow_id"]: {k: (v if v != "" else None) for k, v in row.items()}
                for row in reader
                if row.get("flow_id")
            }
