"""Ground flat ends of a swept spring (TR162 item 2, D2408).

A spring swept along a helix gets ``ground_ends``: the solid is cut flat at each end
of the path, square to the spring's axis, through the path's end points, as a spring
whose end coils are ground so it stands square. The axis is the helix's own axis
(the normal of its circle's sketch) when the path is a Helix feature, else the line
from the path's start to its end. No Qt.
"""

from __future__ import annotations

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError
from fdcad.core.naming.names import NamedShape, carry, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut


def _axis(feature: Feature, ctx: BuildContext, start: gp_Pnt, end: gp_Pnt) -> gp_Dir:
    ref = feature.refs.get("path")
    fid = ref.get("feature") if isinstance(ref, dict) else None
    try:
        path_feature = ctx.document.feature(str(fid)) if isinstance(fid, str) else None
    except KeyError:
        path_feature = None
    if path_feature is not None and path_feature.type == "helix":
        from fdcad.core.features.helix import Placement

        normal = Placement(path_feature, ctx).normal
        d = gp_Vec(start, end)
        axis = gp_Vec(*normal)
        if d.Dot(axis) < 0:
            axis.Reverse()
        return gp_Dir(axis)
    if start.Distance(end) < 1e-6:
        raise FeatureError(
            f"{feature.name}: the path ends where it starts, so it has no axis to grind "
            "square to. Turn off Ground Ends, or use a helix for the path."
        )
    return gp_Dir(gp_Vec(start, end))


def ground(feature: Feature, ctx: BuildContext, tool: NamedShape, path: TopoDS_Wire) -> NamedShape:
    """``tool`` cut flat square to the axis at both ends of ``path``."""
    from fdcad.core.features.sweep import _wire_ends

    start, end = _wire_ends(path)
    axis = _axis(feature, ctx, start, end)
    shape = tool.shape
    names = list(tool.faces)
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    back = gp_Dir(-axis.X(), -axis.Y(), -axis.Z())
    for label, point, outward in (("start", start, back), ("end", end, axis)):
        face = BRepBuilderAPI_MakeFace(gp_Pln(point, outward)).Face()
        beyond = gp_Pnt(*(point.Coord(i) + outward.Coord(i) for i in (1, 2, 3)))
        half = BRepPrimAPI_MakeHalfSpace(face, beyond).Solid()
        explorer = TopExp_Explorer(half, TopAbs_FACE)
        if explorer.More():
            names.append((f"{feature.id}/ground/{label}", explorer.Current()))
        cut = BRepAlgoAPI_Cut(shape, half)
        cut.SetToFillHistory(True)
        cut.Build()
        if not cut.IsDone():
            raise FeatureError(
                f"{feature.name}: the ends could not be ground flat. Turn off Ground Ends."
            )
        names = carry(names, cut.History())
        shape = cut.Shape()
    return NamedShape(shape, restrict(names, shape, feature.id))
