"""Print orientation and the build volume check (PLAN Phase 2, DECISIONS D353).

The print orientation is a face laid flat on the bed (``print_setup.down_face``,
FDEF_SPEC section 2 item 11). It never changes the model: exports and the
build volume check work on a moved copy, and the bed is drawn back in model
coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Quaternion, gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.base import FeatureError
from fdcad.core.features.face_picks import outward_normal
from fdcad.core.features.solids import compound
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.resolve import resolve_face
from fdcad.core.printing.profiles import PrinterProfile

Vec3 = tuple[float, float, float]
UP: Vec3 = (0.0, 0.0, 1.0)


class OrientationError(Exception):
    """The stored print orientation cannot be used. The message is shown to the user."""


def down_face(body: NamedShape | None, print_setup: dict[str, Any]) -> TopoDS_Face | None:
    """The face laid on the bed, or None when the part prints as modelled."""
    ref = print_setup.get("down_face") if isinstance(print_setup, dict) else None
    if not isinstance(ref, dict):
        return None
    try:
        face, _issues = resolve_face(body, ref, "Print orientation")
    except FeatureError as exc:
        raise OrientationError(str(exc)) from exc
    if outward_normal(face) is None:
        raise OrientationError(
            "Print orientation: the face on the bed is no longer flat. Lay another face flat."
        )
    return face


def lay_flat_rotation(face: TopoDS_Face | None) -> gp_Trsf:
    """The turn that puts ``face`` flat on the bed: its outward normal points down."""
    trsf = gp_Trsf()
    if face is None:
        return trsf
    normal = outward_normal(face)
    if normal is None:
        raise OrientationError(
            "Print orientation: the face is not flat. Pick a flat face to lay on the bed."
        )
    turn = gp_Quaternion(gp_Vec(*normal), gp_Vec(0.0, 0.0, -1.0))
    trsf.SetRotation(turn)
    return trsf


def build_direction(face: TopoDS_Face | None) -> Vec3:
    """The direction the print grows in, in model coordinates (away from the bed)."""
    if face is None:
        return UP
    normal = outward_normal(face)
    if normal is None:
        return UP
    return (-normal[0], -normal[1], -normal[2])


def _bounds(shape: TopoDS_Shape) -> tuple[float, float, float, float, float, float]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    if box.IsVoid():
        raise OrientationError("Print orientation: the part has no geometry. Add a feature first.")
    lo, hi = box.CornerMin(), box.CornerMax()
    return lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()


def moved(shape: TopoDS_Shape, trsf: gp_Trsf) -> TopoDS_Shape:
    """A moved copy of ``shape``; the original is untouched."""
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


#: A print scale and turn about the build direction (TR185, D828): (factor, degrees).
Fit = tuple[float, float]


def _fitted(turn: gp_Trsf, fit: Fit | None) -> gp_Trsf:
    """``turn`` followed by a turn about Z and a scale about the origin."""
    if fit is None:
        return turn
    import math

    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    factor, degrees = fit
    spin = gp_Trsf()
    spin.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(degrees))
    grow = gp_Trsf()
    grow.SetScale(gp_Pnt(0, 0, 0), factor)
    return grow.Multiplied(spin).Multiplied(turn)


def placement(
    shape: TopoDS_Shape,
    face: TopoDS_Face | None,
    profile: PrinterProfile,
    fit: Fit | None = None,
) -> gp_Trsf:
    """Model to printer coordinates: lay ``face`` flat, turn and scale by ``fit``, then
    stand the part on the bed (lowest point at Z 0) in the middle of it."""
    turn = _fitted(lay_flat_rotation(face), fit)
    x0, y0, z0, x1, y1, _z1 = _bounds(moved(shape, turn))
    shift = gp_Trsf()
    shift.SetTranslation(
        gp_Vec(profile.bed_x / 2 - (x0 + x1) / 2, profile.bed_y / 2 - (y0 + y1) / 2, -z0)
    )
    return shift.Multiplied(turn)


@dataclass(frozen=True)
class FitResult:
    """The part's size on the bed against the build volume.

    A part with several bodies (the pieces of Split for Print) is checked body by
    body: ``size`` is then the largest body and ``bodies`` and ``too_big`` count
    the bodies (D622).
    """

    size: Vec3
    volume: Vec3
    too_large: tuple[str, ...]
    bodies: int = 1
    too_big: int = 0
    #: Bodies that reach into a no print zone, and bodies taller than the head
    #: clearance (TR413, D992). Both are warnings: the part still fits.
    in_zones: int = 0
    too_tall: int = 0

    @property
    def fits(self) -> bool:
        """True when the part fits inside the build volume."""
        return not self.too_large


def check_fit(
    shape: TopoDS_Shape,
    face: TopoDS_Face | None,
    profile: PrinterProfile,
    fit: Fit | None = None,
) -> FitResult:
    """Lay the part on the bed and compare its size, or each body's, with the build volume."""
    from fdcad.core.features.solids import solids

    turn = _fitted(lay_flat_rotation(face), fit)
    volume = (profile.bed_x, profile.bed_y, profile.height)
    tol = 1e-6
    pieces = solids(shape)
    sizes = []
    for piece in pieces if len(pieces) > 1 else [shape]:
        x0, y0, z0, x1, y1, z1 = _bounds(moved(piece, turn))
        sizes.append((x1 - x0, y1 - y0, z1 - z0))

    def large(size: Vec3) -> tuple[str, ...]:
        return tuple(a for a, s, v in zip("XYZ", size, volume, strict=True) if s > v + tol)

    size = max(sizes, key=lambda s: (len(large(s)), s[0] * s[1] * s[2]))
    too_big = sum(1 for s in sizes if large(s))
    in_zones = 0
    if profile.no_zones:  # TR413: the part sits in the middle of the bed, as drawn
        trsf = placement(shape, face, profile, fit)
        for piece in pieces if len(pieces) > 1 else [shape]:
            x0, y0, _z0, x1, y1, _z1 = _bounds(moved(piece, trsf))
            if any(x0 < z[2] and z[0] < x1 and y0 < z[3] and z[1] < y1 for z in profile.no_zones):
                in_zones += 1
    too_tall = 0
    if profile.head_clearance > 0 and len(sizes) > 1:
        tall = sum(1 for s in sizes if s[2] > profile.head_clearance + tol)
        too_tall = tall if tall > 1 else 0  # one tall part can go last
    return FitResult(size, volume, large(size), len(sizes), too_big, in_zones, too_tall)


def volume_shapes(
    shape: TopoDS_Shape,
    face: TopoDS_Face | None,
    profile: PrinterProfile,
    fit: Fit | None = None,
) -> tuple[TopoDS_Shape, TopoDS_Shape]:
    """The bed (a flat face) and the build volume (its edges) in model coordinates."""
    back = placement(shape, face, profile, fit).Inverted()
    box = BRepPrimAPI_MakeBox(profile.bed_x, profile.bed_y, profile.height).Shape()
    edges = []
    explorer = TopExp_Explorer(box, TopAbs_EDGE)
    while explorer.More():
        edges.append(explorer.Current())
        explorer.Next()
    plane = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    bed = BRepBuilderAPI_MakeFace(plane, 0.0, profile.bed_x, 0.0, profile.bed_y).Face()
    return moved(bed, back), moved(compound(edges), back)


def print_shape(
    shape: TopoDS_Shape,
    face: TopoDS_Face | None,
    profile: PrinterProfile,
    fit: Fit | None = None,
) -> TopoDS_Shape:
    """The shape to export for printing: moved onto the bed when a face is laid flat or a
    print scale is set, else unchanged (the part prints as modelled)."""
    if face is None and fit is None:
        return shape
    return moved(shape, placement(shape, face, profile, fit))


def print_shape_faces(
    shape: TopoDS_Shape,
    face: TopoDS_Face | None,
    profile: PrinterProfile,
    colored: list[tuple[TopoDS_Shape, str]],
    fit: Fit | None = None,
) -> tuple[TopoDS_Shape, list[tuple[TopoDS_Shape, str]]]:
    """``print_shape`` and the coloured faces moved with it, so a 3MF of the laid flat
    part keeps its face colours (spec 2 section 20 item 12, D714)."""
    if face is None and fit is None:
        return shape, list(colored)
    maker = BRepBuilderAPI_Transform(shape, placement(shape, face, profile, fit), True)
    out = []
    for f, color in colored:
        try:
            out.append((maker.ModifiedShape(f), color))
        except Exception:  # a face that is not part of the shape keeps no colour
            continue
    return maker.Shape(), out


def faces_of(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    """Every face of ``shape`` in explorer order."""
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        out.append(TopoDS.Face(explorer.Current()))
        explorer.Next()
    return out


def fit_to_volume(
    shape: TopoDS_Shape, face: TopoDS_Face | None, profile: PrinterProfile, step: float = 5.0
) -> Fit:
    """The turn about the build direction, and the scale (at most 1), that fit the part in
    the build volume (TR185, D828): turning alone when that is enough, else the turn
    that needs the least shrinking. (1, 0) when it fits already."""
    turn = lay_flat_rotation(face)
    volume = (profile.bed_x, profile.bed_y, profile.height)
    best: Fit = (0.0, 0.0)
    angle = 0.0
    while angle < 180.0 - 1e-9:
        x0, y0, z0, x1, y1, z1 = _bounds(moved(shape, _fitted(turn, (1.0, angle))))
        size = (x1 - x0, y1 - y0, z1 - z0)
        factor = min(v / s if s > 1e-9 else float("inf") for v, s in zip(volume, size, strict=True))
        if factor >= 1.0 - 1e-9:
            return (1.0, angle)
        if factor > best[0] + 1e-9:
            best = (factor, angle)
        angle += step
    return (best[0] * (1 - 1e-6), best[1])
