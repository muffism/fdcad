"""Find small holes and fill voids, for a simpler body (TR388, D990).

Delete Face fills the faces it is given. These helpers find more of them: every
round hole up to a diameter (a cylinder face whose surface faces its own axis),
and the enclosed voids of a solid (its inner shells), which are dropped so the
solid keeps only its outer skin. Kernel work: run in the rebuild. No Qt.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
from OCP.BRepClass3d import BRepClass3d
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SHELL
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.solids import compound, solids
from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import ShapeMap


def is_hole(face: TopoDS_Face) -> tuple[bool, float]:
    """(True, radius) when ``face`` is a cylinder whose outward side faces its axis."""
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Cylinder:
        return False, 0.0
    cylinder = surface.Cylinder()
    u = (surface.FirstUParameter() + surface.LastUParameter()) / 2
    v = (surface.FirstVParameter() + surface.LastVParameter()) / 2
    props = BRepLProp_SLProps(surface, u, v, 1, 1e-6)
    if not props.IsNormalDefined():
        return False, 0.0
    normal = props.Normal()
    if face.Orientation() == TopAbs_REVERSED:
        normal.Reverse()
    point = props.Value()
    axis = cylinder.Axis()
    loc, d = axis.Location(), axis.Direction()
    # The direction from the point straight to the axis.
    w = (loc.X() - point.X(), loc.Y() - point.Y(), loc.Z() - point.Z())
    along = w[0] * d.X() + w[1] * d.Y() + w[2] * d.Z()
    to_axis = (w[0] - along * d.X(), w[1] - along * d.Y(), w[2] - along * d.Z())
    facing = to_axis[0] * normal.X() + to_axis[1] * normal.Y() + to_axis[2] * normal.Z()
    return facing > 0, float(cylinder.Radius())


def small_holes(body: NamedShape, diameter: float) -> list[tuple[str, TopoDS_Face]]:
    """Named faces of the round holes of ``body`` up to ``diameter`` across."""
    out: list[tuple[str, TopoDS_Face]] = []
    for name, face in body.faces:
        hole, radius = is_hole(face)
        if hole and 2 * radius <= diameter + 1e-9:
            out.append((name, face))
    return out


def without_voids(body: NamedShape) -> tuple[NamedShape, int]:
    """``body`` with the inner shells (voids) of its solids dropped, and how many."""
    kept: list[TopoDS_Shape] = []
    dropped = 0
    for solid in solids(body.shape) or []:
        outer = BRepClass3d.OuterShell_s(TopoDS.Solid(solid))
        shells = ShapeMap()
        TopExp.MapShapes_s(solid, TopAbs_SHELL, shells)
        if shells.Extent() <= 1 or outer.IsNull():
            kept.append(solid)
            continue
        dropped += shells.Extent() - 1
        kept.append(BRepBuilderAPI_MakeSolid(outer).Solid())
    if not dropped:
        return body, 0
    shape = kept[0] if len(kept) == 1 else compound(kept)
    faces = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, faces)
    named = [(n, f) for n, f in body.faces if faces.Contains(f)]
    return NamedShape(shape, named), dropped
