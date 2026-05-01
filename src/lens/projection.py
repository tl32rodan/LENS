"""Projection layer (L3) building read models from events."""

from lens.events import NodeCompleted, NodeStarted


class BuildProjection:
    def __init__(self) -> None:
        self._state: dict[str, dict[str, int]] = {}

    def apply(self, event: object) -> None:
        if isinstance(event, (NodeStarted, NodeCompleted)):
            build = self._state.setdefault(
                event.build_id,
                {"started": 0, "completed": 0, "failed": 0},
            )
            if isinstance(event, NodeStarted):
                build["started"] += 1
            elif isinstance(event, NodeCompleted):
                build["completed"] += 1
                if event.exit_code != 0:
                    build["failed"] += 1

    def summary(self, build_id: str) -> dict[str, int]:
        return self._state.get(build_id, {"started": 0, "completed": 0, "failed": 0}).copy()
