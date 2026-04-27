"""Unit tests for the pure `diff_snapshots` function.

Per docs/LENS_IMPLEMENTATION.md §4.6 (the diff is a pure function for
testability) and docs/LENS_TEST_REFERENCE.md §3.1 (bridge-emit cases — those
spec tests test the bridge's wiring, but the actual transition logic is what
this file pins down).

Snapshot shape: dict[flow_id, dict[str, Any]] with at least a `state` key
in {"RUNNING", "COMPLETED", "FAILED"}.
"""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import count
from typing import Any
from uuid import UUID


def _id_gen() -> UUID:
    """Deterministic stand-in for uuid4() in tests."""
    n = next(_id_gen.counter)  # type: ignore[attr-defined]
    return UUID(f"00000000-0000-0000-0000-{n:012d}")


_id_gen.counter = count()  # type: ignore[attr-defined]


_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)


def _state(state: str, **extras: Any) -> dict[str, Any]:
    return {"state": state, "library": "libA", "owner": "brian", **extras}


def _types(events: list[Any]) -> list[str]:
    return [e.model_dump()["event_type"] for e in events]


def test_diff_snapshots_emits_flow_started_for_new_running_flow() -> None:
    from lens.observer.ap_bridge import diff_snapshots

    events = diff_snapshots({}, {"f1": _state("RUNNING")}, build_id="b1", now=_NOW, id_gen=_id_gen)
    assert _types(events) == ["FlowStarted"]
    assert events[0].model_dump()["entity_id"] == "f1"


def test_diff_snapshots_emits_flow_completed_on_running_to_completed() -> None:
    from lens.observer.ap_bridge import diff_snapshots

    events = diff_snapshots(
        {"f1": _state("RUNNING")},
        {"f1": _state("COMPLETED")},
        build_id="b1",
        now=_NOW,
        id_gen=_id_gen,
    )
    assert _types(events) == ["FlowCompleted"]


def test_diff_snapshots_emits_flow_failed_on_running_to_failed() -> None:
    from lens.observer.ap_bridge import diff_snapshots

    events = diff_snapshots(
        {"f1": _state("RUNNING")},
        {"f1": _state("FAILED", error_message="boom")},
        build_id="b1",
        now=_NOW,
        id_gen=_id_gen,
    )
    assert _types(events) == ["FlowFailed"]
    assert events[0].model_dump()["error_message"] == "boom"


def test_diff_snapshots_emits_nothing_for_unchanged_running_flow() -> None:
    from lens.observer.ap_bridge import diff_snapshots

    snapshot = {"f1": _state("RUNNING")}
    events = diff_snapshots(snapshot, snapshot, build_id="b1", now=_NOW, id_gen=_id_gen)
    assert events == []


def test_diff_snapshots_emits_nothing_for_terminal_flow_seen_again() -> None:
    """A flow already in COMPLETED/FAILED never re-emits."""
    from lens.observer.ap_bridge import diff_snapshots

    snapshot = {"f1": _state("COMPLETED")}
    events = diff_snapshots(snapshot, snapshot, build_id="b1", now=_NOW, id_gen=_id_gen)
    assert events == []


def test_diff_snapshots_catch_up_for_already_completed_flow_on_first_seen() -> None:
    """Observer just started; flow is already COMPLETED. Emit Started+Completed."""
    from lens.observer.ap_bridge import diff_snapshots

    events = diff_snapshots(
        {},
        {"f1": _state("COMPLETED")},
        build_id="b1",
        now=_NOW,
        id_gen=_id_gen,
    )
    assert _types(events) == ["FlowStarted", "FlowCompleted"]
