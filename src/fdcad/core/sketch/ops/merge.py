"""Merge two sketch points into one (TUTORIAL_REVIEW_SPEC_2 TR40, DECISIONS D822).

Unlike Coincident, which keeps two points that sit together, Merge leaves one
point: every curve, relation and dimension that used the second point uses
the first. Relations and dimensions that would then join the point to
itself are removed. The kept point stays where it was; the solver moves the
rest.
"""

from __future__ import annotations

from fdcad.core.sketch.model import Point, Sketch, entity_points, remap


def merge_problem(sketch: Sketch, keep: str, drop: str) -> str | None:
    """Why ``drop`` cannot be merged into ``keep``, or None when it can."""
    a, b = sketch.entities.get(keep), sketch.entities.get(drop)
    if not isinstance(a, Point) or not isinstance(b, Point) or keep == drop:
        return "Pick two different points to merge."
    for e in sketch.entities.values():
        if isinstance(e, Point):
            continue
        used = entity_points(e)
        if keep in used and drop in used:
            return "Both points belong to the same curve. Pick points of different curves."
    return None


def merge_points(sketch: Sketch, keep: str, drop: str) -> list[str]:
    """Merge point ``drop`` into ``keep``. Returns the removed item ids (the point,
    plus ``r<n>`` and dimension ids). Raises ValueError with what to do."""
    problem = merge_problem(sketch, keep, drop)
    if problem is not None:
        raise ValueError(problem)

    def twin(pid: str) -> str:
        return keep if pid == drop else pid

    point_b = sketch.entities[drop]
    assert isinstance(point_b, Point)
    if point_b.construction is False:
        point_a = sketch.entities[keep]
        assert isinstance(point_a, Point)
        point_a.construction = False  # a real point stays real
    for eid, e in list(sketch.entities.items()):
        if not isinstance(e, Point) and drop in entity_points(e):
            sketch.entities[eid] = remap(e, eid, twin)
    del sketch.entities[drop]
    removed = [drop]
    kept_relations = []
    for index, rel in enumerate(sketch.relations):
        ids = [twin(i) for i in rel.entities]
        if len(ids) > 1 and len(set(ids)) == 1:
            removed.append(f"r{index}")
            continue
        rel.entities = ids
        kept_relations.append(rel)
    sketch.relations = kept_relations
    kept_dims = []
    for dim in sketch.dimensions:
        ids = [twin(i) for i in dim.entities]
        if len(ids) > 1 and len(set(ids)) == 1:
            removed.append(dim.id)
            continue
        dim.entities = ids
        dim.measure_to = {twin(k): v for k, v in dim.measure_to.items()}
        kept_dims.append(dim)
    sketch.dimensions = kept_dims
    return removed
