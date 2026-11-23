"""Keep proportions on the first dimension (TR119, D938).

With the preference on, the first length dimension given a value in a sketch of
unsized geometry scales the whole sketch about its origin, so the shape keeps its
proportions instead of one side stretching. No Qt. The caller checkpoints.
"""

from __future__ import annotations

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Circle, Dimension, Point, Sketch
from fdcad.core.sketch.ops.pieces import _origin
from fdcad.core.sketch.ops.transform import LENGTH_DIMENSIONS, _scaled

#: Relations whose value is a length, so it grows with the sketch.
_LENGTH_RELATIONS = ("offset", "length_difference")


def first_dimension(sketch: Sketch, dim: Dimension) -> bool:
    """True when ``dim`` is the only driving dimension, measures a length, and nothing
    else holds the sketch's size: no geometry taken from the model and no Fix other
    than the origin's."""
    if not dim.driving or dim.type not in LENGTH_DIMENSIONS:
        return False
    if any(d.driving and d is not dim for d in sketch.dimensions):
        return False
    if any(getattr(e, "source", None) for e in sketch.entities.values()):
        return False
    return all(
        r.type != "fixed" or all(_origin(sketch, e) for e in r.entities) for r in sketch.relations
    )


def scale_sketch(sketch: Sketch, factor: float, skip: Dimension | None = None) -> None:
    """Scale every point, circle, length relation and dimension about the origin
    (sketch 0, 0). ``skip`` is a dimension the caller sets itself."""
    if factor <= 0:
        raise ValueError("The scale factor must be larger than zero.")
    for ent in sketch.entities.values():
        if isinstance(ent, Point) and not _origin(sketch, ent.id):
            ent.x *= factor
            ent.y *= factor
        elif isinstance(ent, Circle):
            ent.radius *= factor
    for rel in sketch.relations:
        if rel.type in _LENGTH_RELATIONS and rel.value is not None:
            rel.value *= factor
    for dim in sketch.dimensions:
        if dim is skip:
            continue
        if dim.type in LENGTH_DIMENSIONS:
            dim.param = _scaled(dim.param, factor)
        if dim.label is not None:
            dim.label = (dim.label[0] * factor, dim.label[1] * factor)


def set_keeping_proportions(sketch: Sketch, dim: Dimension, param: Param, now: float) -> bool:
    """Give ``dim`` the value ``param`` and, when it is the first dimension
    (:func:`first_dimension`), scale the sketch by new size / ``now`` first.
    Returns True when the sketch was scaled."""
    scaled = False
    if now > 1e-9 and param.value > 0 and first_dimension(sketch, dim):
        scale_sketch(sketch, param.value / now, skip=dim)
        if dim.label is not None:
            f = param.value / now
            dim.label = (dim.label[0] * f, dim.label[1] * f)
        scaled = True
    dim.param = param
    return scaled
