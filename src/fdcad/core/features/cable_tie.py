"""Cable tie channels (TUTORIAL_REVIEW_SPEC_2 TR363, DECISIONS D879).

Type ``cable_tie``. A sketch on a face of the part gives the positions
(``refs.sketch``: its points and line ends, as the Hole Tool reads them). At each
position a loop is cut for a cable tie: two entry slots down from the face,
``span`` apart along the sketch X axis turned by ``angle``, joined under the face
by a tunnel ``cover`` below it. Slots and tunnel are ``tie_width`` wide and
``tie_thickness`` tall, each grown by ``clearance``. The tunnel's top is pointed
at 45 degrees so it prints without supports; where the cover is too thin for the
point, the top is cut flat at half the cover. New faces are
``<fid>/tie/<point>/...``.
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind


def _num(feature: Feature, key: str, label: str, default: float, positive: bool = True) -> float:
    value = feature.params.get(key)
    v = value.value if isinstance(value, Param) else default
    if positive and v <= 0:
        raise FeatureError(
            f"{feature.name}: the {label} must be greater than zero. Enter a larger value."
        )
    return v


def tie_tools(
    prefix: str,
    origin: Vec3,
    direction: Vec3,
    along: Vec3,
    width: float,
    height: float,
    span: float,
    cover: float,
) -> list[NamedShape]:
    """The two entry slots and the tunnel of one tie loop, as named prisms. ``direction``
    points into the part, ``along`` runs from one slot to the other."""
    from fdcad.core.features.hole import _add, _cross, _dot, _prism, _scale, _unit

    d = _unit(direction)
    u = _unit(_add(along, d, -_dot(along, d)))
    v = _cross(d, u)
    half_w, half_span = width / 2, span / 2

    def at(a: float, b: float, depth: float) -> Vec3:
        return _add(_add(_add(origin, u, a), v, b), d, depth)

    bottom = cover + height
    out: list[NamedShape] = []
    for k, sign in ((1, -1.0), (2, 1.0)):
        inner, outer = sign * half_span, sign * (half_span + height)
        slot = [at(inner, -half_w, -0.1), at(outer, -half_w, -0.1)]
        slot += [at(outer, half_w, -0.1), at(inner, half_w, -0.1)]
        out.append(_prism(prefix, f"slot{k}", slot, _scale(d, 0.1 + bottom)))
    # The tunnel's section across it: a rectangle with a 45 degree point toward the face.
    peak = cover - half_w
    if peak < cover / 2:  # too thin for the point: a flat top at half the cover
        top = [(-half_w, cover / 2), (half_w, cover / 2)]
    else:
        top = [(-half_w, cover), (0.0, peak), (half_w, cover)]
    section = [(-half_w, bottom), (half_w, bottom), *reversed(top)]
    start = -half_span - height
    outline = [at(start, b, depth) for b, depth in section]
    out.append(_prism(prefix, "tunnel", outline, _scale(u, span + 2 * height)))
    return out


@register
class CableTie(FeatureType):
    """Cable tie loops cut under a face at sketch points."""

    type_name = "cable_tie"
    makes_solid = True
    params = (
        ParamSpec("tie_width", kind=Kind.LENGTH),
        ParamSpec("tie_thickness", kind=Kind.LENGTH),
        ParamSpec("span", kind=Kind.LENGTH),
        ParamSpec("cover", kind=Kind.LENGTH),
        ParamSpec("clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut every loop in one boolean."""
        from fdcad.core.features.hole import _sketch_output, cut_all, placements
        from fdcad.core.features.solids import check_result

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        if not isinstance(feature.refs.get("sketch"), dict):
            raise FeatureError(f"{name}: pick a sketch with points on a face of the part.")
        clearance = max(_num(feature, "clearance", "clearance", 0.2, positive=False), 0.0)
        width = _num(feature, "tie_width", "tie width", 5.0) + 2 * clearance
        height = _num(feature, "tie_thickness", "tie thickness", 1.5) + 2 * clearance
        span = _num(feature, "span", "span", 10.0)
        cover = _num(feature, "cover", "cover", 2.0)
        turn = _num(feature, "angle", "angle", 0.0, positive=False)
        sketch = _sketch_output(feature, ctx)
        ax = sketch.plane.ax3()
        xd, yd = ax.XDirection(), ax.YDirection()
        along = (
            math.cos(turn) * xd.X() + math.sin(turn) * yd.X(),
            math.cos(turn) * xd.Y() + math.sin(turn) * yd.Y(),
            math.cos(turn) * xd.Z() + math.sin(turn) * yd.Z(),
        )
        tools: list[NamedShape] = []
        for place in placements(feature, sketch, None):
            prefix = f"{feature.id}/tie/{place.point}"
            try:
                tools += tie_tools(
                    prefix, place.origin, place.direction, along, width, height, span, cover
                )
            except Exception as exc:
                raise FeatureError(
                    f"{name}: the channel at point {place.point} could not be made. "
                    "Check the tie sizes."
                ) from exc
        result = cut_all(feature, ctx.body, tools)
        return FeatureResult(
            body=result, issues=check_result(feature.id, name, ctx.body, result, None)
        )
