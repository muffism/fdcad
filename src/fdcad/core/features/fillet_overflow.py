"""Rounds the kernel cannot build, made by cutting (DECISIONS D1041).

The kernel's fillet fails when a round has to run past the end of its edge into
the faces beyond it. The common case: the top edges of a block are rounded, then
a side edge is given the same radius. The side edge now ends where the top round
starts, and its own round has nowhere to stop.

For a straight outside edge between two flat faces the round is a plain cylinder,
so it can be made here. The cross section between the sharp corner and the arc is
extruded along the edge, carried on past each free end until it leaves the part,
and cut away. The radius and the edge are the ones asked for; only the way the
round ends differs from the kernel's.

An end is free when every other face that meets the edge there faces along the
edge or sideways (a chamfer, a round, a cap): past it there is only the rest of
the corner. An end is closed when a face there faces back along the edge (a wall,
a floor): the part goes on past it, so the cut stops flush, as the kernel's does.

A free end gets a ball corner when the faces past it are rounds of this same
radius: three rounds of one radius on a square corner meet in an eighth of a
ball. The test is on the part, not on how it was made: the two arcs where the
ball would join the rounds past the end must lie on the part's surface. Where
they do not (a chamfer, a flat cap, rounds of another radius) the cylinder runs
straight through, which is what the kernel does at a chamfer.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeSphere
from OCP.GeomAbs import GeomAbs_Sphere
from OCP.gp import gp_Pnt, gp_Vec
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.TopAbs import TopAbs_FACE, TopAbs_IN, TopAbs_ON, TopAbs_REVERSED, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.fillet_profile import Corner, Sizes, corner_of, prism, section
from fdcad.core.features.modify import edge_faces
from fdcad.core.features.solids import breaks_solid, combine, compound, is_valid, volume_of
from fdcad.core.naming.names import NamedFace, NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, ShapeListMap, shape_list

#: A face at the end of an edge counts as facing back along it below this value of
#: the dot product of its normal and the direction out of the edge.
FACING_BACK = -0.05
#: How far past a free end the cut is carried, in steps of the round's size. The
#: first step that leaves the part is used.
REACH_STEPS = (1.5, 3.0, 6.0, 12.0)
#: Thickness of the slice that tests whether the cut has left the part, as a share
#: of the round's size, and the volume below which the slice counts as empty.
SLICE = 0.05
EMPTY = 1e-7
#: How close the ball's joining arcs must lie to the part's surface, in mm, and
#: where along each quarter arc they are tested, in degrees.
ON_SURFACE = 1e-5
ARC_TESTS = (15.0, 45.0, 75.0)


def _normal_at(face: TopoDS_Face, point: gp_Pnt) -> gp_Vec | None:
    """The outward normal of ``face`` at ``point``, or None where it has none."""
    surface = BRep_Tool.Surface_s(face)
    uv = ShapeAnalysis_Surface(surface).ValueOfUV(point, 1e-6)
    adaptor = BRepAdaptor_Surface(face)
    here, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    adaptor.D1(uv.X(), uv.Y(), here, du, dv)
    normal = du.Crossed(dv)
    if normal.Magnitude() < 1e-12:
        return None
    normal.Normalize()
    if face.Orientation() == TopAbs_REVERSED:
        normal.Reverse()
    return normal


def _faces_at(shape: TopoDS_Shape, point: gp_Pnt) -> list[TopoDS_Face]:
    """Every face of ``shape`` with a corner at ``point``."""
    found = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_VERTEX, TopAbs_FACE, found)
    faces: list[TopoDS_Face] = []
    for i in range(1, found.Extent() + 1):
        vertex = TopoDS.Vertex(found.FindKey(i))
        if BRep_Tool.Pnt_s(vertex).Distance(point) > 1e-6:
            continue
        for face in shape_list(found.FindFromIndex(i)):
            if not any(face.IsSame(f) for f in faces):
                faces.append(TopoDS.Face(face))
    return faces


def end_is_free(shape: TopoDS_Shape, edge: TopoDS_Edge, point: gp_Pnt, out: gp_Vec) -> bool:
    """True when nothing at this end of ``edge`` faces back along it (see the module text).

    ``out`` is the unit direction along the edge, out of it, at ``point``.
    """
    sides = edge_faces(shape, edge)
    others = [f for f in _faces_at(shape, point) if not any(f.IsSame(s) for s in sides)]
    if not others:
        return False
    for face in others:
        normal = _normal_at(face, point)
        if normal is None or normal.Dot(out) < FACING_BACK:
            return False
    return True


def _moved(corner: Corner, before: float, after: float) -> Corner:
    """``corner`` made longer by ``before`` at its start and ``after`` at its end."""
    unit = gp_Vec(corner.along.XYZ())
    unit.Normalize()
    start = gp_Pnt(corner.start.XYZ().Subtracted(unit.Scaled(before).XYZ()))
    along = unit.Scaled(corner.along.Magnitude() + before + after)
    return dataclasses.replace(corner, start=start, along=along)


def _slice_is_empty(shape: TopoDS_Shape, corner: Corner, size: Sizes, at: float) -> bool:
    """True when the round's cross section, ``at`` along the edge line from its start
    (negative: before it), holds none of the part."""
    unit = gp_Vec(corner.along.XYZ())
    unit.Normalize()
    start = gp_Pnt(corner.start.XYZ().Added(unit.Scaled(at).XYZ()))
    thin = dataclasses.replace(corner, start=start, along=unit.Scaled(SLICE * size.first))
    tool, _named = prism(thin, size, "")
    common = BRepAlgoAPI_Common(shape, tool)
    if not common.IsDone():
        return False
    return abs(volume_of(common.Shape())) < EMPTY


def reach(shape: TopoDS_Shape, corner: Corner, size: Sizes, at_start: bool) -> float | None:
    """How far past a free end to carry the cut so that it leaves the part, or None
    when it never does within the last of ``REACH_STEPS``."""
    length = corner.along.Magnitude()
    for step in REACH_STEPS:
        far = step * size.first
        place = -far - SLICE * size.first if at_start else length + far
        if _slice_is_empty(shape, corner, size, place):
            return far
    return None


def _at(origin: gp_Pnt, *steps: tuple[gp_Vec, float]) -> gp_Pnt:
    """``origin`` moved by each vector times its length."""
    xyz = origin.XYZ()
    for vector, amount in steps:
        xyz = xyz.Added(vector.Scaled(amount).XYZ())
    return gp_Pnt(xyz)


def ball_fits(
    shape: TopoDS_Shape, corner: Corner, radius: float, point: gp_Pnt, out: gp_Vec
) -> bool:
    """True when an eighth of a ball of ``radius`` closes the round at this free end.

    The ball's centre is on the round's axis at the end of the edge. Its two arcs
    past the end must lie on the part's surface (on rounds of the same radius), and
    its middle must be inside the part (in the crease those rounds leave).
    """
    if abs(corner.u_first.Dot(corner.u_second)) > 1e-6:
        return False  # only a square corner has a ball
    centre = _at(point, (corner.u_first, radius), (corner.u_second, radius))
    for degrees in ARC_TESTS:
        low, high = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
        for side in (corner.u_first, corner.u_second):
            probe = _at(centre, (side, -radius * low), (out, radius * high))
            if BRepClass3d_SolidClassifier(shape, probe, ON_SURFACE).State() != TopAbs_ON:
                return False
    third = radius / math.sqrt(3.0)
    middle = _at(centre, (corner.u_first, -third), (corner.u_second, -third), (out, third))
    state = BRepClass3d_SolidClassifier(shape, middle, ON_SURFACE).State()
    return state in (TopAbs_IN, TopAbs_ON)


def ball_corner(
    corner: Corner, radius: float, point: gp_Pnt, out: gp_Vec, role: str
) -> tuple[TopoDS_Shape, list[NamedFace]] | None:
    """What to cut away past a free end for a ball corner: the cube of the corner
    less the ball. The ball's face is named ``role``."""
    square = BRepBuilderAPI_MakePolygon()
    for a, b in ((0.0, 0.0), (radius, 0.0), (radius, radius), (0.0, radius)):
        square.Add(_at(point, (corner.u_first, a), (corner.u_second, b)))
    square.Close()
    cube = BRepPrimAPI_MakePrism(
        BRepBuilderAPI_MakeFace(square.Wire(), True).Face(), out.Scaled(radius)
    ).Shape()
    centre = _at(point, (corner.u_first, radius), (corner.u_second, radius))
    cut = BRepAlgoAPI_Cut(cube, BRepPrimAPI_MakeSphere(centre, radius).Shape())
    if not cut.IsDone():
        return None
    shape = cut.Shape()
    named: list[NamedFace] = [
        (role, face)
        for face in faces_of(shape)
        if BRepAdaptor_Surface(face).GetType() == GeomAbs_Sphere
    ]
    if not named or abs(volume_of(shape)) < EMPTY:
        return None
    return shape, named


def _on_faces(shape: TopoDS_Shape, corner: Corner, unit: gp_Vec, d1: float, d2: float) -> bool:
    """True when the round stays on the two faces of its edge: the lines where it
    meets them lie on the part's surface, near both ends and in the middle. A radius
    larger than a face is wide fails here, and is reported as before."""
    length = corner.along.Magnitude()
    for share in (0.1, 0.5, 0.9):
        station = _at(corner.start, (unit, share * length))
        for side, distance in ((corner.u_first, d1), (corner.u_second, d2)):
            probe = _at(station, (side, distance))
            if BRepClass3d_SolidClassifier(shape, probe, ON_SURFACE).State() != TopAbs_ON:
                return False
    return True


def cutter(
    body: NamedShape, edge: TopoDS_Edge, radius: float, role: str
) -> tuple[list[TopoDS_Shape], list[NamedFace]] | None:
    """The solids to cut away to round ``edge``, or None when this edge is not one this
    module makes: not straight between two flat faces, not an outside edge, or with a
    free end that the cut cannot leave."""
    corner = corner_of(body, edge)
    if corner is None or not corner.convex or radius <= 0:
        return None
    size = Sizes("radius", "circular", radius, radius, 0.5, False)
    _p0, _p2, d1, d2 = section(corner, size)
    if min(d1, d2) <= 0:
        return None
    unit = gp_Vec(corner.along.XYZ())
    unit.Normalize()
    if not _on_faces(body.shape, corner, unit, d1, d2):
        return None
    end = gp_Pnt(corner.start.XYZ().Added(corner.along.XYZ()))
    extra: list[float] = []
    tools: list[TopoDS_Shape] = []
    names: list[NamedFace] = []
    for point, out, at_start in (
        (corner.start, unit.Reversed(), True),
        (end, unit, False),
    ):
        if not end_is_free(body.shape, edge, point, out):
            extra.append(0.0)
            continue
        if ball_fits(body.shape, corner, radius, point, out):
            which = "start" if at_start else "end"
            ball = ball_corner(corner, radius, point, out, f"{role}/corner_{which}")
            if ball is None:
                return None
            tools.append(ball[0])
            names.extend(ball[1])
            extra.append(0.0)
            continue
        far = reach(body.shape, corner, size, at_start)
        if far is None:
            return None
        extra.append(far)
    shape, named = prism(_moved(corner, extra[0], extra[1]), size, role)
    return [shape, *tools], named + names


def overflow_round(
    fid: str,
    name: str,
    body: NamedShape,
    edges: list[tuple[str, TopoDS_Edge, float]],
    kernel_round: Callable[[list[str]], NamedShape | None],
) -> NamedShape | None:
    """Round ``edges`` (name, edge, radius) when the kernel could not round them all.

    Edges the kernel rounds on their own (``kernel_round`` given one name) are left
    to it, together; the others are cut here. None when any edge is one neither can
    make, or when the result is not a valid solid: the caller then reports the
    failure as before.
    """
    easy = [n for n, _e, _r in edges if kernel_round([n]) is not None]
    hard = [(n, e, r) for n, e, r in edges if n not in easy]
    if not hard:
        return None  # each works alone: they fail only together, which is not this case
    tools: list[TopoDS_Shape] = []
    names: list[NamedFace] = []
    for edge_name, edge, radius in hard:
        made = cutter(body, edge, radius, f"{fid}/fillet/{edge_name}")
        if made is None:
            return None
        tools.extend(made[0])
        names.extend(made[1])
    current = body
    if easy:
        rounded = kernel_round(easy)
        if rounded is None:
            return None
        current = rounded
    try:
        result = combine(fid, name, current, NamedShape(compound(tools), names), "cut", pieces=True)
    except Exception:  # the cut failed: report the round as the kernel's failure
        return None
    if not is_valid(body, result) or breaks_solid(body, result):
        return None
    if volume_of(result.shape) >= volume_of(current.shape) - EMPTY:
        return None  # nothing was removed: the cut missed the part
    return result
