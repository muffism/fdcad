"""Insert Bends (PHASE5_SPEC P5.6, DECISIONS D538): make a thin solid into sheet metal.

Type ``insert_bends``. Params: ``gap`` (bend corners and rips). Refs: ``face`` (a
flat face on the outside of the thin part), ``sheet_metal``.

The thickness is measured from the part and must match the Sheet Metal folder.
The outside faces are found from the picked face; the edges between them become
bends (an edge that would close a loop becomes a rip). The part is then built as
Convert to Sheet Metal (D537), with the same face roles.
"""

from __future__ import annotations

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.sheetmetal.common import value
from fdcad.core.features.sheetmetal.convert_sheet import Solid, _flat, convert, start_check
from fdcad.core.features.sheetmetal.locate import face_normal
from fdcad.core.features.sheetmetal.model import SheetResult
from fdcad.core.features.sheetmetal.params import sheet_defaults
from fdcad.core.features.solids import line_ends
from fdcad.core.naming.names import centroid
from fdcad.core.units import Kind

_TOL = 1e-5


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def measured_thickness(solid: Solid, fixed: int, owner: str) -> float:
    """Distance from the picked face to the parallel face behind it."""
    f0 = solid.faces[fixed]
    n0 = face_normal(f0)
    c0 = centroid(f0)
    best: float | None = None
    for i, face in enumerate(solid.faces):
        if i == fixed or not _flat(face):
            continue
        n = face_normal(face)
        if _dot(n, n0) > -1 + 1e-9:
            continue
        c = centroid(face)
        d = _dot(n0, (c0[0] - c[0], c0[1] - c[1], c0[2] - c[2]))
        if d <= _TOL or (best is not None and d >= best):
            continue
        p = gp_Pnt(c0[0] - n0[0] * d, c0[1] - n0[1] * d, c0[2] - n0[2] * d)
        if BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(p).Vertex(), face).Value() < _TOL:
            best = d
    if best is None:
        raise FeatureError(
            f"{owner}: no face lies behind the picked face. Insert Bends needs a thin part "
            "of even thickness. Pick a face of a thin wall."
        )
    return best


def _on_face(face: TopoDS_Face, p: Vec3) -> bool:
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
    return bool(BRepExtrema_DistShapeShape(vertex, face).Value() < _TOL)


def side_face(face: TopoDS_Face, edge: TopoDS_Edge, inward: Vec3, thickness: float) -> bool:
    """True when ``face`` is exactly one thickness wide going ``inward`` from ``edge``."""
    ends = line_ends(edge)
    if ends is None:
        return False
    mid = tuple((ends[0][i] + ends[1][i]) / 2 for i in range(3))

    def at(d: float) -> Vec3:
        return (mid[0] + inward[0] * d, mid[1] + inward[1] * d, mid[2] + inward[2] * d)

    return _on_face(face, at(thickness / 2)) and not _on_face(face, at(thickness * 1.5))


def outside_bends(solid: Solid, fixed: int, thickness: float, owner: str) -> list[TopoDS_Edge]:
    """Edges between outside faces, in the order found from the picked face (D538)."""
    order = [fixed]
    bends: list[TopoDS_Edge] = []
    k = 0
    while k < len(order):
        here = order[k]
        k += 1
        n_here = face_normal(solid.faces[here])
        explorer = TopExp_Explorer(solid.faces[here], TopAbs_EDGE)
        while explorer.More():
            edge = TopoDS.Edge(explorer.Current())
            explorer.Next()
            sides = solid.sides(edge)
            if len(sides) != 2:
                continue
            other = sides[0] if sides[1] == here else sides[1]
            if other in order:
                continue
            face = solid.faces[other]
            if not _flat(face):
                raise FeatureError(
                    f"{owner}: the part has curved faces. Insert Bends needs sharp edges "
                    "between flat faces. Remove the rounds, or use Convert to Sheet Metal."
                )
            n = face_normal(face)
            inward = (-n_here[0], -n_here[1], -n_here[2])
            if abs(_dot(n, n_here)) < 1e-6 and side_face(face, edge, inward, thickness):
                continue  # a thickness side face
            order.append(other)
            bends.append(edge)
    if not bends:
        raise FeatureError(
            f"{owner}: the picked face has no neighbouring walls to bend. "
            "Pick a face that has walls along its edges."
        )
    return bends


@register
class InsertBends(FeatureType):
    """Turns a thin solid of even thickness into a sheet metal part."""

    type_name = "insert_bends"
    makes_solid = True
    params = (ParamSpec("gap", kind=Kind.LENGTH, optional=True),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Find the outside faces and bends, then build as Convert to Sheet Metal."""
        name = feature.name
        start_check(feature, ctx)
        assert ctx.body is not None
        defaults = sheet_defaults(feature, ctx)
        ref = feature.refs.get("face")
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: pick a flat face on the outside of the part.")
        face, issues = resolve_face(ctx.body, ref, name)
        solid = Solid(ctx.body.shape)
        fixed = solid.index(face)
        thickness = measured_thickness(solid, fixed, name)
        if abs(thickness - defaults.thickness) > 1e-4:
            raise FeatureError(
                f"{name}: the part is {thickness:g} mm thick but the sheet metal parameters "
                f"say {defaults.thickness:g} mm. Set the thickness to {thickness:g} mm."
            )
        bends = outside_bends(solid, fixed, thickness, name)
        gap = value(feature, "gap", 0.0)
        if gap < 0:
            raise FeatureError(f"{name}: the gap cannot be negative. Enter zero or more.")
        model = convert(feature.id, solid, fixed, bends, thickness, defaults.rule, gap, name)
        return SheetResult(body=model.build(feature.id, name), issues=issues, sheet=model)
