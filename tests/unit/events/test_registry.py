"""Unit tests for lens.events.registry — JSON Schema loader and validator.

Per docs/LENS_IMPLEMENTATION.md §2.3 (Public Interfaces) and §2.7 (Phase 0 scope).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
