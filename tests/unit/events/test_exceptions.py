"""Unit tests for lens.events.exceptions.

Per docs/LENS_IMPLEMENTATION.md §1.5 (error handling).
"""

from __future__ import annotations


def test_schema_validation_error_message_round_trips() -> None:
    """SchemaValidationError carries a human-readable message accessible via str()."""
    from lens.events.exceptions import SchemaValidationError

    err = SchemaValidationError("missing field 'event_id'")
    assert str(err) == "missing field 'event_id'"


def test_schema_validation_error_carries_event_type_and_version_when_provided() -> None:
    """The error optionally carries the event_type/version for debug logs."""
    from lens.events.exceptions import SchemaValidationError

    err = SchemaValidationError(
        "field exit_code is required",
        event_type="NodeCompleted",
        version="1.0",
    )
    assert err.event_type == "NodeCompleted"
    assert err.version == "1.0"
    assert "field exit_code is required" in str(err)
