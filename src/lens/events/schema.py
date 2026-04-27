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
    duration_seconds: float = Field(ge=0)
    output_hash: str | None = None  # Phase 2+ CAS output key


class _FlowEventBase(EventEnvelope):
    """Shared shape for FlowStarted/FlowCompleted/FlowFailed.

    `level` is fixed to "flow" since these events describe flow-level
    transitions (DP-3 still applies — the level is on the data).
    `library` and `owner` are optional per decision Q2, matching the
    nullable columns in dashboard_kg_state.
    """

    level: Literal["flow"] = "flow"
    entity_id: str
    library: str | None = None
    owner: str | None = None


class FlowStarted(_FlowEventBase):
    """A flow has begun execution."""

    event_type: Literal["FlowStarted"] = "FlowStarted"


class FlowCompleted(_FlowEventBase):
    """A flow has finished. Per decision Q1, exit_code is loose at schema level;
    success/failure interpretation is the projection layer's job.
    """

    event_type: Literal["FlowCompleted"] = "FlowCompleted"
    exit_code: int
    duration_seconds: float = Field(ge=0)


class FlowFailed(_FlowEventBase):
    """A flow has failed. exit_code is loose (Q1); error_message is optional."""

    event_type: Literal["FlowFailed"] = "FlowFailed"
    exit_code: int
    duration_seconds: float = Field(ge=0)
    error_message: str | None = None
