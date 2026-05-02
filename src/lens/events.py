"""Event models for LENS MVP."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

_SCHEMA_PATTERN = re.compile(r"^\d+\.\d+$")


@dataclass(frozen=True)
class EventEnvelope:
    """Base event envelope shared by all event types."""

    event_type: ClassVar[str] = "event"
    event_id: str
    schema_version: str
    timestamp: datetime
    build_id: str
    node_id: str
    entity_id: str

    def __post_init__(self) -> None:
        if not _SCHEMA_PATTERN.match(self.schema_version):
            raise ValueError("schema_version must be in 'X.Y' format")


@dataclass(frozen=True)
class NodeStarted(EventEnvelope):
    event_type: ClassVar[str] = "node.started"


@dataclass(frozen=True)
class NodeCompleted(EventEnvelope):
    event_type: ClassVar[str] = "node.completed"
    exit_code: int
    duration_seconds: float


class SchemaRegistry:
    """Minimal runtime registry for accepted event type discriminators."""

    def __init__(self) -> None:
        self._allowed_event_types = {NodeStarted.event_type, NodeCompleted.event_type}

    def validate(self, event: EventEnvelope) -> None:
        if event.event_type not in self._allowed_event_types:
            raise ValueError(f"unsupported event type: {event.event_type}")
