"""API layer (L5) simplified query facade."""

from lens.projection import BuildProjection


def get_build_summary(projection: BuildProjection, build_id: str) -> dict[str, int | str]:
    summary = projection.summary(build_id)
    return {"build_id": build_id, **summary}
