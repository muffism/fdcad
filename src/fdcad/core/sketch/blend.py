"""Blend curve between two sketch curves (TUTORIAL_REVIEW_SPEC_2 TR318, DECISIONS D884).

A spline from the nearest end of one curve to the nearest end of another. It uses
the curves' own end points, so it stays joined, and its handles point along each
curve's direction at that end, so it leaves and arrives tangent. ``weights`` set
how far each handle reaches (1 is a third of the gap). A line end also gets its
handle held on the line, so the blend stays tangent when the line moves. No Qt.
"""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Arc, Line, Sketch, Spline

Vec = tuple[float, float]


class BlendError(ValueError):
    """The picks cannot be blended; the message says what to do."""


def _ends(sketch: Sketch, eid: str) -> list[str]:
    e = sketch.entities[eid]
    if isinstance(e, Line):
        return [e.p1, e.p2]
    if isinstance(e, Arc):
        return [e.start, e.end]
    if isinstance(e, Spline):
        return [e.points[0], e.points[-1]]
    raise BlendError("Blend Curve joins lines, arcs and splines. Pick the end of one of those.")


def outward(sketch: Sketch, eid: str, end: str) -> Vec:
    """Unit direction a curve keeps going in past its end point ``end``."""
    e = sketch.entities[eid]
    p = sketch.xy(end)
    if isinstance(e, Line):
        other = e.p2 if end == e.p1 else e.p1
        q = sketch.xy(other)
        d = (p[0] - q[0], p[1] - q[1])
    elif isinstance(e, Arc):
        c = sketch.xy(e.center)
        r = (p[0] - c[0], p[1] - c[1])
        ccw = (-r[1], r[0])  # the arc runs counter clockwise from start to end
        d = ccw if end == e.end else (-ccw[0], -ccw[1])
    else:
        assert isinstance(e, Spline)
        i = 0 if end == e.points[0] else len(e.points) - 1
        h = sketch.xy(e.handles[i])
        d = (h[0] - p[0], h[1] - p[1]) if i == len(e.points) - 1 else (p[0] - h[0], p[1] - h[1])
    size = math.hypot(*d)
    if size < 1e-12:
        raise BlendError("A picked curve has no length. Pick another curve.")
    return d[0] / size, d[1] / size


def nearest_end(sketch: Sketch, eid: str, at: Vec) -> str:
    """The end point of curve ``eid`` nearest to ``at``."""
    return min(_ends(sketch, eid), key=lambda pid: math.dist(sketch.xy(pid), at))


def add_blend(
    sketch: Sketch,
    first: str,
    second: str,
    at1: Vec,
    at2: Vec,
    weights: tuple[float, float] = (1.0, 1.0),
    construction: bool = False,
) -> str:
    """Add the blend spline between the ends of ``first`` and ``second`` nearest the
    clicks. Returns the spline's id."""
    if first == second:
        raise BlendError("Pick two different curves to blend between.")
    e1, e2 = nearest_end(sketch, first, at1), nearest_end(sketch, second, at2)
    p1, p2 = sketch.xy(e1), sketch.xy(e2)
    gap = math.dist(p1, p2)
    if gap < 1e-9:
        raise BlendError("The two ends already meet. Pick ends with a gap between them.")
    t1, t2 = outward(sketch, first, e1), outward(sketch, second, e2)
    reach1, reach2 = gap / 3 * max(weights[0], 0.01), gap / 3 * max(weights[1], 0.01)
    h1 = sketch.add_point(p1[0] + t1[0] * reach1, p1[1] + t1[1] * reach1, True)
    # The curve arrives travelling into the second curve, against its outward direction.
    h2 = sketch.add_point(p2[0] - t2[0] * reach2, p2[1] - t2[1] * reach2, True)
    sid = sketch.new_id()
    sketch.entities[sid] = Spline(sid, [e1, e2], [h1, h2], construction)
    for curve, handle in ((first, h1), (second, h2)):
        if isinstance(sketch.entities[curve], Line):
            sketch.relate("coincident", handle, curve)  # the handle stays on the line
    return sid
