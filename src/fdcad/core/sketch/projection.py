"""Project part edges, vertices and the origin onto a sketch plane (WP14, D250).

Run off the UI thread (CLAUDE.md rule 2): the sketch editor calls
:func:`project_model` once per opened sketch, never per mouse move. Rebuilds call
:func:`find_sources` to check the copies a sketch made from the part.

Edges and vertices are named as ``NamedShape.edge_name`` and ``vertex_name`` do,
but from one ancestor map for the whole part, so naming is linear in the number
of edges. Straight and round edges are projected with whole array numpy maths
(CLAUDE.md 5A item 2); other curves are sampled by the kernel.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable
from typing import TypeVar

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.Standard import Standard_Failure
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_ShapeEnum, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Shape, TopoDS_Vertex

from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import ShapeListMap, ShapeMap, shape_list
from fdcad.core.sketch.links import (
    ModelCircle,
    ModelGeometry,
    ModelLine,
    ModelPoint,
    ModelTarget,
    SourceKey,
)
from fdcad.core.sketch.profiles import SketchPlane

K = TypeVar("K", bound=Hashable)
T = TypeVar("T", ModelPoint, ModelLine, ModelCircle)

#: Most points sampled on one projected edge.
MAX_SAMPLES = 256
_DEGENERATE = 1e-7  # mm: an edge along the sketch normal projects to a point
_PARALLEL = 1e-9


class _Frame:
    """The sketch plane as numpy arrays, for whole array projection."""

    def __init__(self, plane: SketchPlane) -> None:
        ax = plane.ax3()
        o, x, y, n = ax.Location(), ax.XDirection(), ax.YDirection(), ax.Direction()
        self.origin = np.array([o.X(), o.Y(), o.Z()])
        self.axes = np.array([[x.X(), x.Y(), x.Z()], [y.X(), y.Y(), y.Z()], [n.X(), n.Y(), n.Z()]])

    def project(self, points: np.ndarray) -> np.ndarray:
        """(N, 3) model points to (N, 3) sketch u, v and height."""
        result: np.ndarray = (points - self.origin) @ self.axes.T
        return result


Named = tuple[list[tuple[str | None, TopoDS_Edge]], list[tuple[str | None, TopoDS_Vertex]]]


def _names(body: NamedShape) -> Named:
    """Every edge and vertex of the part with its persistent name (FDEF_SPEC 8.3, 8.4)."""
    shape = body.shape
    fmap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, fmap)
    face_names: dict[int, str] = {}
    for name, face in body.faces:
        index = fmap.FindIndex(face)
        if index and index not in face_names:
            face_names[index] = name

    def ancestors(kind: TopAbs_ShapeEnum) -> Iterable[tuple[list[str], TopoDS_Shape]]:
        amap = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(shape, kind, TopAbs_FACE, amap)
        for i in range(1, amap.Extent() + 1):
            names = set()
            for f in shape_list(amap.FindFromIndex(i)):
                n = face_names.get(fmap.FindIndex(f))
                if n is not None:
                    names.add(n)
            yield sorted(names), amap.FindKey(i)

    edges: list[tuple[str | None, TopoDS_Edge]] = []
    for names, sub in ancestors(TopAbs_EDGE):
        if len(names) == 1:
            names = names * 2  # seam edge
        ename = f"edge({'|'.join(names)})" if names else None
        edges.append((ename, TopoDS.Edge(sub)))
    vertices: list[tuple[str | None, TopoDS_Vertex]] = []
    for names, sub in ancestors(TopAbs_VERTEX):
        vname = f"vertex({'|'.join(names)})" if len(names) >= 3 else None
        vertices.append((vname, TopoDS.Vertex(sub)))
    return edges, vertices


def _samples(sweep: float, radius: float, deviation: float) -> int:
    if radius <= deviation:
        return 8
    step = 2.0 * math.acos(max(-1.0, 1.0 - deviation / radius))
    return int(min(MAX_SAMPLES, max(8, math.ceil(abs(sweep) / max(step, 1e-6)) + 1)))


def _edge(
    edge: TopoDS_Edge, key: SourceKey | None, frame: _Frame, deviation: float
) -> tuple[ModelTarget | None, ModelPoint | None, np.ndarray | None]:
    """One edge projected: its snap target (line or circle), its centre, and a polyline."""
    try:
        curve = BRepAdaptor_Curve(edge)
        kind = curve.GetType()
        t0, t1 = curve.FirstParameter(), curve.LastParameter()
        if kind == GeomAbs_Line:
            a, b = curve.Value(t0), curve.Value(t1)
            uvh = frame.project(np.array([[a.X(), a.Y(), a.Z()], [b.X(), b.Y(), b.Z()]]))
            if float(np.hypot(*(uvh[1, :2] - uvh[0, :2]))) < _DEGENERATE:
                return None, None, None
            depth = float(np.min(np.abs(uvh[:, 2])))
            line = ModelLine(_vec(uvh[0]), _vec(uvh[1]), key, depth)
            return line, None, uvh[:, :2]
        if kind == GeomAbs_Circle:
            circ = curve.Circle()
            c, r = circ.Location(), circ.Radius()
            xd, yd, zd = circ.XAxis().Direction(), circ.YAxis().Direction(), circ.Axis().Direction()
            angles = np.linspace(t0, t1, _samples(t1 - t0, r, deviation))
            centre3 = np.array([c.X(), c.Y(), c.Z()])
            pts = (
                centre3
                + r * np.outer(np.cos(angles), [xd.X(), xd.Y(), xd.Z()])
                + r * np.outer(np.sin(angles), [yd.X(), yd.Y(), yd.Z()])
            )
            uvh = frame.project(pts)
            normal = frame.axes[2]
            along = abs(float(np.dot(normal, [zd.X(), zd.Y(), zd.Z()])))
            if along < 1.0 - _PARALLEL:
                return None, None, uvh[:, :2]  # seen at a slant: an ellipse, drawn only
            cuv = frame.project(centre3[None, :])[0]
            depth = abs(float(cuv[2]))
            arc = None
            if t1 - t0 < 2 * math.pi - 1e-9:
                s, e = uvh[0, :2] - cuv[:2], uvh[-1, :2] - cuv[:2]
                a0, a1 = math.atan2(s[1], s[0]), math.atan2(e[1], e[0])
                # The projection may mirror the turn direction: keep arcs counter clockwise.
                mid = uvh[len(uvh) // 2, :2] - cuv[:2]
                cross = s[0] * mid[1] - s[1] * mid[0]
                arc = (a0, a1) if cross >= 0 else (a1, a0)
            centre = _vec(cuv)
            circle = ModelCircle(centre, r, key, depth, arc)
            return circle, ModelPoint(centre, key, depth), uvh[:, :2]
        sampler = GCPnts_QuasiUniformDeflection(curve, deviation)
        if not sampler.IsDone():
            return None, None, None
        n = min(sampler.NbPoints(), MAX_SAMPLES)
        step = max(1, sampler.NbPoints() // n)
        raw = []
        for i in range(1, sampler.NbPoints() + 1, step):
            p = sampler.Value(i)
            raw.append((p.X(), p.Y(), p.Z()))
        return None, None, frame.project(np.array(raw))[:, :2]
    except Standard_Failure:
        return None, None, None


def _vec(row: np.ndarray) -> tuple[float, float]:
    return float(row[0]), float(row[1])


def _key(xy: tuple[float, float]) -> tuple[float, float]:
    return round(xy[0], 6), round(xy[1], 6)


def project_model(
    body: NamedShape | None, plane: SketchPlane, deviation: float = 0.01
) -> ModelGeometry:
    """All part edges, vertices, round edge centres and the origin, seen on ``plane``.

    Items that land on the same spot (a box seen from above shows its top and
    bottom corners together) are kept once: the one nearest the sketch plane.
    """
    frame = _Frame(plane)
    origin = _vec(frame.project(np.zeros((1, 3)))[0])
    geometry = ModelGeometry(origin=origin)
    geometry.points.append(ModelPoint(origin, ("origin", ""), 0.0))
    if body is None:
        return geometry
    edges, vertices = _names(body)
    points: dict[tuple[float, float], ModelPoint] = {}
    lines: dict[tuple[tuple[float, float], ...], ModelLine] = {}
    circles: dict[tuple[float, ...], ModelCircle] = {}

    def keep(store: dict[K, T], k: K, item: T) -> None:
        old = store.get(k)
        if old is None or item.depth < old.depth - 1e-9:
            store[k] = item

    if vertices:
        coords = np.array([_pnt(v) for _, v in vertices])
        uvh = frame.project(coords)
        for (vname, _), row in zip(vertices, uvh, strict=True):
            xy = _vec(row)
            source = ("vertex", vname) if vname is not None else None
            keep(points, _key(xy), ModelPoint(xy, source, abs(float(row[2]))))
    for ename, edge in edges:
        source = ("edge", ename) if ename is not None else None
        target, centre, poly = _edge(edge, source, frame, deviation)
        if poly is not None and len(poly) >= 2:
            geometry.polylines.append([_vec(p) for p in poly])
        if isinstance(target, ModelLine):
            keep(lines, tuple(sorted((_key(target.a), _key(target.b)))), target)
        elif isinstance(target, ModelCircle):
            arc = target.arc or (0.0, 0.0)
            ck = (*_key(target.centre), round(target.radius, 6), round(arc[0], 6), round(arc[1], 6))
            keep(circles, ck, target)
        if centre is not None:
            keep(points, _key(centre.xy), centre)
    geometry.points.extend(p for p in points.values() if _key(p.xy) != _key(origin))
    geometry.lines = list(lines.values())
    geometry.circles = list(circles.values())
    return geometry


def _pnt(vertex: TopoDS_Vertex) -> tuple[float, float, float]:
    p = BRep_Tool.Pnt_s(vertex)
    return p.X(), p.Y(), p.Z()


def find_sources(
    body: NamedShape | None, plane: SketchPlane, keys: Iterable[SourceKey]
) -> dict[SourceKey, ModelTarget | None]:
    """Current projected geometry of each source, or None when it no longer resolves.

    A vertex gives a point, the origin gives a point, a straight edge a line and a
    round edge seen face on a circle (whose centre serves centre copies).
    """
    wanted = set(keys)
    frame = _Frame(plane)
    out: dict[SourceKey, ModelTarget | None] = {k: None for k in wanted}
    if ("origin", "") in wanted:
        out[("origin", "")] = ModelPoint(_vec(frame.project(np.zeros((1, 3)))[0]), ("origin", ""))
    if body is None or not any(k[0] != "origin" for k in wanted):
        return out
    edges, vertices = _names(body)
    for vname, vertex in vertices:
        key = ("vertex", vname or "")
        if vname is not None and key in wanted and out[key] is None:
            row = frame.project(np.array([_pnt(vertex)]))[0]
            out[key] = ModelPoint(_vec(row), key, abs(float(row[2])))
    for ename, edge in edges:
        key = ("edge", ename or "")
        if ename is not None and key in wanted and out[key] is None:
            target, _, _ = _edge(edge, key, frame, 0.01)
            out[key] = target
    return out
