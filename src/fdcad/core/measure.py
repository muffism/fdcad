"""Measure faces, edges and vertices of the part (PHASE2_SPEC P2.12, D252).

Pure kernel maths, no Qt: the Measure box runs :func:`measure` on a worker thread
(CLAUDE.md rule 2). Lengths are millimetres, areas square millimetres, angles
radians; the UI formats them in the user's units. Results are listed as
:class:`Value` rows in a fixed order so the box and the history read the same.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Line
from OCP.GProp import GProp_GProps
from OCP.Standard import Standard_Failure
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.plane_normal import plane_normal

Vec3 = tuple[float, float, float]
#: How two circles or arcs are measured (P2.12 item 2).
ARC_MODES = ("centre", "minimum", "maximum")


@dataclass(frozen=True)
class Value:
    """One result row. ``kind`` is ``length``, ``area``, ``angle``, ``point`` or ``count``."""

    key: str
    kind: str
    value: float | Vec3


@dataclass(frozen=True)
class Frame:
    """Where X, Y and Z are measured from: an origin and unit X, Y and Z axes."""

    origin: Vec3 = (0.0, 0.0, 0.0)
    x: Vec3 = (1.0, 0.0, 0.0)
    y: Vec3 = (0.0, 1.0, 0.0)
    z: Vec3 = (0.0, 0.0, 1.0)

    def local(self, p: Vec3) -> Vec3:
        """``p`` in this frame's coordinates."""
        d = _sub(p, self.origin)
        return _dot(d, self.x), _dot(d, self.y), _dot(d, self.z)

    def along(self, d: Vec3) -> Vec3:
        """A difference vector in this frame's axes."""
        return _dot(d, self.x), _dot(d, self.y), _dot(d, self.z)


@dataclass(frozen=True)
class Options:
    """Measure settings that change the results (P2.12 items 2 and 3)."""

    arc_mode: str = "centre"
    frame: Frame = field(default_factory=Frame)
    #: Projection plane normal (unit), or None for no projection.
    project: Vec3 | None = None
    #: Where a single picked face was clicked, and the part's solid: Measure then adds
    #: the wall thickness there (TR349, D876).
    at: Vec3 | None = None
    solid: TopoDS_Shape | None = field(default=None, compare=False)


@dataclass
class Measurement:
    """What :func:`measure` found. ``error`` is set when the kernel failed."""

    values: list[Value] = field(default_factory=list)
    error: str = ""

    def get(self, key: str) -> float | Vec3 | None:
        """The value of row ``key``, or None."""
        return next((v.value for v in self.values if v.key == key), None)


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _pnt(p: object) -> Vec3:
    return p.X(), p.Y(), p.Z()  # type: ignore[attr-defined]


def _length(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(shape, props)
    return float(props.Mass())


def _area(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, props)
    return float(props.Mass())


def _circle(shape: TopoDS_Shape) -> tuple[Vec3, float, Vec3] | None:
    if shape.ShapeType() != TopAbs_EDGE:
        return None
    curve = BRepAdaptor_Curve(TopoDS.Edge(shape))
    if curve.GetType() != GeomAbs_Circle:
        return None
    c = curve.Circle()
    return _pnt(c.Location()), c.Radius(), _pnt(c.Axis().Direction())


def _direction(shape: TopoDS_Shape) -> tuple[str, Vec3] | None:
    """("line", direction) for a straight edge, ("plane", normal) for a flat face."""
    if shape.ShapeType() == TopAbs_EDGE:
        curve = BRepAdaptor_Curve(TopoDS.Edge(shape))
        if curve.GetType() == GeomAbs_Line:
            return "line", _pnt(curve.Line().Direction())
    if shape.ShapeType() == TopAbs_FACE:
        face = TopoDS.Face(shape)
        normal = plane_normal(face)
        if normal is not None:
            return "plane", normal
    return None


def _single(shape: TopoDS_Shape, opts: Options) -> list[Value]:
    kind = shape.ShapeType()
    out: list[Value] = []
    if kind == TopAbs_VERTEX:
        p = _pnt(BRep_Tool.Pnt_s(TopoDS.Vertex(shape)))
        out.append(Value("point", "point", opts.frame.local(p)))
    elif kind == TopAbs_EDGE:
        out.append(Value("length", "length", _length(shape)))
        circle = _circle(shape)
        if circle is not None:
            centre, r, _ = circle
            out += [
                Value("radius", "length", r),
                Value("diameter", "length", 2 * r),
                Value("centre", "point", opts.frame.local(centre)),
            ]
        if opts.solid is not None:  # TR199 (D996): the angle across the edge along it
            from fdcad.core.edge_deviation import DeviationError, edge_deviation

            try:
                spread = edge_deviation(opts.solid, shape)
            except DeviationError:
                spread = None
            if spread is not None:
                out += [
                    Value("deviation_max", "angle", spread.largest),
                    Value("deviation_min", "angle", spread.smallest),
                    Value("deviation_avg", "angle", spread.average),
                ]
    elif kind == TopAbs_FACE:
        area = _area(shape)
        out.append(Value("area", "area", area))
        perimeter = 0.0
        face = TopoDS.Face(shape)
        exp = TopExp_Explorer(shape, TopAbs_EDGE)
        while exp.More():
            edge = TopoDS.Edge(exp.Current())
            # A seam (both sides on this face, met twice) is not part of the outline.
            if not BRep_Tool.IsClosed_s(edge, face) and not BRep_Tool.Degenerated_s(edge):
                perimeter += _length(edge)
            exp.Next()
        out.append(Value("perimeter", "length", perimeter))
        surface = BRepAdaptor_Surface(TopoDS.Face(shape))
        if surface.GetType() == GeomAbs_Cylinder:
            r = surface.Cylinder().Radius()
            out += [Value("radius", "length", r), Value("diameter", "length", 2 * r)]
        if opts.at is not None and opts.solid is not None:
            found = thickness_at(opts.solid, TopoDS.Face(shape), opts.at)
            if found is not None:
                out.append(Value("thickness", "length", found[0]))
        direction = _direction(shape)
        if opts.project is not None and direction is not None:
            cos = abs(_dot(direction[1], opts.project))
            out.append(Value("projected_area", "area", area * cos))
    return out


def thickness_at(solid: TopoDS_Shape, face: TopoDS_Shape, at: Vec3) -> tuple[float, Vec3] | None:
    """The wall thickness at ``at`` on ``face``: how far a line from that spot along the
    face's inward normal runs through the solid before it leaves (TR349, D876). Returns
    (thickness, the point where it leaves), or None when the line meets nothing."""
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.TopAbs import TopAbs_REVERSED

    f = TopoDS.Face(face)
    surface = BRep_Tool.Surface_s(f)
    project = GeomAPI_ProjectPointOnSurf(gp_Pnt(*at), surface)
    if project.NbPoints() < 1:
        return None
    u, v = project.LowerDistanceParameters()
    props = BRepLProp_SLProps(BRepAdaptor_Surface(f), u, v, 1, 1e-7)
    if not props.IsNormalDefined():
        return None
    n = props.Normal()
    if f.Orientation() != TopAbs_REVERSED:
        n.Reverse()  # inward: against the outward normal
    start = props.Value()
    hits = IntCurvesFace_ShapeIntersector()
    hits.Load(solid, 1e-6)
    hits.Perform(gp_Lin(start, gp_Dir(n.XYZ())), 1e-5, 1e9)
    if not hits.IsDone():
        return None
    best: tuple[float, Vec3] | None = None
    for i in range(1, hits.NbPnt() + 1):
        w = hits.WParameter(i)
        if w > 1e-5 and (best is None or w < best[0]):
            best = (w, _pnt(hits.Pnt(i)))
    return best


def _distance(a: TopoDS_Shape, b: TopoDS_Shape) -> tuple[float, Vec3, Vec3] | None:
    dist = BRepExtrema_DistShapeShape(a, b)
    if not dist.IsDone() or dist.NbSolution() == 0:
        return None
    return dist.Value(), _pnt(dist.PointOnShape1(1)), _pnt(dist.PointOnShape2(1))


def _pair(a: TopoDS_Shape, b: TopoDS_Shape, opts: Options) -> list[Value]:
    out: list[Value] = []
    ca, cb = _circle(a), _circle(b)
    if ca is not None and cb is not None:
        centre = _norm(_sub(ca[0], cb[0]))
        if opts.arc_mode == "maximum":
            span = centre + ca[1] + cb[1]
            out.append(Value("distance_max", "length", span))
        elif opts.arc_mode == "minimum":
            found = _distance(a, b)
            if found is not None:
                out.append(Value("distance_min", "length", found[0]))
        out.append(Value("centre_distance", "length", centre))
        start, end = ca[0], cb[0]
    else:
        found = _distance(a, b)
        if found is None:
            return out
        out.append(Value("distance", "length", found[0]))
        start, end = found[1], found[2]
    delta = _sub(end, start)
    out.append(Value("delta", "point", opts.frame.along(delta)))
    if opts.project is not None:
        normal = _dot(delta, opts.project)
        along = _sub(
            delta, (opts.project[0] * normal, opts.project[1] * normal, opts.project[2] * normal)
        )
        out += [
            Value("projected_distance", "length", _norm(along)),
            Value("normal_distance", "length", abs(normal)),
        ]
    da, db = _direction(a), _direction(b)
    if da is not None and db is not None:
        cos = abs(_dot(da[1], db[1]))
        angle = math.acos(min(1.0, cos))
        if da[0] != db[0]:
            angle = math.pi / 2 - angle  # a line against a plane: angle to the plane
        out.append(Value("angle", "angle", angle))
    return out


def measure(shapes: list[TopoDS_Shape], opts: Options | None = None) -> Measurement:
    """Measure one item (its size) or several (smallest distance, angle, dX dY dZ).

    With three or more items the distance is the smallest between any two. Never
    raises: a kernel failure gives ``error`` (CLAUDE.md rule 7).
    """
    opts = opts or Options()
    result = Measurement()
    try:
        if len(shapes) == 1:
            result.values = _single(shapes[0], opts)
        elif len(shapes) == 2:
            result.values = _pair(shapes[0], shapes[1], opts)
        elif len(shapes) > 2:
            best: tuple[float, Vec3, Vec3] | None = None
            for a, b in itertools.combinations(shapes, 2):
                found = _distance(a, b)
                if found is not None and (best is None or found[0] < best[0]):
                    best = found
            if best is not None:
                result.values = [
                    Value("distance", "length", best[0]),
                    Value("delta", "point", opts.frame.along(_sub(best[2], best[1]))),
                ]
            total = sum(_length(s) for s in shapes if s.ShapeType() == TopAbs_EDGE)
            if total:
                result.values.append(Value("total_length", "length", total))
            area = sum(_area(s) for s in shapes if s.ShapeType() == TopAbs_FACE)
            if area:
                result.values.append(Value("total_area", "area", area))
    except Standard_Failure as exc:
        result.error = (
            f"The measurement failed in the geometry kernel ({type(exc).__name__}). "
            "Pick other items and try again."
        )
    return result


def summary(shapes: list[TopoDS_Shape]) -> Measurement:
    """Common values of a selection for the status bar (P2.12 item 5)."""
    found = measure(shapes)
    keep = {"length", "area", "radius", "distance", "centre_distance", "angle"}
    found.values = [v for v in found.values if v.key in keep]
    return found
