"""Unit tests for lens.events.registry — JSON Schema loader and validator.

Per docs/LENS_IMPLEMENTATION.md §2.3 (Public Interfaces) and §2.7 (Phase 0 scope).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def _write_schema(
    dir_: Path, event_type: str, major: int, schema: dict[str, Any]
) -> Path:
    """Write a JSON Schema file using the project's filename convention."""
    snake = "".join("_" + c.lower() if c.isupper() else c for c in event_type).lstrip("_")
    file_ = dir_ / f"{snake}.v{major}.json"
    file_.write_text(json.dumps(schema))
    return file_


def _minimal_node_started_schema() -> dict[str, Any]:
    """A pared-down NodeStarted schema sufficient for registry tests."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "NodeStarted",
        "type": "object",
        "additionalProperties": False,
        "required": ["event_type", "schema_version", "event_id", "node_id"],
        "properties": {
            "event_type": {"const": "NodeStarted"},
            "schema_version": {"type": "string", "pattern": r"^\d+\.\d+$"},
            "event_id": {"type": "string", "format": "uuid"},
            "node_id": {"type": "string"},
        },
    }


def test_registry_constructs_from_empty_dir(tmp_path: Path) -> None:
    """An empty schema directory yields a registry with zero loaded schemas."""
    from lens.events.registry import SchemaRegistry

    registry = SchemaRegistry(tmp_path)
    assert registry.schema_count() == 0


def test_registry_loads_single_valid_schema_file(tmp_path: Path) -> None:
    """A single well-formed schema file is loaded and indexed by (event_type, major)."""
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())

    registry = SchemaRegistry(tmp_path)
    assert registry.schema_count() == 1
    schema = registry.get_schema("NodeStarted", "1.0")
    assert schema["title"] == "NodeStarted"


def test_registry_loads_multiple_schema_files(tmp_path: Path) -> None:
    """Multiple files in the directory are all loaded."""
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    _write_schema(
        tmp_path,
        "NodeCompleted",
        1,
        {**_minimal_node_started_schema(), "title": "NodeCompleted"},
    )

    registry = SchemaRegistry(tmp_path)
    assert registry.schema_count() == 2


def test_registry_skips_files_not_matching_naming_pattern(tmp_path: Path) -> None:
    """Files like README.md or `node_started.json` (no v<major>) must be ignored."""
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    (tmp_path / "README.md").write_text("docs go here")
    (tmp_path / "node_started.json").write_text("{}")  # no version segment
    (tmp_path / "node_started.v1.txt").write_text("wrong extension")

    registry = SchemaRegistry(tmp_path)
    assert registry.schema_count() == 1


def test_registry_raises_on_malformed_json_at_construction(tmp_path: Path) -> None:
    """Malformed JSON must fail fast at construction (DP-6, not deferred to validate)."""
    import pytest

    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    (tmp_path / "node_started.v1.json").write_text("{not valid json")

    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaRegistry(tmp_path)
    assert "node_started.v1.json" in str(exc_info.value)


def test_registry_raises_when_schema_dir_does_not_exist(tmp_path: Path) -> None:
    """A non-existent schema directory must raise loud (DP-6), not silently skip."""
    import pytest

    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    missing = tmp_path / "no_such_dir"
    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaRegistry(missing)
    assert "no_such_dir" in str(exc_info.value)


# ---------------------------------------------------------------------------
# validate() — happy paths
# ---------------------------------------------------------------------------


def _valid_node_started_payload() -> dict[str, Any]:
    """A dict that satisfies _minimal_node_started_schema()."""
    return {
        "event_type": "NodeStarted",
        "schema_version": "1.0",
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "node_id": "node_1",
    }


def test_validate_returns_none_for_valid_node_started_payload(tmp_path: Path) -> None:
    """A payload matching its schema must pass without raising."""
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)
    registry.validate(_valid_node_started_payload())  # must not raise


def _all_event_types_with_payload() -> list[tuple[str, dict[str, Any]]]:
    """The 5 Phase-0 event types with a minimal payload satisfying their schema."""
    base_envelope = {
        "schema_version": "1.0",
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    return [
        ("NodeStarted", {**base_envelope, "event_type": "NodeStarted", "node_id": "n"}),
        (
            "NodeCompleted",
            {**base_envelope, "event_type": "NodeCompleted", "exit_code": 0},
        ),
        ("FlowStarted", {**base_envelope, "event_type": "FlowStarted", "entity_id": "f"}),
        (
            "FlowCompleted",
            {**base_envelope, "event_type": "FlowCompleted", "entity_id": "f", "exit_code": 0},
        ),
        ("FlowFailed", {**base_envelope, "event_type": "FlowFailed", "entity_id": "f"}),
    ]


@pytest.fixture
def registry_with_minimal_schemas(tmp_path: Path) -> Any:
    """Registry seeded with one minimal schema per Phase-0 event type."""
    from lens.events.registry import SchemaRegistry

    for event_type, payload in _all_event_types_with_payload():
        required = ["event_type", "schema_version", "event_id", *(
            k for k in payload if k not in ("event_type", "schema_version", "event_id")
        )]
        _write_schema(
            tmp_path,
            event_type,
            1,
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": event_type,
                "type": "object",
                "additionalProperties": False,
                "required": required,
                "properties": {k: {} for k in required},
            },
        )
    return SchemaRegistry(tmp_path)


@pytest.mark.parametrize("event_type,payload", _all_event_types_with_payload())
def test_validate_accepts_each_of_the_five_event_types(
    registry_with_minimal_schemas: Any,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Every Phase-0 event type can pass validation given a matching schema."""
    registry_with_minimal_schemas.validate(payload)


def test_validate_accepts_payload_with_higher_minor_version(tmp_path: Path) -> None:
    """A payload claiming version 1.5 still validates against the v1 file
    (additive evolution per docs/LENS_IMPLEMENTATION.md §2.1)."""
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    payload["schema_version"] = "1.5"
    registry.validate(payload)  # must not raise


# ---------------------------------------------------------------------------
# validate() — failure paths (DP-6: loud, specific)
# ---------------------------------------------------------------------------


def test_validate_raises_on_missing_event_type_key(tmp_path: Path) -> None:
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    del payload["event_type"]
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "event_type" in str(exc_info.value)


def test_validate_raises_on_missing_schema_version_key(tmp_path: Path) -> None:
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    del payload["schema_version"]
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "schema_version" in str(exc_info.value)


def test_validate_raises_on_unknown_event_type(tmp_path: Path) -> None:
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    payload["event_type"] = "MysteriousEvent"
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "MysteriousEvent" in str(exc_info.value)


def test_validate_raises_when_no_schema_for_major_version(tmp_path: Path) -> None:
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    payload["schema_version"] = "2.0"
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "2.0" in str(exc_info.value)


def test_validate_raises_on_missing_required_field_in_payload(tmp_path: Path) -> None:
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    del payload["node_id"]
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "node_id" in str(exc_info.value)


def test_validate_raises_on_extra_unknown_field(tmp_path: Path) -> None:
    """additionalProperties:false rejects extra fields (mirrors Pydantic 'extra=forbid')."""
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    payload["mystery"] = "?"
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "mystery" in str(exc_info.value)


def test_validate_raises_on_wrong_type_for_field(tmp_path: Path) -> None:
    """Wrong-typed field values must be rejected (DP-6)."""
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    payload["node_id"] = 42  # schema requires string
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "node_id" in str(exc_info.value)


def test_validate_raises_on_invalid_uuid_format_for_event_id(tmp_path: Path) -> None:
    """The schema declares format:uuid; non-UUID strings must fail."""
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    payload["event_id"] = "not-a-uuid"
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "event_id" in str(exc_info.value)


def test_validate_raises_on_invalid_level_enum_value(tmp_path: Path) -> None:
    """level is a closed enum (DP-3); unknown values must be rejected."""
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "NodeStarted",
        "type": "object",
        "additionalProperties": False,
        "required": ["event_type", "schema_version", "event_id", "level"],
        "properties": {
            "event_type": {"const": "NodeStarted"},
            "schema_version": {"type": "string", "pattern": r"^\d+\.\d+$"},
            "event_id": {"type": "string", "format": "uuid"},
            "level": {"enum": ["build", "library", "flow", "pvt", "cell"]},
        },
    }
    _write_schema(tmp_path, "NodeStarted", 1, schema)
    registry = SchemaRegistry(tmp_path)

    payload = {**_valid_node_started_payload(), "level": "INVALID"}
    del payload["node_id"]  # not in this schema's required list
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    assert "level" in str(exc_info.value)


def test_validate_error_message_includes_field_path(tmp_path: Path) -> None:
    """DP-6 specificity: the error must point at the offending field path."""
    from lens.events.exceptions import SchemaValidationError
    from lens.events.registry import SchemaRegistry

    _write_schema(tmp_path, "NodeStarted", 1, _minimal_node_started_schema())
    registry = SchemaRegistry(tmp_path)

    payload = _valid_node_started_payload()
    payload["node_id"] = 42
    with pytest.raises(SchemaValidationError) as exc_info:
        registry.validate(payload)
    msg = str(exc_info.value)
    assert "node_id" in msg
    assert "NodeStarted" in msg
    assert "1.0" in msg


# ---------------------------------------------------------------------------
# get_schema()
# ---------------------------------------------------------------------------


def test_get_schema_returns_loaded_dict_for_known_type_and_version(tmp_path: Path) -> None:
    from lens.events.registry import SchemaRegistry

    schema = _minimal_node_started_schema()
    _write_schema(tmp_path, "NodeStarted", 1, schema)

    registry = SchemaRegistry(tmp_path)
    assert registry.get_schema("NodeStarted", "1.0") == schema
    assert registry.get_schema("NodeStarted", "1.7") == schema  # any minor of major 1


