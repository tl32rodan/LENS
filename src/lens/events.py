"""Event models for LENS MVP."""

import re
from dataclasses import dataclass
from datetime import datetime

_SCHEMA_PATTERN = re.compile(r"^\d+\.\d+$")


@dataclass(frozen=True)
class EventEnvelope:
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
    pass


@dataclass(frozen=True)
class NodeCompleted(EventEnvelope):
    exit_code: int
    duration_seconds: float
