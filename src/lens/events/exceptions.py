"""Domain exceptions for the L2 event-data layer.

Per docs/LENS_IMPLEMENTATION.md §1.5 (Error handling principles, system-level).
"""

from __future__ import annotations


class SchemaValidationError(Exception):
    """Raised when an event payload fails JSON Schema validation."""

    def __init__(
        self,
        message: str,
        *,
        event_type: str | None = None,
        version: str | None = None,
    ) -> None:
        super().__init__(message)
        self.event_type = event_type
        self.version = version
