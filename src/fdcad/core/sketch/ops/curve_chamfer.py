"""Sketch chamfers where an arc or a spline meets a line, an arc or a spline
(TUTORIAL_REVIEW_SPEC_2 TR48, D1701). The two-line case stays in ``ops.corner``.

Each distance is the straight distance from the corner to the chamfer's end on that
curve. The curves are cut back there and a line joins the new ends. A construction
point keeps the corner (on each line or arc that met there), and two distance
dimensions run from it to the chamfer's ends.
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Line, Sketch, Spline
from fdcad.core.sketch.ops import spline_corner as sc
from fdcad.core.sketch.ops.corner import CornerError, CornerResult
from fdcad.core.sketch.ops.curve_fillet import (
    _corner_of,
    check_free_corner,
    drop_corner,
    move_curve_end,
)

Vec = tuple[float, float]


def _far_end(sketch: Sketch, c: Line | Arc, corner: str) -> str:
    if isinstance(c, Line):
        return c.p2 if c.p1 == corner else c.p1
    return c.end if c.start == corner else c.start


def _along(sketch: Sketch, c: Line | Arc, corner: str, d: float) -> Vec | None:
    """The point on ``c`` at straight distance ``d`` from its ``corner`` end, or None."""
    x = sketch.xy(corner)
    far = sketch.xy(_far_end(sketch, c, corner))
    if isinstance(c, Line):
        length = math.dist(x, far)
        if d > length + 1e-9:
            return None
        return x[0] + (far[0] - x[0]) * d / length, x[1] + (far[1] - x[1]) * d / length
    o = sketch.xy(c.center)
    r = sketch.radius(c.id)
    if d > 2 * r:
        return None
    turn = 2 * math.asin(min(d / (2 * r), 1.0))
    a0 = math.atan2(x[1] - o[1], x[0] - o[0])
    af = math.atan2(far[1] - o[1], far[0] - o[0])
    # Walk from the corner end into the arc: counter clockwise from its start.
    sign = 1.0 if (corner == c.start) == c.ccw else -1.0
    sweep = ((af - a0) * sign) % (2 * math.pi)
    if turn > sweep + 1e-9:
        return None
    a = a0 + sign * turn
    return o[0] + r * math.cos(a), o[1] + r * math.sin(a)


def chamfer_curves(
    sketch: Sketch, a_id: str, b_id: str, kind: str, d1: float, d2: float
) -> CornerResult:
    """Cut the corner where curve ``a_id`` meets curve ``b_id`` (at least one an arc or
    a spline) with a straight line, ``d1`` from the corner on the first and ``d2`` on
    the second."""
    a, b = sketch.entities.get(a_id), sketch.entities.get(b_id)
    kinds = Line | Arc | Spline
    if not isinstance(a, kinds) or not isinstance(b, kinds) or a_id == b_id:
        raise CornerError("Pick two curves that meet: lines, arcs or splines.")
    if kind != "distance_distance":
        raise CornerError(
            "Angle and distance needs two lines. Use Distance and distance for arcs and splines."
        )
    if d1 <= 1e-9 or d2 <= 1e-9:
        raise CornerError("Type chamfer distances larger than zero.")
    end_a, end_b, x = _corner_of(sketch, a, b)
    check_free_corner(sketch, end_a, end_b)
    cuts: list[tuple[Line | Arc | Spline, str, Vec, float | None]] = []
    for curve, end, d in ((a, end_a, d1), (b, end_b, d2)):
        if isinstance(curve, Spline):
            u = sc.point_at_distance(sketch, curve, sc.end_index(sketch, curve, x), d)
            if u is None:
                raise CornerError(
                    "The chamfer is longer than the curves allow. Use smaller distances."
                )
            cuts.append((curve, end, sc.at(sc.poles(sketch, curve), u)[0], u))
        else:
            q = _along(sketch, curve, end, d)
            if q is None:
                raise CornerError(
                    "The chamfer is longer than the curves allow. Use smaller distances."
                )
            cuts.append((curve, end, q, None))
    new: list[str] = []
    for curve, end, q, u in cuts:
        if isinstance(curve, Spline):
            assert u is not None
            new.append(sc.cut(sketch, curve, u, sc.end_index(sketch, curve, x)))
        else:
            new.append(move_curve_end(sketch, curve, end, q))
    drop_corner(sketch, end_a, end_b)
    result = CornerResult()
    pid = sketch.add_point(x[0], x[1], construction=True)
    for curve in (a, b):
        if not isinstance(curve, Spline):
            sketch.relate("coincident", pid, curve.id)
    result.corner_point = pid
    lid = sketch.new_id()
    sketch.entities[lid] = Line(lid, new[0], new[1])
    for d, p in ((d1, new[0]), (d2, new[1])):
        dim = sketch.dimension("distance", [pid, p], Param(f"{d:.6g}mm", d))
        result.dimensions.append(dim.id)
    result.curve = lid
    return result
