"""Domain exceptions for the L2 event-data layer.

Per docs/LENS_IMPLEMENTATION.md §1.5 (Error handling principles, system-level).
"""

from __future__ import annotations


class SchemaValidationError(Exception):
    """Raised when an event payload fails JSON Schema validation."""
