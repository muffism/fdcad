"""Sheet metal Corner Relief (TR168, DECISIONS D1103): relief cuts where bends meet.

Type ``sheet_corner_relief`` (``corner_relief`` is the machining relief of TR244).

A corner is a pair of bends that start on the same wall and whose tangent lines
meet near an end of each. Three bends round one corner make pairs too. The relief
is drawn in the flat frame of that wall and cut through the sheet from the wall,
both bend strips (wrapped round the bends when folded) and both flange walls, so it
shows in the folded part and in the flat pattern alike.

Params:
- ``all_corners``: Collect All Corners (otherwise the corners between the picked bends).
- ``relief_type``: "rectangular" (default), "circular", "tear", "obround",
  "constant_width".
- ``corner_types`` (optional text): one type per corner in corner order, such as
  "circular, , tear"; a blank keeps ``relief_type``.
- ``size_by``: "ratio" (default) or "value"; ``ratio`` (times the thickness, default
  2) or ``size`` (length).
- ``placement``: "bend_lines" (centred on the bend lines, default) or "tangent" (touching the
  bends' tangent lines on the wall).

Refs: ``bends`` (faces of bends), ``sheet_metal``.

Face roles: ``<fid>/corner<k>/<role>``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

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
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.edit_bends import picked_bends
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    Vec2,
    along,
    basis,
    box,
    flat_child,
    fuse_all,
    volume,
)
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.units import Kind

TYPE = "sheet_corner_relief"
KINDS = ("rectangular", "circular", "tear", "obround", "constant_width")
_TOL = 1e-7


@dataclass(frozen=True)
class Corner:
    """Two bends on one wall whose tangent lines meet at ``point`` (wall frame)."""

    first: str
    second: str
    wall: str
    point: Vec2


def _cross(a: Vec2, b: Vec2) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _outside(p: Vec2, bend: Bend) -> float:
    e = along(bend.w)
    x = (p[0] - bend.p0[0]) * e[0] + (p[1] - bend.p0[1]) * e[1]
    return -x if x < 0 else x - bend.length if x > bend.length else 0.0


def sheet_corners(model: SheetModel, only: set[str] | None = None) -> list[Corner]:
    """Every corner of the sheet, in a stable order (by bend ids)."""
    t = model.thickness
    out: list[Corner] = []
    bends = sorted(model.bends.values(), key=lambda b: b.bid)
    for i, b1 in enumerate(bends):
        for b2 in bends[i + 1 :]:
            if b1.parent != b2.parent:
                continue
            if only is not None and not {b1.bid, b2.bid} <= only:
                continue
            e1, e2 = along(b1.w), along(b2.w)
            det = _cross(e1, e2)
            if abs(det) < 1e-6:
                continue
            r = (b2.p0[0] - b1.p0[0], b2.p0[1] - b1.p0[1])
            s = _cross(r, e2) / det
            c = (b1.p0[0] + e1[0] * s, b1.p0[1] + e1[1] * s)
            reach = 3 * (t + max(b1.radius, b2.radius)) + 2.0
            if _outside(c, b1) > reach or _outside(c, b2) > reach:
                continue
            # The bends must lie away from the corner on both sides, so the corner is
            # at an end of each (not where one bend crosses the middle of the other).
            ends = [min(abs(_along(c, b)), abs(_along(c, b) - b.length)) <= reach for b in (b1, b2)]
            if all(ends):
                out.append(Corner(b1.bid, b2.bid, b1.parent, c))
    return out


def _along(p: Vec2, bend: Bend) -> float:
    e = along(bend.w)
    return (p[0] - bend.p0[0]) * e[0] + (p[1] - bend.p0[1]) * e[1]


def _solve(u1: Vec2, u2: Vec2, d1: float, d2: float) -> Vec2:
    """The vector v with v . u1 = d1 and v . u2 = d2."""
    det = u1[0] * u2[1] - u1[1] * u2[0]
    return ((d1 * u2[1] - d2 * u1[1]) / det, (u1[0] * d2 - u2[0] * d1) / det)


def _prism(prefix: str, points: list[Vec2], t: float) -> NamedShape:
    poly = BRepBuilderAPI_MakePolygon()
    for p in points:
        poly.Add(gp_Pnt(p[0], p[1], -1.0))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    shape = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, t + 2.0)).Shape()
    return NamedShape(shape, [(f"{prefix}/side", f) for f in faces_of(shape)])


def _disc(prefix: str, c: Vec2, radius: float, t: float) -> NamedShape:
    axis = gp_Ax2(gp_Pnt(c[0], c[1], -1.0), gp_Dir(0, 0, 1))
    shape = BRepPrimAPI_MakeCylinder(axis, radius, t + 2.0).Shape()
    return NamedShape(shape, [(f"{prefix}/round", f) for f in faces_of(shape)])


def _stadium(prefix: str, a: Vec2, b: Vec2, radius: float, t: float) -> NamedShape:
    d = (b[0] - a[0], b[1] - a[1])
    n = math.hypot(*d)
    if n < 1e-9:
        return _disc(prefix, a, radius, t)
    side = (-d[1] / n * radius, d[0] / n * radius)
    body = _prism(
        prefix,
        [
            (a[0] + side[0], a[1] + side[1]),
            (b[0] + side[0], b[1] + side[1]),
            (b[0] - side[0], b[1] - side[1]),
            (a[0] - side[0], a[1] - side[1]),
        ],
        t,
    )
    ends = [_disc(prefix, a, radius, t), _disc(prefix, b, radius, t)]
    return fuse_all(prefix, prefix, [body, *ends])


def relief_shape(
    prefix: str, kind: str, corner: Corner, model: SheetModel, size: float, tangent: bool
) -> NamedShape:
    """The relief outline at ``corner`` through the sheet, in the wall's flat frame."""
    t = model.thickness
    b1, b2 = model.bends[corner.first], model.bends[corner.second]
    u1, u2 = b1.w, b2.w
    c = corner.point
    half = size / 2

    def at(d1: float, d2: float) -> Vec2:
        v = _solve(u1, u2, d1, d2)
        return (c[0] + v[0], c[1] + v[1])

    if kind == "tear":
        return _disc(prefix, c, half, t)
    if kind == "constant_width":
        return _stadium(prefix, c, at(b1.allowance, b2.allowance), half, t)
    centre = at(half, half) if tangent else at(b1.allowance / 2, b2.allowance / 2)
    if kind == "circular":
        return _disc(prefix, centre, half, t)
    if kind == "obround":
        diag = (u1[0] + u2[0], u1[1] + u2[1])
        n = math.hypot(*diag) or 1.0
        d = (diag[0] / n * half, diag[1] / n * half)
        a = (centre[0] - d[0], centre[1] - d[1])
        b = (centre[0] + d[0], centre[1] + d[1])
        return _stadium(prefix, a, b, half, t)
    # Rectangular: a parallelogram with sides along the two bends, ``size`` across each.
    o = _solve(u1, u2, half, half)
    base = (centre[0] - o[0], centre[1] - o[1])
    s1 = _solve(u1, u2, size, 0.0)
    s2 = _solve(u1, u2, 0.0, size)
    pts = [
        base,
        (base[0] + s1[0], base[1] + s1[1]),
        (base[0] + s1[0] + s2[0], base[1] + s1[1] + s2[1]),
        (base[0] + s2[0], base[1] + s2[1]),
    ]
    return _prism(prefix, pts, t)


def corner_trim(prefix: str, corner: Corner, model: SheetModel) -> NamedShape:
    """The square where the two bend strips of ``corner`` meet, in the wall's flat frame
    (Corner Trim of the flat pattern, TR76, D1105)."""
    b1, b2 = model.bends[corner.first], model.bends[corner.second]
    c = corner.point
    s1 = _solve(b1.w, b2.w, b1.allowance, 0.0)
    s2 = _solve(b1.w, b2.w, 0.0, b2.allowance)
    pts = [
        c,
        (c[0] + s1[0], c[1] + s1[1]),
        (c[0] + s1[0] + s2[0], c[1] + s1[1] + s2[1]),
        (c[0] + s2[0], c[1] + s2[1]),
    ]
    return _prism(prefix, pts, model.thickness)


def _meets(a: NamedShape, b: NamedShape) -> bool:
    common = BRepAlgoAPI_Common(a.shape, b.shape)
    return bool(common.IsDone() and volume(common.Shape()) > _TOL)


def cut_corner(model: SheetModel, corner: Corner, shape: NamedShape) -> None:
    """Cut ``shape`` (wall flat frame) from the wall, both bend strips and both flanges."""
    t = model.thickness
    if _meets(model.piece(corner.wall), shape):
        model.walls[corner.wall].cuts.append(shape)
    for bid in (corner.first, corner.second):
        bend = model.bends[bid]
        local = transform(shape, basis(bend.p0, bend.w).Inverted())
        strip = box(bend.bid, (0.0, 0.0, 0.0), (bend.length, bend.allowance, t))
        if _meets(strip, local):
            model.bends[bid] = replace(bend, cuts=(*bend.cuts, local))
        child = transform(shape, flat_child(bend).Inverted())
        if bend.child in model.walls and _meets(model.piece(bend.child), child):
            model.walls[bend.child].cuts.append(child)


def corner_kinds(feature: Feature, count: int) -> list[str]:
    """The relief type of each corner: ``corner_types`` entries, else ``relief_type``."""
    name = feature.name
    main = str(feature.params.get("relief_type", "rectangular"))
    if main not in KINDS:
        raise FeatureError(f"{name}: the relief type is not known. Choose one of the list.")
    raw = feature.params.get("corner_types")
    own = (
        [w.strip().lower().replace(" ", "_") for w in raw.split(",")]
        if isinstance(raw, str)
        else []
    )
    out = []
    for k in range(count):
        kind = own[k] if k < len(own) and own[k] else main
        if kind not in KINDS:
            raise FeatureError(
                f"{name}: corner {k + 1} has the unknown type {kind!r}. "
                f"Enter one of {', '.join(KINDS)}."
            )
        out.append(kind)
    return out


@register
class SheetCornerRelief(FeatureType):
    """Cuts reliefs where two or three bends meet."""

    type_name = TYPE
    makes_solid = True
    params = (
        ParamSpec("all_corners", default=True, optional=True),
        ParamSpec("relief_type", choices=KINDS, default="rectangular", optional=True),
        ParamSpec("corner_types", optional=True),
        ParamSpec("size_by", choices=("ratio", "value"), default="ratio", optional=True),
        ParamSpec("ratio", kind=Kind.NUMBER, optional=True),
        ParamSpec("size", kind=Kind.LENGTH, optional=True),
        ParamSpec(
            "placement", choices=("bend_lines", "tangent"), default="bend_lines", optional=True
        ),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the reliefs and rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The part with the reliefs, for the live preview."""
        return self.model(feature, ctx)[0].build(feature.id, feature.name)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with the corner reliefs cut."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        issues: list[Issue] = []
        only = None
        if feature.params.get("all_corners", True) is False:
            only = picked_bends(feature, ctx, model, issues)
        corners = sheet_corners(model, only)
        if not corners:
            raise FeatureError(
                f"{name}: no corner where two bends meet was found. Add flanges on two edges "
                "that share a corner, or pick their bends."
            )
        t = model.thickness
        if feature.params.get("size_by", "ratio") == "value":
            size = value(feature, "size", 2 * t)
        else:
            size = value(feature, "ratio", 2.0) * t
        if size <= 0:
            raise FeatureError(f"{name}: the relief size must be greater than zero. Enter a size.")
        tangent = feature.params.get("placement", "bend_lines") == "tangent"
        for k, (corner, kind) in enumerate(
            zip(corners, corner_kinds(feature, len(corners)), strict=True), 1
        ):
            shape = relief_shape(f"{fid}/corner{k}", kind, corner, model, size, tangent)
            cut_corner(model, corner, shape)
        return model, issues
