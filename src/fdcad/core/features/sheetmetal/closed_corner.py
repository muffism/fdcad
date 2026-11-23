"""Closed Corner (PHASE5_SPEC P5.6, DECISIONS D533): lengthen two flange walls to meet.

Type ``closed_corner``. Params (all optional): ``corner_type`` ("overlap", the
default, "underlap" or "butt") and ``gap``. ``overlap_ratio`` (0 to 1, 1 when
missing): how far across the other wall's thickness an overlap or underlap reaches
(TR174 item 2, D1107). ``bend_region`` ("open" when missing, or "closed",
D2308) fills the corner between the two bends in the folded part. Several faces
close several corners at once.

Refs: ``faces`` (end faces of flange walls), ``sheet_metal``.

Face roles: the tabs are ``<fid>/tab<k>a/<role>`` (picked wall) and
``<fid>/tab<k>b/<role>`` (partner), the cuts ``<fid>/cut<k>a/plane`` and ``<fid>/cut<k>b/plane``.
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.locate import (
    bounds,
    half_space,
    local_vector,
    to_wall,
    wall_end,
)
from fdcad.core.features.sheetmetal.model import (
    SheetModel,
    SheetResult,
    apply,
    box,
    volume,
)
from fdcad.core.features.sheetmetal.params import sheet_defaults
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.units import Kind

CORNER_TYPES = ("overlap", "underlap", "butt")
_TOL = 1e-6


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


class _Plate:
    """A wall's two face planes and centre, in world coordinates (folded)."""

    def __init__(self, model: SheetModel, wid: str) -> None:
        place = model.placements(False)[wid]
        t = model.thickness
        lo, hi = bounds(model.piece(wid))
        self.wid = wid
        self.centre = apply(place, ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, t / 2))
        self.faces = [
            (apply(place, (0.0, 0.0, 0.0)), _unit(local_vector(place, (0.0, 0.0, -1.0)))),
            (apply(place, (0.0, 0.0, t)), _unit(local_vector(place, (0.0, 0.0, 1.0)))),
        ]

    def facing(self, point: Vec3, toward: bool) -> tuple[Vec3, Vec3]:
        """The face whose outward normal points toward ``point`` (or away from it)."""
        for origin, n in self.faces:
            if (_dot(n, _sub(point, origin)) > 0) == toward:
                return origin, n
        return self.faces[0]


@register
class ClosedCorner(FeatureType):
    """Closes the gap between two flange walls at a corner."""

    type_name = "closed_corner"
    makes_solid = True
    params = (
        ParamSpec("corner_type", choices=CORNER_TYPES, optional=True),
        ParamSpec("gap", kind=Kind.LENGTH, optional=True),
        ParamSpec("overlap_ratio", kind=Kind.NUMBER, optional=True),
        ParamSpec("bend_region", choices=("open", "closed"), optional=True),  # D2308
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Lengthen and cut the walls, then rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with the corners closed."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        radius = sheet_defaults(feature, ctx).rule.radius
        gap = value(feature, "gap", 0.0)
        if gap < 0:
            raise FeatureError(f"{name}: the gap cannot be negative. Enter zero or more.")
        kind = str(feature.params.get("corner_type", "overlap"))
        ratio = value(feature, "overlap_ratio", 1.0)
        if not 0 <= ratio <= 1:
            raise FeatureError(
                f"{name}: the overlap ratio must be from 0 to 1. Enter another ratio."
            )
        refs = feature.refs.get("faces")
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{name}: pick the end face of a flange wall at each corner.")
        issues: list[Issue] = []
        reach = 4 * (radius + t) + gap
        for k, ref in enumerate(refs, start=1):
            if not isinstance(ref, dict):
                raise FeatureError(f"{name}: a face pick is damaged. Pick the faces again.")
            face, found = resolve_face(ctx.body, ref, name)
            issues.extend(found)
            wid, sign, end = wall_end(model, face, name)
            partner, psign, pend, dist = _partner(model, wid, sign, end, reach, name)
            a, b = _Plate(model, wid), _Plate(model, partner)
            if kind == "butt":
                a_out = a.facing(b.centre, toward=False)
                b_out = b.facing(a.centre, toward=False)
                m = _sub(a_out[1], b_out[1])
                if _dot(m, m) < 1e-12:
                    raise FeatureError(
                        f"{name}: corner {k}: the walls are parallel. "
                        "Pick a corner between walls that meet at an angle."
                    )
                size = math.sqrt(_dot(m, m))
                m = (m[0] / size, m[1] / size, m[2] / size)
                c = (_dot(a_out[1], a_out[0]) - _dot(b_out[1], b_out[0])) / size
                on = (m[0] * c, m[1] * c, m[2] * c)
                side = 1.0 if _dot(m, a.centre) - c > 0 else -1.0
                into_b = (-m[0] * side, -m[1] * side, -m[2] * side)
                plane_a = (_shift(on, into_b, -gap / 2), into_b)
                plane_b = (_shift(on, into_b, gap / 2), (-into_b[0], -into_b[1], -into_b[2]))
            else:
                cover, under = (a, b) if kind == "overlap" else (b, a)
                origin, n = under.facing(cover.centre, toward=False)
                inner, n_in = cover.facing(under.centre, toward=True)
                cover_plane = (_shift(origin, n, -(1 - ratio) * t), n)
                under_plane = (_shift(inner, n_in, gap), (-n_in[0], -n_in[1], -n_in[2]))
                plane_a, plane_b = (
                    (cover_plane, under_plane) if kind == "overlap" else (under_plane, cover_plane)
                )
            ext = dist + 3 * t + 2 * radius + gap + 1.0
            _close(model, fid, f"{k}a", wid, sign, end, ext, plane_a)
            _close(model, fid, f"{k}b", partner, psign, pend, ext, plane_b)
            _check(model, wid, partner, name, k)
            closed = feature.params.get("bend_region") == "closed"  # TR174 (D2308)
            if closed and not _close_region(model, fid, k, wid, partner):
                issues.append(
                    Issue(
                        FeatureState.WARNING,
                        f"{name}: the bend region of corner {k} stays open: the two "
                        "flanges must bend from one wall with bends that cross at "
                        "the corner. Choose Open, or pick another corner.",
                        code="region_open",
                    )
                )
        return model, issues


def _shift(p: Vec3, n: Vec3, d: float) -> Vec3:
    return (p[0] + n[0] * d, p[1] + n[1] * d, p[2] + n[2] * d)


def _end_point(model: SheetModel, wid: str, end: float) -> Vec3:
    lo, hi = bounds(model.piece(wid))
    place = model.placements(False)[wid]
    return apply(place, (end, (lo[1] + hi[1]) / 2, model.thickness / 2))


def _partner(
    model: SheetModel, wid: str, sign: int, end: float, reach: float, owner: str
) -> tuple[str, int, float, float]:
    """The nearest end of another flange wall: wall, end sign, end x and distance."""
    here = _end_point(model, wid, end)
    best: tuple[str, int, float, float] | None = None
    for other in model.walls:
        if other == wid or model.parent_bend(other) is None:
            continue
        lo, hi = bounds(model.piece(other))
        for s, x in ((-1, lo[0]), (1, hi[0])):
            p = _end_point(model, other, x)
            d = math.dist(here, p)
            if d <= reach and (best is None or d < best[3]):
                best = (other, s, x, d)
    if best is None:
        raise FeatureError(
            f"{owner}: no other flange wall ends near the picked face. "
            "Pick the end of a wall at a corner between two flanges."
        )
    del sign
    return best


def _close(
    model: SheetModel,
    fid: str,
    tag: str,
    wid: str,
    sign: int,
    end: float,
    ext: float,
    plane: tuple[Vec3, Vec3],
) -> None:
    """Lengthen wall ``wid`` at its ``end`` and cut it on ``plane`` (normal into the cut)."""
    wall = model.walls[wid]
    lo, hi = bounds(model.piece(wid))
    t = model.thickness
    x0, x1 = (end, end + ext) if sign > 0 else (end - ext, end)
    tab = box(f"{fid}/tab{tag}", (x0, lo[1], 0.0), (x1, hi[1], t))
    model.add_material(wid, [tab])
    cut = half_space(f"{fid}/cut{tag}", plane[0], plane[1], 10 * ext + 1000.0)
    wall.cuts.append(to_wall(model, wid, cut))


def _close_region(model: SheetModel, fid: str, k: int, a: str, b: str) -> bool:
    """Fill the bend region of a corner (TR174, D2308): where the two bends, run on past
    their ends, both lie. That is the piece of sheet where the two bent surfaces cross
    (a vault at a square corner of two 90 degree bends). Folded part only; the flat
    pattern keeps its corner. False when there is nothing to fill."""
    from dataclasses import replace

    from fdcad.core.features.sheetmetal.model import along, folded_bend

    ba, bb = model.parent_bend(a), model.parent_bend(b)
    if ba is None or bb is None or ba.parent != bb.parent:
        return False
    t = model.thickness
    run = 2 * (ba.radius + bb.radius + 2 * t) + ba.length + bb.length
    longer = []
    for bend in (ba, bb):
        e = along(bend.w)
        p0 = (bend.p0[0] - e[0] * run, bend.p0[1] - e[1] * run)
        longer.append(folded_bend(replace(bend, p0=p0, length=bend.length + 2 * run), t))
    op = BRepAlgoAPI_Common(longer[0].shape, longer[1].shape)
    op.Build()
    if not op.IsDone() or volume(op.Shape()) < _TOL:
        return False
    shape = op.Shape()
    from fdcad.core.naming.names import faces_of

    fill = NamedShape(shape, [(f"{fid}/region{k}/face", f) for f in faces_of(shape)])
    model.part_adds.append((ba.parent, fill))
    return True


def _check(model: SheetModel, a: str, b: str, owner: str, k: int) -> None:
    places = model.placements(False)
    pa = transform(model.piece(a), places[a])
    pb = transform(model.piece(b), places[b])
    common = BRepAlgoAPI_Common(pa.shape, pb.shape)
    if common.IsDone() and volume(common.Shape()) > 1e-6:
        raise FeatureError(
            f"{owner}: corner {k} cannot be closed: the walls would overlap. "
            "Pick the other wall's end or another corner type."
        )
    if volume(pa.shape) < _TOL or volume(pb.shape) < _TOL:
        raise FeatureError(f"{owner}: corner {k}: a wall was cut away. Pick another face.")
