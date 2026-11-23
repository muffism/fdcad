"""Modify Sketch: move, turn, scale or flip the whole sketch (TUTORIAL_REVIEW_SPEC TR50,
DECISIONS D895).

Acts on every entity of the sketch except what is held to the part: the origin and
copies of part geometry (a ``source``, or a Fixed relation), so links stay true.
Scaling also scales length dimensions (Move Entities' own rules, TR1). Flipping
mirrors about the vertical (``x``), the horizontal (``y``) or both axes through the
base point; arcs swap their ends so they still run counter clockwise. No Qt.
"""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Arc, EllipseArc, Point, Sketch, entity_points
from fdcad.core.sketch.ops.transform import Step, TransformError, move

Vec = tuple[float, float]
FLIPS = ("none", "x", "y", "both")


def free_entities(sketch: Sketch) -> list[str]:
    """The entities Modify Sketch moves: everything not held to the part."""
    held = {e for r in sketch.relations if r.type == "fixed" for e in r.entities}
    out = []
    for eid, e in sketch.entities.items():
        if eid in held or getattr(e, "source", None) is not None:
            continue
        points = [sketch.entities.get(p) for p in entity_points(e)]
        if any(p is not None and (p.id in held or getattr(p, "source", None)) for p in points):
            continue
        out.append(eid)
    return out


def _flip(sketch: Sketch, ids: list[str], base: Vec, flip: str) -> None:
    sx = -1.0 if flip in ("x", "both") else 1.0
    sy = -1.0 if flip in ("y", "both") else 1.0
    points: set[str] = set()
    for eid in ids:
        points.update(entity_points(sketch.entities[eid]))
    for pid in points:
        p = sketch.entities.get(pid)
        if isinstance(p, Point):
            p.x = base[0] + sx * (p.x - base[0])
            p.y = base[1] + sy * (p.y - base[1])
    if sx * sy < 0:  # one mirror: counter clockwise curves now run clockwise
        for eid in ids:
            e = sketch.entities[eid]
            if isinstance(e, (Arc, EllipseArc)):
                e.start, e.end = e.end, e.start


def modify_sketch(
    sketch: Sketch,
    base: Vec = (0.0, 0.0),
    dx: float = 0.0,
    dy: float = 0.0,
    angle: float = 0.0,
    factor: float = 1.0,
    flip: str = "none",
) -> list[str]:
    """Scale, turn and flip about ``base``, then move, in that order. Returns the ids moved.
    Raises TransformError when nothing can move or a value cannot work."""
    if flip not in FLIPS:
        raise TransformError(f"Unknown flip '{flip}'. Choose none, x, y or both.")
    ids = free_entities(sketch)
    if not ids:
        raise TransformError("Everything in this sketch is held to the part. Nothing can move.")
    if abs(factor - 1.0) > 1e-12:
        move(sketch, ids, Step("scale", centre=base, factor=factor))
    if abs(angle) > 1e-12:
        move(sketch, ids, Step("rotate", centre=base, angle=angle))
    if flip != "none":
        _flip(sketch, ids, base, flip)
    if math.hypot(dx, dy) > 1e-12:
        move(sketch, ids, Step("move", dx=dx, dy=dy))
    return ids
