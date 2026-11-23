"""Snap hook (PHASE4_SPEC P4.4 item 2, DECISIONS D317).

A cantilever beam standing on a face with a hook lip at its top. The side
outline lies in the plane of the up and hook directions and is extruded across
the total width, centred on the position point.

Params (FDEF_SPEC 5.3.25):

- ``body_height`` (length): from the face to the catch, unless ``refs.mate_face``
  gives it (the distance along up to that face).
- ``base_depth``, ``top_depth``: the beam's thickness along the hook direction at
  its base and just under the catch. ``total_width``: across.
- ``overhang``: how far the lip reaches past the beam. ``hook_height``: from the
  catch to the top. ``lip_height``: the straight front of the lip above the
  catch. ``top_draft``: angle of the lead in slope from the up direction.
- ``up_reverse``, ``hook_reverse``: optional booleans. ``hook_angle``: optional
  angle turning the hook direction about up.
- ``pos_x``, ``pos_y``, ``pos_z``: typed position when ``refs.position`` is empty.

Refs: ``face``, ``position``, ``up`` and ``hook_direction`` (optional: a plane
feature, a flat face or a straight edge), ``mate_face`` (optional).

Face roles: ``hook/face/<k>`` for the outline sides in this order: base, back,
top, lead, lip, catch, front; ``hook/face/start`` and ``hook/face/end`` for the
two side faces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fdcad.core.document.model import Feature, Param
from fdcad.core.features import fastening as fx
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
    value_label,
)
from fdcad.core.features.modify import require_body
from fdcad.core.features.solids import check_result, combine
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

_LENGTHS = (
    "body_height",
    "base_depth",
    "top_depth",
    "total_width",
    "overhang",
    "hook_height",
    "lip_height",
    "pos_x",
    "pos_y",
    "pos_z",
)


def value(feature: Feature, name: str, default: float | None = None) -> float:
    """A typed value in mm or radians (``default`` when missing, else an error)."""
    v = feature.params.get(name)
    if isinstance(v, Param):
        return v.value
    if default is None:
        raise FeatureError(
            f"{feature.name}: the {value_label(name)} value is missing. Enter a value."
        )
    return default


@dataclass(frozen=True)
class HookShape:
    """A built hook's frame and sizes, for the groove (P4.4 item 3)."""

    frame: fx.Frame  # x: hook direction, y: across, up: up
    height: float  # face to catch
    base: float
    top: float
    overhang: float
    hook_height: float
    lip_height: float
    tip_x: float  # where the lead in slope meets the top
    width: float
    reach: float  # how far the base reaches below the frame (curved faces)


def hook_shape(feature: Feature, ctx: BuildContext) -> tuple[HookShape, list[Issue]]:
    """Frame and checked sizes of a snap hook."""
    name = feature.name
    face, issues = fx.face_of(feature, ctx)
    point, more = fx.position(feature, ctx)
    up_ref, found = fx.direction_ref(feature, ctx, "up")
    origin, normal = fx.on_face(face, point, up_ref)
    up = fx.unit(up_ref) if up_ref is not None else normal
    if feature.params.get("up_reverse") is True:
        up = fx.neg(up)
    toward, extra = fx.direction_ref(feature, ctx, "hook_direction")
    f = fx.frame(origin, up, toward, value(feature, "hook_angle", 0.0))
    if feature.params.get("hook_reverse") is True:
        f = fx.Frame(f.origin, f.up, fx.neg(f.x), fx.neg(f.y))
    issues = issues + more + found + extra
    if feature.refs.get("mate_face"):
        from fdcad.core.naming.names import centroid

        mate, mate_issues = fx.face_of(feature, ctx, "mate_face")
        issues += mate_issues
        height = fx.dot(fx.sub(centroid(mate), f.origin), f.up)
    else:
        height = value(feature, "body_height")
    base, top = value(feature, "base_depth"), value(feature, "top_depth")
    width, overhang = value(feature, "total_width"), value(feature, "overhang")
    hook_h, lip_h = value(feature, "hook_height"), value(feature, "lip_height", 0.0)
    draft = value(feature, "top_draft", math.radians(30.0))
    if min(height, base, top, width, overhang, hook_h) <= 0:
        raise FeatureError(
            f"{name}: the body height, depths, width, overhang and hook height must be above "
            "zero. Check the hook data."
        )
    if not 0 <= lip_h < hook_h:
        raise FeatureError(
            f"{name}: the lip height must be smaller than the hook height. Reduce the lip height."
        )
    if not 0 <= draft < math.radians(89):
        raise FeatureError(
            f"{name}: the top draft must be between 0 and 89 degrees. Enter an angle in that range."
        )
    tip_x = top + overhang - (hook_h - lip_h) * math.tan(draft)
    if tip_x <= 0:
        raise FeatureError(
            f"{name}: the lead in slope runs past the back of the hook. "
            "Use a smaller top draft or a larger overhang."
        )
    reach = fx.reach_down(
        face,
        f,
        [(0.0, w) for w in (-width / 2, width / 2)]
        + [
            (base, -width / 2),
            (base, width / 2),
        ],
    )
    return HookShape(f, height, base, top, overhang, hook_h, lip_h, tip_x, width, reach), issues


def hook_solid(fid: str, shape: HookShape) -> NamedShape:
    """The hook as a named prism."""
    f = shape.frame
    bottom = -shape.reach - (0.01 if shape.reach > 0 else 0.0)
    h, t = shape.height, shape.top
    lean = (shape.top - shape.base) / h

    def at(x: float, y: float) -> fx.Vec3:
        return fx.add(fx.add(f.origin, f.x, x), fx.add((0, 0, 0), f.up, y))

    front_bottom = shape.base + lean * bottom
    outline = [
        at(0.0, bottom),
        at(0.0, h + shape.hook_height),
        at(shape.tip_x, h + shape.hook_height),
        at(t + shape.overhang, h + shape.lip_height),
        at(t + shape.overhang, h),
        at(t, h),
        at(front_bottom, bottom),
    ]
    outline = [fx.add(p, f.y, -shape.width / 2) for p in outline]
    if shape.lip_height <= 0:
        outline.pop(3)
    return fx.named_prism(f"{fid}/hook", "face", outline, fx.add((0, 0, 0), f.y, shape.width))


@register
class SnapHook(FeatureType):
    """A cantilever snap hook."""

    type_name = "snap_hook"
    makes_solid = True
    params = (
        ParamSpec("base_depth", kind=Kind.LENGTH),
        ParamSpec("top_depth", kind=Kind.LENGTH),
        ParamSpec("total_width", kind=Kind.LENGTH),
        ParamSpec("overhang", kind=Kind.LENGTH),
        ParamSpec("hook_height", kind=Kind.LENGTH),
    )

    def kind_of(self, name: str) -> Kind | None:
        """Lengths and the two angles."""
        if name in _LENGTHS:
            return Kind.LENGTH
        if name in ("top_draft", "hook_angle"):
            return Kind.ANGLE
        return super().kind_of(name)

    def _solid(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        shape, issues = hook_shape(feature, ctx)
        return hook_solid(feature.id, shape), issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the hook to the part."""
        body = require_body(feature, ctx)
        solid, issues = self._solid(feature, ctx)
        from fdcad.core.features.bodies import in_body_of

        face, _found = fx.face_of(feature, ctx)
        result = in_body_of(
            body, face, feature.id, lambda b: combine(feature.id, feature.name, b, solid, "boss")
        )
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The hook, for the preview."""
        solid, _issues = self._solid(feature, ctx)
        return solid
