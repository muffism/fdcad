"""Sketch curves as one connected chain of edges: open profiles and sweep paths.

Closed regions come from ``sketch.profiles``. Thin features with an open
profile and sweep paths need the curves joined end to end instead, open or
closed. Construction curves are left out. Each edge keeps the id of the
sketch entity that made it, for face names (PLAN section 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire
from OCP.TopoDS import TopoDS_Edge, TopoDS_Wire

from fdcad.core.features.base import FeatureError
from fdcad.core.sketch.model import Arc, Circle, Curve, Ellipse, EllipseArc, Line, Sketch, Spline
from fdcad.core.sketch.profiles import ProfileError, SketchPlane, _EdgeMaker

_JOIN_TOL = 1e-6  # mm


@dataclass
class Chain:
    """Curves joined end to end into one wire."""

    wire: TopoDS_Wire
    edges: list[tuple[TopoDS_Edge, str]] = field(default_factory=list)
    closed: bool = False

    def entity_of(self, edge: TopoDS_Edge) -> str | None:
        """Sketch entity id that made ``edge``, or None."""
        for e, eid in self.edges:
            if e.IsSame(edge):
                return eid
        return None


def _key(sketch: Sketch, pid: str) -> tuple[float, float]:
    x, y = sketch.xy(pid)
    return (round(x / _JOIN_TOL) * _JOIN_TOL, round(y / _JOIN_TOL) * _JOIN_TOL)


def _end_ids(curve: Curve) -> tuple[str, str] | None:
    """The point ids at the two ends of an open curve; None for a closed one."""
    if isinstance(curve, Line):
        return curve.p1, curve.p2
    if isinstance(curve, Arc | EllipseArc):
        return curve.start, curve.end
    if isinstance(curve, Spline) and curve.points[0] != curve.points[-1]:
        return curve.points[0], curve.points[-1]
    return None


def _closed(sketch: Sketch, curve: Curve) -> bool:
    if isinstance(curve, Circle | Ellipse):
        return True
    ends = _end_ids(curve)
    return ends is None or _key(sketch, ends[0]) == _key(sketch, ends[1])


def sketch_chain(sketch: Sketch, plane: SketchPlane, owner: str) -> Chain:
    """The sketch's curves as one chain. Raises FeatureError when they branch or split.

    Lines, arcs, partial ellipses and splines join end to end; a circle, a full
    ellipse or a closed spline is a chain on its own (spec 2 section 20 item 2, D706).
    """
    curves = sketch.curves()
    if not curves:
        raise FeatureError(f"{owner}: the sketch has no curves. Draw a profile or a path.")
    maker_ = _EdgeMaker(sketch, plane)

    def edge(cid: str) -> TopoDS_Edge:
        try:
            return maker_.edge(cid)
        except ProfileError as exc:
            raise FeatureError(f"{owner}: {exc}") from exc

    closed = [c for c in curves if _closed(sketch, c)]
    if closed:
        if len(curves) != 1:
            raise FeatureError(
                f"{owner}: a closed curve (circle, ellipse or closed spline) cannot join "
                "other curves in one chain. Use open curves, or a sketch with only that curve."
            )
        c = curves[0]
        made = edge(c.id)
        return Chain(BRepBuilderAPI_MakeWire(made).Wire(), [(made, c.id)], closed=True)

    ends = {c.id: _end_ids(c) for c in curves}
    degree: dict[tuple[float, float], int] = {}
    for c in curves:
        pair = ends[c.id]
        assert pair is not None
        for pid in pair:
            key = _key(sketch, pid)
            degree[key] = degree.get(key, 0) + 1
    if any(d > 2 for d in degree.values()):
        raise FeatureError(f"{owner}: the sketch curves branch. Make one chain without branches.")
    loose = [k for k, d in degree.items() if d == 1]
    # Walk the chain from a loose end (or anywhere for a closed chain).
    first = ends[curves[0].id]
    assert first is not None
    start = loose[0] if loose else _key(sketch, first[0])
    order: list[Curve] = []
    used: set[str] = set()
    here = start
    while True:
        nxt = None
        for c in curves:
            pair = ends[c.id]
            if c.id in used or pair is None:
                continue
            a, b = _key(sketch, pair[0]), _key(sketch, pair[1])
            if a == here:
                nxt, here = c, b
                break
            if b == here:
                nxt, here = c, a
                break
        if nxt is None:
            break
        used.add(nxt.id)
        order.append(nxt)
    if len(order) != len(curves):
        raise FeatureError(
            f"{owner}: the sketch curves are not joined into one chain. "
            "Join the ends or delete the extra curves."
        )
    edges: list[tuple[TopoDS_Edge, str]] = []
    maker = BRepBuilderAPI_MakeWire()
    for c in order:
        made = edge(c.id)
        maker.Add(made)
        edges.append((made, c.id))
    if not maker.IsDone():
        raise FeatureError(
            f"{owner}: the sketch curves could not be joined into one chain. "
            "Edit the sketch so the curves meet end to end."
        )
    return Chain(maker.Wire(), edges, closed=not loose)
