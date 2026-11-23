"""Extrude, boss or cut (FDEF_SPEC 5.3 example).

Params:
- ``operation``: "boss" or "cut".
- ``end_condition``: "blind", "through_all", "through_all_both", "mid_plane" or
  "two_directions" (Direction 1 Blind plus Direction 2).
- ``depth``: length. ``depth2``: length, second direction.
- ``reverse``: boolean, flips the direction.
- ``merge``: boolean, optional (default true). False keeps a boss as a separate body.
- ``end_condition2``: optional, "blind" or "through_all": Direction 2's end condition.
  Not allowed with Mid Plane or Through All Both.
  Direction 2 is on when ``end_condition`` is "two_directions" or this key is
  present (D141). Not allowed with Mid Plane.
- ``start_condition``, ``start_offset``, ``start_reverse``: optional, where the
  feature starts (the From list, see ``extrude_start``).
- ``cut_outside``: optional boolean for cuts: remove the material outside the profile.
- ``print_top``: optional, for cuts: ``teardrop`` or ``flat`` gives every round hole
  the cut makes along a sideways direction a pointed or flat top toward the
  printer's up, as the Hole Tool does (TR175, D784). Faces ``top/<k>/...``.

Refs: ``sketch`` (``{"feature": "f5"}``), for some start conditions ``start``, and
optionally ``regions``: the Selected Regions picks (``fdcad.core.naming.regions``).
Without picks the whole sketch is used.

Phase 2 additions (PHASE2_SPEC P2.1): the end conditions ``up_to_vertex``,
``up_to_face`` and ``offset_from_face`` for either direction (see ``extrude_end``),
draft while extruding (``extrude_draft``) and Thin Feature (``extrude_thin``).

TOOL_SPEC T16 additions: Through All Both (Through All both ways at once, no
Direction 2), and ``up_to_next`` and ``up_to_body`` for either direction (see
``extrude_next``; Up to Body keeps the body pick in ``refs.end`` or ``refs.end2``).

Through All goes through the whole part from the start. For a boss it ends at
the far side of the existing body along the direction (D142).

Face roles: ``cap/start`` (start side), ``cap/end``, ``side/<entity>`` for the face
swept from sketch entity ``<entity>``. Several regions add ``#1``, ``#2`` to caps.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace

from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    PreviewHandle,
    SketchOutput,
    Vec3,
    register,
    ruler_step,
)
from fdcad.core.features.extrude_draft import draft_on, drafted_prism
from fdcad.core.features.extrude_end import (
    END_CONDITIONS,
    End,
    bounded_sweep,
    offset_handle_base,
    resolve_end,
)
from fdcad.core.features.extrude_next import (
    CLIP_CONDITIONS,
    body_reach,
    clip,
    needs_body,
    start_shape,
)
from fdcad.core.features.extrude_start import (
    START_CONDITIONS,
    Start,
    not_on_face,
    resolve_start,
)
from fdcad.core.features.extrude_thin import (
    THIN_TYPES,
    cap_faces,
    cap_thickness,
    thin_on,
    thin_region_issues,
    thin_sketch,
)
from fdcad.core.features.sketch import PickedSketch, sketch_for
from fdcad.core.features.solids import (
    bounding_size,
    check_result,
    combine,
    combine_or_keep,
    common,
    expected_issues,
    extent_along,
    face_area,
    polygon_face,
    prism,
    profile_centre,
    transform,
    volume_of,
)
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.sketch.profiles import Profile
from fdcad.core.units import Kind, UnitSystem

_VOLUME_TOL = 1e-6  # relative
_DRAFT_MARGIN = 1.0  # mm: how far a drafted Through All cut goes past the part


@dataclass
class _Plan:
    """What the extrusion needs: sketch, unit direction, start and the two extents."""

    sketch: SketchOutput
    direction: gp_Vec
    start: Start
    forward: float
    back: float
    issues: list[Issue] = field(default_factory=list)  # from the region picks
    front_end: End | None = None
    back_end: End | None = None
    clip1: str | None = None  # Up to Next or Up to Body (boss) in Direction 1
    clip2: str | None = None


@register
class Extrude(FeatureType):
    """Extrudes a sketch profile and adds it to, or cuts it from, the part."""

    type_name = "extrude"
    makes_solid = True
    params = (
        ParamSpec("operation", choices=("boss", "cut"), default="boss"),
        ParamSpec("print_top", choices=("none", "teardrop", "flat"), optional=True),  # TR175
        ParamSpec(
            "end_condition",
            choices=(
                "blind",
                "through_all",
                "through_all_both",
                "mid_plane",
                "two_directions",
                *END_CONDITIONS,
                *CLIP_CONDITIONS,
            ),
            default="blind",
        ),
        ParamSpec("depth", kind=Kind.LENGTH),
        ParamSpec("depth2", kind=Kind.LENGTH, optional=True),
        ParamSpec("reverse", default=False),
        ParamSpec("merge", default=True, optional=True),
        ParamSpec(
            "end_condition2",
            choices=("blind", "through_all", *END_CONDITIONS, *CLIP_CONDITIONS),
            optional=True,
        ),
        ParamSpec("start_condition", choices=START_CONDITIONS, optional=True),
        ParamSpec("start_offset", kind=Kind.LENGTH, optional=True),
        ParamSpec("start_reverse", default=False, optional=True),
        ParamSpec("cut_outside", default=False, optional=True),
        ParamSpec("auto_operation", default=False, optional=True),  # TR334 (D2110)
        ParamSpec("auto_alternate", default=False, optional=True),
        # Sheet metal cuts: the Blind depth is the sheet thickness (TR30.1, D696).
        ParamSpec("link_thickness", default=False, optional=True),
        # Sheet metal cuts are square to the sheet unless this is false (TR12.2, D700).
        ParamSpec("normal_cut", default=True, optional=True),
        ParamSpec("end_offset", kind=Kind.LENGTH, optional=True),
        ParamSpec("end_offset2", kind=Kind.LENGTH, optional=True),
        ParamSpec("end_offset_reverse", default=False, optional=True),
        ParamSpec("end_offset_reverse2", default=False, optional=True),
        ParamSpec("end_translate", default=False, optional=True),
        ParamSpec("end_translate2", default=False, optional=True),
        ParamSpec("depth_along", choices=("direction", "normal"), optional=True),  # TR239
        ParamSpec("end_twist", kind=Kind.ANGLE, optional=True),  # TR240
        ParamSpec("profile_offset", kind=Kind.LENGTH, optional=True),  # TR344
        ParamSpec("end_scale", kind=Kind.NUMBER, optional=True),
        ParamSpec("draft_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("draft_angle2", kind=Kind.ANGLE, optional=True),
        ParamSpec("draft_outward", default=False, optional=True),
        ParamSpec("draft_outward2", default=False, optional=True),
        ParamSpec("thin_type", choices=THIN_TYPES, optional=True),
        ParamSpec("thin_thickness", kind=Kind.LENGTH, optional=True),
        ParamSpec("thin_thickness2", kind=Kind.LENGTH, optional=True),
        ParamSpec("thin_reverse", default=False, optional=True),
        ParamSpec("thin_cap", default=False, optional=True),
        ParamSpec("thin_cap_thickness", kind=Kind.LENGTH, optional=True),
        ParamSpec("flip_side", default=False, optional=True),  # TR157 (D1023)
        ParamSpec("thin_merge_ends", default=False, optional=True),  # TR272 (D1025)
        ParamSpec("thin_fillet", default=False, optional=True),  # TR65
        ParamSpec("thin_fillet_radius", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Build the extrusion and combine it with the part."""
        auto = ""
        from fdcad.core.features import extrude_auto

        if extrude_auto.wanted(feature):  # TR334 (D2110): choose from where it sits
            import copy as _copy

            probe = _copy.deepcopy(feature)
            probe.params["operation"] = "boss"
            probe.params.pop("cut_outside", None)
            plan = self._plan(probe, ctx)
            shape = self._per_region(probe, ctx) or self._solid(probe, ctx, plan)
            body_shape = ctx.body.shape if ctx.body is not None else None
            feature, auto = extrude_auto.resolved(feature, shape.shape, body_shape)
        result = self._execute(feature, ctx)
        if auto:
            result.extras["operation"] = auto
        return result

    def _execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        operation = str(self.setting(feature, "operation", "boss"))
        plan = self._plan(feature, ctx)
        tool = self._per_region(feature, ctx) or self._solid(feature, ctx, plan)
        square = self._normal_cut(feature, ctx, tool, operation)
        if square is not None:
            square.issues = plan.issues + plan.start.issues + square.issues
            return square
        from fdcad.core.features.extrude_open import merge_ends_on, merged_ends_tool

        if merge_ends_on(feature) and ctx.body is not None:  # TR272 (D1025)
            import copy as _copy

            plain = _copy.deepcopy(feature)
            plain.params.pop("thin_merge_ends", None)
            drawn = self._solid(plain, ctx, self._plan(plain, ctx))
            tool = merged_ends_tool(feature.id, feature.name, ctx.body, tool, drawn)
        picked: list[Issue] = []
        body = combine_or_keep(feature, ctx.body, tool, operation, ctx, picked)
        if operation == "cut" and not _cut_outside(feature):
            body = _print_tops(feature, ctx, tool, body)
        thickness = "depth" if direction1(feature) == "blind" else None
        issues = check_result(feature.id, feature.name, ctx.body, body, thickness)
        issues = picked + expected_issues(feature, issues)
        if operation == "cut" and ctx.body is not None:
            issues += cut_misses(feature, ctx.body, body)
        return FeatureResult(body=body, issues=plan.issues + plan.start.issues + issues)

    @staticmethod
    def _normal_cut(
        feature: Feature, ctx: BuildContext, tool: NamedShape, operation: str
    ) -> FeatureResult | None:
        """A cut in a sheet metal part cuts square to the sheet (TR12.2, D700), unless
        ``normal_cut`` is off, the cut is outside, or it acts on picked bodies."""
        if operation != "cut" or feature.params.get("normal_cut", True) is False:
            return None
        if _cut_outside(feature) or feature.params.get("bodies_scope") == "selected":
            return None
        from fdcad.core.features.bodies import join
        from fdcad.core.features.sheetmetal.common import current_sheets
        from fdcad.core.features.sheetmetal.model import SheetResult
        from fdcad.core.features.sheetmetal.normal_cut import normal_cut
        from fdcad.core.features.solids import compound, reached_bodies, solids

        if ctx.body is None:
            return None
        # The sheet the cut reaches (D1080). The newest sheet of the part was taken,
        # whichever body the cut was in, and its solid was handed back alone: in a part
        # of several bodies a hole in one sheet removed every other body, and a hole
        # in any sheet but the newest was not made at all.
        sheets = current_sheets(feature, ctx)
        if not sheets:  # no sheet metal in the part: nothing to measure
            return None
        pieces = solids(ctx.body.shape)
        hit = {id(pieces[i]) for i in reached_bodies(ctx.body.shape, tool.shape)}
        if not hit:
            return None
        chosen = None
        for last in sheets:
            own = last.own or last.body
            assert own is not None
            mine = [p for p in pieces if any(p.IsSame(s) for s in solids(own.shape))]
            if not any(id(p) in hit for p in mine):
                continue
            if chosen is not None or len(hit) > len(mine):
                return None  # it reaches another body too: a plain cut through them all
            chosen = (last, mine)
        if chosen is None:
            return None
        last, mine = chosen
        assert last.sheet is not None
        model, leftover = normal_cut(last.sheet.copy(), tool, feature.id)
        if leftover is not None:
            # A cut across a bend keeps the plain cut, which the flat pattern takes in by
            # wrapping it round the bend exactly (D541).
            return None
        own_body = model.build(feature.id, feature.name)
        others = [p for p in pieces if not any(p is m for m in mine)]
        body = own_body
        if others:
            rest = NamedShape(compound(others), list(ctx.body.faces))
            body = join([own_body, rest], feature.id) or own_body
        issues = check_result(feature.id, feature.name, ctx.body, body, None)
        return SheetResult(body=body, issues=issues, sheet=model, own=own_body)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The solid the feature adds, or for a cut the material it removes."""
        plan = self._plan(feature, ctx)
        tool = self._per_region(feature, ctx) or self._solid(feature, ctx, plan)
        if _cut_outside(feature) and ctx.body is not None:
            return common(feature.id, feature.name, ctx.body, tool)
        return tool

    def _per_region(self, feature: Feature, ctx: BuildContext) -> NamedShape | None:
        """Selected Regions with a depth of their own (TR242, D842): one extrusion per
        region, joined; None when no region has its own depth. A region without one
        uses the feature's depth."""
        import copy as _copy

        picks = feature.refs.get("regions")
        if not isinstance(picks, list) or not any(
            isinstance(p, dict) and isinstance(p.get("depth"), dict) for p in picks
        ):
            return None
        name = feature.name
        if direction1(feature) != "blind" or direction2(feature) is not None or thin_on(feature):
            raise FeatureError(
                f"{name}: a depth per region works with one Blind direction and no Thin "
                "Feature. Change the end condition, or give the regions one depth."
            )
        if _cut_outside(feature):
            raise FeatureError(f"{name}: a depth per region cannot cut outside. Turn it off.")
        out: NamedShape | None = None
        for k, pick in enumerate(picks):
            if not isinstance(pick, dict):
                continue
            sub = _copy.deepcopy(feature)
            sub.refs["regions"] = [{key: v for key, v in pick.items() if key != "depth"}]
            own = pick.get("depth")
            if isinstance(own, dict):
                try:
                    value = float(own["value"])
                except (KeyError, TypeError, ValueError):
                    raise FeatureError(
                        f"{name}: Region {k + 1} has a damaged depth. Type it again."
                    ) from None
                if value <= 0:
                    raise FeatureError(
                        f"{name}: Region {k + 1} needs a depth greater than zero. Enter a depth."
                    )
                sub.params["depth"] = Param(str(own.get("expr", value)), value)
            piece = self._solid(sub, ctx, self._plan(sub, ctx))
            if k:
                prefix = f"{feature.id}/"
                piece = NamedShape(
                    piece.shape,
                    [
                        (
                            n.replace(prefix, f"{prefix}r{k + 1}/", 1)
                            if n.startswith(prefix)
                            else n,
                            f,
                        )
                        for n, f in piece.faces
                    ],
                )
            out = piece if out is None else combine(feature.id, name, out, piece, "boss")
        return out

    # Planning --------------------------------------------------------------------

    def _plan(self, feature: Feature, ctx: BuildContext) -> _Plan:
        name = feature.name
        operation = str(self.setting(feature, "operation", "boss"))
        condition = str(self.setting(feature, "end_condition", "blind"))
        picked = extrude_sketch(feature, ctx)
        sketch = picked.sketch
        assert sketch.profile is not None
        if _cut_outside(feature) and operation != "cut":
            raise FeatureError(f"{name}: Cut Outside works only for cuts. Turn it off.")
        if condition == "mid_plane" and "end_condition2" in feature.params:
            raise FeatureError(
                f"{name}: Direction 2 is not available with Mid Plane. "
                "Turn off Direction 2 or choose Blind."
            )
        if condition == "through_all_both" and "end_condition2" in feature.params:
            raise FeatureError(
                f"{name}: Direction 2 is not available with Through All Both. "
                "Turn off Direction 2 or choose Through All."
            )
        direction = self._direction(feature, sketch, ctx)
        start = resolve_start(feature, ctx, sketch)
        unit = (direction.X(), direction.Y(), direction.Z())
        first = direction1(feature)
        depth = self.number(feature, "depth") if first in ("blind", "mid_plane") else 0.0
        if first == "blind" and feature.params.get("link_thickness") is True:
            depth = sheet_thickness(feature, ctx)
        back = 0.0
        front_end: End | None = None
        back_end: End | None = None
        clips: dict[str, str | None] = {"": None, "2": None}
        if first in END_CONDITIONS:
            front_end = resolve_end(feature, ctx, sketch, start, unit, first)
            forward = front_end.distance if front_end.distance is not None else 1.0
        elif first == "through_all":
            forward = self._through_all(feature, ctx, sketch, start, unit)
        elif first == "through_all_both":
            minus = (-unit[0], -unit[1], -unit[2])
            forward = self._through_all(feature, ctx, sketch, start, unit, True)
            back = self._through_all(feature, ctx, sketch, start, minus, True)
            if forward + back <= 1e-6:
                raise FeatureError(
                    f"{name}: Through All Both finds no body in either direction. "
                    "Choose Blind, or move the sketch onto the part."
                )
        elif first in CLIP_CONDITIONS:
            forward, clips[""] = self._clip_reach(feature, ctx, sketch, start, unit, first, "")
        elif first == "mid_plane":
            forward = back = depth / 2
        else:
            forward = depth
        second = direction2(feature)
        if second == "blind":
            back = self.number(feature, "depth2")
            if back <= 0:
                raise FeatureError(
                    f"{name}: Depth 2 must be greater than zero. Enter a larger depth."
                )
        elif second == "through_all":
            back = self._through_all(feature, ctx, sketch, start, (-unit[0], -unit[1], -unit[2]))
        elif second in END_CONDITIONS:
            minus = (-unit[0], -unit[1], -unit[2])
            back_end = resolve_end(feature, ctx, sketch, start, minus, second, "2")
            back = back_end.distance if back_end.distance is not None else 1.0
        elif second in CLIP_CONDITIONS:
            minus = (-unit[0], -unit[1], -unit[2])
            back, clips["2"] = self._clip_reach(feature, ctx, sketch, start, minus, second, "2")
        if first == "through_all_both":
            pass  # one side may be empty; checked above
        elif forward <= 0 or (first == "mid_plane" and depth <= 0):
            raise FeatureError(f"{name}: Depth must be greater than zero. Enter a positive depth.")
        issues = (front_end.issues if front_end else []) + (back_end.issues if back_end else [])
        start.issues = start.issues + issues
        if front_end is not None and front_end.surface is None:
            front_end = None  # a plain depth after all
        if back_end is not None and back_end.surface is None:
            back_end = None
        if (clips[""] or clips["2"]) and draft_on(feature):
            raise FeatureError(_DRAFT_NEEDS_DEPTH.format(name=name))
        if first == "through_all_both" and draft_on(feature):
            raise FeatureError(
                f"{name}: draft is not available with Through All Both. "
                "Turn the draft off or choose Through All."
            )
        return _Plan(
            sketch,
            direction,
            start,
            forward,
            back,
            picked.issues,
            front_end,
            back_end,
            clips[""],
            clips["2"],
        )

    def _clip_reach(
        self,
        feature: Feature,
        ctx: BuildContext,
        sketch: SketchOutput,
        start: Start,
        unit: Vec3,
        condition: str,
        which: str,
    ) -> tuple[float, str | None]:
        """How far an Up to Next or Up to Body direction sweeps, and whether it is clipped."""
        if ctx.body is None:
            raise needs_body(feature.name, condition)
        operation = str(self.setting(feature, "operation", "boss"))
        if condition == "up_to_body" and operation == "cut":
            level = _start_level(sketch, start, unit)
            return body_reach(feature, ctx, unit, level, which), None
        assert sketch.profile is not None
        shapes = [ctx.body.shape, *sketch.profile.faces]
        if start.surface is not None:
            shapes.append(start.surface)
        return 2 * bounding_size(*shapes) + 10.0 + abs(start.shift), condition

    @staticmethod
    def _direction(
        feature: Feature, sketch: SketchOutput, ctx: BuildContext | None = None
    ) -> gp_Vec:
        """The way the extrusion goes: the sketch's normal, or a picked direction (TR239,
        D815). Along a picked direction the depth is measured along it, or square to the
        sketch with ``depth_along`` "normal" (the vector then has a normal part of 1)."""
        nx, ny, nz = sketch.plane.normal
        sign = -1.0 if feature.params.get("reverse", False) else 1.0
        ref = feature.refs.get("direction")
        if ctx is None or not isinstance(ref, (dict, list)) or not ref:
            return gp_Vec(nx * sign, ny * sign, nz * sign)
        from fdcad.core.features.geometry_refs import resolve_placement

        if isinstance(ref, list):
            ref = ref[0]
        d = resolve_placement(ctx, ref, feature.name, "direction").direction
        along = d[0] * nx + d[1] * ny + d[2] * nz
        if abs(along) < 0.017:  # within about 1 degree of the sketch plane
            raise FeatureError(
                f"{feature.name}: the direction lies in the sketch plane, so the profile would "
                "not leave it. Pick a direction that points out of the sketch."
            )
        if along < 0:
            d, along = (-d[0], -d[1], -d[2]), -along
        if feature.params.get("depth_along") == "normal":
            d = (d[0] / along, d[1] / along, d[2] / along)
        return gp_Vec(d[0] * sign, d[1] * sign, d[2] * sign)

    def _through_all(
        self,
        feature: Feature,
        ctx: BuildContext,
        sketch: SketchOutput,
        start: Start,
        unit: Vec3,
        optional: bool = False,
    ) -> float:
        """How far Through All reaches from the start along ``unit``.

        ``optional`` (Through All Both): a boss side with no body gives 0.
        """
        name = feature.name
        operation = str(self.setting(feature, "operation", "boss"))
        if ctx.body is None:
            if operation == "cut":
                raise FeatureError(f"{name} has nothing to cut. Add a boss feature first.")
            raise FeatureError(
                f"{name}: Through All needs a body to go through. Choose Blind, "
                "or add a body first."
            )
        assert sketch.profile is not None
        if operation == "cut" and draft_on(feature):
            # A draft leans along the whole sweep: end just past the part (bug hunt E2).
            span = extent_along(ctx.body.shape, unit)
            far = span[1] - _start_level(sketch, start, unit) if span is not None else 0.0
            if far > 1e-6:
                return far + _DRAFT_MARGIN
        if operation == "cut":
            shapes = [ctx.body.shape, *sketch.profile.faces]
            if start.surface is not None:
                shapes.append(start.surface)
            return 2 * bounding_size(*shapes) + 10.0 + abs(start.shift)
        from fdcad.core.features.bodies import scope_body

        scope = scope_body(feature, ctx) or ctx.body
        body = extent_along(scope.shape, unit)
        level = _start_level(sketch, start, unit)
        far = body[1] - level if body is not None else 0.0
        if far <= 1e-6 and optional:
            return 0.0
        if far <= 1e-6:
            raise FeatureError(
                f"{name}: Through All finds no body in that direction. "
                "Reverse the direction or choose Blind."
            )
        return far

    # Building --------------------------------------------------------------------

    def _solid(self, feature: Feature, ctx: BuildContext, plan: _Plan) -> NamedShape:
        """The extruded solid, or for Cut Outside the material outside it."""
        from fdcad.core.features.law_sections import extrude_law_on, law_extrude

        if extrude_law_on(feature):  # TR240 (D816)
            return self._law_tool(feature, plan, law_extrude)
        tool = self._clipped(feature, ctx, plan, None)
        tool = self._capped(feature, ctx, plan, tool)
        if not _cut_outside(feature):
            return tool
        if ctx.body is None:
            raise FeatureError(f"{feature.name} has nothing to cut. Add a boss feature first.")
        region = self._clipped(feature, ctx, plan, self._big_face(ctx, plan))
        return combine(feature.id, feature.name, region, tool, "cut")

    def _law_tool(
        self, feature: Feature, plan: _Plan, make: Callable[..., NamedShape]
    ) -> NamedShape:
        """End twist and end scale (TR240): a blind extrusion from the sketch plane."""
        from OCP.gp import gp_Pnt

        name = feature.name
        if direction1(feature) != "blind" or plan.back > 0 or plan.back_end is not None:
            raise FeatureError(
                f"{name}: an end twist or scale needs a Blind extrusion in one direction. "
                "Choose Blind and turn off Direction 2."
            )
        if plan.start.surface is not None or abs(plan.start.shift) > 1e-12:
            raise FeatureError(
                f"{name}: an end twist or scale starts on the sketch plane. Set From to "
                "Sketch Plane."
            )
        if feature.params.get("draft_angle") is not None or thin_on(feature):
            raise FeatureError(
                f"{name}: an end twist or scale cannot be used with draft or Thin Feature. "
                "Turn those off."
            )
        sketch = plan.sketch
        assert sketch.profile is not None
        c = profile_centre(sketch.profile.faces)
        d = plan.direction
        length = plan.forward * d.Magnitude()
        return make(feature, sketch.profile, d.Normalized(), length, gp_Pnt(*c))

    def _clipped(
        self, feature: Feature, ctx: BuildContext, plan: _Plan, face: TopoDS_Face | None
    ) -> NamedShape:
        """The sweep, with Up to Next and Up to Body directions clipped (T16 item 1).

        Without clipped directions this is the plain sweep. Otherwise each
        direction is swept on its own, clipped when it needs it, and the two fused.
        """
        if plan.clip1 is None and plan.clip2 is None:
            return self._sweep(feature, ctx, plan, face)
        fid, name = feature.id, feature.name
        operation = str(self.setting(feature, "operation", "boss"))
        sketch = plan.sketch
        begin = start_shape(sketch, plan.start, face)
        one = replace(plan, back=0.0, back_end=None)
        d = plan.direction
        tool = self._sweep(feature, ctx, one, face)
        if plan.clip1 is not None:
            unit = (d.X(), d.Y(), d.Z())
            tool = clip(feature, ctx, tool, plan.clip1, operation, unit, begin, "")
        if plan.back <= 0 and plan.back_end is None:
            return tool
        minus = d.Reversed()
        two = replace(plan, direction=minus, forward=plan.back, back=0.0, front_end=plan.back_end)
        two = replace(two, back_end=None)
        other = self._sweep(feature, ctx, two, face)
        if plan.clip2 is not None:
            unit2 = (minus.X(), minus.Y(), minus.Z())
            other = clip(feature, ctx, other, plan.clip2, operation, unit2, begin, "2")
        # Direction 2's far end is the start side of the whole feature.
        names = []
        for n, f in other.faces:
            if n.startswith(f"{fid}/cap/start"):
                continue
            names.append((n.replace(f"{fid}/cap/end", f"{fid}/cap/start", 1), f))
        other = NamedShape(other.shape, names)
        return combine(fid, name, tool, other, "boss")

    def _big_face(self, ctx: BuildContext, plan: _Plan) -> TopoDS_Face:
        """A square on the sketch plane, larger than the part and the profile."""
        sketch = plan.sketch
        assert sketch.profile is not None
        shapes = list(sketch.profile.faces)
        if ctx.body is not None:
            shapes.append(ctx.body.shape)
        size = 2 * bounding_size(*shapes) + 10.0
        u, v, _h = sketch.plane.to_2d(*profile_centre(sketch.profile.faces))
        corners = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            p = sketch.plane.to_3d(u + su * size, v + sv * size)
            corners.append((p.X(), p.Y(), p.Z()))
        return polygon_face(corners)

    def _sweep(
        self, feature: Feature, ctx: BuildContext, plan: _Plan, face: TopoDS_Face | None
    ) -> NamedShape:
        """Sweep the profile (or ``face``, a plain region) from the start."""
        sketch, d, start = plan.sketch, plan.direction, plan.start
        assert sketch.profile is not None
        profile = sketch.profile if face is None else Profile([face])
        total = plan.forward + plan.back
        if plan.front_end is not None or plan.back_end is not None:
            if draft_on(feature):
                raise FeatureError(_DRAFT_NEEDS_DEPTH.format(name=feature.name))
            front = plan.front_end or End(distance=plan.forward)
            back = plan.back_end or (End(distance=plan.back) if plan.back > 0 else None)
            return bounded_sweep(feature, ctx, sketch, profile, start, d, front, back)
        if draft_on(feature) and face is None:
            if start.surface is not None:
                raise FeatureError(_DRAFT_NEEDS_DEPTH.format(name=feature.name))
            return drafted_prism(
                feature, profile, sketch.plane, d, start.shift, plan.forward, plan.back
            )
        if start.surface is None:
            n = sketch.plane.normal
            shift = gp_Vec(n[0] * start.shift, n[1] * start.shift, n[2] * start.shift)
            tool = prism(feature.id, profile, d.Multiplied(total))
            offset = shift.Added(d.Multiplied(-plan.back))
            if offset.Magnitude() > 0:
                move = gp_Trsf()
                move.SetTranslation(offset)
                tool = transform(tool, move)
            return tool
        return self._carried(feature, ctx, plan, profile, face is None)

    def _carried(
        self, feature: Feature, ctx: BuildContext, plan: _Plan, profile: Profile, check: bool
    ) -> NamedShape:
        """Sweep onto a face or a slanted plane: a long prism cut to the start surface."""
        sketch, d, start = plan.sketch, plan.direction, plan.start
        assert start.surface is not None and sketch.profile is not None
        fid, total = feature.id, plan.forward + plan.back
        shapes = [start.surface, *profile.faces]
        if ctx.body is not None:
            shapes.append(ctx.body.shape)
        reach = 2 * bounding_size(*shapes) + total + 10.0
        long = prism(fid, profile, d.Multiplied(2 * reach))
        move = gp_Trsf()
        move.SetTranslation(d.Multiplied(-reach))
        long = transform(long, move)
        long = NamedShape(long.shape, [(n, f) for n, f in long.faces if "/cap/" not in n])
        slab = self._slab(fid, start.surface, d, plan.forward, plan.back)
        tool = common(fid, feature.name, long, slab)
        if check:
            expected = face_area(sketch.profile.faces) * total
            if abs(volume_of(tool.shape) - expected) > _VOLUME_TOL * expected:
                raise not_on_face(feature.name)
        return tool

    @staticmethod
    def _slab(fid: str, surface: TopoDS_Face, d: gp_Vec, forward: float, back: float) -> NamedShape:
        """The space between the start surface moved back by ``back`` and forward by ``forward``."""
        maker = BRepPrimAPI_MakePrism(surface, d.Multiplied(forward + back))
        maker.Build()
        if not maker.IsDone():
            raise FeatureError("The From face could not be swept. Pick another face.")
        names = [
            (f"{fid}/cap/start", TopoDS.Face(maker.FirstShape())),
            (f"{fid}/cap/end", TopoDS.Face(maker.LastShape())),
        ]
        slab = NamedShape(maker.Shape(), restrict(names, maker.Shape(), f"{fid}/limit"))
        if back:
            move = gp_Trsf()
            move.SetTranslation(d.Multiplied(-back))
            slab = transform(slab, move)
        return slab

    def _capped(
        self, feature: Feature, ctx: BuildContext, plan: _Plan, tool: NamedShape
    ) -> NamedShape:
        """A thin closed profile with Cap ends gets a lid at each end (P2.1 item 3)."""
        if not thin_on(feature):
            return tool
        raw = sketch_input_raw(feature, ctx)
        lids = cap_faces(feature, raw)
        if lids is None:
            return tool
        clipped = plan.clip1 is not None or plan.clip2 is not None
        if plan.start.surface is not None or plan.front_end or plan.back_end or clipped:
            raise FeatureError(
                f"{feature.name}: Cap ends needs a flat start and Blind ends. Turn it off."
            )
        lid = cap_thickness(feature)
        if 2 * lid >= plan.forward + plan.back:
            raise FeatureError(
                f"{feature.name}: the caps are thicker than the depth. Use thinner caps."
            )
        d, n, shift = plan.direction, plan.sketch.plane.normal, plan.start.shift
        fid = feature.id
        out = tool
        for at, role in ((-plan.back, "start"), (plan.forward - lid, "end")):
            slab = prism(f"{fid}/lid", Profile(lids), d.Multiplied(lid))
            move = gp_Trsf()
            offset = gp_Vec(n[0] * shift, n[1] * shift, n[2] * shift).Added(d.Multiplied(at))
            move.SetTranslation(offset)
            slab = transform(slab, move)
            names = []
            for nm, f in slab.faces:
                if nm.startswith(f"{fid}/lid/cap/"):
                    outer = nm.startswith(f"{fid}/lid/cap/{'start' if role == 'start' else 'end'}")
                    nm = f"{fid}/cap/{role}" if outer else f"{fid}/thin_cap/{role}"
                else:
                    nm = nm.replace(f"{fid}/lid/side/", f"{fid}/lid_side/", 1)
                names.append((nm, f))
            out = combine(fid, feature.name, out, NamedShape(slab.shape, names), "boss")
        return out

    # Handles ---------------------------------------------------------------------

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """Drag arrows at the ends of the extrusion (one per blind direction)."""
        sketch = extrude_sketch(feature, ctx).sketch
        assert sketch.profile is not None
        start = resolve_start(feature, ctx, sketch)
        d = self._direction(feature, sketch, ctx)
        unit = (d.X(), d.Y(), d.Z())
        base = _start_point(sketch, start, unit)
        first, second = direction1(feature), direction2(feature)
        inch = ctx.document.units is UnitSystem.IN
        step = ruler_step(bounding_size(*sketch.profile.faces), inch)
        handles: list[PreviewHandle] = []
        if first == "mid_plane":
            depth = self.number(feature, "depth")
            return [PreviewHandle("depth", base, unit, depth, 2.0, step=step, snaps=True)]
        if first == "blind":
            depth = self.number(feature, "depth")
            # Only a lone Blind direction flips when dragged past the start (T5.2.5, D147).
            flips = second is None
            handles.append(
                PreviewHandle("depth", base, unit, depth, step=step, flips=flips, snaps=True)
            )
        if second == "blind":
            back = (-unit[0], -unit[1], -unit[2])
            depth2 = self.number(feature, "depth2")
            handles.append(PreviewHandle("depth2", base, back, depth2, step=step, snaps=True))
        # Offset from Face keeps an arrow for the offset (T16 item 3).
        for which, condition, sign in (("", first, 1.0), ("2", second, -1.0)):
            if condition != "offset_from_face":
                continue
            along = (unit[0] * sign, unit[1] * sign, unit[2] * sign)
            at = offset_handle_base(feature, ctx, sketch, start, along, base, which)
            offset = feature.params.get(f"end_offset{which}")
            if at is None or not isinstance(offset, Param):
                continue
            beyond = feature.params.get(f"end_offset_reverse{which}") is True
            toward = 1.0 if beyond else -1.0
            pointing = (along[0] * toward, along[1] * toward, along[2] * toward)
            handles.append(
                PreviewHandle(f"end_offset{which}", at, pointing, offset.value, step=step)
            )
        return handles


_DRAFT_NEEDS_DEPTH = (
    "{name}: draft needs a flat start and an end given by a depth. "
    "Choose Blind or Up to Vertex, or turn the draft off."
)


def sketch_input_raw(feature: Feature, ctx: BuildContext) -> SketchOutput:
    """The feature's sketch output, with or without a closed profile."""
    ref = feature.refs.get("sketch")
    if not isinstance(ref, dict) or "feature" not in ref:
        raise FeatureError(f"{feature.name} has no sketch. Choose a sketch.")
    out = ctx.result(str(ref["feature"])).sketch
    if out is None:
        raise FeatureError(f"{feature.name}: the chosen feature is not a sketch. Pick a sketch.")
    return out


def extrude_sketch(feature: Feature, ctx: BuildContext) -> PickedSketch:
    """The sketch to extrude: its picked regions (T5.3), or the thin wall around its curves."""
    if thin_on(feature):
        picked = PickedSketch(
            thin_sketch(feature, ctx, sketch_input_raw(feature, ctx)),
            thin_region_issues(feature),
        )
    else:
        raw = sketch_input_raw(feature, ctx)
        from fdcad.core.features.extrude_open import open_cut_sketch, wants_open_cut

        if wants_open_cut(feature, raw):  # TR157 (D1023): cut on one side of an open line
            picked = PickedSketch(open_cut_sketch(feature, ctx, raw))
        else:
            picked = sketch_for(feature, ctx)
    grow = feature.params.get("profile_offset")
    if isinstance(grow, Param) and abs(grow.value) > 1e-12:  # TR344 (D880)
        from fdcad.core.features.profile_offset import offset_sketch

        picked.sketch = offset_sketch(picked.sketch, grow.value, feature.name)
    return picked


def direction1(feature: Feature) -> str:
    """Direction 1's end condition, with "two_directions" read as "blind"."""
    condition = str(feature.params.get("end_condition", "blind"))
    return "blind" if condition == "two_directions" else condition


def direction2(feature: Feature) -> str | None:
    """Direction 2's end condition, or None when Direction 2 is off (D141)."""
    stored = feature.params.get("end_condition2")
    if isinstance(stored, str):
        return stored
    return "blind" if feature.params.get("end_condition") == "two_directions" else None


def _print_tops(
    feature: Feature, ctx: BuildContext, tool: NamedShape, body: NamedShape
) -> NamedShape:
    """Cut the teardrop or flat tops of the round holes the cut made (TR175, D784)."""
    kind = feature.params.get("print_top")
    from fdcad.core.features.hole import PRINT_TOPS, print_up, top_prism

    if kind not in PRINT_TOPS:
        return body
    import math

    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_SurfaceType

    from fdcad.core.features.solids import combine, compound

    up = print_up(ctx)
    prisms: list[NamedShape] = []
    for k, (_name, face) in enumerate(tool.faces, start=1):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
        if u1 - u0 < 2 * math.pi - 1e-6:
            continue  # only whole round holes
        cyl = surface.Cylinder()
        axis = cyl.Axis()
        loc, d = axis.Location(), axis.Direction()
        dv = (d.X(), d.Y(), d.Z())
        start = (loc.X() + dv[0] * v0, loc.Y() + dv[1] * v0, loc.Z() + dv[2] * v0)
        prism = top_prism(f"{feature.id}/top/{k}", start, dv, cyl.Radius(), v1 - v0, up, kind)
        if prism is not None:
            prisms.append(prism)
    if not prisms:
        return body
    shape = prisms[0].shape if len(prisms) == 1 else compound([p.shape for p in prisms])
    whole = NamedShape(shape, [n for p in prisms for n in p.faces])
    return combine(feature.id, feature.name, body, whole, "cut")


def _cut_outside(feature: Feature) -> bool:
    return feature.params.get("cut_outside", False) is True


def _start_level(sketch: SketchOutput, start: Start, unit: Vec3) -> float:
    """The lowest point of the start along ``unit``."""
    if start.surface is not None:
        span = extent_along(start.surface, unit)
        if span is not None:
            return span[0]
    o, n = sketch.plane.origin, sketch.plane.normal
    p = (o[0] + n[0] * start.shift, o[1] + n[1] * start.shift, o[2] + n[2] * start.shift)
    return p[0] * unit[0] + p[1] * unit[1] + p[2] * unit[2]


def _start_point(sketch: SketchOutput, start: Start, unit: Vec3) -> Vec3:
    """Where the profile centre lands on the start, for the drag handles."""
    assert sketch.profile is not None
    c = profile_centre(sketch.profile.faces)
    if start.surface is None:
        n = sketch.plane.normal
        return (c[0] + n[0] * start.shift, c[1] + n[1] * start.shift, c[2] + n[2] * start.shift)
    from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector

    hits = IntCurvesFace_ShapeIntersector()
    hits.Load(start.surface, 1e-7)
    hits.Perform(gp_Lin(gp_Pnt(*c), gp_Dir(*unit)), -1e9, 1e9)
    if hits.IsDone() and hits.NbPnt() > 0:
        p = hits.Pnt(1)
        return (p.X(), p.Y(), p.Z())
    t = _start_level(sketch, start, unit) - sum(c[i] * unit[i] for i in range(3))
    return (c[0] + unit[0] * t, c[1] + unit[1] * t, c[2] + unit[2] * t)


def sheet_thickness(feature: Feature, ctx: BuildContext) -> float:
    """The thickness of the sheet metal part before ``feature`` (Link to thickness,
    TR30.1). Raises FeatureError when the part is not sheet metal."""
    from fdcad.core.features.sheetmetal.common import latest_sheet

    last, _blocker = latest_sheet(feature, ctx)
    sheet = getattr(last, "sheet", None) if last is not None else None
    if sheet is None:
        raise FeatureError(
            f"{feature.name}: Link to thickness needs a sheet metal part above it. "
            "Turn it off or type a depth."
        )
    return float(sheet.thickness)


def _on_surface(shape: TopoDS_Shape, point: gp_Pnt) -> bool:
    """True when ``point`` lies on the boundary of one of the solids of
    ``shape``."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_ON, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer

    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = explorer.Current()
        explorer.Next()
        box = Bnd_Box()
        BRepBndLib.Add_s(solid, box)
        box.Enlarge(1e-6)
        if box.IsOut(point):
            continue
        if BRepClass3d_SolidClassifier(solid, point, 1e-6).State() == TopAbs_ON:
            return True
    return False


def cut_misses(feature: Feature, before: NamedShape, body: NamedShape) -> list[Issue]:
    """A warning when a cut removed no material (D1086).

    Each face a cut leaves in the part has the removed material on its outer side.
    So just outside one of them, the part before the cut was solid, unless the cut
    removed nothing. A cut drawn on a face of the part and pointing away from it
    built that way with no word. (Whether the cut's faces are in the part at all
    does not tell: a cut that only touches the part gives its name to the face it
    touches.) A few faces are enough; each costs one point test.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepTools import BRepTools
    from OCP.GeomLProp import GeomLProp_SLProps
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_IN, TopAbs_REVERSED

    from fdcad.core.features.base import FeatureState
    from fdcad.core.occ import point_inside

    prefix = f"{feature.id}/"
    # A face of the cut with no name from the part before is a new surface left inside
    # the old material, so the cut removed some (D2614). Only faces that also carry a
    # name of the part (the cut only touches there) need the point test, which costs
    # about 2 ms on a part of 200 faces.
    looked = 0
    for name, face in body.faces:
        if not name.startswith(prefix):
            continue
        looked += 1
        if looked > 12:
            break
        if all(n.startswith(prefix) for n in body.names_of(face)):
            return []
    tried = 0
    for name, face in body.faces:
        if not name.startswith(prefix):
            continue
        tried += 1
        if tried > 12:
            return []  # not worth more tests: call it a cut
        u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
        surface = BRep_Tool.Surface_s(face)
        for fu, fv in ((0.5, 0.5), (0.3, 0.6), (0.7, 0.4), (0.2, 0.2), (0.8, 0.8)):
            u, v = u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv
            if BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7).State() != TopAbs_IN:
                continue
            props = GeomLProp_SLProps(surface, u, v, 1, 1e-7)
            if not props.IsNormalDefined():
                continue
            n = props.Normal()
            sign = -1.0 if face.Orientation() == TopAbs_REVERSED else 1.0
            q = props.Value()
            if _on_surface(before.shape, q):
                # This part of the face was already the part's surface: a cut floor
                # merged into a level face beside it (D2632). Only where the cut made
                # the face does the side outside it say whether material went.
                continue
            probe = (q.X() + sign * n.X() * 0.01, q.Y() + sign * n.Y() * 0.01,
                     q.Z() + sign * n.Z() * 0.01)  # fmt: skip
            if point_inside(before.shape, probe, 1e-7):
                return []
            break
    return [
        Issue(
            FeatureState.WARNING,
            f"{feature.name} removes no material: its solid does not reach into the part. "
            "Turn on Reverse direction, or change the depth or the sketch.",
            code="cut_misses",
        )
    ]
