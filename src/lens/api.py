"""API layer (L5) simplified query facade."""

from typing import TypedDict

from lens.projection import BuildProjection


class BuildSummary(TypedDict):
    build_id: str
    started: int
    completed: int
    failed: int


def get_build_summary(projection: BuildProjection, build_id: str) -> BuildSummary:
    summary = projection.summary(build_id)
    return {
        "build_id": build_id,
        "started": summary["started"],
        "completed": summary["completed"],
        "failed": summary["failed"],
    }
