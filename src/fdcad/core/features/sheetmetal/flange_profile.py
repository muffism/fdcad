"""Edit Flange Profile (TR166 item 1, DECISIONS D1101): an Edge Flange shaped by a sketch.

The Edge Flange's ``refs.profile_sketch`` names a sketch with a closed outline. The
outline is read in the sketch's own coordinates: X runs along the picked edge from
the start of the bend, Y runs up the flange, measured as the flange Length is (so
Y = 0 is where Length starts). The part of the outline above Y = 0 is the flange
wall; where it crosses Y = 0 sets the bend's start and width, so the flange can be
narrower than the edge, wider (the sketch runs past the ends of the edge), notched
or shaped. Where a narrower flange stops inside the edge a relief of the flange's
relief size is cut.

Face roles: the wall's ``<child>/bottom`` and ``<child>/top``, and
``<fid>/profile/side/<entity>`` round the outline.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from OCP.gp import gp_Vec

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError
from fdcad.core.features.sheetmetal.locate import bounds
from fdcad.core.features.sheetmetal.model import (
    along,
    box,
    common_with,
    frame,
    oriented_box,
    translate,
    volume,
)
from fdcad.core.features.sheetmetal.params import Relief
from fdcad.core.features.solids import prism, transform
from fdcad.core.naming.names import NamedShape

if TYPE_CHECKING:
    from fdcad.core.features.sheetmetal.edge_flange import _Plan

_TOL = 1e-6
_BASE = 1e-3  # height of the strip at Y = 0 that finds the bend's width


def has_profile(feature: Feature) -> bool:
    """True when the flange has a profile sketch."""
    return isinstance(feature.refs.get("profile_sketch"), dict)


def profile_plan(
    feature: Feature, ctx: BuildContext, plan: _Plan, relief: Relief, thickness: float
) -> _Plan:
    """``plan`` with its wall cut to the profile and its bend sized to the profile's base."""
    name, fid, t = feature.name, feature.id, thickness
    ref = feature.refs.get("profile_sketch")
    assert isinstance(ref, dict)
    out = ctx.result(str(ref.get("feature"))).sketch
    if out is None or out.profile is None:
        raise FeatureError(
            f"{name}: the flange profile must be a sketch with a closed outline. "
            "Close the profile sketch."
        )
    plane = out.plane
    n = plane.normal
    world = prism(f"{fid}/profile", out.profile, gp_Vec(n[0] * t, n[1] * t, n[2] * t))
    local = transform(world, frame(plane.origin, plane.x_dir, n).Inverted())
    local = translate(local, (0.0, -plan.offset, 0.0))
    lo, hi = bounds(local)
    if hi[1] <= _TOL:
        raise FeatureError(
            f"{name}: the flange profile lies below the edge. Draw it above Y = 0 of its sketch."
        )
    size = max(abs(lo[0]), abs(hi[0]), hi[1]) + 1.0
    above = common_with(fid, local, box(f"{fid}/clip", (-size, 0.0, -1.0), (size, size, t + 1)))
    try:
        base = common_with(fid, above, box(f"{fid}/base", (-size, 0.0, -1.0), (size, _BASE, t + 1)))
        found = volume(base.shape) > _TOL * _BASE
    except FeatureError:
        found = False
    if not found:
        raise FeatureError(
            f"{name}: the flange profile does not reach the edge. Draw the outline down to "
            "Y = 0 of its sketch."
        )
    (x0, _y0, _z0), (x1, _y1, _z1) = bounds(base)
    child = plan.bend.child
    plate = translate(above, (-x0, 0.0, 0.0))
    rename = {
        f"{fid}/profile/cap/start": f"{child}/bottom",
        f"{fid}/profile/cap/end": f"{child}/top",
    }
    plate = NamedShape(plate.shape, [(rename.get(nm, nm), f) for nm, f in plate.faces])
    bend = plan.bend
    e, w = along(bend.w), bend.w
    old = bend.length
    p0 = (bend.p0[0] + e[0] * x0, bend.p0[1] + e[1] * x0)
    bend = replace(bend, p0=p0, length=x1 - x0)
    depth = (plan.pick.a[0] - plan.bend.p0[0]) * w[0] + (plan.pick.a[1] - plan.bend.p0[1]) * w[1]
    cuts: list[NamedShape] = []
    if depth > _TOL:
        reach = depth + t + 1.0
        cuts.append(
            oriented_box(f"{fid}/trim{plan.length_param}", p0, w, (0.0, 0.0, -1.0),
                         (x1 - x0, reach, t + 1.0))
        )  # fmt: skip
        width = relief.width
        for side, (n0, n1) in (("a", (x0 - width, x0)), ("b", (x1, x1 + width))):
            inner = n1 > _TOL if side == "a" else n0 < old - _TOL
            if inner:
                cuts.append(
                    oriented_box(f"{fid}/profile_relief{side}", plan.bend.p0, w,
                                 (max(n0, 0.0), -relief.depth, -1.0),
                                 (min(n1, old), reach, t + 1.0))
                )  # fmt: skip
    return replace(plan, bend=bend, cuts=cuts, relief_ends=[], plate=plate)
