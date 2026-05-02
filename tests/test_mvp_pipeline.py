import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from lens.api import get_build_summary
from lens.events import EventEnvelope, NodeCompleted, NodeStarted, SchemaRegistry
from lens.observer import Observer
from lens.projection import BuildProjection


@dataclass(frozen=True)
class UnknownEvent(EventEnvelope):
    event_type = "unknown.event"


class TestMVPPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(timezone.utc)

    def _node_started(self, event_id: str, build_id: str = "build-1") -> NodeStarted:
        return NodeStarted(
            event_id=event_id,
            schema_version="1.0",
            timestamp=self.now,
            build_id=build_id,
            node_id="node-a",
            entity_id="flow-1",
        )

    def _node_completed(
        self, event_id: str, exit_code: int, build_id: str = "build-1"
    ) -> NodeCompleted:
        return NodeCompleted(
            event_id=event_id,
            schema_version="1.0",
            timestamp=self.now,
            build_id=build_id,
            node_id="node-a",
            entity_id="flow-1",
            exit_code=exit_code,
            duration_seconds=3.5,
        )

    def test_end_to_end_build_summary(self) -> None:
        projection = BuildProjection()
        observer = Observer(subscribers=[projection.apply])

        observer.emit(self._node_started("evt-1"))
        observer.emit(self._node_completed("evt-2", exit_code=0))

        summary = get_build_summary(projection, "build-1")
        self.assertEqual(
            summary,
            {"build_id": "build-1", "started": 1, "completed": 1, "failed": 0},
        )

    def test_failed_node_is_counted(self) -> None:
        projection = BuildProjection()
        projection.apply(self._node_completed("evt-3", exit_code=1))
        self.assertEqual(projection.summary("build-1"), {"started": 0, "completed": 1, "failed": 1})

    def test_projection_is_idempotent_by_event_id(self) -> None:
        projection = BuildProjection()
        event = self._node_started("evt-dup")
        projection.apply(event)
        projection.apply(event)

        self.assertEqual(projection.summary("build-1"), {"started": 1, "completed": 0, "failed": 0})

    def test_summary_default_for_missing_build(self) -> None:
        projection = BuildProjection()
        self.assertEqual(projection.summary("unknown"), {"started": 0, "completed": 0, "failed": 0})

    def test_observer_fans_out(self) -> None:
        received_ids: list[str] = []
        observer = Observer(subscribers=[lambda event: received_ids.append(event.event_id)])
        observer.emit(self._node_started("evt-fanout"))
        self.assertEqual(received_ids, ["evt-fanout"])

    def test_schema_registry_rejects_unknown_event_type(self) -> None:
        observer = Observer(subscribers=[])
        with self.assertRaises(ValueError):
            observer.emit(
                UnknownEvent(
                    event_id="evt-unknown",
                    schema_version="1.0",
                    timestamp=self.now,
                    build_id="build-1",
                    node_id="node-a",
                    entity_id="flow-1",
                )
            )

    def test_invalid_schema_version_raises(self) -> None:
        invalid_versions = ["v1", "1.", ".0", "", "1"]
        for invalid_version in invalid_versions:
            with self.subTest(invalid_version=invalid_version):
                with self.assertRaises(ValueError):
                    NodeStarted(
                        event_id="evt-invalid",
                        schema_version=invalid_version,
                        timestamp=self.now,
                        build_id="build-1",
                        node_id="node-a",
                        entity_id="flow-1",
                    )

    def test_schema_registry_accepts_known_events(self) -> None:
        registry = SchemaRegistry()
        registry.validate(self._node_started("evt-known-1"))
        registry.validate(self._node_completed("evt-known-2", exit_code=0))


if __name__ == "__main__":
    unittest.main()
