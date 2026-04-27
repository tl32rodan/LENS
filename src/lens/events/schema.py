"""LENS event schema — Pydantic models for the L2 event-data contract.

Per docs/LENS_CHARTER.md DP-3, DP-6 and docs/LENS_IMPLEMENTATION.md §2.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

NodeLevel = Literal["build", "library", "flow", "pvt", "cell"]
"""Granularity level — DP-3: data, not schema."""


class EventEnvelope(BaseModel):
    """Common fields shared by every LENS event."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    timestamp: AwareDatetime
    build_id: str
    parent_event_id: UUID | None = None


class NodeStarted(EventEnvelope):
    """A node (at any level) has begun execution."""

    event_type: Literal["NodeStarted"] = "NodeStarted"
    node_id: str
    level: NodeLevel
    entity_id: str
    input_hash: str | None = None  # Phase 2+ content-addressed cache key
    resource_request: dict[str, int] | None = None  # Phase 2+ scheduling hint


class NodeCompleted(EventEnvelope):
    """A node has finished execution (success or failure)."""

    event_type: Literal["NodeCompleted"] = "NodeCompleted"
    node_id: str
    level: NodeLevel
    entity_id: str
    exit_code: int
    duration_seconds: float
    output_hash: str | None = None  # Phase 2+ CAS output key
