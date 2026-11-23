"""Replace Entity (TUTORIAL_REVIEW_SPEC_2 TR104, DECISIONS D846).

The new curve takes the old curve's id, so faces and edges named after the old
one keep their names and the features that use them keep working. Relations
and dimensions of the old curve move to the new one when they still fit it; the
old curve's end and centre points hand theirs to the nearest point of the new
curve. The old curve is deleted, or kept as construction under a new id. What
could not move is returned so the tool can name it. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fdcad.core.sketch.model import Arc, Circle, Point, Sketch, entity_points, remap

#: Dimensions that need a round curve.
_ROUND_DIMS = ("radius", "diameter")
#: Relations that need a straight line.
_LINE_RELATIONS = ("horizontal", "vertical", "parallel", "perpendicular", "collinear")
#: Relations that need a round curve.
_ROUND_RELATIONS = ("concentric", "coradial")


class ReplaceError(ValueError):
    """The entity cannot be replaced; the message says what to do."""


@dataclass
class ReplaceResult:
    """What Replace Entity left behind: the old curve's new id (when kept) and the
    relations and dimensions that could not move."""

    kept_as: str | None = None
    dropped: list[str] = field(default_factory=list)


def _round(entity: object) -> bool:
    return isinstance(entity, Circle | Arc)


def replace_entity(sketch: Sketch, old: str, new: str, keep_old: bool = False) -> ReplaceResult:
    """Replace curve ``old`` by curve ``new`` (see the module)."""
    from fdcad.core.sketch.model import Line

    a, b = sketch.entities.get(old), sketch.entities.get(new)
    if a is None or b is None or isinstance(a, Point) or isinstance(b, Point) or old == new:
        raise ReplaceError("Pick the curve to replace, then the curve that takes its place.")
    result = ReplaceResult()
    # 1. Points of the old curve hand their relations to the nearest point of the new one.
    new_points = entity_points(b)
    moved: dict[str, str] = {}
    for pid in entity_points(a):
        here = sketch.xy(pid)
        best = min(
            new_points,
            key=lambda q: (sketch.xy(q)[0] - here[0]) ** 2 + (sketch.xy(q)[1] - here[1]) ** 2,
        )
        moved[pid] = best
    straight, round_ = isinstance(b, Line), _round(b)
    kept_relations = []
    for index, rel in enumerate(sketch.relations):
        if old not in rel.entities and not set(moved) & set(rel.entities):
            kept_relations.append(rel)
            continue
        fits = not (
            (rel.type in _LINE_RELATIONS and old in rel.entities and not straight)
            or (rel.type in _ROUND_RELATIONS and old in rel.entities and not round_)
        )
        ids = [moved.get(e, e) for e in rel.entities]
        if not fits or (len(ids) > 1 and len(set(ids)) == 1):
            result.dropped.append(f"{rel.type} relation {index + 1}")
            continue
        rel.entities = ids
        kept_relations.append(rel)
    sketch.relations = kept_relations
    kept_dims = []
    for dim in sketch.dimensions:
        if old not in dim.entities and not set(moved) & set(dim.entities):
            kept_dims.append(dim)
            continue
        if dim.type in _ROUND_DIMS and old in dim.entities and not round_:
            result.dropped.append(f"{dim.type} dimension {dim.id}")
            continue
        ids = [moved.get(e, e) for e in dim.entities]
        if len(ids) > 1 and len(set(ids)) == 1:
            result.dropped.append(f"{dim.type} dimension {dim.id}")
            continue
        dim.entities = ids
        dim.measure_to = {moved.get(k, k): v for k, v in dim.measure_to.items()}
        kept_dims.append(dim)
    sketch.dimensions = kept_dims
    # 2. The new curve takes the old id; the old curve goes, or stays as construction.
    del sketch.entities[new]
    old_curve = sketch.entities.pop(old)
    sketch.entities[old] = remap(b, old, lambda p: p)
    for rel in sketch.relations:
        rel.entities = [old if e == new else e for e in rel.entities]
    for dim in sketch.dimensions:
        dim.entities = [old if e == new else e for e in dim.entities]
    if keep_old:
        nid = sketch.new_id()
        copy_ = remap(old_curve, nid, lambda p: p)  # type: ignore[arg-type]
        copy_.construction = True
        sketch.entities[nid] = copy_
        result.kept_as = nid
    else:
        still = {
            p
            for e in sketch.entities.values()
            for p in entity_points(e)
            if not isinstance(e, Point)
        }
        used = {e for r in sketch.relations for e in r.entities} | {
            e for d in sketch.dimensions for e in d.entities
        }
        for pid in entity_points(old_curve):
            if pid not in still and pid not in used and pid in sketch.entities:
                del sketch.entities[pid]
    return result
