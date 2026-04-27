"""SchemaRegistry — load and validate against hand-written JSON Schema files.

Per docs/LENS_IMPLEMENTATION.md §2.3 (Public Interfaces) and §2.7 (MVP scope).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]

from lens.events.exceptions import SchemaValidationError

_FILENAME_PATTERN = re.compile(r"^(?P<snake>[a-z][a-z0-9_]*)\.v(?P<major>\d+)\.json$")


def _snake_to_pascal(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_"))


class SchemaRegistry:
    """Load `*.v<major>.json` schema files from a directory and validate events."""

    def __init__(self, schema_dir: Path) -> None:
        self._schemas: dict[tuple[str, int], dict[str, Any]] = {}
        if not schema_dir.is_dir():
            raise SchemaValidationError(
                f"schema_dir does not exist or is not a directory: {schema_dir}"
            )
        for path in sorted(schema_dir.iterdir()):
            match = _FILENAME_PATTERN.match(path.name)
            if match is None:
                continue
            event_type = _snake_to_pascal(match.group("snake"))
            major = int(match.group("major"))
            try:
                self._schemas[(event_type, major)] = json.loads(path.read_text())
            except json.JSONDecodeError as e:
                raise SchemaValidationError(
                    f"malformed JSON in {path.name}: {e.msg}",
                    event_type=event_type,
                ) from e

    def schema_count(self) -> int:
        """Return the number of distinct (event_type, major) schemas loaded."""
        return len(self._schemas)

    def validate(self, event_dict: dict[str, Any]) -> None:
        """Validate event_dict against the registered schema for its type/version.

        Raises SchemaValidationError if event_type / schema_version are missing,
        if no schema is registered for the (event_type, major) pair, or if the
        payload fails JSON Schema validation (DP-6 — loud, specific).
        """
        try:
            event_type = event_dict["event_type"]
        except KeyError as e:
            raise SchemaValidationError("payload is missing required 'event_type'") from e
        try:
            version = event_dict["schema_version"]
        except KeyError as e:
            raise SchemaValidationError(
                "payload is missing required 'schema_version'",
                event_type=event_type,
            ) from e
        schema = self.get_schema(event_type, version)
        try:
            jsonschema.validate(event_dict, schema)
        except jsonschema.ValidationError as e:
            path = "/".join(str(p) for p in e.absolute_path) or "<root>"
            raise SchemaValidationError(
                f"{event_type} v{version} payload invalid at {path}: {e.message}",
                event_type=event_type,
                version=version,
            ) from e

    def get_schema(self, event_type: str, version: str) -> dict[str, Any]:
        """Return the loaded JSON Schema dict for the given event_type+version.

        `version` is the full `major.minor` string from the payload; only the
        major segment is used to look up the file (additive evolution per §2.1).
        Raises SchemaValidationError if no schema is registered.
        """
        major = int(version.split(".", 1)[0])
        try:
            return self._schemas[(event_type, major)]
        except KeyError as e:
            raise SchemaValidationError(
                f"no schema registered for event_type={event_type!r} version={version!r}",
                event_type=event_type,
                version=version,
            ) from e
