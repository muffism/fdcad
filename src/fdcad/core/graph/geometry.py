"""Kernel helpers for the curve, solid and pattern nodes.

Every function raises NodeError with a plain message when the kernel fails.
Point sets move between the kernel and numpy as whole arrays (CLAUDE.md 5A).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_CompCurve
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_RightCorner,
    BRepBuilderAPI_Transform,
)
from OCP.BRepGProp import BRepGProp
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset, BRepOffsetAPI_MakePipeShell
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakePrism,
    BRepPrimAPI_MakeSphere,
)
from OCP.collections import HArray1_gp_Pnt
from OCP.GC import GC_MakeArcOfCircle
from OCP.GCPnts import GCPnts_UniformAbscissa
from OCP.GeomAbs import GeomAbs_Arc
from OCP.GeomAPI import GeomAPI_Interpolate
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_SOLID, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape, TopoDS_Wire

from fdcad.core.features.solids import FUZZY_TOLERANCE, compound
from fdcad.core.graph.nodes.base import NodeError
from fdcad.core.graph.types import Plane, Vec3, make_plane
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, ShapeList


def pnt(p: Vec3) -> gp_Pnt:
    """A kernel point."""
    return gp_Pnt(p[0], p[1], p[2])


def direction(v: Vec3, what: str) -> gp_Dir:
    """A kernel direction. Raises NodeError for a zero vector."""
    if math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) < 1e-12:
        raise NodeError(f"{what} has zero length. Give it a direction.")
    return gp_Dir(v[0], v[1], v[2])


def ax2(plane: Plane) -> gp_Ax2:
    """Kernel axes of a plane."""
    return gp_Ax2(
        pnt(plane.origin),
        direction(plane.normal, "The plane normal"),
        direction(plane.x_dir, "The plane X direction"),
    )


def _wire_of(edges: Sequence[Any]) -> TopoDS_Wire:
    maker = BRepBuilderAPI_MakeWire()
    for edge in edges:
        maker.Add(edge)
    if not maker.IsDone():
        raise NodeError("The curve pieces do not join end to end. Check the points.")
    return maker.Wire()


def line(a: Vec3, b: Vec3) -> TopoDS_Wire:
    """A straight line from ``a`` to ``b``."""
    if math.dist(a, b) < 1e-9:
        raise NodeError("The line start and end are the same point. Move one of them.")
    return _wire_of([BRepBuilderAPI_MakeEdge(pnt(a), pnt(b)).Edge()])


def polyline(points: Sequence[Vec3], closed: bool) -> TopoDS_Wire:
    """Straight segments through ``points``."""
    pts = _distinct(points)
    if len(pts) < 2:
        raise NodeError("A polyline needs at least 2 different points. Connect more points.")
    maker = BRepBuilderAPI_MakePolygon()
    for p in pts:
        maker.Add(pnt(p))
    if closed and len(pts) >= 3:
        maker.Close()
    if not maker.IsDone():
        raise NodeError("The polyline could not be made. Check the points.")
    return maker.Wire()


def _distinct(points: Sequence[Vec3]) -> list[Vec3]:
    out: list[Vec3] = []
    for p in points:
        if not out or math.dist(out[-1], p) > 1e-9:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) < 1e-9:
        out.pop()
    return out


def circle(plane: Plane, radius: float) -> TopoDS_Wire:
    """A circle in ``plane`` about its origin."""
    if radius <= 0:
        raise NodeError("The circle radius must be more than 0. Enter a larger radius.")
    return _wire_of([BRepBuilderAPI_MakeEdge(gp_Circ(ax2(plane), radius)).Edge()])


def arc(a: Vec3, b: Vec3, c: Vec3) -> TopoDS_Wire:
    """An arc from ``a`` through ``b`` to ``c``."""
    try:
        maker = GC_MakeArcOfCircle(pnt(a), pnt(b), pnt(c))
        if not maker.IsDone():
            raise NodeError("The three arc points lie on a line. Move the middle point.")
        return _wire_of([BRepBuilderAPI_MakeEdge(maker.Value()).Edge()])
    except NodeError:
        raise
    except Exception as exc:
        raise NodeError("The three arc points lie on a line. Move the middle point.") from exc


def interpolate(points: Sequence[Vec3], closed: bool) -> TopoDS_Wire:
    """A smooth curve through ``points``."""
    pts = _distinct(points)
    if len(pts) < 2:
        raise NodeError("A curve needs at least 2 different points. Connect more points.")
    array = HArray1_gp_Pnt(1, len(pts))
    for i, p in enumerate(pts, start=1):
        array.SetValue(i, pnt(p))
    try:
        maker = GeomAPI_Interpolate(array, closed and len(pts) >= 3, 1e-7)
        maker.Perform()
        if not maker.IsDone():
            raise NodeError("No smooth curve fits these points. Remove points that double back.")
        return _wire_of([BRepBuilderAPI_MakeEdge(maker.Curve()).Edge()])
    except NodeError:
        raise
    except Exception as exc:
        raise NodeError(
            "No smooth curve fits these points. Remove points that double back."
        ) from exc


def wire_of(shape: Any, what: str = "Curve") -> TopoDS_Wire:
    """``shape`` as one wire. Raises NodeError."""
    if not isinstance(shape, TopoDS_Shape) or shape.IsNull():
        raise NodeError(f"{what} needs a curve. Connect a curve.")
    if shape.ShapeType() == TopAbs_WIRE:
        return TopoDS.Wire(shape)
    if shape.ShapeType() == TopAbs_EDGE:
        return _wire_of([TopoDS.Edge(shape)])
    wires = []
    explorer = TopExp_Explorer(shape, TopAbs_WIRE)
    while explorer.More():
        wires.append(TopoDS.Wire(explorer.Current()))
        explorer.Next()
    if len(wires) == 1:
        return wires[0]
    if wires:
        # Several curves: join them when they meet end to end, else say so instead of
        # using the first one (audit B item 18, D730).
        from fdcad.core.features.curves import connect, edges_in

        joined = connect([e for w in wires for e in edges_in(w)])
        if len(joined) == 1:
            return TopoDS.Wire(joined[0])
        raise NodeError(
            f"{what} got {len(wires)} separate curves. Connect one curve, or join them "
            "end to end first."
        )
    edges = []
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edges.append(TopoDS.Edge(explorer.Current()))
        explorer.Next()
    if not edges:
        raise NodeError(f"{what} needs a curve. Connect a curve.")
    return _wire_of(edges)


def is_closed(wire: TopoDS_Wire) -> bool:
    """True when the wire ends where it starts."""
    from OCP.BRep import BRep_Tool

    return bool(BRep_Tool.IsClosed_s(wire))


def sample(wire: TopoDS_Wire, count: int) -> np.ndarray:
    """``count`` points evenly spaced by length along ``wire`` (an N by 3 array)."""
    curve = BRepAdaptor_CompCurve(wire)
    closed = is_closed(wire)
    n = count + 1 if closed else count
    if n < 2:
        u = [curve.FirstParameter()]
    else:
        abscissa = GCPnts_UniformAbscissa(curve, n)
        if not abscissa.IsDone():
            raise NodeError("The curve could not be divided. Use fewer points.")
        u = [abscissa.Parameter(i) for i in range(1, abscissa.NbPoints() + 1)]
    if closed:
        u = u[:count]
    pts = [curve.Value(t) for t in u]
    return np.array([[p.X(), p.Y(), p.Z()] for p in pts], dtype=float).reshape(-1, 3)


def tangents(wire: TopoDS_Wire, count: int) -> np.ndarray:
    """Unit tangents at the ``sample`` points."""
    curve = BRepAdaptor_CompCurve(wire)
    closed = is_closed(wire)
    n = count + 1 if closed else count
    abscissa = GCPnts_UniformAbscissa(curve, max(n, 2))
    u = [abscissa.Parameter(i) for i in range(1, abscissa.NbPoints() + 1)][:count]
    out = []
    for t in u:
        p, v = gp_Pnt(), gp_Vec()
        curve.D1(t, p, v)
        m = v.Magnitude()
        out.append([v.X() / m, v.Y() / m, v.Z() / m] if m > 0 else [0.0, 0.0, 0.0])
    return np.array(out, dtype=float).reshape(-1, 3)


def curve_length(wire: TopoDS_Wire) -> float:
    """Length of the wire."""
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(wire, props)
    return float(props.Mass())


def plane_of(wire: TopoDS_Wire) -> Plane:
    """The plane a flat closed curve lies in. Raises NodeError."""
    try:
        face = BRepBuilderAPI_MakeFace(wire, True)
        if not face.IsDone():
            raise NodeError("The curve is not flat. Use a curve that lies in one plane.")
        from OCP.BRep import BRep_Tool
        from OCP.GeomAdaptor import GeomAdaptor_Surface

        surf = GeomAdaptor_Surface(BRep_Tool.Surface_s(face.Face()))
        pl = surf.Plane()
        o, n = pl.Location(), pl.Axis().Direction()
        return make_plane((o.X(), o.Y(), o.Z()), (n.X(), n.Y(), n.Z()))
    except NodeError:
        raise
    except Exception as exc:
        raise NodeError("The curve is not flat. Use a curve that lies in one plane.") from exc


def face_of(wire: TopoDS_Wire) -> TopoDS_Shape:
    """A flat face bounded by a closed curve. Raises NodeError."""
    if not is_closed(wire):
        raise NodeError("The curve is open. Use a closed curve.")
    face = BRepBuilderAPI_MakeFace(wire, True)
    if not face.IsDone():
        raise NodeError("The curve is not flat. Use a curve that lies in one plane.")
    return face.Face()


def offset(wire: TopoDS_Wire, distance: float) -> TopoDS_Wire:
    """A flat curve moved sideways by ``distance`` (outwards for closed curves)."""
    try:
        maker = BRepOffsetAPI_MakeOffset()
        maker.Init(GeomAbs_Arc, not is_closed(wire))
        maker.AddWire(wire)
        maker.Perform(distance)
        if not maker.IsDone():
            raise NodeError("The offset curve could not be made. Use a smaller distance.")
        return wire_of(maker.Shape(), "Offset")
    except NodeError:
        raise
    except Exception as exc:
        raise NodeError("The offset curve could not be made. Use a smaller distance.") from exc


def box(plane: Plane, x: float, y: float, z: float) -> TopoDS_Shape:
    """A box with one corner at the plane origin, sides along the plane axes."""
    if min(x, y, z) <= 0:
        raise NodeError("Box sizes must be more than 0. Enter larger sizes.")
    return BRepPrimAPI_MakeBox(ax2(plane), x, y, z).Shape()


def cylinder(base: Vec3, axis: Vec3, radius: float, height: float) -> TopoDS_Shape:
    """A cylinder standing on ``base`` along ``axis``."""
    if radius <= 0 or height <= 0:
        raise NodeError("Cylinder radius and height must be more than 0. Enter larger values.")
    return BRepPrimAPI_MakeCylinder(
        gp_Ax2(pnt(base), direction(axis, "The axis")), radius, height
    ).Shape()


def sphere(centre: Vec3, radius: float) -> TopoDS_Shape:
    """A sphere."""
    if radius <= 0:
        raise NodeError("The sphere radius must be more than 0. Enter a larger radius.")
    return BRepPrimAPI_MakeSphere(pnt(centre), radius).Shape()


def extrude(wire: TopoDS_Wire, vector: Vec3) -> TopoDS_Shape:
    """A closed flat curve pulled into a solid along ``vector``."""
    if math.sqrt(sum(c * c for c in vector)) < 1e-9:
        raise NodeError("The extrude distance is 0. Enter a distance.")
    face = face_of(wire)
    return BRepPrimAPI_MakePrism(face, gp_Vec(*vector)).Shape()


def pipe(wire: TopoDS_Wire, radius: float) -> TopoDS_Shape:
    """A round tube of ``radius`` along a curve."""
    if radius <= 0:
        raise NodeError("The pipe radius must be more than 0. Enter a larger radius.")
    curve = BRepAdaptor_CompCurve(wire)
    p, t = gp_Pnt(), gp_Vec()
    curve.D1(curve.FirstParameter(), p, t)
    section = _wire_of([BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(p, gp_Dir(t)), radius)).Edge()])
    maker = BRepOffsetAPI_MakePipeShell(wire)
    maker.SetMode(False)
    maker.SetTransitionMode(BRepBuilderAPI_RightCorner)
    maker.Add(section, False, False)
    try:
        maker.Build()
        if maker.IsDone():
            maker.MakeSolid()
    except Exception as exc:
        raise NodeError("The pipe could not follow the curve. Use a smaller radius.") from exc
    if not maker.IsDone():
        raise NodeError("The pipe could not follow the curve. Use a smaller radius.")
    return maker.Shape()


def solids_of(shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    """The solids in a shape."""
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def shape_of(value: Any, what: str) -> TopoDS_Shape:
    """``value`` as a shape. Raises NodeError."""
    if isinstance(value, TopoDS_Shape) and not value.IsNull():
        return value
    raise NodeError(f"{what} needs a body. Connect a body.")


def boolean(
    operation: str,
    arguments: Sequence[TopoDS_Shape],
    tools: Sequence[TopoDS_Shape],
    unify: bool = True,
) -> TopoDS_Shape:
    """One boolean of many shapes: ``fuse``, ``cut`` or ``common`` (one kernel call)."""
    op = {"fuse": BRepAlgoAPI_Fuse, "cut": BRepAlgoAPI_Cut, "common": BRepAlgoAPI_Common}[
        operation
    ]()
    args, tl = ShapeList(), ShapeList()
    for s in arguments:
        args.Append(s)
    for s in tools:
        tl.Append(s)
    op.SetArguments(args)
    op.SetTools(tl)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.SetRunParallel(True)
    try:
        op.Build()
    except Exception as exc:
        raise NodeError("The boolean failed in the kernel. Move the bodies slightly.") from exc
    if not op.IsDone():
        raise NodeError("The boolean failed in the kernel. Move the bodies slightly.")
    shape = op.Shape()
    if shape is None or shape.IsNull():
        raise NodeError("The boolean gave nothing. Check that the bodies overlap.")
    if operation == "fuse" and unify:
        from fdcad.core.unify import unify_faces

        shape = unify_faces(shape)[0]
    return shape


def union(shapes: Sequence[TopoDS_Shape], unify: bool = True) -> TopoDS_Shape:
    """All shapes fused into one, in one kernel call. ``unify`` merges faces that
    lie on the same surface afterwards."""
    if not shapes:
        raise NodeError("Union needs at least one body. Connect bodies.")
    if len(shapes) == 1:
        return shapes[0]
    return boolean("fuse", shapes[:1], shapes[1:], unify)


def transformed(shape: TopoDS_Shape, trsf: gp_Trsf) -> TopoDS_Shape:
    """A moved, turned, scaled or mirrored copy."""
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def translation(v: Vec3) -> gp_Trsf:
    """A move by ``v``."""
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*v))
    return t


def rotation(origin: Vec3, axis: Vec3, angle: float) -> gp_Trsf:
    """A turn by ``angle`` radians about the axis through ``origin``."""
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(pnt(origin), direction(axis, "The axis")), angle)
    return t


def scaling(centre: Vec3, factor: float) -> gp_Trsf:
    """A uniform scale about ``centre``."""
    if abs(factor) < 1e-9:
        raise NodeError("The scale factor is 0. Enter a factor other than 0.")
    t = gp_Trsf()
    t.SetScale(pnt(centre), factor)
    return t


def mirroring(plane: Plane) -> gp_Trsf:
    """A mirror in ``plane``."""
    t = gp_Trsf()
    t.SetMirror(ax2(plane))
    return t


def group(shapes: Sequence[TopoDS_Shape]) -> TopoDS_Shape:
    """Shapes gathered into one compound without joining them."""
    return compound(list(shapes))


def volume(shape: TopoDS_Shape) -> float:
    """Volume of a shape (mm cubed)."""
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def bounds(shape: TopoDS_Shape) -> tuple[Vec3, Vec3]:
    """Lowest and highest corner of the shape's box."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box_ = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box_, False, False)
    lo, hi = box_.CornerMin(), box_.CornerMax()
    return (lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z())


def polygon_of(wire: TopoDS_Wire, plane: Plane, count: int = 256) -> np.ndarray:
    """A closed flat curve as an N by 2 array of plane coordinates."""
    pts = sample(wire, count)
    o = np.array(plane.origin)
    x, y = np.array(plane.x_dir), np.array(plane.y_dir)
    rel = pts - o
    return np.stack([rel @ x, rel @ y], axis=1)


def inside_polygon(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """For each 2D point, True when it lies inside ``polygon`` (even odd rule, numpy)."""
    px, py = points[:, 0][:, None], points[:, 1][:, None]
    ax, ay = polygon[:, 0][None, :], polygon[:, 1][None, :]
    bx, by = np.roll(polygon[:, 0], -1)[None, :], np.roll(polygon[:, 1], -1)[None, :]
    crosses = (ay > py) != (by > py)
    with np.errstate(divide="ignore", invalid="ignore"):
        xs = ax + (py - ay) * (bx - ax) / (by - ay)
    hit = crosses & (px < xs)
    result: np.ndarray = np.count_nonzero(hit, axis=1) % 2 == 1
    return result
