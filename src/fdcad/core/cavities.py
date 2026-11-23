"""Enclosed cavities (TR284, DECISIONS D772).

- ``enclosed_voids``: closed voids inside the bodies. A void is a shell of a solid
  other than its outer shell; it has no opening, so in resin and powder printing
  it traps liquid or powder. Each comes with its volume and middle.
- ``drain_hole``: a Hole feature that drains one void, offered as a fix button:
  a small hole from the outer flat face nearest the void, square to that face and
  ending where it meets the void (Up to Next).
- ``cavity_volume``: the volume of the space a cup, bottle or tank holds: what is
  enclosed by the picked faces below an opening plane.

Kernel work, run in a kernel job (CLAUDE.md 5.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from OCP.BRepClass3d import BRepClass3d
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.solids import solids
from fdcad.core.naming.names import NamedShape, faces_of

Vec3 = tuple[float, float, float]
#: Voids smaller than this (mm3) are kernel noise, not cavities.
MIN_VOLUME = 1e-3
#: The drain hole diameter offered, in mm.
DRAIN_DIAMETER = 3.0


@dataclass
class Void:
    """One closed void: which body it is in (0 based), its volume and middle."""

    body: int
    volume: float
    centre: Vec3
    shell: TopoDS_Shape = field(repr=False)


def _shell_props(shell: TopoDS_Shape) -> tuple[float, Vec3]:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid

    solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(shell)).Solid()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, props)
    c = props.CentreOfMass()
    return abs(props.Mass()), (c.X(), c.Y(), c.Z())


def enclosed_voids(shape: TopoDS_Shape) -> list[Void]:
    """Every closed void of every body of ``shape``."""
    out: list[Void] = []
    for index, solid in enumerate(solids(shape)):
        outer = BRepClass3d.OuterShell_s(TopoDS.Solid(solid))
        explorer = TopExp_Explorer(solid, TopAbs_SHELL)
        while explorer.More():
            shell = explorer.Current()
            explorer.Next()
            if shell.IsSame(outer):
                continue
            volume, centre = _shell_props(shell)
            if volume > MIN_VOLUME:
                out.append(Void(index, volume, centre, shell))
    return out


def _nearest_flat_face(body: NamedShape, void: Void) -> tuple[str, TopoDS_Face, Vec3] | None:
    """The named outer flat face of the void's body nearest the void's middle, with the
    point straight across from the middle on it."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.gp import gp_Pnt, gp_Pnt2d
    from OCP.TopAbs import TopAbs_IN

    solid = solids(body.shape)[void.body]
    outer = BRepClass3d.OuterShell_s(TopoDS.Solid(solid))
    best: tuple[float, str, TopoDS_Face, Vec3] | None = None
    centre = gp_Pnt(*void.centre)
    for face in faces_of(outer):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        name = body.primary_name(face)
        if name is None:
            continue
        plane = surface.Plane()
        u, v = (0.0, 0.0)
        from OCP.ElSLib import ElSLib

        u, v = ElSLib.Parameters_s(plane, centre)
        if BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7).State() != TopAbs_IN:
            continue
        foot = ElSLib.Value_s(u, v, plane)
        distance = centre.Distance(foot)
        if best is None or distance < best[0]:
            best = (distance, name, face, (foot.X(), foot.Y(), foot.Z()))
    return None if best is None else (best[1], best[2], best[3])


def drain_hole(doc: Document, body: NamedShape, void: Void) -> Feature | None:
    """A Hole feature, not yet in ``doc``, that drains ``void``; None when no outer flat
    face lies straight across from it (the user then places a hole by hand)."""
    from fdcad.core.features.sketch import face_plane
    from fdcad.core.naming.select import reference_for
    from fdcad.core.sketch.model import Sketch, sketch_to_data

    found = _nearest_flat_face(body, void)
    if found is None:
        return None
    _name, face, foot = found
    plane = face_plane(face)
    ref = reference_for(body, face)
    if plane is None or ref is None:
        return None
    o, x = plane.origin, plane.x_dir
    n = plane.normal
    y = (n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0])
    d = (foot[0] - o[0], foot[1] - o[1], foot[2] - o[2])
    positions = Sketch()
    positions.add_point(
        sum(a * b for a, b in zip(d, x, strict=True)), sum(a * b for a, b in zip(d, y, strict=True))
    )
    from fdcad.core.features.names import default_name

    return Feature(
        doc.new_feature_id(),
        "hole",
        default_name(doc, "hole", "cut"),
        params={
            "hole_type": "simple",
            "end_condition": "up_to_next",
            "diameter": Param(f"{DRAIN_DIAMETER:g}mm", DRAIN_DIAMETER),
        },
        refs={"plane": ref, "face": [ref]},
        data={"positions": sketch_to_data(positions)},
    )


def cavity_volume(
    body: TopoDS_Shape, faces: list[TopoDS_Face], origin: Vec3, normal: Vec3
) -> tuple[float, TopoDS_Shape | None]:
    """The volume the picked faces hold below the opening plane (``normal`` points out
    of the opening), and that space as a solid. (0, None) when they hold nothing."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeHalfSpace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    from fdcad.core.features.booleans import boolean_shape
    from fdcad.core.occ import BRepAlgoAPI_Cut

    box = Bnd_Box()
    for face in faces:
        BRepBndLib.Add_s(face, box)
    if box.IsVoid():
        return 0.0, None
    lo, hi = box.CornerMin(), box.CornerMax()
    x0, y0, z0, x1, y1, z1 = lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()
    pad = 1.0
    room = BRepPrimAPI_MakeBox(
        gp_Pnt(x0 - pad, y0 - pad, z0 - pad), gp_Pnt(x1 + pad, y1 + pad, z1 + pad)
    ).Shape()
    # Keep the side of the opening plane away from ``normal``.
    plane_face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(*origin), gp_Dir(*normal))).Face()
    inside = (origin[0] - normal[0], origin[1] - normal[1], origin[2] - normal[2])
    half = BRepPrimAPI_MakeHalfSpace(plane_face, gp_Pnt(*inside)).Solid()
    below = boolean_shape("common", room, half)
    if below is None:
        return 0.0, None
    space = BRepAlgoAPI_Cut(below, body).Shape()
    held = []
    for piece in solids(space):
        pb = Bnd_Box()
        BRepBndLib.Add_s(piece, pb)
        plo, phi = pb.CornerMin(), pb.CornerMax()
        a0, b0, c0, a1, b1, c1 = plo.X(), plo.Y(), plo.Z(), phi.X(), phi.Y(), phi.Z()
        # A piece that reaches the padded room's sides is outside the cup, not in it.
        if (
            a0 > x0 - pad / 2
            and b0 > y0 - pad / 2
            and c0 > z0 - pad / 2
            and a1 < x1 + pad / 2
            and b1 < y1 + pad / 2
            and c1 < z1 + pad / 2
        ):
            held.append(piece)
    if not held:
        return 0.0, None
    total = 0.0
    for piece in held:
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(piece, props)
        total += abs(props.Mass())
    from fdcad.core.features.solids import compound

    return total, held[0] if len(held) == 1 else compound(held)
