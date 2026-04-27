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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from lens.events.schema import (
    EventEnvelope,
    FlowCompleted,
    FlowFailed,
    FlowStarted,
)

_TERMINAL_STATES = frozenset({"COMPLETED", "FAILED"})


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


def diff_snapshots(
    old: dict[str, dict[str, Any]],
    new: dict[str, dict[str, Any]],
    *,
    build_id: str,
    now: datetime,
    id_gen: Callable[[], str],
) -> list[EventEnvelope]:
    """Pure function: compute events that represent the transition `old → new`.

    Phase-0 transition rules:
        old missing, new=RUNNING            → FlowStarted
        old=RUNNING, new=COMPLETED          → FlowCompleted
        old=RUNNING, new=FAILED             → FlowFailed
        old=RUNNING, new=RUNNING            → (nothing)
        old terminal (COMPLETED/FAILED)     → (nothing — terminal)
        old missing, new=COMPLETED/FAILED   → FlowStarted + matching terminal event
            (catch-up; relies on projection-layer dedup if duplicates)
    """
    events: list[EventEnvelope] = []
    for flow_id, new_state in new.items():
        old_state = old.get(flow_id)
        old_status = (old_state or {}).get("state")
        new_status = new_state.get("state")

        if old_status in _TERMINAL_STATES:
            continue  # already terminal — never re-emit

        envelope_kwargs: dict[str, Any] = {
            "schema_version": "1.0",
            "timestamp": now,
            "build_id": build_id,
            "entity_id": flow_id,
            "library": new_state.get("library"),
            "owner": new_state.get("owner"),
        }

        if old_status is None and new_status == "RUNNING":
            events.append(FlowStarted(event_id=id_gen(), **envelope_kwargs))
        elif old_status is None and new_status in _TERMINAL_STATES:
            # catch-up: emit FlowStarted then terminal
            events.append(FlowStarted(event_id=id_gen(), **envelope_kwargs))
            events.append(_terminal_event(new_status, new_state, id_gen, envelope_kwargs))
        elif old_status == "RUNNING" and new_status in _TERMINAL_STATES:
            events.append(_terminal_event(new_status, new_state, id_gen, envelope_kwargs))
    return events


def _terminal_event(
    status: str,
    state: dict[str, Any],
    id_gen: Callable[[], str],
    base: dict[str, Any],
) -> EventEnvelope:
    extras = {
        "exit_code": 0 if status == "COMPLETED" else 1,
        "duration_seconds": 0.0,  # observer doesn't track duration in Phase 0
    }
    if status == "COMPLETED":
        return FlowCompleted(event_id=id_gen(), **base, **extras)
    return FlowFailed(
        event_id=id_gen(),
        **base,
        **extras,
        error_message=state.get("error_message"),
    )
