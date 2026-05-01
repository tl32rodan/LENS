"""Projection layer (L3) building read models from events."""

from lens.events import EventEnvelope, NodeCompleted, NodeStarted

_SUMMARY_TEMPLATE = {"started": 0, "completed": 0, "failed": 0}


class BuildProjection:
    def __init__(self) -> None:
        self._state: dict[str, dict[str, int]] = {}
        self._seen_event_ids: set[str] = set()

    def apply(self, event: EventEnvelope) -> None:
        if event.event_id in self._seen_event_ids:
            return
        self._seen_event_ids.add(event.event_id)

        build = self._state.setdefault(event.build_id, _SUMMARY_TEMPLATE.copy())
        if isinstance(event, NodeStarted):
            build["started"] += 1
        elif isinstance(event, NodeCompleted):
            build["completed"] += 1
            if event.exit_code != 0:
                build["failed"] += 1

    def summary(self, build_id: str) -> dict[str, int]:
        return self._state.get(build_id, _SUMMARY_TEMPLATE).copy()
