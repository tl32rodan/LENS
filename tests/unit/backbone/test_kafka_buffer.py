"""Unit tests for the producer's ndjson local buffer.

The local buffer is the only documented "silent" handling per IR-3 / DP-6 —
it absorbs sends when Kafka is unavailable, then drains on recovery. Per
spec §3.6 it stores newline-delimited JSON.

These tests run in CI (no Kafka required); the aiokafka-backed adapter
wrappers live in tests/integration/.
"""

from __future__ import annotations

from pathlib import Path


def test_buffer_is_empty_when_path_does_not_exist(tmp_path: Path) -> None:
    from lens.backbone.kafka_bus import NDJSONLocalBuffer

    buf = NDJSONLocalBuffer(tmp_path / "buffer.ndjson")
    assert buf.is_empty() is True


def test_buffer_append_then_drain_round_trips(tmp_path: Path) -> None:
    from lens.backbone.kafka_bus import NDJSONLocalBuffer

    buf = NDJSONLocalBuffer(tmp_path / "buf.ndjson")
    buf.append({"event_type": "FlowStarted", "id": 1})
    buf.append({"event_type": "FlowCompleted", "id": 1})

    drained = buf.drain()
    assert drained == [
        {"event_type": "FlowStarted", "id": 1},
        {"event_type": "FlowCompleted", "id": 1},
    ]


def test_buffer_drain_clears_storage(tmp_path: Path) -> None:
    from lens.backbone.kafka_bus import NDJSONLocalBuffer

    buf = NDJSONLocalBuffer(tmp_path / "buf.ndjson")
    buf.append({"a": 1})
    buf.drain()
    assert buf.is_empty() is True
    assert buf.drain() == []


def test_buffer_drain_returns_empty_list_for_missing_file(tmp_path: Path) -> None:
    from lens.backbone.kafka_bus import NDJSONLocalBuffer

    buf = NDJSONLocalBuffer(tmp_path / "never-created.ndjson")
    assert buf.drain() == []
    assert buf.is_empty() is True


def test_buffer_skips_blank_lines_on_drain(tmp_path: Path) -> None:
    """Robustness: a stray blank line in the buffer file does not break drain."""
    from lens.backbone.kafka_bus import NDJSONLocalBuffer

    path = tmp_path / "buf.ndjson"
    path.write_text('{"id": 1}\n\n{"id": 2}\n')

    drained = NDJSONLocalBuffer(path).drain()
    assert drained == [{"id": 1}, {"id": 2}]
