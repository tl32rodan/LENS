import unittest
from datetime import datetime, timezone

from lens.api import get_build_summary
from lens.events import NodeCompleted, NodeStarted
from lens.observer import Observer
from lens.projection import BuildProjection


class TestMVPPipeline(unittest.TestCase):
    def test_end_to_end_build_summary(self):
        projection = BuildProjection()
        observer = Observer(subscribers=[projection.apply])

        now = datetime.now(timezone.utc)
        observer.emit(
            NodeStarted(
                event_id="evt-1",
                schema_version="1.0",
                timestamp=now,
                build_id="build-1",
                node_id="node-a",
                entity_id="flow-1",
            )
        )
        observer.emit(
            NodeCompleted(
                event_id="evt-2",
                schema_version="1.0",
                timestamp=now,
                build_id="build-1",
                node_id="node-a",
                entity_id="flow-1",
                exit_code=0,
                duration_seconds=3.5,
            )
        )

        summary = get_build_summary(projection, "build-1")
        self.assertEqual(summary["build_id"], "build-1")
        self.assertEqual(summary["started"], 1)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["failed"], 0)

    def test_invalid_schema_version_raises(self):
        with self.assertRaises(ValueError):
            NodeStarted(
                event_id="evt-1",
                schema_version="v1",
                timestamp=datetime.now(timezone.utc),
                build_id="build-1",
                node_id="node-a",
                entity_id="flow-1",
            )


if __name__ == "__main__":
    unittest.main()
