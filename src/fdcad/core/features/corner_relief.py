"""Corner Relief: let a round cutter reach inside corners (TR244, DECISIONS D785).

Inside corners of a pocket or slot get a relief, so a part milled with a round
tool still takes a square mating part.

Params:

- ``relief_type``: ``dogbone`` (a round cut along the corner's diagonal, into
  both walls), ``t_bone`` (a round cut into one wall only) or ``fillet`` (the
  corner rounded to the tool, which the tool can cut as it is).
- ``tool_diameter``: length, the cutter's diameter. ``clearance``: optional
  length added to the relief radius (default 0).
- ``flip``: optional boolean: a T-bone cuts into the other wall.

Refs: ``edges`` (picked straight inside edges), or ``feature``
(``{"feature": "f7"}``): every straight inside edge where two side faces of that
feature meet, so the upright corners of a cut pocket.

Face roles: ``relief/<k>`` for the round face at edge ``k`` (in pick order).
"""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.GeomAbs import GeomAbs_CurveType
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.face_picks import outward_normal
from fdcad.core.features.modify import require_body, resolve_edges
from fdcad.core.features.solids import check_result, combine, compound
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.occ import point_inside
from fdcad.core.units import Kind

RELIEF_TYPES = ("dogbone", "t_bone", "fillet")
#: How far the inside test steps off the edge, in mm.
_STEP = 0.01


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3, s: float = 1.0) -> Vec3:
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    return (a[0] / n, a[1] / n, a[2] / n)


def _edges_of(face: TopoDS_Face) -> list[TopoDS_Edge]:
    out = []
    ex = TopExp_Explorer(face, TopAbs_EDGE)
    while ex.More():
        out.append(TopoDS.Edge(ex.Current()))
        ex.Next()
    return out


def faces_at(body: NamedShape, edge: TopoDS_Edge) -> list[TopoDS_Face]:
    """The faces of ``body`` that hold ``edge``."""
    return [f for _n, f in body.faces if any(e.IsSame(edge) for e in _edges_of(f))]


def inside_corner(body: NamedShape, edge: TopoDS_Edge) -> tuple[Vec3, Vec3, Vec3, Vec3] | None:
    """(start, end, outward normal of the first face, of the second) for a straight edge
    where two flat faces meet with the material wrapping round it (an inside corner),
    else None. The faces are in name order."""
    curve = BRepAdaptor_Curve(edge)
    if curve.GetType() != GeomAbs_CurveType.GeomAbs_Line:
        return None
    named = {id(f): n for n, f in body.faces}
    faces = sorted(faces_at(body, edge), key=lambda f: named.get(id(f), ""))
    if len(faces) != 2:
        return None
    normals = [outward_normal(f) for f in faces]
    if normals[0] is None or normals[1] is None:
        return None
    n1, n2 = normals[0], normals[1]
    if abs(sum(a * b for a, b in zip(n1, n2, strict=True))) > 0.999:
        return None  # the faces are parallel: no corner
    a = curve.Value(curve.FirstParameter())
    b = curve.Value(curve.LastParameter())
    start, end = (a.X(), a.Y(), a.Z()), (b.X(), b.Y(), b.Z())
    mid = tuple((s + e) / 2 for s, e in zip(start, end, strict=True))
    # Inside a corner, a step along one normal and back along the other lands in material.
    probe = _add(_add(mid, n1, _STEP), n2, -_STEP)
    if not point_inside(body.shape, probe, 1e-7):  # each body on its own (D1082)
        return None
    return start, end, n1, n2


def feature_corners(body: NamedShape, fid: str) -> list[TopoDS_Edge]:
    """Every inside edge where two side faces of feature ``fid`` meet."""
    sides = [f for n, f in body.faces if n.startswith(f"{fid}/side/")]
    out: list[TopoDS_Edge] = []
    for i, face in enumerate(sides):
        for edge in _edges_of(face):
            if any(edge.IsSame(e) for e in out):
                continue
            others = sides[:i] + sides[i + 1 :]
            shared = any(any(edge.IsSame(e) for e in _edges_of(o)) for o in others)
            if shared and inside_corner(body, edge) is not None:
                out.append(edge)
    return out


def relief_cylinder(
    prefix: str,
    corner: tuple[Vec3, Vec3, Vec3, Vec3],
    radius: float,
    kind: str,
    flip: bool,
) -> NamedShape:
    """The round cut at one corner (a dogbone or a T-bone)."""
    start, end, n1, n2 = corner
    # Dogbone: the normals point into the pocket and their sum runs along the diagonal.
    # T-bone: centred on one wall's plane, cutting into the other wall only.
    t_bone = n1 if flip else n2
    offset = _unit(_add(n1, n2)) if kind == "dogbone" else t_bone
    axis = _sub(end, start)
    length = math.sqrt(sum(c * c for c in axis))
    centre = _add(start, offset, radius)
    maker = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*centre), gp_Dir(*axis)), radius, length)
    shape = maker.Shape()
    lateral = TopoDS.Face(maker.Cylinder().LateralFace())
    return NamedShape(shape, restrict([(prefix, lateral)], shape, prefix))


@register
class CornerRelief(FeatureType):
    """Reliefs on inside corners for a round cutter."""

    type_name = "corner_relief"
    makes_solid = True
    params = (
        ParamSpec("relief_type", choices=RELIEF_TYPES, default="dogbone"),
        ParamSpec("tool_diameter", kind=Kind.LENGTH),
        ParamSpec("clearance", kind=Kind.LENGTH, optional=True),
    )

    def _corners(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[tuple[Vec3, Vec3, Vec3, Vec3]], list[TopoDS_Edge], list[Issue]]:
        body = require_body(feature, ctx)
        issues: list[Issue] = []
        ref = feature.refs.get("feature")
        if isinstance(ref, dict) and ref.get("feature"):
            edges = feature_corners(body, str(ref["feature"]))
            if not edges:
                raise FeatureError(
                    f"{feature.name}: the picked feature has no inside corners. "
                    "Pick a cut with square inside corners, or pick the edges."
                )
        else:
            picked, issues = resolve_edges(feature, ctx, "edges")
            edges = [e for _n, e in picked]
        corners = []
        for edge in edges:
            found = inside_corner(body, edge)
            if found is None:
                raise FeatureError(
                    f"{feature.name}: a picked edge is not a straight inside corner between "
                    "two flat faces. Pick inside corner edges only."
                )
            corners.append(found)
        return corners, edges, issues

    def _radius(self, feature: Feature) -> float:
        diameter = self.number(feature, "tool_diameter")
        clearance_param = feature.params.get("clearance")
        clearance = getattr(clearance_param, "value", 0.0) or 0.0
        if diameter <= 0 or clearance < 0:
            raise FeatureError(
                f"{feature.name}: the tool diameter must be more than 0 and the clearance "
                "0 or more. Type new values."
            )
        return diameter / 2.0 + clearance

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the reliefs, or round the corners, in one step."""
        body = require_body(feature, ctx)
        corners, edges, issues = self._corners(feature, ctx)
        radius = self._radius(feature)
        kind = str(feature.params.get("relief_type", "dogbone"))
        if kind == "fillet":
            result = self._fillet(feature, body, edges, radius)
        else:
            tools = self._tools(feature, corners, radius, kind)
            shape = tools[0].shape if len(tools) == 1 else compound([t.shape for t in tools])
            whole = NamedShape(shape, [n for t in tools for n in t.faces])
            result = combine(feature.id, feature.name, body, whole, "cut")
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def _tools(
        self,
        feature: Feature,
        corners: list[tuple[Vec3, Vec3, Vec3, Vec3]],
        radius: float,
        kind: str,
    ) -> list[NamedShape]:
        flip = feature.params.get("flip") is True
        return [
            relief_cylinder(f"{feature.id}/relief/{k}", c, radius, kind, flip)
            for k, c in enumerate(corners, start=1)
        ]

    @staticmethod
    def _fillet(
        feature: Feature, body: NamedShape, edges: list[TopoDS_Edge], radius: float
    ) -> NamedShape:
        from OCP.TopAbs import TopAbs_FACE

        from fdcad.core.features.modify import MakerHistory
        from fdcad.core.naming.names import carry
        from fdcad.core.occ import shape_list

        maker = BRepFilletAPI_MakeFillet(body.shape)
        try:
            for edge in edges:
                maker.Add(radius, edge)
            maker.Build()
            ok = maker.IsDone()
        except Exception:
            ok = False
        if not ok:
            raise FeatureError(
                f"{feature.name} failed: the corners cannot be rounded to this tool. "
                "Use a smaller tool diameter or Dogbone."
            )
        shape = maker.Shape()
        names = carry(body.faces, MakerHistory(maker))
        for k, edge in enumerate(edges, start=1):
            for made in shape_list(maker.Generated(edge)):
                if made.ShapeType() == TopAbs_FACE:
                    names.append((f"{feature.id}/relief/{k}", TopoDS.Face(made)))
        return NamedShape(shape, restrict(names, shape, f"{feature.id}/relief"))

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The relief cuts, for the preview."""
        corners, _edges, _issues = self._corners(feature, ctx)
        kind = str(feature.params.get("relief_type", "dogbone"))
        if kind == "fillet":
            return NamedShape(compound([]), [])
        tools = self._tools(feature, corners, self._radius(feature), kind)
        return NamedShape(compound([t.shape for t in tools]), [])
