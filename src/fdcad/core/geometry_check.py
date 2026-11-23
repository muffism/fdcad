"""Geometry check tool (PLAN section 5A item 10, DECISIONS D356).

Finds invalid faces, sliver faces, tiny edges and gaps on any body, including
imported ones. With ``Limits`` (TR87, TR262, D1416) also faces bending tighter
than a typed radius, knife edges, edges a little short of smooth, duplicate faces
and inexact edges. It only reports: nothing is repaired (CLAUDE.md rule 12).
The loops run over faces and edges (topology), never over mesh triangles.
"""

from __future__ import annotations

from dataclasses import dataclass

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.features.solids import solids
from fdcad.core.occ import ShapeListMap

#: Default limits in mm.
SLIVER_WIDTH = 0.01
TINY_EDGE = 0.01
GAP_TOLERANCE = 0.01
#: At most this many problems are listed, so a badly broken import stays readable.
MAX_ISSUES = 200

KINDS = (
    "invalid",
    "gap",
    "sliver",
    "duplicate",
    "tiny_edge",
    "knife",
    "not_smooth",
    "not_square",
    "inexact",
    "tight_curve",
)
#: Default angle limits (TR87, D1416): a knife edge's faces meet at less than 5 degrees;
#: faces that meet within 2 degrees of smooth "should" be smooth.
KNIFE_ANGLE = 0.0872664626
NEAR_SMOOTH = 0.0349065850
#: Two flat faces meeting within 1 degree of square "should" be square (TR262, D2303).
NEAR_SQUARE = 0.0174532925
#: An edge whose curve and face curves differ by more than this is inexact (mm).
INEXACT = 1e-4


@dataclass(frozen=True)
class Limits:
    """Optional checks (TR87, TR262; D1416). None turns a check off."""

    curvature: float | None = None  # mm: faces bending tighter than this
    knife: float | None = KNIFE_ANGLE  # radians
    near_smooth: float | None = NEAR_SMOOTH  # radians
    near_square: float | None = NEAR_SQUARE  # radians (TR262, D2303)
    duplicates: bool = True
    inexact: bool = True


@dataclass(frozen=True)
class GeometryIssue:
    """One problem: its kind, the face or edge, the body number (from 1) and a message."""

    kind: str
    shape: TopoDS_Shape
    body: int
    message: str
    #: The fix of a nearly smooth or nearly square edge between two flat faces
    #: (TR262, D2303): the face to turn about the edge and the angle, signed about the
    #: edge's curve direction (as Move Face's Rotate about a straight edge reads it).
    turn: tuple[TopoDS_Shape, float] | None = None


def _items(shape: TopoDS_Shape, kind: object) -> list[TopoDS_Shape]:
    out = []
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def _unique(shapes: list[TopoDS_Shape]) -> list[TopoDS_Shape]:
    out: list[TopoDS_Shape] = []
    for shape in shapes:
        if not any(shape.IsSame(o) for o in out):
            out.append(shape)
    return out


def _area_and_perimeter(face: TopoDS_Shape) -> tuple[float, float]:
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    line = GProp_GProps()
    BRepGProp.LinearProperties_s(face, line)
    return float(props.Mass()), float(line.Mass())


def _edge_length(edge: TopoDS_Shape) -> float:
    return float(GCPnts_AbscissaPoint.Length_s(BRepAdaptor_Curve(TopoDS.Edge(edge))))


def _check_body(
    body: TopoDS_Shape,
    number: int,
    sliver: float,
    tiny: float,
    gap: float,
    limits: Limits | None = None,
) -> list[GeometryIssue]:
    issues: list[GeometryIssue] = []
    name = f"Body {number}"
    faces = _unique(_items(body, TopAbs_FACE))
    for k, face in enumerate(faces, start=1):
        if not BRepCheck_Analyzer(face).IsValid():
            issues.append(
                GeometryIssue(
                    "invalid",
                    face,
                    number,
                    f"{name}, face {k} is invalid: its outline or surface is broken. "
                    "Rebuild the feature that made it, or heal the imported file.",
                )
            )
            continue
        area, perimeter = _area_and_perimeter(face)
        width = 2 * area / perimeter if perimeter > 0 else 0.0
        if width < sliver:
            issues.append(
                GeometryIssue(
                    "sliver",
                    face,
                    number,
                    f"{name}, face {k} is a sliver about {width:.3g} mm wide. "
                    "Check the dimensions that make two faces almost meet.",
                )
            )
    if limits is not None:
        issues += _face_extras(body, name, number, faces, limits)
    edges = _unique(_items(body, TopAbs_EDGE))
    owners = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, owners)
    for k, edge in enumerate(edges, start=1):
        e = TopoDS.Edge(edge)
        if BRep_Tool.Degenerated_s(e):
            continue
        length = _edge_length(edge)
        if length < tiny:
            issues.append(
                GeometryIssue(
                    "tiny_edge",
                    edge,
                    number,
                    f"{name}, edge {k} is only {length:.3g} mm long. "
                    "Tiny edges often make fillets and shells fail. "
                    "Remove the edge or heal the body.",
                )
            )
        tolerance = BRep_Tool.Tolerance_s(e)
        if tolerance > gap:
            issues.append(
                GeometryIssue(
                    "gap",
                    edge,
                    number,
                    f"{name}, edge {k} closes a gap of up to {tolerance:.3g} mm between its "
                    "faces. Heal the imported file or rebuild the feature.",
                )
            )
        elif owners.Contains(edge) and owners.FindFromKey(edge).Size() < 2:
            issues.append(
                GeometryIssue(
                    "gap",
                    edge,
                    number,
                    f"{name}, edge {k} is an open edge: only one face meets it, so the body "
                    "has a hole. Heal the imported file or rebuild the feature.",
                )
            )
        if limits is not None and owners.Contains(edge) and owners.FindFromKey(edge).Size() == 2:
            issues += _edge_extras(body, e, k, name, number, limits, tolerance <= gap)
    return issues


def _face_extras(
    body: TopoDS_Shape, name: str, number: int, faces: list[TopoDS_Shape], limits: Limits
) -> list[GeometryIssue]:
    """Tight bends and duplicate faces (TR87 item 1, TR262 item 3)."""
    from fdcad.core.features.shell import smallest_radius
    from fdcad.core.naming.resolve import _matches, face_snapshot

    out: list[GeometryIssue] = []
    snapshots = [face_snapshot(TopoDS.Face(f)) for f in faces] if limits.duplicates else []
    for k, face in enumerate(faces, start=1):
        f = TopoDS.Face(face)
        if limits.curvature is not None:
            radii = [r for r in (smallest_radius(f, False), smallest_radius(f, True)) if r]
            if radii and min(radii) < limits.curvature:
                out.append(
                    GeometryIssue(
                        "tight_curve",
                        face,
                        number,
                        f"{name}, face {k} bends with a radius of {min(radii):.3g} mm, under the "
                        f"{limits.curvature:.3g} mm limit. Use a larger radius there, or check "
                        "the limit.",
                    )
                )
        if limits.duplicates:
            for j in range(k, len(faces)):
                if _matches(snapshots[k - 1], snapshots[j]):
                    out.append(
                        GeometryIssue(
                            "duplicate",
                            face,
                            number,
                            f"{name}, faces {k} and {j + 1} lie on top of each other. Delete one "
                            "of them, or rebuild the feature that made both.",
                        )
                    )
                    break
    return out


def _edge_extras(
    body: TopoDS_Shape,
    edge: TopoDS_Shape,
    k: int,
    name: str,
    number: int,
    limits: Limits,
    no_gap: bool,
) -> list[GeometryIssue]:
    """Knife edges, nearly smooth edges and inexact edges (TR87 item 1, TR262 item 3)."""
    import math

    from fdcad.core.features.fillet_profile import edge_angle
    from fdcad.core.naming.names import NamedShape

    out: list[GeometryIssue] = []
    e = TopoDS.Edge(edge)
    angle = edge_angle(NamedShape(body, []), e)
    if angle is not None:
        if limits.knife is not None and angle < limits.knife:
            out.append(
                GeometryIssue(
                    "knife",
                    edge,
                    number,
                    f"{name}, edge {k} is a knife edge: its faces meet at "
                    f"{math.degrees(angle):.3g} degrees. Make the part thicker there, or round it.",
                )
            )
        off = math.pi - angle
        if limits.near_smooth is not None and 1e-6 < off < limits.near_smooth:
            out.append(
                GeometryIssue(
                    "not_smooth",
                    edge,
                    number,
                    f"{name}, edge {k} is {math.degrees(off):.3g} degrees short of smooth. "
                    "Make its faces meet smoothly, or make the corner clearly sharp.",
                    turn_fix(body, e, smooth=True),
                )
            )
        skew = abs(angle - math.pi / 2)
        if limits.near_square is not None and 1e-6 < skew < limits.near_square:
            turn = turn_fix(body, e, smooth=False)
            if turn is not None:  # flat faces only (TR262, D2303)
                out.append(
                    GeometryIssue(
                        "not_square",
                        edge,
                        number,
                        f"{name}, edge {k} is {math.degrees(skew):.3g} degrees off square. "
                        "Use Fix to square it up, or make the angle clearly different.",
                        turn,
                    )
                )
    loose = not BRep_Tool.SameParameter_s(e) or BRep_Tool.Tolerance_s(e) > INEXACT
    if limits.inexact and no_gap and loose:
        out.append(
            GeometryIssue(
                "inexact",
                edge,
                number,
                f"{name}, edge {k} is inexact: its curve and its faces differ by up to "
                f"{BRep_Tool.Tolerance_s(e):.2g} mm. Heal the imported file if fillets "
                "or shells fail near it.",
            )
        )
    return out


def turn_fix(
    body: TopoDS_Shape, edge: TopoDS_Shape, smooth: bool
) -> tuple[TopoDS_Shape, float] | None:
    """The face to turn about ``edge`` and the signed angle that makes the two flat faces
        meeting there exactly smooth (``smooth``) or exactly square, or None when a face is
        curved (TR262, D2303). The face leaning further off the X, Y and Z axes turns
    (the smaller one when they lean alike); the angle is about the edge's curve
        direction (first to last point)."""
    import math

    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Vec

    from fdcad.core.features.modify import edge_faces
    from fdcad.core.plane_normal import plane_normal

    e = TopoDS.Edge(edge)
    faces = edge_faces(body, e)
    if len(faces) != 2:
        return None
    found = [plane_normal(f) for f in faces]
    normals = [n for n in found if n is not None]
    if len(normals) != 2:
        return None
    # The face that leans off the X, Y and Z axes turns (the other is most likely the
    # one drawn square); when both lean the same, the smaller face turns.
    leans = [min(math.acos(min(1.0, abs(c))) for c in n) for n in normals]
    if abs(leans[0] - leans[1]) > 1e-9:
        turn = 0 if leans[0] > leans[1] else 1
    else:
        areas = [_area_and_perimeter(f)[0] for f in faces]
        turn = 0 if areas[0] <= areas[1] else 1
    n1, n2 = gp_Vec(*normals[turn]), gp_Vec(*normals[1 - turn])
    curve = BRepAdaptor_Curve(e)
    a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
    along = gp_Vec(a, b)
    if along.Magnitude() < 1e-9:
        return None
    axis = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(along))
    theta = n1.Angle(n2)
    delta = theta if smooth else abs(theta - math.pi / 2)

    def error(angle: float) -> float:
        moved = n1.Rotated(axis, angle)
        return float(moved.Angle(n2) if smooth else abs(moved.Dot(n2)))

    angle = delta if error(delta) <= error(-delta) else -delta
    return faces[turn], angle


def clip_box(lo: tuple[float, float, float], hi: tuple[float, float, float]) -> list[object]:
    """Six section planes that keep only a box round a finding, padded by half its size
    and at least 2 mm (the tour's clip, TR262, D2303). Each plane cuts away what lies on
    its normal side, so with one chain per plane only the box stays."""
    from fdcad.core.section import CutPlane

    size = max(h - lo_ for lo_, h in zip(lo, hi, strict=True))
    pad = max(2.0, size / 2)
    out: list[object] = []
    for axis in range(3):
        unit = tuple(1.0 if i == axis else 0.0 for i in range(3))
        top = tuple(hi[i] + pad if i == axis else (lo[i] + hi[i]) / 2 for i in range(3))
        low = tuple(lo[i] - pad if i == axis else (lo[i] + hi[i]) / 2 for i in range(3))
        out.append(CutPlane(top, unit))  # type: ignore[arg-type]
        out.append(CutPlane(low, tuple(-c for c in unit)))  # type: ignore[arg-type]
    return out


def check(
    shape: TopoDS_Shape,
    sliver: float = SLIVER_WIDTH,
    tiny: float = TINY_EDGE,
    gap: float = GAP_TOLERANCE,
    limits: Limits | None = None,
) -> tuple[list[GeometryIssue], int]:
    """Every problem of every body of ``shape`` (at most MAX_ISSUES), and the body count.

    Bodies are the solids of the shape; open shells (for example from an
    imported surface model) are checked as bodies too.
    """
    bodies = solids(shape)
    shells = [s for s in _items(shape, TopAbs_SHELL) if not _in_any(s, bodies)]
    every = bodies + shells or ([shape] if _items(shape, TopAbs_FACE) else [])
    issues: list[GeometryIssue] = []
    for number, body in enumerate(every, start=1):
        issues += _check_body(body, number, sliver, tiny, gap, limits)
        if not issues and not BRepCheck_Analyzer(body).IsValid():
            issues.append(
                GeometryIssue(
                    "invalid",
                    body,
                    number,
                    f"Body {number} is invalid as a whole although each face is valid: "
                    "faces may cross each other. Rebuild the feature that made it.",
                )
            )
        if len(issues) >= MAX_ISSUES:
            break
    order = {k: i for i, k in enumerate(KINDS)}
    issues.sort(key=lambda i: (i.body, order[i.kind]))
    return issues[:MAX_ISSUES], len(every)


def _in_any(shell: TopoDS_Shape, bodies: list[TopoDS_Shape]) -> bool:
    return any(any(shell.IsSame(s) for s in _items(b, TopAbs_SHELL)) for b in bodies)


def symmetry(
    shape: TopoDS_Shape, origin: tuple[float, float, float], normal: tuple[float, float, float]
) -> tuple[bool, list[TopoDS_Shape]]:
    """Whether ``shape`` is the same on both sides of a plane, and the faces that differ
    (TR87 item 3, D1416).

    The shape is mirrored; a face differs when its mirror image matches no face of the
    shape. Kernel work: worker only.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf

    from fdcad.core.naming.resolve import _matches, face_snapshot

    trsf = gp_Trsf()
    trsf.SetMirror(gp_Ax2(gp_Pnt(*origin), gp_Dir(*normal)))
    mirrored = BRepBuilderAPI_Transform(shape, trsf, True).Shape()
    faces = _unique(_items(shape, TopAbs_FACE))
    mine = [face_snapshot(TopoDS.Face(f)) for f in faces]
    images = [face_snapshot(TopoDS.Face(f)) for f in _unique(_items(mirrored, TopAbs_FACE))]
    differ = [
        face for face, image in zip(faces, images, strict=True)
        if not any(_matches(image, other) for other in mine)
    ]  # fmt: skip
    return not differ, differ
