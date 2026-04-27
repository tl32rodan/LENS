"""Unit tests for lens.events.schema — event-data contract.

Spec references:
- docs/LENS_CHARTER.md DP-3 (level enum is data), DP-6 (loud failure)
- docs/LENS_IMPLEMENTATION.md §2.3 Public Interfaces, §2.6 Notes
- docs/LENS_TEST_REFERENCE.md §1.2 sample style
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

_VALID_EVENT_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


def _valid_envelope_input() -> dict[str, object]:
    """Return a kwargs dict that satisfies every required EventEnvelope field."""
    return {
        "event_id": str(_VALID_EVENT_ID),
        "schema_version": "1.0",
        "timestamp": datetime(2024, 4, 24, 10, 0, 0, tzinfo=UTC),
        "build_id": "build_42",
    }


def test_envelope_accepts_valid_minimal_input() -> None:
    """A minimal envelope with all required fields constructs successfully."""
    from lens.events.schema import EventEnvelope

    env = EventEnvelope(**_valid_envelope_input())  # type: ignore[arg-type]
    assert env.event_id == _VALID_EVENT_ID
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


def test_envelope_requires_schema_version() -> None:
    """Missing schema_version must raise ValidationError (DP-6)."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    del payload["schema_version"]
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(**payload)  # type: ignore[arg-type]
    assert "schema_version" in str(exc_info.value)


def test_envelope_requires_timestamp() -> None:
    """Missing timestamp must raise ValidationError (DP-6)."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    del payload["timestamp"]
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(**payload)  # type: ignore[arg-type]
    assert "timestamp" in str(exc_info.value)


def test_envelope_requires_build_id() -> None:
    """Missing build_id must raise ValidationError (DP-6)."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    del payload["build_id"]
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(**payload)  # type: ignore[arg-type]
    assert "build_id" in str(exc_info.value)


def test_envelope_rejects_schema_version_with_v_prefix() -> None:
    """schema_version must match `^\\d+\\.\\d+$` (per Implementation §2.3) — `v1` is invalid."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    payload["schema_version"] = "v1"
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(**payload)  # type: ignore[arg-type]
    assert "schema_version" in str(exc_info.value)


def test_envelope_rejects_schema_version_missing_minor() -> None:
    """`schema_version="1"` (no `.minor`) must be rejected by the regex."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    payload["schema_version"] = "1"
    with pytest.raises(ValidationError):
        EventEnvelope(**payload)  # type: ignore[arg-type]


def test_envelope_accepts_null_parent_event_id() -> None:
    """parent_event_id is optional; explicit None must be accepted."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    payload["parent_event_id"] = None
    env = EventEnvelope(**payload)  # type: ignore[arg-type]
    assert env.parent_event_id is None


def test_envelope_rejects_extra_unknown_field() -> None:
    """Unknown fields must raise ValidationError (Implementation §2.6, DP-6)."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    payload["unexpected_field"] = "garbage"
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(**payload)  # type: ignore[arg-type]
    assert "unexpected_field" in str(exc_info.value)


def test_envelope_parses_iso8601_timestamp_with_z() -> None:
    """`Z` suffix must parse as UTC."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    payload["timestamp"] = "2024-04-24T10:00:00Z"
    env = EventEnvelope(**payload)  # type: ignore[arg-type]
    assert env.timestamp.tzinfo is not None
    assert env.timestamp.utcoffset() == timedelta(0)


def test_envelope_parses_iso8601_timestamp_with_offset() -> None:
    """Numeric tz offset (e.g., `+08:00`) must parse with that offset."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    payload["timestamp"] = "2024-04-24T18:00:00+08:00"
    env = EventEnvelope(**payload)  # type: ignore[arg-type]
    assert env.timestamp.utcoffset() == timedelta(hours=8)


def test_envelope_rejects_naive_timestamp() -> None:
    """Naive datetimes are ambiguous across regions; reject them (DP-6, decision Q3)."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    payload["timestamp"] = datetime(2024, 4, 24, 10, 0, 0)  # no tzinfo
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(**payload)  # type: ignore[arg-type]
    assert "timestamp" in str(exc_info.value)


def test_envelope_rejects_non_uuid_event_id() -> None:
    """event_id is a UUID v4 (Implementation §2.3); reject malformed values (DP-6)."""
    from lens.events.schema import EventEnvelope

    payload = _valid_envelope_input()
    payload["event_id"] = "not-a-uuid"
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(**payload)  # type: ignore[arg-type]
    assert "event_id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# NodeStarted
# ---------------------------------------------------------------------------


def _valid_node_started_input() -> dict[str, object]:
    return {
        **_valid_envelope_input(),
        "node_id": "node_1",
        "level": "flow",
        "entity_id": "drc_flow",
    }


def test_node_started_accepts_valid_input() -> None:
    """NodeStarted constructs from envelope fields plus node identity."""
    from lens.events.schema import NodeStarted

    evt = NodeStarted(**_valid_node_started_input())  # type: ignore[arg-type]
    assert evt.node_id == "node_1"
    assert evt.level == "flow"
    assert evt.entity_id == "drc_flow"
    assert evt.event_type == "NodeStarted"


def test_node_started_requires_node_id() -> None:
    from lens.events.schema import NodeStarted

    payload = _valid_node_started_input()
    del payload["node_id"]
    with pytest.raises(ValidationError) as exc_info:
        NodeStarted(**payload)  # type: ignore[arg-type]
    assert "node_id" in str(exc_info.value)


def test_node_started_requires_level() -> None:
    from lens.events.schema import NodeStarted

    payload = _valid_node_started_input()
    del payload["level"]
    with pytest.raises(ValidationError) as exc_info:
        NodeStarted(**payload)  # type: ignore[arg-type]
    assert "level" in str(exc_info.value)


def test_node_started_requires_entity_id() -> None:
    from lens.events.schema import NodeStarted

    payload = _valid_node_started_input()
    del payload["entity_id"]
    with pytest.raises(ValidationError) as exc_info:
        NodeStarted(**payload)  # type: ignore[arg-type]
    assert "entity_id" in str(exc_info.value)


def test_node_started_rejects_unknown_level_value() -> None:
    """Per DP-3, level is a closed enum; unknown values must be rejected."""
    from lens.events.schema import NodeStarted

    payload = _valid_node_started_input()
    payload["level"] = "INVALID"
    with pytest.raises(ValidationError) as exc_info:
        NodeStarted(**payload)  # type: ignore[arg-type]
    assert "level" in str(exc_info.value)


@pytest.mark.parametrize("level", ["build", "library", "flow", "pvt", "cell"])
def test_node_started_accepts_each_valid_level(level: str) -> None:
    """All five levels in the DP-3 enum must be accepted."""
    from lens.events.schema import NodeStarted

    payload = _valid_node_started_input()
    payload["level"] = level
    evt = NodeStarted(**payload)  # type: ignore[arg-type]
    assert evt.level == level


def test_node_started_event_type_field_is_literal() -> None:
    """event_type for a NodeStarted instance must be the constant `'NodeStarted'`."""
    from lens.events.schema import NodeStarted

    payload = _valid_node_started_input()
    payload["event_type"] = "FlowStarted"  # wrong literal
    with pytest.raises(ValidationError) as exc_info:
        NodeStarted(**payload)  # type: ignore[arg-type]
    assert "event_type" in str(exc_info.value)


def test_node_started_input_hash_is_optional() -> None:
    """input_hash is a Phase 2+ field; absence and explicit None must both work."""
    from lens.events.schema import NodeStarted

    evt_default = NodeStarted(**_valid_node_started_input())  # type: ignore[arg-type]
    assert evt_default.input_hash is None

    payload = _valid_node_started_input()
    payload["input_hash"] = "sha256:abc"
    evt_set = NodeStarted(**payload)  # type: ignore[arg-type]
    assert evt_set.input_hash == "sha256:abc"


def test_node_started_resource_request_accepts_int_dict() -> None:
    """resource_request is an optional dict[str, int] for Phase 2+ scheduling."""
    from lens.events.schema import NodeStarted

    payload = _valid_node_started_input()
    payload["resource_request"] = {"cpu": 4, "memory_gb": 16}
    evt = NodeStarted(**payload)  # type: ignore[arg-type]
    assert evt.resource_request == {"cpu": 4, "memory_gb": 16}


def test_node_started_serialization_roundtrip() -> None:
    """model -> JSON -> model must reconstruct an equal value."""
    from lens.events.schema import NodeStarted

    original = NodeStarted(**_valid_node_started_input())  # type: ignore[arg-type]
    payload = original.model_dump_json()
    reconstructed = NodeStarted.model_validate_json(payload)
    assert reconstructed == original


def test_node_started_rejects_extra_unknown_field() -> None:
    """ConfigDict(extra='forbid') is inherited from EventEnvelope."""
    from lens.events.schema import NodeStarted

    payload = _valid_node_started_input()
    payload["mystery"] = "?"
    with pytest.raises(ValidationError) as exc_info:
        NodeStarted(**payload)  # type: ignore[arg-type]
    assert "mystery" in str(exc_info.value)




