"""Unit tests for lens.events.exceptions.

Per docs/LENS_IMPLEMENTATION.md §1.5 (error handling).
"""

from __future__ import annotations


def test_schema_validation_error_message_round_trips() -> None:
    """SchemaValidationError carries a human-readable message accessible via str()."""
    from lens.events.exceptions import SchemaValidationError

    err = SchemaValidationError("missing field 'event_id'")
    assert str(err) == "missing field 'event_id'"
