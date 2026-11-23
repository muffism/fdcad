"""Revolve, boss or cut.

Params:
- ``operation``: "boss" or "cut".
- ``direction``: "one_direction", "mid_plane" or "two_directions".
- ``angle``: angle. ``angle2``: angle, second direction for "two_directions".
- ``reverse``: boolean, revolves the other way.
- ``merge``: boolean, optional (default true). False keeps a boss as a separate body.
- ``cut_outside``: boolean, optional (default false), cuts only: removes the material
  outside the profile within the revolved angle (D143).

Refs: ``sketch`` (``{"feature": "f5"}``), optionally ``regions`` (the Selected Regions
picks, ``fdcad.core.naming.regions``), and ``axis``: either a line in that sketch
(``{"sketch_entity": "e9"}``), usually a centerline, or a straight edge of the part
that lies in the sketch plane, stored as an edge reference (FDEF_SPEC 7) with its
name and snapshot. The snapshot direction fixes which way the angle turns.

End conditions (TOOL_SPEC T16 item 2): optional ``end_condition``,
``end_condition2``, ``end_offset``, ``end_offset2`` and refs ``end_ref``,
``end_ref2``; see ``revolve_end``. Files with only ``direction`` read as before.

Thin Feature (TOOL_SPEC T6.1 item 5, D523): the extrude's optional ``thin_*`` keys;
see ``revolve_thin``.

Face roles: ``cap/start``, ``cap/end`` (only when less than a full turn) and
``side/<entity>`` for the face swept from sketch entity ``<entity>``.
"""

from __future__ import annotations

import math

from OCP.gp import gp_Ax1, gp_Dir, gp_Trsf
from OCP.TopoDS import TopoDS_Face

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    ANGLE_RULER_STEP,
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    PreviewHandle,
    SketchOutput,
    register,
)
from fdcad.core.features.extrude_thin import THIN_TYPES, thin_on
from fdcad.core.features.revolve_end import (
    ENDS1,
    ENDS2,
    PICKED,
    Turn,
    resolve_turn,
    revolve_ends,
    turn_to_plane,
    turned,
)
from fdcad.core.features.revolve_thin import capped, check_wall_side, thin_revolve_sketch
from fdcad.core.features.sketch import PickedSketch, sketch_for
from fdcad.core.features.solids import (
    bounding_size,
    check_result,
    combine,
    combine_or_keep,
    common,
    expected_issues,
    line_ends,
    polygon_face,
    profile_centre,
    revolve,
    transform,
)
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.model import Line
from fdcad.core.sketch.profiles import Profile
from fdcad.core.sketch.topology import curve_points
from fdcad.core.units import Kind

_FULL_TURN = 2 * math.pi
_ANGLE_TOL = 1e-9
_PLANE_TOL = 1e-4  # mm: how far an axis edge may sit off the sketch plane


@register
class Revolve(FeatureType):
    """Revolves a sketch profile around a line and adds it to, or cuts it from, the part."""

    type_name = "revolve"
    makes_solid = True
    params = (
        ParamSpec("operation", choices=("boss", "cut"), default="boss"),
        ParamSpec(
            "direction",
            choices=("one_direction", "mid_plane", "two_directions"),
            default="one_direction",
        ),
        ParamSpec("angle", kind=Kind.ANGLE),
        ParamSpec("angle2", kind=Kind.ANGLE, optional=True),
        ParamSpec("reverse", default=False),
        ParamSpec("merge", default=True, optional=True),
        ParamSpec("cut_outside", default=False, optional=True),
        ParamSpec("end_condition", choices=ENDS1, optional=True),
        ParamSpec("end_condition2", choices=ENDS2, optional=True),
        ParamSpec("end_offset", kind=Kind.ANGLE, optional=True),
        ParamSpec("end_offset2", kind=Kind.ANGLE, optional=True),
        ParamSpec("thin_type", choices=THIN_TYPES, optional=True),
        ParamSpec("thin_thickness", kind=Kind.LENGTH, optional=True),
        ParamSpec("thin_thickness2", kind=Kind.LENGTH, optional=True),
        ParamSpec("thin_reverse", default=False, optional=True),
        ParamSpec("thin_cap", default=False, optional=True),
        ParamSpec("thin_cap_thickness", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Build the revolved solid and combine it with the part."""
        tool, axis_issues = self._build(feature, ctx)
        operation = str(self.setting(feature, "operation", "boss"))
        body = combine_or_keep(feature, ctx.body, tool, operation, ctx, axis_issues)
        issues = check_result(feature.id, feature.name, ctx.body, body, None)
        issues = expected_issues(feature, issues)
        return FeatureResult(body=body, issues=axis_issues + issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The revolved solid on its own, or for Cut Outside the material it removes."""
        tool = self._build(feature, ctx)[0]
        if feature.params.get("cut_outside", False) is True and ctx.body is not None:
            return common(feature.id, feature.name, ctx.body, tool)
        return tool

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        picked = revolve_sketch(feature, ctx)
        sketch = picked.sketch
        assert sketch.profile is not None
        axis, issues = self._axis(feature, ctx, picked)
        issues = picked.issues + issues
        if thin_on(feature):
            check_wall_side(name, sketch.profile, axis, sketch.plane.normal)
        outside = feature.params.get("cut_outside", False) is True
        if outside and self.setting(feature, "operation", "boss") != "cut":
            raise FeatureError(f"{name}: Cut Outside works only for cuts. Turn it off.")
        if outside and ctx.body is None:
            raise FeatureError(f"{name} has nothing to cut. Add a boss feature first.")

        tool, turn_issues = self._turned(feature, ctx, sketch.profile, axis)
        issues = issues + turn_issues
        if thin_on(feature) and feature.params.get("thin_cap") is True:
            span = self._span(feature, ctx, sketch.profile, axis)
            tool = capped(feature, ctx, tool, axis, span)
        if outside:
            assert ctx.body is not None
            half = Profile([self._half_plane(axis, sketch, ctx.body.shape)])
            region, _found = self._turned(feature, ctx, half, axis)
            tool = combine(feature.id, name, region, tool, "cut")
        return tool, issues

    def _turned(
        self, feature: Feature, ctx: BuildContext, profile: Profile, axis: gp_Ax1
    ) -> tuple[NamedShape, list[Issue]]:
        """``profile`` turned about ``axis`` as the end conditions say (T16 item 2)."""
        name, fid = feature.name, feature.id
        first, second = revolve_ends(feature)
        if second is not None and first in ("through_all", "mid_plane"):
            label = "Through All" if first == "through_all" else "Mid Plane"
            raise FeatureError(
                f"{name}: Direction 2 is not available with {label}. "
                "Turn off Direction 2 or choose Blind."
            )
        issues: list[Issue] = []
        back_axis = axis.Reversed()
        if first == "mid_plane":
            angle = self.number(feature, "angle")
            return self._checked_sweep(feature, profile, axis, angle, angle / 2), issues
        if first == "through_all":
            copy = thin_on(feature)
            return self._sweep(fid, profile, axis, _FULL_TURN, 0.0, copy), issues
        one = self._turn(feature, ctx, profile, axis, first, "")
        two = self._turn(feature, ctx, profile, back_axis, second, "2") if second else None
        issues = one.issues + (two.issues if two is not None else [])
        if one.plane is None and (two is None or two.plane is None):
            assert one.angle is not None
            back = two.angle if two is not None and two.angle is not None else 0.0
            return self._checked_sweep(feature, profile, axis, one.angle + back, back), issues
        # A plane that does not hold the axis: each direction is turned on its own.
        tool = self._side(fid, name, profile, axis, one, "")
        if two is None:
            return tool, issues
        other = self._side(fid, name, profile, back_axis, two, "2")
        names = []
        for n, f in other.faces:
            if n.startswith(f"{fid}/cap/start"):
                continue
            names.append((n.replace(f"{fid}/cap/end", f"{fid}/cap/start", 1), f))
        return combine(fid, name, tool, NamedShape(other.shape, names), "boss"), issues

    def _span(
        self, feature: Feature, ctx: BuildContext, profile: Profile, axis: gp_Ax1
    ) -> tuple[float, float] | None:
        """Total angle and how far it starts before the sketch, or None (a plane end)."""
        first, second = revolve_ends(feature)
        if first == "mid_plane":
            angle = self.number(feature, "angle")
            return angle, angle / 2
        if first == "through_all":
            return _FULL_TURN, 0.0
        one = self._turn(feature, ctx, profile, axis, first, "")
        two = self._turn(feature, ctx, profile, axis.Reversed(), second, "2") if second else None
        if one.angle is None or (two is not None and two.angle is None):
            return None
        back = two.angle if two is not None and two.angle is not None else 0.0
        return one.angle + back, back

    def _turn(
        self,
        feature: Feature,
        ctx: BuildContext,
        profile: Profile,
        axis: gp_Ax1,
        condition: str,
        which: str,
    ) -> Turn:
        if condition in PICKED:
            return resolve_turn(feature, ctx, profile, axis, condition, which)
        angle = self.number(feature, "angle2" if which == "2" else "angle")
        return Turn(angle=angle)

    def _side(
        self, fid: str, name: str, profile: Profile, axis: gp_Ax1, turn: Turn, which: str
    ) -> NamedShape:
        if turn.plane is not None:
            return turn_to_plane(fid, name, profile, axis, turn.plane, which)
        assert turn.angle is not None
        if turn.angle <= _ANGLE_TOL or turn.angle > _FULL_TURN + _ANGLE_TOL:
            raise FeatureError(
                f"{name}: the angle must be more than 0 and at most 360 degrees in total. "
                "Enter an angle in that range."
            )
        return self._sweep(fid, profile, axis, turn.angle, 0.0)

    def _checked_sweep(
        self, feature: Feature, profile: Profile, axis: gp_Ax1, angle: float, back: float
    ) -> NamedShape:
        if angle <= _ANGLE_TOL or back < 0 or angle > _FULL_TURN + _ANGLE_TOL:
            raise FeatureError(
                f"{feature.name}: the angle must be more than 0 and at most 360 degrees in total. "
                "Enter an angle in that range."
            )
        return self._sweep(feature.id, profile, axis, angle, back, thin_on(feature))

    @staticmethod
    def _sweep(
        fid: str, profile: Profile, axis: gp_Ax1, angle: float, back: float, copy: bool = False
    ) -> NamedShape:
        """Revolve ``profile`` by ``angle`` in total, starting ``back`` before the sketch.

        ``copy`` (thin walls) makes the kernel name every face of a full turn.
        """
        full = abs(angle - _FULL_TURN) <= _ANGLE_TOL
        tool = revolve(fid, profile, axis, min(angle, _FULL_TURN), full, copy)
        if back and not full:
            turn = gp_Trsf()
            turn.SetRotation(axis, -back)
            tool = transform(tool, turn)
        return tool

    @staticmethod
    def _half_plane(axis: gp_Ax1, sketch: SketchOutput, body: object) -> TopoDS_Face:
        """A rectangle in the sketch plane from the axis out past the part, on the profile side."""
        from OCP.TopoDS import TopoDS_Shape

        assert sketch.profile is not None and isinstance(body, TopoDS_Shape)
        size = 2 * bounding_size(body, *sketch.profile.faces) + 10.0
        loc, d = axis.Location(), axis.Direction()
        p = (loc.X(), loc.Y(), loc.Z())
        a = (d.X(), d.Y(), d.Z())
        c = profile_centre(sketch.profile.faces)
        rel = [c[i] - p[i] for i in range(3)]
        along = sum(rel[i] * a[i] for i in range(3))
        w = [rel[i] - a[i] * along for i in range(3)]
        length = math.sqrt(sum(v * v for v in w))
        if length < 1e-9:
            raise FeatureError("The profile lies on the axis. Move it off the axis.")
        w = [v / length for v in w]
        foot = [p[i] + a[i] * along for i in range(3)]
        corners = []
        for sa, sw in ((-1, 0), (1, 0), (1, 1), (-1, 1)):
            q = tuple(foot[i] + a[i] * sa * size + w[i] * sw * size for i in range(3))
            corners.append((q[0], q[1], q[2]))
        return polygon_face(corners)

    def _axis(
        self, feature: Feature, ctx: BuildContext, picked: PickedSketch
    ) -> tuple[gp_Ax1, list[Issue]]:
        """The axis of revolution, from a sketch line or a straight model edge (W6.3)."""
        name = feature.name
        sketch = picked.sketch
        ref = feature.refs.get("axis")
        issues: list[Issue] = []
        if isinstance(ref, dict) and ref.get("kind") == "edge":
            (x1, y1), (x2, y2), issues = self._edge_axis(name, ref, ctx, sketch)
        elif isinstance(ref, dict) and (
            ref.get("kind") == "face" or isinstance(ref.get("feature"), str)
        ):
            # A round face's axis, a reference axis or an origin axis (TR17, D712).
            (x1, y1), (x2, y2), issues = self._face_axis(name, ref, ctx, sketch)
        else:
            axis_id = ref.get("sketch_entity") if isinstance(ref, dict) else None
            line = sketch.model.entities.get(str(axis_id))
            if not isinstance(line, Line):
                raise FeatureError(
                    f"{name} has no axis. Choose a line or centerline in the sketch, "
                    "or a straight edge of the part."
                )
            (x1, y1), (x2, y2) = sketch.model.xy(line.p1), sketch.model.xy(line.p2)
            if math.hypot(x2 - x1, y2 - y1) < 1e-9:
                raise FeatureError(f"{name}: the axis line has no length. Choose another line.")
            ref = {"skip": line.id}
        self._check_one_side(
            name, _profile_points(picked, str(ref.get("skip", ""))), (x1, y1), (x2, y2)
        )

        p1, p2 = sketch.plane.to_3d(x1, y1), sketch.plane.to_3d(x2, y2)
        direction = gp_Dir(p2.X() - p1.X(), p2.Y() - p1.Y(), p2.Z() - p1.Z())
        if self.setting(feature, "reverse", False):
            direction.Reverse()
        return gp_Ax1(p1, direction), issues

    @staticmethod
    def _face_axis(
        name: str, ref: dict[str, object], ctx: BuildContext, sketch: SketchOutput
    ) -> tuple[tuple[float, float], tuple[float, float], list[Issue]]:
        """Sketch coordinates of two points on the axis of a round face (a temporary
        axis, TR17). The axis must lie in the sketch plane."""
        from fdcad.core.features.geometry_refs import resolve_placement

        placement = resolve_placement(ctx, ref, name, "axis")
        p = placement.point
        d = placement.direction
        u0, v0, h0 = sketch.plane.to_2d(*p)
        u1, v1, h1 = sketch.plane.to_2d(p[0] + d[0], p[1] + d[1], p[2] + d[2])
        if abs(h0) > 1e-6 or abs(h1) > 1e-6:
            raise FeatureError(
                f"{name}: the picked axis is not in the sketch plane. "
                "Pick an axis that lies in the sketch, or a sketch line."
            )
        return (u0, v0), (u1, v1), list(placement.issues)

    @staticmethod
    def _edge_axis(
        name: str, ref: dict[str, object], ctx: BuildContext, sketch: SketchOutput
    ) -> tuple[tuple[float, float], tuple[float, float], list[Issue]]:
        """Sketch coordinates of the ends of a straight model edge used as the axis."""
        from fdcad.core.naming.resolve import resolve_edge  # resolve imports the features

        edge, issues = resolve_edge(ctx.body, ref, name)
        ends = line_ends(edge)
        if ends is None:
            raise FeatureError(f"{name}: the axis edge is not straight. Choose a straight edge.")
        start, end = ends
        snapshot = ref.get("snapshot")
        stored = snapshot.get("direction") if isinstance(snapshot, dict) else None
        if isinstance(stored, list) and len(stored) == 3:
            # Keep the direction the user picked, even if the kernel flips the edge later.
            d = [end[i] - start[i] for i in range(3)]
            if sum(d[i] * float(stored[i]) for i in range(3)) < 0:
                start, end = end, start
        a, b = sketch.plane.to_2d(*start), sketch.plane.to_2d(*end)
        if abs(a[2]) > _PLANE_TOL or abs(b[2]) > _PLANE_TOL:
            raise FeatureError(
                f"{name}: the axis edge is not in the sketch plane. "
                "Choose an edge that lies in the sketch plane."
            )
        return (a[0], a[1]), (b[0], b[1]), issues

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """Curved drag arrows at the ends of the revolve (W6.4)."""
        picked = revolve_sketch(feature, ctx)
        sketch = picked.sketch
        assert sketch.profile is not None
        axis, _issues = self._axis(feature, ctx, picked)
        loc, d = axis.Location(), axis.Direction()
        centre = (loc.X(), loc.Y(), loc.Z())
        forward = (d.X(), d.Y(), d.Z())
        base = profile_centre(sketch.profile.faces)
        first, second = revolve_ends(feature)
        step = ANGLE_RULER_STEP
        if first == "mid_plane":
            angle = self.number(feature, "angle")
            handle = PreviewHandle("angle", base, forward, angle, 2.0, centre, step)
            return [handle] if handle.radius >= 1e-6 else []
        handles: list[PreviewHandle] = []
        if first == "blind":
            angle = self.number(feature, "angle")
            handles.append(PreviewHandle("angle", base, forward, angle, 1.0, centre, step))
        back = (-forward[0], -forward[1], -forward[2])
        if second == "blind":
            angle2 = self.number(feature, "angle2")
            handles.append(PreviewHandle("angle2", base, back, angle2, 1.0, centre, step))
        # Offset from Face keeps a curved arrow for the offset (T16 item 3).
        for which, condition, turn_axis, toward in (
            ("", first, axis, back),
            ("2", second, axis.Reversed(), forward),
        ):
            if condition != "offset_from_face":
                continue
            offset = feature.params.get(f"end_offset{which}")
            if not isinstance(offset, Param):
                continue
            try:
                turn = resolve_turn(feature, ctx, sketch.profile, turn_axis, condition, which)
            except FeatureError:
                continue
            if turn.angle is None:
                continue
            at = turned(turn_axis, base, turn.angle + offset.value)
            name = f"end_offset{which}"
            handles.append(PreviewHandle(name, at, toward, offset.value, 1.0, centre, step))
        return [h for h in handles if h.radius >= 1e-6]

    @staticmethod
    def _check_one_side(
        name: str,
        points: list[tuple[float, float]],
        a: tuple[float, float],
        b: tuple[float, float],
    ) -> None:
        """The profile must stay on one side of the axis, or the solid crosses itself."""
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        sides: set[int] = set()
        for x, y in points:
            d = (x - a[0]) * uy - (y - a[1]) * ux
            if abs(d) > 1e-6:
                sides.add(1 if d > 0 else -1)
        if len(sides) > 1:
            raise FeatureError(
                f"{name} failed: the profile crosses the axis. Move the profile to one side "
                "of the axis or pick regions on one side."
            )


def revolve_sketch(feature: Feature, ctx: BuildContext) -> PickedSketch:
    """The sketch to revolve: its picked regions (T5.3), or the thin wall (D523)."""
    if thin_on(feature):
        return thin_revolve_sketch(feature, ctx)
    return sketch_for(feature, ctx)


def _profile_points(picked: PickedSketch, skip: str) -> list[tuple[float, float]]:
    """Sketch points along the profile: the picked regions, or every curve but ``skip``."""
    if picked.regions is not None:
        return [p for r in picked.regions for poly in (r.polygon, *r.hole_polygons) for p in poly]
    sketch = picked.sketch.model
    return [p for curve in sketch.curves() if curve.id != skip for p in curve_points(sketch, curve)]
