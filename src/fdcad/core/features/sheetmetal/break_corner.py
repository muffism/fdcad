"""Break Corner (PHASE5_SPEC P5.6, DECISIONS D534): chamfer or round a corner of a wall.

Type ``break_corner``. Params: ``break_type`` ("chamfer", the default, or
"fillet"), ``distance`` (chamfer), ``radius`` (fillet). ``collect_all`` takes every
corner of the flat outline instead of picked edges, and ``corner_kind`` ("outside", the
default, or "inside") says which (TR174 item 5, D1107). An inside corner is filled:
material is added instead of cut.

Refs: ``edges`` (short edges through the sheet at corners of walls), ``sheet_metal``.

Face roles: ``<fid>/corner<k>/<role>``.
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.lookup import resolve_edge
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.locate import thickness_edge
from fdcad.core.features.sheetmetal.model import (
    SheetModel,
    SheetResult,
    Vec2,
    along,
    cut_all,
    inside,
)
from fdcad.core.features.solids import line_ends
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.units import Kind

BREAK_TYPES = ("chamfer", "fillet")
_TOL = 1e-6


def outline_edges(piece: NamedShape, c: Vec2) -> list[tuple[Vec2, float]]:
    """Unit directions and lengths of the straight outline edges leaving corner ``c`` on z = 0."""
    out: list[tuple[Vec2, float]] = []
    explorer = TopExp_Explorer(piece.shape, TopAbs_EDGE)
    seen: set[tuple[int, int, int, int]] = set()
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        ends = line_ends(edge)
        if ends is None:
            continue
        a, b = ends
        if abs(a[2]) > _TOL or abs(b[2]) > _TOL:
            continue
        for p, q in ((a, b), (b, a)):
            if math.hypot(p[0] - c[0], p[1] - c[1]) < 1e-5:
                size = math.hypot(q[0] - p[0], q[1] - p[1])
                d = ((q[0] - p[0]) / size, (q[1] - p[1]) / size)
                key = (round(d[0] * 1e6), round(d[1] * 1e6), round(size * 1e4), 0)
                if key not in seen:
                    seen.add(key)
                    out.append((d, size))
    return out


def _prism(prefix: str, points: list[Vec2], thickness: float) -> NamedShape:
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in points:
        poly.Add(gp_Pnt(x, y, -1.0))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    shape = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, thickness + 2.0)).Shape()
    return NamedShape(shape, [(f"{prefix}/cut", f) for f in faces_of(shape)])


def corner_cut(
    prefix: str, c: Vec2, u1: Vec2, u2: Vec2, kind: str, size: float, thickness: float
) -> NamedShape:
    """The chamfer or round cut at corner ``c`` between outline directions ``u1`` and ``u2``."""
    if kind == "chamfer":
        p1 = (c[0] + u1[0] * size, c[1] + u1[1] * size)
        p2 = (c[0] + u2[0] * size, c[1] + u2[1] * size)
        return _prism(prefix, [c, p1, p2], thickness)
    phi = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
    reach = size / math.tan(phi / 2)
    p1 = (c[0] + u1[0] * reach, c[1] + u1[1] * reach)
    p2 = (c[0] + u2[0] * reach, c[1] + u2[1] * reach)
    bis = (u1[0] + u2[0], u1[1] + u2[1])
    n = math.hypot(*bis)
    far = size / math.sin(phi / 2)
    centre = (c[0] + bis[0] / n * far, c[1] + bis[1] / n * far)
    tri = _prism(prefix, [c, p1, p2], thickness)
    axis = gp_Ax2(gp_Pnt(centre[0], centre[1], -2.0), gp_Dir(0, 0, 1))
    cyl = BRepPrimAPI_MakeCylinder(axis, size, thickness + 4.0).Shape()
    disc = NamedShape(cyl, [(f"{prefix}/round", f) for f in faces_of(cyl)])
    return cut_all(tri, [disc], prefix)


def on_bend_line(model: SheetModel, wid: str, c: Vec2) -> bool:
    """True when ``c`` lies on a line where a bend meets wall ``wid``."""
    parent = model.parent_bend(wid)
    if parent is not None and abs(c[1]) < 1e-5 and -1e-5 <= c[0] <= parent.length + 1e-5:
        return True
    for bend in model.children(wid):
        e = along(bend.w)
        rel = (c[0] - bend.p0[0], c[1] - bend.p0[1])
        across = rel[0] * bend.w[0] + rel[1] * bend.w[1]
        run = rel[0] * e[0] + rel[1] * e[1]
        if abs(across) < 1e-5 and -1e-5 <= run <= bend.length + 1e-5:
            return True
    return False


@register
class BreakCorner(FeatureType):
    """Chamfers or rounds outside corners of the sheet."""

    type_name = "break_corner"
    makes_solid = True
    params = (
        ParamSpec("break_type", choices=BREAK_TYPES, optional=True),
        ParamSpec("distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("collect_all", default=False, optional=True),
        ParamSpec("corner_kind", choices=("outside", "inside"), optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the corners and rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with its corners broken."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        kind = str(feature.params.get("break_type", "chamfer"))
        size = value(feature, "radius" if kind == "fillet" else "distance", 0.0)
        if size <= 0:
            what = "radius" if kind == "fillet" else "distance"
            raise FeatureError(f"{name}: enter a {what} greater than zero.")
        issues: list[Issue] = []
        spots = self._spots(feature, ctx, model, issues)
        adds: dict[str, list[NamedShape]] = {}
        for k, (wid, c) in enumerate(spots, start=1):
            if on_bend_line(model, wid, c):
                raise FeatureError(
                    f"{name}: corner {k} is on a bend. Pick a corner of the flat outline."
                )
            piece = model.piece(wid)
            legs = outline_edges(piece, c)
            if len(legs) != 2:
                raise FeatureError(
                    f"{name}: corner {k} is not where two straight outline edges meet. "
                    "Pick a corner between two straight edges."
                )
            (u1, l1), (u2, l2) = legs
            bis = (u1[0] + u2[0], u1[1] + u2[1])
            n = math.hypot(*bis)
            probe = (c[0] + bis[0] / max(n, 1e-12) * 1e-3, c[1] + bis[1] / max(n, 1e-12) * 1e-3)
            cross = u1[0] * u2[1] - u1[1] * u2[0]
            if n < 1e-9 or abs(cross) < 1e-9:
                raise FeatureError(
                    f"{name}: corner {k} is not a corner between two edges. Pick a corner."
                )
            outside = inside(piece.shape, (*probe, t / 2))
            phi = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
            reach = size if kind == "chamfer" else size / math.tan(phi / 2)
            if reach > min(l1, l2) + _TOL:
                raise FeatureError(
                    f"{name}: corner {k}: the {kind} is larger than the corner's edges allow. "
                    "Enter a smaller size."
                )
            shape = corner_cut(f"{fid}/corner{k}", c, u1, u2, kind, size, t)
            if outside:
                model.walls[wid].cuts.append(shape)
            else:  # an inside corner is filled, one sheet thick (D1107)
                from fdcad.core.features.sheetmetal.model import box, common_with

                slab = box(f"{fid}/slab{k}", (c[0] - 2 * size - 1, c[1] - 2 * size - 1, 0.0),
                           (c[0] + 2 * size + 1, c[1] + 2 * size + 1, t))  # fmt: skip
                adds.setdefault(wid, []).append(common_with(fid, shape, slab))
        for wid, extra in adds.items():
            model.add_material(wid, extra)
        return model, issues

    @staticmethod
    def _spots(
        feature: Feature, ctx: BuildContext, model: SheetModel, issues: list[Issue]
    ) -> list[tuple[str, Vec2]]:
        """The corners to break: picked, or all of one kind (D1107)."""
        name = feature.name
        if feature.params.get("collect_all") is True:
            want_inside = feature.params.get("corner_kind", "outside") == "inside"
            found = all_corners(model, want_inside)
            if not found:
                raise FeatureError(
                    f"{name}: the sheet has no corners of this kind. Choose the other kind, "
                    "or pick corner edges."
                )
            return found
        refs = feature.refs.get("edges")
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{name}: pick the corner edges through the sheet.")
        out = []
        for ref in refs:
            if not isinstance(ref, dict):
                raise FeatureError(f"{name}: an edge pick is damaged. Pick the edges again.")
            edge, found_issues = resolve_edge(ctx.body, ref, name)
            issues.extend(found_issues)
            out.append(thickness_edge(model, edge, name))
        return out


def all_corners(model: SheetModel, want_inside: bool) -> list[tuple[str, Vec2]]:
    """Every corner of the walls' flat outlines between two straight edges, off the bend
    lines: outside corners, or inside ones (TR174 item 5, D1107)."""
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopoDS import TopoDS

    t = model.thickness
    out: list[tuple[str, Vec2]] = []
    for wid in sorted(model.walls):
        piece = model.piece(wid)
        seen: set[tuple[int, int]] = set()
        explorer = TopExp_Explorer(piece.shape, TopAbs_VERTEX)
        while explorer.More():
            q = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
            p = (q.X(), q.Y(), q.Z())
            explorer.Next()
            if abs(p[2]) > _TOL:
                continue
            key = (round(p[0] * 1e5), round(p[1] * 1e5))
            if key in seen:
                continue
            seen.add(key)
            c = (p[0], p[1])
            if on_bend_line(model, wid, c):
                continue
            legs = outline_edges(piece, c)
            if len(legs) != 2:
                continue
            (u1, _l1), (u2, _l2) = legs
            bis = (u1[0] + u2[0], u1[1] + u2[1])
            n = math.hypot(*bis)
            if n < 1e-9 or abs(u1[0] * u2[1] - u1[1] * u2[0]) < 1e-9:
                continue
            probe = (c[0] + bis[0] / n * 1e-3, c[1] + bis[1] / n * 1e-3, t / 2)
            if inside(piece.shape, probe) != want_inside:
                out.append((wid, c))
    return out
