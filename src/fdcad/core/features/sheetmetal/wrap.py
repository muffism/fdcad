"""Wrapping cut outlines from a flat bend strip onto the folded bend (DECISIONS D541).

A point (x, y) on the strip (x along the bend, y across it, 0 to BA) lands at
the angle y / BA x A about the bend axis, x along it. The map is affine in
(angle, axial) space, so the outline is mapped there (circles become exact
ellipses), laid on cylinders around the bend axis and thickened through the sheet.
"""

from __future__ import annotations

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_GTransform,
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepLib import BRepLib
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.Geom import Geom_CylindricalSurface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GeomAPI import GeomAPI
from OCP.gp import gp_Ax3, gp_Dir, gp_GTrsf, gp_Pln, gp_Pnt
from OCP.ShapeFix import ShapeFix_Face
from OCP.TopAbs import TopAbs_REVERSED, TopAbs_SHELL, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face

from fdcad.core.features.base import FeatureError
from fdcad.core.features.sheetmetal.model import Bend, along, bend_centre, box, volume
from fdcad.core.naming.names import NamedShape, centroid, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common

#: How far the wrapped tool reaches past the inner and outer faces of the bend.
_PAST = 0.01


def strip_outlines(cut: NamedShape, bend: Bend, thickness: float) -> list[TopoDS_Face]:
    """The flat faces at z = thickness of a cut on the strip: its outline (D541)."""
    out = []
    for face in faces_of(cut.shape):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        if abs(abs(surface.Plane().Axis().Direction().Z()) - 1) > 1e-9:
            continue
        if abs(centroid(face)[2] - thickness) < 1e-7:
            out.append(face)
    del bend
    return out


def through(cut: NamedShape, thickness: float) -> bool:
    """True when the strip cut goes straight through the sheet."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    area = 0.0
    for face in strip_outlines(cut, None, thickness):  # type: ignore[arg-type]
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        area += props.Mass()
    return abs(area * thickness - volume(cut.shape)) <= 1e-6 * max(1.0, volume(cut.shape))


def _surface(bend: Bend, thickness: float, radius: float) -> Geom_CylindricalSurface:
    e = along(bend.w)
    c = bend_centre(bend, thickness)
    axis = gp_Dir(e[0] * bend.up, e[1] * bend.up, 0.0)
    start = gp_Dir(0.0, 0.0, -1.0 if bend.up > 0 else 1.0)
    return Geom_CylindricalSurface(gp_Ax3(gp_Pnt(*c), axis, start), radius)


def wrapped_cuts(bend: Bend, thickness: float) -> list[NamedShape]:
    """The bend's strip cuts as solids around the folded bend, in the parent's frame."""
    if bend.radius < 4 * _PAST:
        raise FeatureError(
            f"{bend.owner}: cuts across a bend need an inside radius of at least "
            f"{4 * _PAST:g} mm. Increase the bend radius or move the cut off the bend."
        )
    inner = bend.radius - _PAST
    surfaces = (
        _surface(bend, thickness, inner),
        _surface(bend, thickness, inner + thickness + 2 * _PAST),
    )
    k = bend.angle / bend.allowance
    gtrsf = gp_GTrsf()
    gtrsf.SetValue(1, 1, 0.0)
    gtrsf.SetValue(1, 2, k)
    gtrsf.SetValue(2, 1, float(bend.up))
    gtrsf.SetValue(2, 2, 0.0)
    plane = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    out: list[NamedShape] = []
    for n, cut in enumerate(bend.cuts):
        for face in strip_outlines(cut, bend, thickness):
            mapped = TopoDS.Face(BRepBuilderAPI_GTransform(face, gtrsf, True).Shape())
            shape = _tool(mapped, surfaces, plane, bend.owner)
            name = f"{bend.bid}/cut{n + 1}"
            out.append(NamedShape(shape, [(name, f) for f in faces_of(shape)]))
    return out


def _tool(
    mapped: TopoDS_Face,
    surfaces: tuple[Geom_CylindricalSurface, Geom_CylindricalSurface],
    plane: gp_Pln,
    owner: str,
) -> object:
    """The solid between the two cylinders over the outline ``mapped`` (angle, axial)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
    from OCP.BRepFill import BRepFill
    from OCP.TopoDS import TopoDS_Shell

    outer = BRepTools.OuterWire_s(mapped)
    wires = []
    explorer = TopExp_Explorer(mapped, TopAbs_WIRE)
    while explorer.More():
        wire = TopoDS.Wire(explorer.Current())
        explorer.Next()
        wires.append((not wire.IsSame(outer), wire))
    wires.sort(key=lambda w: w[0])
    sewing = BRepBuilderAPI_Sewing(1e-6)
    for surface in surfaces:
        maker: BRepBuilderAPI_MakeFace | None = None
        for _inner, wire in wires:
            edges = _on_surface(wire, mapped, surface, plane)
            built = BRepBuilderAPI_MakeWire()
            for edge in edges:
                built.Add(edge)
            if maker is None:
                maker = BRepBuilderAPI_MakeFace(surface, built.Wire(), True)
            else:
                maker.Add(built.Wire())
        if maker is None or not maker.IsDone():
            raise FeatureError(
                f"{owner}: a cut across a bend could not be wrapped. "
                "Move the cut off the bend or make it smaller."
            )
        face = maker.Face()
        BRepLib.BuildCurves3d_s(face)
        fix = ShapeFix_Face(face)
        fix.Perform()
        sewing.Add(fix.Face())
    for _inner, wire in wires:
        low = _on_surface(wire, mapped, surfaces[0], plane)
        high = _on_surface(wire, mapped, surfaces[1], plane)
        for a, b in zip(low, high, strict=True):
            BRepLib.BuildCurves3d_s(a)
            BRepLib.BuildCurves3d_s(b)
            sewing.Add(BRepFill.Face_s(a, b))
    sewing.Perform()
    shell = sewing.SewedShape()
    explorer = TopExp_Explorer(shell, TopAbs_SHELL)
    if not explorer.More():
        raise FeatureError(
            f"{owner}: a cut across a bend could not be wrapped. "
            "Move the cut off the bend or make it smaller."
        )
    solid_maker = BRepBuilderAPI_MakeSolid(TopoDS.Shell(explorer.Current()))
    shape = solid_maker.Solid()
    if volume(shape) < 0:
        shape = TopoDS.Solid(shape.Reversed())
    del TopoDS_Shell
    return shape


def _outward(face: TopoDS_Face, surface: Geom_CylindricalSurface) -> float:
    """+1 when the face's normal points away from the bend axis, else -1."""
    from OCP.BRepGProp import BRepGProp_Face
    from OCP.gp import gp_Vec

    props = BRepGProp_Face(face)
    u0, u1, v0, v1 = props.Bounds()
    u, v = (u0 + u1) / 2, (v0 + v1) / 2
    point, normal = gp_Pnt(), gp_Vec()
    props.Normal(u, v, point, normal)
    axis = surface.Position()
    radial = gp_Vec(axis.Location(), point)
    along_axis = gp_Vec(axis.Direction())
    radial = radial - along_axis * radial.Dot(along_axis)
    return 1.0 if radial.Dot(normal) > 0 else -1.0


def _on_surface(
    wire: object, face: TopoDS_Face, surface: Geom_CylindricalSurface, plane: gp_Pln
) -> list[object]:
    """The edges of ``wire`` (in the (angle, axial) plane) rebuilt on ``surface``, in order."""
    out: list[object] = []
    explorer = BRepTools_WireExplorer(TopoDS.Wire(wire), face)
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        adaptor = BRepAdaptor_Curve(edge)
        first, last = adaptor.FirstParameter(), adaptor.LastParameter()
        curve = BRep_Tool.Curve_s(edge, first, last)
        flat = GeomAPI.To2d_s(curve, plane)
        made = BRepBuilderAPI_MakeEdge(flat, surface, first, last).Edge()
        if edge.Orientation() == TopAbs_REVERSED:
            made = TopoDS.Edge(made.Reversed())
        out.append(made)
    return out


def strip_cut(
    removed: NamedShape, bend: Bend, thickness: float, to_strip: object
) -> NamedShape | None:
    """The part of ``removed`` (world) on the bend's flat strip, in strip coordinates."""
    from fdcad.core.features.solids import transform

    local = transform(removed, to_strip)
    strip = box(bend.bid, (0.0, 0.0, 0.0), (bend.length, bend.allowance, thickness))
    common = BRepAlgoAPI_Common(strip.shape, local.shape)
    if not common.IsDone() or volume(common.Shape()) <= 1e-7:
        return None
    shape = common.Shape()
    return NamedShape(shape, [(f"{bend.bid}/cut", f) for f in faces_of(shape)])
