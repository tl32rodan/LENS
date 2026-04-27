"""LENS event schema — Pydantic models for the L2 event-data contract.

Per docs/LENS_CHARTER.md DP-3, DP-6 and docs/LENS_IMPLEMENTATION.md §2.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    """Common fields shared by every LENS event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    timestamp: AwareDatetime
    build_id: str
    parent_event_id: str | None = None
