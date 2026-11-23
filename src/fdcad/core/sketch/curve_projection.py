"""Project curve feature edges onto a sketch plane (IDEAS.md item 2, DECISIONS D517).

Kernel work: run off the UI thread (CLAUDE.md rule 2). Straight edges stay lines,
round edges seen face on stay arcs or circles, edges that project onto a straight
segment become lines and every other edge becomes samples for a spline.
"""

from __future__ import annotations

import math

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_TangentialDeflection
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.Standard import Standard_Failure
from OCP.TopoDS import TopoDS_Edge, TopoDS_Shape

from fdcad.core.sketch.curve_convert import MIN_SIZE, CurvePiece, ProjectedCurve, Vec
from fdcad.core.sketch.links import ModelCircle, ModelLine
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.sketch.projection import _edge, _Frame

#: Most points of one spline copy.
MAX_SPLINE_POINTS = 64
#: How far a sample may sit off the chord for an edge to count as straight (mm).
_STRAIGHT = 1e-6


def _xy(row: np.ndarray) -> Vec:
    return float(row[0]), float(row[1])


def _straight(pts: np.ndarray) -> tuple[Vec, Vec] | None:
    """The two extreme points of samples that lie on one line, else None."""
    a = pts[0]
    far = int(np.argmax(np.hypot(*(pts - a).T)))
    d = pts[far] - a
    length = float(np.hypot(*d))
    if length < MIN_SIZE:
        return None
    u = d / length
    off = np.abs((pts[:, 0] - a[0]) * u[1] - (pts[:, 1] - a[1]) * u[0])
    if float(np.max(off)) > _STRAIGHT * max(1.0, length):
        return None
    along = (pts - a) @ u
    lo, hi = int(np.argmin(along)), int(np.argmax(along))
    if (lo == 0 and hi == len(pts) - 1) or (hi == 0 and lo == len(pts) - 1):
        return _xy(pts[0]), _xy(pts[-1])  # keep the edge's own ends and direction
    return _xy(pts[lo]), _xy(pts[hi])


def _turn(c: Vec, p: Vec, angle: float) -> float:
    """How far the direction from ``c`` to ``p`` is from ``angle``, in radians."""
    return abs(math.remainder(math.atan2(p[1] - c[1], p[0] - c[0]) - angle, math.tau))


def _thin(pts: np.ndarray, most: int) -> np.ndarray:
    """At most ``most`` samples, first and last kept."""
    if len(pts) <= most:
        return pts
    index = np.unique(np.round(np.linspace(0, len(pts) - 1, most)).astype(int))
    out: np.ndarray = pts[index]
    return out


def _sampled(curve: BRepAdaptor_Curve, frame: _Frame, deviation: float) -> np.ndarray:
    """Points along a free form edge, projected: evenly spread in its parameter, as many
    as the kernel needs to keep within ``deviation`` (at least 8, at most 64)."""
    t0, t1 = curve.FirstParameter(), curve.LastParameter()
    count = GCPnts_TangentialDeflection(curve, 0.1, deviation).NbPoints()
    params = np.linspace(t0, t1, max(8, min(MAX_SPLINE_POINTS, count)))
    raw = []
    for t in params:  # at most 64 points per edge (CLAUDE.md 5A: bounded)
        p = curve.Value(float(t))
        raw.append((p.X(), p.Y(), p.Z()))
    uvh = frame.project(np.array(raw))
    out: np.ndarray = uvh[:, :2]
    return out


def _circle_ends(curve: BRepAdaptor_Curve, frame: _Frame, seg: tuple[Vec, Vec]) -> tuple[Vec, Vec]:
    """The exact ends of a round edge seen edge on (samples miss its extremes)."""
    circ = curve.Circle()
    c, r = circ.Location(), circ.Radius()
    xd, yd = circ.XAxis().Direction(), circ.YAxis().Direction()
    x2 = frame.axes[:2] @ np.array([xd.X(), xd.Y(), xd.Z()])
    y2 = frame.axes[:2] @ np.array([yd.X(), yd.Y(), yd.Z()])
    c2 = frame.project(np.array([[c.X(), c.Y(), c.Z()]]))[0, :2]
    d = np.subtract(seg[1], seg[0])
    u = d / float(np.hypot(*d))
    t0, t1 = curve.FirstParameter(), curve.LastParameter()
    peak = math.atan2(float(y2 @ u), float(x2 @ u))
    ts = [t0, t1]
    for k in range(-4, 5):
        t = peak + k * math.pi
        if t0 < t < t1:
            ts.append(t)
    angles = np.array(ts)
    pts = c2 + r * (np.outer(np.cos(angles), x2) + np.outer(np.sin(angles), y2))
    along = pts @ u
    return _xy(pts[int(np.argmin(along))]), _xy(pts[int(np.argmax(along))])


def _piece(edge: TopoDS_Edge, frame: _Frame, deviation: float) -> CurvePiece | None:
    """One edge projected, or None when it projects to a point."""
    target, _centre, poly = _edge(edge, None, frame, deviation)
    curve = BRepAdaptor_Curve(edge)
    kind = curve.GetType()
    if kind not in (GeomAbs_Line, GeomAbs_Circle):
        poly = _sampled(curve, frame, deviation)
    if poly is None or len(poly) < 2:
        return None
    pts = np.asarray(poly, dtype=float)
    if float(np.max(np.ptp(pts, axis=0))) < MIN_SIZE:
        return None
    ends = (_xy(pts[0]), _xy(pts[-1]))
    if isinstance(target, ModelLine):
        return CurvePiece("line", (target.a, target.b))
    if isinstance(target, ModelCircle):
        if target.arc is None:
            return CurvePiece("circle", (), target.centre, target.radius)
        a0, a1 = target.arc
        # The edge may run either way: the arc starts at the end nearer ``a0``.
        near = _turn(target.centre, ends[0], a0) <= _turn(target.centre, ends[1], a0)
        start, end = ends if near else (ends[1], ends[0])
        return CurvePiece("arc", (start, end), target.centre, target.radius, (a0, a1))
    seg = _straight(pts)
    if seg is not None:
        if kind == GeomAbs_Circle:
            seg = _circle_ends(curve, frame, seg)
        return CurvePiece("line", seg)
    return CurvePiece("spline", tuple(_xy(p) for p in _thin(pts, MAX_SPLINE_POINTS)))


def project_curve(
    shape: TopoDS_Shape, plane: SketchPlane, deviation: float = 0.01
) -> tuple[list[CurvePiece], int]:
    """Every edge of ``shape`` projected onto ``plane``, and how many were skipped."""
    from fdcad.core.features.curves import edges_in

    frame = _Frame(plane)
    pieces: list[CurvePiece] = []
    skipped = 0
    for edge in edges_in(shape):
        try:
            piece = _piece(edge, frame, deviation)
        except Standard_Failure:
            piece = None
        if piece is None:
            skipped += 1
        else:
            pieces.append(piece)
    return pieces, skipped


def project_curves(
    sources: list[tuple[str, str, TopoDS_Shape]], plane: SketchPlane
) -> list[ProjectedCurve]:
    """Each ``(feature id, name, curve shape)`` projected onto ``plane``.

    A curve the kernel cannot project is left out, never raised (reference only).
    """
    out: list[ProjectedCurve] = []
    for fid, name, shape in sources:
        try:
            pieces, skipped = project_curve(shape, plane)
        except Exception:  # a broken curve is just not offered
            continue
        out.append(ProjectedCurve(fid, name, pieces, skipped))
    return out
