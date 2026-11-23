"""Mounting boss (PHASE4_SPEC P4.4 item 1, DECISIONS D316).

A round boss on a flat or curved face, with a screw hole (head side with a
counterbore, or thread side with a plain hole) or a pin or pin hole on top, and
optional fins that brace it against the face.

Params (FDEF_SPEC 5.3.24):

- ``boss_type``: ``screw_head``, ``screw_thread``, ``pin`` or ``pin_hole``.
- ``boss_diameter``, ``boss_height`` (lengths), ``boss_draft`` (optional angle,
  the side leans in going up).
- Screw types: ``hole_diameter``, ``hole_depth`` (from the top); head side also
  ``head_diameter``, ``head_depth``. Pin types: ``pin_diameter``, ``pin_height``.
- Fins: ``fin_count`` (number, 0 for none), ``fin_angle`` (angle of the first
  fin), ``equally_spaced`` (boolean, default true) or ``fin_angle2`` (the second
  fin's angle when not equally spaced), ``fin_length`` (out from the boss side),
  ``fin_width``, ``fin_height``, ``fin_draft`` (optional angle), and the end
  chamfer ``chamfer_distance`` (length, 0 for none) and ``chamfer_angle``.
- ``pos_x``, ``pos_y``, ``pos_z``: typed position when ``refs.position`` is empty.
- ``step_diameter``, ``step_height`` (TR146, D1916): optional, a narrower collar on
  top of the boss (roles ``step/side`` and ``step/top``); the hole or pin starts on it.
- ``height_clearance`` (TR146, D1517): with ``refs.height_face`` the boss reaches the
  mating face less this gap, in place of ``boss_height``. ``pin_clearance``: with
  ``refs.pin_edge`` (a round edge of the mating hole or pin) the pin is that edge's
  diameter less twice this gap (a pin hole: plus).

Refs: ``face`` (the face the boss stands on), ``position`` (a vertex, round edge
or sketch point), ``direction`` (optional: the boss axis, for curved faces) and
``fin_direction`` (optional: what fin angle 0 points along).

Face roles: ``boss/side``, ``boss/top``, ``fin/<k>/<j>``, ``hole/wall``,
``hole/bottom``, ``hole/cbore_wall``, ``hole/cbore_floor``, ``pin/side``,
``pin/top``.
"""

from __future__ import annotations

import math

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

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
from fdcad.core.features.hole import Placement, _revolved, _Spec
from fdcad.core.features.modify import require_body
from fdcad.core.features.solids import check_result, combine
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.units import Kind

BOSS_TYPES = ("screw_head", "screw_thread", "pin", "pin_hole")
_LENGTHS = (
    "boss_diameter",
    "boss_height",
    "hole_diameter",
    "hole_depth",
    "head_diameter",
    "head_depth",
    "pin_diameter",
    "height_clearance",  # TR146 (D1517)
    "step_diameter",  # TR146 (D1916)
    "step_height",
    "pin_clearance",
    "pin_height",
    "fin_length",
    "fin_width",
    "fin_height",
    "chamfer_distance",
    "pos_x",
    "pos_y",
    "pos_z",
)


#: Fin sizes when the feature has none stored: the panel's defaults, so raising the
#: fin count from 0 (by a formula or a design table) builds (audit E item 9.1, D728).
FIN_DEFAULTS = {"fin_length": 3.0, "fin_width": 1.2, "fin_height": 6.0}


def _fin(feature: Feature, name: str) -> float:
    return _v(feature, name, FIN_DEFAULTS[name])


def _v(feature: Feature, name: str, default: float | None = None) -> float:
    value = feature.params.get(name)
    if isinstance(value, Param):
        return value.value
    if default is None:
        raise FeatureError(
            f"{feature.name}: the {value_label(name)} value is missing. Enter a value."
        )
    return default


def round_solid(
    prefix: str, f: fx.Frame, bottom: float, top: float, r_base: float, draft: float
) -> NamedShape:
    """A cylinder (or a cone with draft) from height ``bottom`` to ``top``; radius
    ``r_base`` at height 0. Faces ``side``, ``top`` and ``bottom``."""
    height = top - bottom
    r_bottom = r_base - bottom * math.tan(draft)
    r_top = r_base - top * math.tan(draft)
    if r_top <= 0:
        raise FeatureError("the draft closes the boss before its top. Use a smaller draft.")
    ax = gp_Ax2(gp_Pnt(*fx.add(f.origin, f.up, bottom)), gp_Dir(*f.up), gp_Dir(*f.x))
    if abs(draft) < 1e-12:
        cyl = BRepPrimAPI_MakeCylinder(ax, r_base, height)
        cyl.Build()
        prim = cyl.Cylinder()
        shape = cyl.Shape()
    else:
        cone = BRepPrimAPI_MakeCone(ax, r_bottom, r_top, height)
        cone.Build()
        prim = cone.Cone()
        shape = cone.Shape()
    names = [
        (f"{prefix}/side", prim.LateralFace()),
        (f"{prefix}/top", prim.TopFace()),
        (f"{prefix}/bottom", prim.BottomFace()),
    ]
    return NamedShape(shape, restrict(names, shape, prefix))


def fin_angles(feature: Feature, count: int) -> list[float]:
    """Angles of the fins about the axis."""
    first = _v(feature, "fin_angle", 0.0)
    if count <= 0:
        return []
    if feature.params.get("equally_spaced", True) is not False:
        return [first + 2 * math.pi * k / count for k in range(count)]
    second = _v(feature, "fin_angle2", first + math.pi)
    step = second - first
    return [first + step * k for k in range(count)]


def _mating_height(feature: Feature, ctx: BuildContext, f: fx.Frame) -> float:
    """The boss height: typed, or up to a mating face less ``height_clearance`` (TR146,
    D1517), measured along the boss axis from where it stands."""
    from fdcad.core.features.hole import line_hits

    if not feature.refs.get("height_face"):
        return _v(feature, "boss_height")
    face, _issues = fx.face_of(feature, ctx, "height_face")
    hits = [h for h in line_hits(face, f.origin, f.up) if h[0] > 1e-6]
    if not hits:
        raise FeatureError(
            f"{feature.name}: the boss axis does not meet the mating face. Pick a face above "
            "the boss, or type the height."
        )
    height = hits[0][0] - _v(feature, "height_clearance", 0.0)
    if height <= 0:
        raise FeatureError(
            f"{feature.name}: the clearance is as large as the gap to the mating face. Enter "
            "a smaller clearance."
        )
    return height


def _pin_diameter(feature: Feature, ctx: BuildContext) -> float:
    """The pin size: typed, or a picked round edge's diameter (a hole for a pin, a pin
    for a pin hole) with ``pin_clearance`` taken off or added (TR146, D1517)."""
    if not feature.refs.get("pin_edge"):
        return _v(feature, "pin_diameter")
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle

    from fdcad.core.features.modify import resolve_edges

    picked, _issues = resolve_edges(feature, ctx, "pin_edge")
    curve = BRepAdaptor_Curve(picked[0][1])
    if curve.GetType() != GeomAbs_Circle:
        raise FeatureError(
            f"{feature.name}: the mating edge is not round. Pick the round edge of the hole "
            "or pin it fits."
        )
    gap = 2 * _v(feature, "pin_clearance", 0.0)
    size = 2.0 * float(curve.Circle().Radius())
    return size - gap if feature.params.get("boss_type") == "pin" else size + gap


@register
class MountingBoss(FeatureType):
    """A boss with a screw hole or pin and bracing fins."""

    type_name = "mounting_boss"
    makes_solid = True
    params = (
        ParamSpec("boss_type", choices=BOSS_TYPES, default="screw_thread"),
        ParamSpec("boss_diameter", kind=Kind.LENGTH),
        ParamSpec("boss_height", kind=Kind.LENGTH),
    )

    def kind_of(self, name: str) -> Kind | None:
        """Lengths, angles and the fin count."""
        if name in _LENGTHS:
            return Kind.LENGTH
        if name.endswith("_angle") or name.endswith("_draft") or name == "fin_angle2":
            return Kind.ANGLE
        if name == "fin_count":
            return Kind.NUMBER
        return super().kind_of(name)

    def validate(self, feature: Feature) -> None:
        """Sizes must fit inside each other."""
        super().validate(feature)
        name = feature.name
        d, h = _v(feature, "boss_diameter"), _v(feature, "boss_height")
        if d <= 0 or h <= 0:
            raise FeatureError(
                f"{name}: the boss diameter and height must be greater than zero. "
                "Enter larger values."
            )
        kind = feature.params.get("boss_type", "screw_thread")
        if kind in ("screw_head", "screw_thread"):
            hole = _v(feature, "hole_diameter")
            if not 0 < hole < d:
                raise FeatureError(
                    f"{name}: the hole must be smaller than the boss. Enter a smaller hole."
                )
            if _v(feature, "hole_depth") <= 0:
                raise FeatureError(
                    f"{name}: the hole depth must be greater than zero. Enter a larger depth."
                )
        if kind == "screw_head":
            head = _v(feature, "head_diameter")
            if not hole < head < d:
                raise FeatureError(
                    f"{name}: the head bore must be larger than the hole and smaller than the "
                    "boss. Check the head diameter."
                )
        if kind in ("pin", "pin_hole") and not 0 < _v(feature, "pin_diameter") < d:
            raise FeatureError(
                f"{name}: the pin must be smaller than the boss. Reduce the pin diameter."
            )
        count = round(_v(feature, "fin_count", 0.0))
        if not 0 <= count <= 12:
            raise FeatureError(f"{name}: use 0 to 12 fins.")
        if _v(feature, "step_height", 0.0) > 0:  # TR146 (D1916)
            inner = _v(feature, "hole_diameter") if kind in ("screw_head", "screw_thread") else 0
            if kind == "screw_head":
                inner = _v(feature, "head_diameter")
            if kind in ("pin", "pin_hole"):
                inner = _v(feature, "pin_diameter")
            if not inner < _v(feature, "step_diameter") < d:
                raise FeatureError(
                    f"{name}: the step must be smaller than the boss and larger than its hole "
                    "or pin. Enter a step diameter between them."
                )
        if count and min(_fin(feature, n) for n in FIN_DEFAULTS) <= 0:
            raise FeatureError(
                f"{name}: fin length, width and height must be above zero. Enter larger values."
            )

    def _frame(self, feature: Feature, ctx: BuildContext) -> tuple[fx.Frame, float, list[Issue]]:
        face, issues = fx.face_of(feature, ctx)
        point, more = fx.position(feature, ctx)
        direction, found = fx.direction_ref(feature, ctx, "direction")
        origin, normal = fx.on_face(face, point, direction)
        up = fx.unit(direction) if direction is not None else normal
        if fx.dot(up, normal) < 0:
            up = fx.neg(up)
        toward, extra = fx.direction_ref(feature, ctx, "fin_direction")
        f = fx.frame(origin, up, toward)
        radius = _v(feature, "boss_diameter") / 2
        reach = 0.0
        count = round(_v(feature, "fin_count", 0.0))
        outer = radius + (_fin(feature, "fin_length") if count else 0.0)
        ring = [(outer * math.cos(a), outer * math.sin(a)) for a in fin_angles(feature, count)]
        ring += [
            (radius * math.cos(k * math.pi / 8), radius * math.sin(k * math.pi / 8))
            for k in range(16)
        ]
        reach = fx.reach_down(face, f, ring)
        return f, reach, issues + more + found + extra

    def _shapes(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[NamedShape, list[NamedShape], list[Issue]]:
        """The material to add and the holes to cut. Messages name the feature (D609)."""
        try:
            return self._build_shapes(feature, ctx)
        except FeatureError as exc:
            if str(exc).startswith(feature.name):
                raise
            text = str(exc)
            raise FeatureError(
                f"{feature.name}: {text[:1].lower()}{text[1:]}", exc.fixes, exc.highlight
            ) from exc

    def _build_shapes(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[NamedShape, list[NamedShape], list[Issue]]:
        fid = feature.id
        f, reach, issues = self._frame(feature, ctx)
        radius = _v(feature, "boss_diameter") / 2
        height = _mating_height(feature, ctx, f)  # TR146 (D1517)
        pins = feature.params.get("boss_type") in ("pin", "pin_hole")
        pin_d = _pin_diameter(feature, ctx) if pins else 0.0
        draft = _v(feature, "boss_draft", 0.0)
        bottom = -reach - 0.01 * radius if reach > 0 else 0.0
        parts = [round_solid(f"{fid}/boss", f, bottom, height, radius, draft)]
        step = _v(feature, "step_height", 0.0)  # TR146 (D1916): a collar on top
        if step > 0:
            parts.append(
                round_solid(
                    f"{fid}/step",
                    fx.frame(fx.add(f.origin, f.up, height), f.up, f.x),
                    -0.01 * radius,
                    step,
                    _v(feature, "step_diameter") / 2,
                    0.0,
                )
            )
            height += step
        for k, angle in enumerate(fin_angles(feature, round(_v(feature, "fin_count", 0.0))), 1):
            parts.append(self._fin(feature, f, k, angle, radius, bottom))
        kind = str(feature.params.get("boss_type", "screw_thread"))
        if kind == "pin":
            parts.append(
                round_solid(
                    f"{fid}/pin",
                    fx.frame(fx.add(f.origin, f.up, height), f.up, f.x),
                    -0.0,
                    _v(feature, "pin_height"),
                    pin_d / 2,
                    0.0,
                )
            )
        material = fx.fuse_all(parts, f"{fid}/boss")
        cuts: list[NamedShape] = []
        top = fx.add(f.origin, f.up, height)
        place = Placement("hole", top, fx.neg(f.up), False)
        if kind in ("screw_head", "screw_thread"):
            spec = _Spec(
                "simple",
                _v(feature, "hole_diameter") / 2,
                _v(feature, "hole_depth"),
                None,
                False,
                0.0,
                0.0,
            )
            if kind == "screw_head":
                spec.hole_type = "counterbore"
                spec.cbore_radius = _v(feature, "head_diameter") / 2
                spec.cbore_depth = _v(feature, "head_depth")
            cuts.append(_revolved(f"{fid}/hole", place, spec, f.x))
        elif kind == "pin_hole":
            spec = _Spec(
                "simple",
                pin_d / 2,
                _v(feature, "pin_height"),
                None,
                False,
                0.0,
                0.0,
            )
            cuts.append(_revolved(f"{fid}/hole", place, spec, f.x))
        return material, cuts, issues

    def _fin(
        self, feature: Feature, f: fx.Frame, k: int, angle: float, radius: float, bottom: float
    ) -> NamedShape:
        along = fx.add(
            (f.x[0] * math.cos(angle), f.x[1] * math.cos(angle), f.x[2] * math.cos(angle)),
            f.y,
            math.sin(angle),
        )
        side = fx.cross(f.up, along)
        length = _fin(feature, "fin_length")
        width = _fin(feature, "fin_width")
        height = _fin(feature, "fin_height")
        chamfer = _v(feature, "chamfer_distance", 0.0)
        c_angle = _v(feature, "chamfer_angle", math.radians(45.0))
        outer = radius + length
        drop = chamfer * math.tan(c_angle) if chamfer > 0 else 0.0
        if chamfer >= length or drop >= height:
            raise FeatureError(
                f"{feature.name}: the fin chamfer is larger than the fin. Make it smaller."
            )
        corner = fx.add(f.origin, side, -width / 2)

        def at(rho: float, h: float) -> fx.Vec3:
            return fx.add(fx.add(corner, along, rho), f.up, h)

        outline = [at(0.0, bottom), at(outer, bottom)]
        if chamfer > 0:
            outline += [at(outer, height - drop), at(outer - chamfer, height)]
        else:
            outline.append(at(outer, height))
        outline.append(at(0.0, height))
        fin = fx.named_prism(
            f"{feature.id}/fin/{k}", "face", outline, fx.add((0, 0, 0), side, width)
        )
        draft = _v(feature, "fin_draft", 0.0)
        if draft:
            fin = fx.draft_sides(fin, f.origin, f.up, draft, "/start")
            fin = fx.draft_sides(fin, f.origin, f.up, draft, "/end")
        return fin

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the boss and fins, then cut the hole."""
        body = require_body(feature, ctx)
        material, cuts, issues = self._shapes(feature, ctx)
        from fdcad.core.features.bodies import in_body_of

        def build(target: NamedShape) -> NamedShape:
            out = combine(feature.id, feature.name, target, material, "boss")
            for cut in cuts:
                out = combine(feature.id, feature.name, out, cut, "cut")
            return out

        face, _found = fx.face_of(feature, ctx)
        result = in_body_of(body, face, feature.id, build)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The boss and fins, for the preview."""
        material, _cuts, _issues = self._shapes(feature, ctx)
        return material
