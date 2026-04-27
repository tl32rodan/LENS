"""Unit tests for lens.events.schema — event-data contract.

Spec references:
- docs/LENS_CHARTER.md DP-3 (level enum is data), DP-6 (loud failure)
- docs/LENS_IMPLEMENTATION.md §2.3 Public Interfaces, §2.6 Notes
- docs/LENS_TEST_REFERENCE.md §1.2 sample style
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError


def _valid_envelope_input() -> dict[str, object]:
    """Return a kwargs dict that satisfies every required EventEnvelope field."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "schema_version": "1.0",
        "timestamp": datetime(2024, 4, 24, 10, 0, 0, tzinfo=UTC),
        "build_id": "build_42",
    }


def test_envelope_accepts_valid_minimal_input() -> None:
    """A minimal envelope with all required fields constructs successfully."""
    from lens.events.schema import EventEnvelope

    env = EventEnvelope(**_valid_envelope_input())  # type: ignore[arg-type]
    assert env.event_id == "550e8400-e29b-41d4-a716-446655440000"
    assert env.schema_version == "1.0"
    assert env.build_id == "build_42"
    assert env.parent_event_id is None


def test_envelope_requires_event_id() -> None:
    """Missing event_id must raise ValidationError mentioning the field (DP-6)."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    del payload["event_id"]
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(**payload)  # type: ignore[arg-type]
    assert "event_id" in str(exc_info.value)
