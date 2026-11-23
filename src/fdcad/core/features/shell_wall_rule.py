"""Shell wall rule (TR322, D1803): keep the wall Never Thinner or Never Thicker than
the thickness.

The wall is measured as the distance from a point of the new wall to the nearest
kept face of the part (removed faces left out). The kernel offsets each face
exactly; only the corners differ. Sharp joins reach past the thickness where
offset faces open apart (a corner point lies further than the thickness from the
part), so they keep the wall never thinner. Round joins keep every point at the
thickness, so Never Thicker uses them only. After the build the wall's vertices
and face middles are measured (an approximate check, as the spec asks) and a
warning names the thinnest or thickest point when the rule is not kept.
"""

from __future__ import annotations

from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.base import FeatureError, FeatureState, Issue

WALL_RULES = ("never_thinner", "never_thicker")
#: Share of the thickness a measured wall may differ by before the rule counts as broken.
TOLERANCE = 0.02
#: More sample points than this are not measured (each is a distance query).
MAX_POINTS = 400


def corners_for(owner: str, rule: object, corners: object) -> object:
    """The corner join to use for ``rule``: Never Thicker needs rounded corners."""
    if rule != "never_thicker":
        return corners
    if corners == "sharp":
        raise FeatureError(
            f"{owner}: Never thicker needs rounded corners, since sharp corners reach past "
            "the wall. Choose Rounded or Automatic corners, or choose Never thinner."
        )
    return "rounded"


def _points(faces: list[TopoDS_Face]) -> list[gp_Pnt]:
    """Every vertex and edge middle of ``faces`` (points that are always on a face)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE

    out: list[gp_Pnt] = []
    for face in faces:
        explorer = TopExp_Explorer(face, TopAbs_VERTEX)
        while explorer.More():
            out.append(BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current())))
            explorer.Next()
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            edge = TopoDS.Edge(explorer.Current())
            explorer.Next()
            if BRep_Tool.Degenerated_s(edge):
                continue
            curve = BRepAdaptor_Curve(edge)
            out.append(curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2))
    return out[:MAX_POINTS]


def _on_removed(face: TopoDS_Face, removed: list[TopoDS_Face]) -> bool:
    """True for a rim face: flat and on the plane of a removed face."""
    from OCP.GeomAbs import GeomAbs_Plane

    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Plane:
        return False
    plane = surface.Plane()
    for other in removed:
        o = BRepAdaptor_Surface(other)
        if o.GetType() != GeomAbs_Plane:
            continue
        op = o.Plane()
        if plane.Axis().Direction().IsParallel(op.Axis().Direction(), 1e-6) and (
            op.Distance(plane.Location()) < 1e-6
        ):
            return True
    return False


def _kept(solid: TopoDS_Shape, removed: list[TopoDS_Face]) -> TopoDS_Compound:
    builder, kept = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(kept)
    explorer = TopExp_Explorer(solid, TopAbs_FACE)
    while explorer.More():
        face = explorer.Current()
        if not any(face.IsSame(r) for r in removed):
            builder.Add(kept, face)
        explorer.Next()
    return kept


def wall_range(
    solid: TopoDS_Shape, removed: list[TopoDS_Face], walls: list[TopoDS_Face]
) -> tuple[float, float] | None:
    """The smallest and largest measured wall: each sample point of the new ``walls``
    to the nearest kept face of the part before the shell."""
    kept = _kept(solid, removed)
    found: list[float] = []
    for point in _points([w for w in walls if not _on_removed(w, removed)]):
        dist = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(point).Vertex(), kept)
        if dist.IsDone() and dist.NbSolution() > 0:
            found.append(dist.Value())
    if not found:
        return None
    return min(found), max(found)


def check_rule(
    owner: str,
    rule: object,
    thickness: float,
    solid: TopoDS_Shape,
    removed: list[TopoDS_Face],
    walls: list[TopoDS_Face],
) -> list[Issue]:
    """A warning when the wall breaks ``rule`` by more than the tolerance."""
    if rule not in WALL_RULES or not walls:
        return []
    measured = wall_range(solid, removed, walls)
    if measured is None:
        return []
    low, high = measured
    if rule == "never_thinner" and low < thickness * (1 - TOLERANCE):
        message = (
            f"{owner}: the wall is {low:.3g} mm at its thinnest, under the {thickness:g} mm "
            "it should never go below. Choose Sharp or Automatic corners, or use a thicker wall."
        )
    elif rule == "never_thicker" and high > thickness * (1 + TOLERANCE):
        message = (
            f"{owner}: the wall is {high:.3g} mm at its thickest, over the {thickness:g} mm "
            "it should never go past. Choose Rounded corners, or use a thinner wall."
        )
    else:
        return []
    return [Issue(FeatureState.WARNING, message, code="wall_rule")]
