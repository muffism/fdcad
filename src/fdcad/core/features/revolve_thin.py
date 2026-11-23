"""Thin Feature for Revolve and Revolved Cut (TOOL_SPEC T6.1 item 5, DECISIONS D523).

The wall is made exactly as for the extrude (``extrude_thin``, D211) and then
turned with the revolve's own angles and end conditions. The keys are the
extrude's ``thin_*`` keys. A sketch line used as the axis is left out of an open
chain. The wall must stay on one side of the axis.

Cap ends (closed profiles, less than a full turn, ends given by angles): each
angular end gets a flat lid of the cap thickness, the region inside the wall's
outer side moved into the revolve and clipped to the turned region. Lid faces:
``cap/start`` and ``cap/end`` (outer, with the wall's end faces),
``thin_cap/start`` and ``thin_cap/end`` (inner), ``lid_side/...`` and
``lid_clip/...`` (where the clip trims a lid near the axis).
"""

from __future__ import annotations

import copy
import math
from dataclasses import replace

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.gp import gp_Ax1, gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, SketchOutput
from fdcad.core.features.extrude_thin import (
    cap_faces,
    cap_thickness,
    thin_on,
    thin_region_issues,
    thin_sketch,
)
from fdcad.core.features.sketch import PickedSketch
from fdcad.core.features.solids import combine, common, prism, profile_centre, revolve, transform
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.profiles import Profile

_FULL_TURN = 2 * math.pi
_SIDE_TOL = 1e-5  # mm: how far the wall may reach past the axis (offset rounding)
_SAMPLES = 16  # points per wall edge for the axis check


def raw_sketch(feature: Feature, ctx: BuildContext) -> SketchOutput:
    """The feature's sketch output, with or without a closed profile."""
    ref = feature.refs.get("sketch")
    if not isinstance(ref, dict) or "feature" not in ref:
        raise FeatureError(f"{feature.name} has no sketch. Choose a sketch.")
    out = ctx.result(str(ref["feature"])).sketch
    if out is None:
        raise FeatureError(f"{feature.name}: the chosen feature is not a sketch. Pick a sketch.")
    return out


def thin_revolve_sketch(feature: Feature, ctx: BuildContext) -> PickedSketch:
    """The sketch with its profile replaced by the thin wall (the axis line left out)."""
    raw = raw_sketch(feature, ctx)
    axis = feature.refs.get("axis")
    skip = axis.get("sketch_entity") if isinstance(axis, dict) else None
    source = raw
    if isinstance(skip, str) and skip in raw.model.entities:
        model = copy.deepcopy(raw.model)
        del model.entities[skip]
        source = replace(raw, model=model)
    wall = thin_sketch(feature, ctx, source)
    # Keep the whole sketch so the axis line can still be found by its id.
    return PickedSketch(replace(wall, model=raw.model), thin_region_issues(feature))


def check_wall_side(name: str, profile: Profile, axis: gp_Ax1, normal: tuple[float, ...]) -> None:
    """The thin wall must stay on one side of the axis (it may touch it)."""
    loc, d = axis.Location(), axis.Direction()
    # In the sketch plane, the side of a point is the sign of (p - loc) x d . normal.
    side = (
        d.Y() * normal[2] - d.Z() * normal[1],
        d.Z() * normal[0] - d.X() * normal[2],
        d.X() * normal[1] - d.Y() * normal[0],
    )
    sides: set[int] = set()
    for face in profile.faces:
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            curve = BRepAdaptor_Curve(TopoDS.Edge(explorer.Current()))
            explorer.Next()
            t0, t1 = curve.FirstParameter(), curve.LastParameter()
            for k in range(_SAMPLES + 1):
                p = curve.Value(t0 + (t1 - t0) * k / _SAMPLES)
                rel = (p.X() - loc.X(), p.Y() - loc.Y(), p.Z() - loc.Z())
                s = rel[0] * side[0] + rel[1] * side[1] + rel[2] * side[2]
                if abs(s) > _SIDE_TOL:
                    sides.add(1 if s > 0 else -1)
    if len(sides) > 1:
        raise FeatureError(
            f"{name} failed: the thin wall crosses the axis. Make the wall thinner, put it "
            "on the other side with Reverse, or move the profile away from the axis."
        )


def capped(
    feature: Feature,
    ctx: BuildContext,
    tool: NamedShape,
    axis: gp_Ax1,
    span: tuple[float, float] | None,
) -> NamedShape:
    """``tool`` with a lid at each angular end when Cap ends is on.

    ``span`` is the total angle and how far it starts before the sketch, or None
    when an end is not given by an angle.
    """
    if not thin_on(feature):
        return tool
    raw = raw_sketch(feature, ctx)
    lids = cap_faces(feature, raw)
    if lids is None:
        return tool
    name, fid = feature.name, feature.id
    if span is None or span[0] >= _FULL_TURN - 1e-9:
        raise FeatureError(
            f"{name}: Cap ends needs a revolve of less than 360 degrees with angle ends. "
            "Turn it off."
        )
    angle, back = span
    thickness = cap_thickness(feature)
    # The way the revolve turns at the sketch plane: axis direction x (centre - axis).
    loc, d = axis.Location(), axis.Direction()
    c = profile_centre(lids)
    rel = gp_Vec(c[0] - loc.X(), c[1] - loc.Y(), c[2] - loc.Z())
    along = gp_Vec(d.X(), d.Y(), d.Z())
    radial = rel.Subtracted(along.Multiplied(rel.Dot(along)))
    if radial.Magnitude() < 1e-9:
        raise FeatureError(f"{name}: the profile lies on the axis. Move it off the axis.")
    turning = along.Crossed(radial).Normalized()
    region = _turned(f"{fid}/lid_clip", Profile(lids), axis, angle, back)
    out = tool
    for role, at, sign in (("start", -back, 1.0), ("end", angle - back, -1.0)):
        slab = prism(f"{fid}/lid", Profile(list(lids)), turning.Multiplied(sign * thickness))
        turn = gp_Trsf()
        turn.SetRotation(axis, at)
        slab = transform(slab, turn)
        names = []
        for label, f in slab.faces:
            if label.startswith(f"{fid}/lid/cap/start"):
                label = f"{fid}/cap/{role}"
            elif label.startswith(f"{fid}/lid/cap/end"):
                label = f"{fid}/thin_cap/{role}"
            else:
                label = label.replace(f"{fid}/lid/side/", f"{fid}/lid_side/", 1)
            names.append((label, f))
        lid = common(fid, name, NamedShape(slab.shape, names), region)
        out = combine(fid, name, out, lid, "boss")
    return out


def _turned(fid: str, profile: Profile, axis: gp_Ax1, angle: float, back: float) -> NamedShape:
    tool = revolve(fid, profile, axis, angle, False)
    if back:
        turn = gp_Trsf()
        turn.SetRotation(axis, -back)
        tool = transform(tool, turn)
    return tool
