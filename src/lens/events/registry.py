"""SchemaRegistry — load and validate against hand-written JSON Schema files.

Per docs/LENS_IMPLEMENTATION.md §2.3 (Public Interfaces) and §2.7 (MVP scope).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class SchemaRegistry:
    """Load `*.v<major>.json` schema files from a directory and validate events."""

    def __init__(self, schema_dir: Path) -> None:
        self._schemas: dict[tuple[str, int], dict[str, Any]] = {}

    def schema_count(self) -> int:
        """Return the number of distinct (event_type, major) schemas loaded."""
        return len(self._schemas)
