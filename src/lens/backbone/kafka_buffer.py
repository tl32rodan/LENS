"""Append-and-drain newline-delimited JSON buffer.

Per docs/LENS_IMPLEMENTATION.md §3.6 and IR-3: this is the only "silent"
handling allowed in the producer. It is documented, observable (file on
disk, log line on append), and drained on Kafka recovery.

Lives in its own module so it stays unit-tested in CI (no aiokafka
dependency); the aiokafka-backed adapters in `kafka_bus.py` are
integration-only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class NDJSONLocalBuffer:
    """Newline-delimited JSON buffer for events that failed to send."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
        logger.warning(
            "kafka send failed; buffered to %s (%d events queued)",
            self._path,
            self._line_count(),
        )

    def drain(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        events: list[dict[str, Any]] = []
        for raw in self._path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            events.append(json.loads(line))
        self._path.unlink(missing_ok=True)
        return events

    def is_empty(self) -> bool:
        return not self._path.exists() or self._path.stat().st_size == 0

    def _line_count(self) -> int:
        if not self._path.exists():
            return 0
        return sum(1 for _ in self._path.read_text(encoding="utf-8").splitlines())
