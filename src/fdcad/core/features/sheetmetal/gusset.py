"""Gusset (TUTORIAL_REVIEW_SPEC TR12.1, DECISIONS D700): a stiffening rib pressed into a bend.

Type ``gusset``. Params: ``depth`` (how far the rib reaches along each wall from the
bend), ``width`` (across the rib, along the bend), ``profile`` ("round", the default,
or "flat"), ``rib_position`` (how far the rib's middle sits from the middle of the
bend, along it; 0 when missing) and ``flat_cutout`` (cut the rib's place out of the
flat pattern; off leaves the flat pattern as it is).

Refs: ``walls`` (two face references, one on each wall the bend joins),
``sheet_metal``.

In the bend's cross section the rib fills the inside corner between the two walls,
up to ``depth`` along each wall; the outside gets the same shape pressed in, moved
out by the sheet thickness, so the sheet keeps its thickness at the rib's middle.
Both are folded part only, like forming tools (D546).

Face roles: ``<fid>/rib/<role>`` and ``<fid>/press/<role>``.
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Pnt, gp_Vec

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
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.locate import wall_face
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    along,
    oriented_box,
)
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.units import Kind

PROFILES = ("round", "flat")
#: Points along a curved part of the rib's outline.
_STEPS = 16


def _bend_between(model: SheetModel, a: str, b: str, owner: str) -> Bend:
    for bend in model.bends.values():
        if {bend.parent, bend.child} == {a, b}:
            return bend
    raise FeatureError(
        f"{owner}: the two picked walls are not joined by a bend. "
        "Pick a face on each of two walls that meet at a bend."
    )


def outline(bend: Bend, thickness: float, depth: float, profile: str) -> list[tuple[float, float]]:
    """The rib's cross section as (u, z) points in the bend's plane: u across the bend from
    its start line on the parent wall, z the parent's z. Runs from the parent wall, along
    the rib's outer edge to the child wall, then back along the bend's inside."""
    r, t, a = bend.radius, thickness, bend.angle
    up = 1.0 if bend.up > 0 else -1.0
    level = t if up > 0 else 0.0  # the parent wall's inside face

    def arc_point(phi: float) -> tuple[float, float]:
        return (r * math.sin(phi), level + up * (r - r * math.cos(phi)))

    start = (-depth, level)  # on the parent wall, ``depth`` back from the bend
    tip = arc_point(a)
    direction = (math.cos(a), up * math.sin(a))
    end = (tip[0] + depth * direction[0], tip[1] + depth * direction[1])
    edge: list[tuple[float, float]]
    if profile == "flat":
        edge = [start, end]
    else:
        # A round edge: the circle touching both walls at ``start`` and ``end``.
        n1 = (0.0, up)  # into the corner from the parent wall
        n2 = (-math.sin(a), up * math.cos(a))  # into the corner from the child wall
        # The centre lies along each wall's inward normal from its touching point.
        denom = n1[0] * n2[1] - n1[1] * n2[0]
        if abs(denom) < 1e-9:
            edge = [start, end]
        else:
            dx, dy = end[0] - start[0], end[1] - start[1]
            k = (dx * n2[1] - dy * n2[0]) / denom
            centre = (start[0] + k * n1[0], start[1] + k * n1[1])
            radius = math.dist(centre, start)
            a0 = math.atan2(start[1] - centre[1], start[0] - centre[0])
            a1 = math.atan2(end[1] - centre[1], end[0] - centre[0])
            sweep = math.remainder(a1 - a0, 2 * math.pi)
            edge = [
                (
                    centre[0] + radius * math.cos(a0 + sweep * i / _STEPS),
                    centre[1] + radius * math.sin(a0 + sweep * i / _STEPS),
                )
                for i in range(_STEPS + 1)
            ]
    inside = [arc_point(a * (1 - i / _STEPS)) for i in range(_STEPS + 1)]
    return [*edge, tip, *inside[1:], (0.0, level)]


Pt = tuple[float, float]
#: An outline piece: ("line", a, b) or ("arc", a, middle, b).
Piece = tuple[str, Pt, Pt] | tuple[str, Pt, Pt, Pt]


def pieces(pts: list[Pt], profile: str) -> list[Piece]:
    """The outline of ``outline`` as lines and true arcs (round faces stay smooth)."""
    n = _STEPS + 1 if profile == "round" else 2
    edge, rest = pts[:n], pts[n:]
    tip, back = rest[0], rest[-1]
    inside_mid = rest[1 + _STEPS // 2 - 1] if len(rest) > _STEPS // 2 else rest[len(rest) // 2]
    out: list[Piece] = []
    if profile == "round":
        out.append(("arc", edge[0], edge[_STEPS // 2], edge[-1]))
    else:
        out.append(("line", edge[0], edge[-1]))
    out.append(("line", edge[-1], tip))
    out.append(("arc", tip, inside_mid, back))
    out.append(("line", back, edge[0]))
    return [p for p in out if math.dist(p[1], p[-1]) > 1e-9]


def _prism(
    prefix: str, bend: Bend, pts: list[Pt], centre: float, width: float, profile: str = "flat"
) -> NamedShape:
    """The outline swept ``width`` along the bend, centred at ``centre`` from its start."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.GC import GC_MakeArcOfCircle

    w, e = bend.w, along(bend.w)
    s0 = centre - width / 2

    def place(p: Pt) -> gp_Pnt:
        u, z = p
        x = bend.p0[0] + w[0] * u + e[0] * s0
        y = bend.p0[1] + w[1] * u + e[1] * s0
        return gp_Pnt(x, y, z)

    wire = BRepBuilderAPI_MakeWire()
    for piece in pieces(pts, profile):
        if piece[0] == "arc" and len(piece) == 4:
            arc = GC_MakeArcOfCircle(place(piece[1]), place(piece[2]), place(piece[3]))
            if not arc.IsDone():
                raise FeatureError(
                    f"{prefix}: the gusset outline could not be made. Change its depth."
                )
            wire.Add(BRepBuilderAPI_MakeEdge(arc.Value()).Edge())
        else:
            wire.Add(BRepBuilderAPI_MakeEdge(place(piece[1]), place(piece[-1])).Edge())
    if not wire.IsDone():
        raise FeatureError(f"{prefix}: the gusset outline could not be made. Change its depth.")
    face = BRepBuilderAPI_MakeFace(wire.Wire(), True)
    if not face.IsDone():
        raise FeatureError(f"{prefix}: the gusset outline could not be made. Change its depth.")
    maker = BRepPrimAPI_MakePrism(face.Face(), gp_Vec(e[0] * width, e[1] * width, 0.0))
    maker.Build()
    shape = maker.Shape()
    return NamedShape(shape, [(f"{prefix}/face{i}", f) for i, f in enumerate(faces_of(shape))])


@register
class Gusset(FeatureType):
    """Presses a stiffening rib into a bend."""

    type_name = "gusset"
    makes_solid = True
    params = (
        ParamSpec("depth", kind=Kind.LENGTH),
        ParamSpec("width", kind=Kind.LENGTH),
        ParamSpec("profile", choices=PROFILES, optional=True),
        ParamSpec("rib_position", kind=Kind.LENGTH, optional=True),
        ParamSpec("flat_cutout", default=False, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the rib and rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with the gusset pressed in."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        refs = feature.refs.get("walls")
        if not isinstance(refs, list) or len(refs) != 2:
            raise FeatureError(f"{name}: pick a face on each of the two walls the bend joins.")
        issues: list[Issue] = []
        walls = []
        for ref in refs:
            face, found = resolve_face(ctx.body, ref, name)
            issues.extend(found)
            walls.append(wall_face(model, face, name).wid)
        bend = _bend_between(model, walls[0], walls[1], name)
        depth = value(feature, "depth", 0.0)
        width = value(feature, "width", 0.0)
        if depth <= 0 or width <= 0:
            raise FeatureError(
                f"{name}: the depth and width must be greater than zero. Enter larger values."
            )
        if not 1e-6 < bend.angle < math.pi - 1e-6:
            raise FeatureError(
                f"{name}: the bend is too flat or too sharp for a gusset. "
                "Pick walls of another bend."
            )
        centre = bend.length / 2 + value(feature, "rib_position", 0.0)
        if centre - width / 2 < -1e-9 or centre + width / 2 > bend.length + 1e-9:
            raise FeatureError(
                f"{name}: the gusset runs past the end of the bend. "
                "Make it narrower or move it toward the middle."
            )
        profile = str(feature.params.get("profile", "round"))
        pts = outline(bend, t, depth, profile)
        rib = _prism(f"{fid}/rib", bend, pts, centre, width, profile)
        up = 1.0 if bend.up > 0 else -1.0
        # Pressed in from outside: the rib's shape moved out of the corner by t, along
        # the line that halves the bend.
        half = bend.angle / 2
        into_corner = (-math.sin(half), up * math.cos(half))
        shift = (-into_corner[0] * t, -into_corner[1] * t)
        press = _prism(
            f"{fid}/press",
            bend,
            [(u + shift[0], z + shift[1]) for u, z in pts],
            centre,
            width,
            profile,
        )
        model.part_cuts.append((bend.parent, press))
        model.part_adds.append((bend.parent, rib))
        if feature.params.get("flat_cutout") is True:
            e = along(bend.w)
            lo = (-depth, -width / 2, -1.0)
            hi = (bend.allowance + depth, width / 2, t + 1.0)
            origin = (bend.p0[0] + e[0] * centre, bend.p0[1] + e[1] * centre)
            cut = oriented_box(f"{fid}/cutout", origin, bend.w, lo, hi)
            model.flat_cuts.append((bend.parent, cut))
        return model, issues
