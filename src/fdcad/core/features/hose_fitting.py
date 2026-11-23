"""Hose barbs and luer fittings (TUTORIAL_REVIEW_SPEC_2 TR406, DECISIONS D914).

Type ``hose_fitting``: a round fitting standing on a face (``refs.base_face``) at
a vertex or the centre of a round edge (``refs.base_point``; the typed ``pos_x/y/z``,
or the middle of the face when neither is given), square to the face or along
``refs.direction``, joined to the part, with a bore through it that goes
``bore_depth`` into the part.

- ``fitting`` ``barb``: a stem the size of the hose's inside (``hose_diameter``)
  with ``ring_count`` barbs, each ``ring_length`` long, that step out to
  ``barb_diameter`` (default 1.15 times the hose size) facing the part and taper
  back toward the tip, so a hose slides on and does not pull off.
- ``luer_male`` and ``luer_female``: the 6 percent luer taper (ISO 80369-7 sizes:
  a male tip 3.925 mm across at its end, a female opening 4.27 mm, 7.5 mm long),
  on a round base ``body_diameter`` across.

``shank_height`` is the plain round part between the face and the barbs or taper.
New faces are ``<fid>/fitting/<k>`` and ``<fid>/bore/<k>``.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind

FITTINGS = ("barb", "luer_male", "luer_female")
#: Luer sizes (ISO 80369-7): the taper changes the diameter by 6 percent of the length.
LUER_TAPER = 0.06
LUER_LENGTH = 7.5
LUER_MALE_TIP = 3.925
LUER_FEMALE_OPENING = 4.27

Profile = list[tuple[float, float]]


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


def barb_profile(
    hose: float, barb: float, rings: int, ring_length: float, shank: float, bottom: float = 0.0
) -> Profile:
    """The outside of a barb as (radius, height) points from the axis at ``bottom`` round
    to the axis at the tip."""
    r0, r1 = hose / 2, barb / 2
    out: Profile = [(0.0, bottom), (r0, bottom), (r0, shank)]
    for k in range(rings):
        z = shank + k * ring_length
        out += [(r1, z), (r0, z + ring_length)]
    out.append((0.0, shank + rings * ring_length))
    return out


def luer_profiles(
    male: bool, body: float, shank: float, bottom: float = 0.0
) -> tuple[Profile, Profile | None]:
    """The outside of a luer fitting and, for a female one, its tapered socket."""
    grow = LUER_TAPER * LUER_LENGTH
    if male:
        base, tip = (LUER_MALE_TIP + grow) / 2, LUER_MALE_TIP / 2
        top = shank + LUER_LENGTH
        outside = [
            (0.0, bottom),
            (body / 2, bottom),
            (body / 2, shank),
            (base, shank),
            (tip, top),
            (0.0, top),
        ]
        return outside, None
    top = shank + LUER_LENGTH
    opening, inner = LUER_FEMALE_OPENING / 2, (LUER_FEMALE_OPENING - grow) / 2
    outside = [(0.0, bottom), (body / 2, bottom), (body / 2, top), (0.0, top)]
    socket = [(0.0, shank), (inner, shank), (opening, top + 1.0), (0.0, top + 1.0)]
    return outside, socket


def _check(feature: Feature) -> None:
    name = feature.name
    kind = str(feature.params.get("fitting", "barb"))
    if kind not in FITTINGS:
        raise FeatureError(f"{name}: unknown fitting '{kind}'. Choose a fitting in the panel.")
    bore = _value(feature, "bore_diameter", 0.0)
    if _value(feature, "shank_height", 2.0) < 0 or bore < 0:
        raise FeatureError(f"{name}: sizes cannot be below zero. Enter the sizes again.")
    if kind == "barb":
        hose = _value(feature, "hose_diameter", 6.0)
        barb = _value(feature, "barb_diameter", hose * 1.15)
        if hose <= 0 or _value(feature, "ring_length", 3.0) <= 0:
            raise FeatureError(
                f"{name}: the hose size and ring length must be above zero. Enter them."
            )
        if barb <= hose:
            raise FeatureError(
                f"{name}: the barbs must be wider than the stem. Enter a larger barb diameter."
            )
        if not 1 <= round(_value(feature, "ring_count", 3)) <= 20:
            raise FeatureError(f"{name}: use 1 to 20 barbs. Enter another count.")
        if bore >= hose:
            raise FeatureError(
                f"{name}: the bore is as wide as the stem. Enter a smaller bore diameter."
            )
        return
    body = _value(feature, "body_diameter", 7.0)
    widest = (
        LUER_MALE_TIP + LUER_TAPER * LUER_LENGTH if kind == "luer_male" else LUER_FEMALE_OPENING
    )
    if body <= widest + (0.0 if kind == "luer_male" else 1.0):
        raise FeatureError(
            f"{name}: the base is too narrow for the luer taper. Enter a larger body diameter."
        )
    if bore >= LUER_MALE_TIP - 0.8:
        raise FeatureError(f"{name}: the bore leaves no wall in the tip. Enter a smaller bore.")


def _point(feature: Feature, ctx: BuildContext, face: Any) -> tuple[Any, list[Any]]:
    """The picked point, the typed one, or the middle of the face."""
    from fdcad.core.features import fastening as fx

    if feature.refs.get("base_point") or isinstance(feature.params.get("pos_x"), Param):
        return fx.position(feature, ctx, "base_point")
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    c = props.CentreOfMass()
    return (c.X(), c.Y(), c.Z()), []


def _revolve(profile: Profile, origin: Any, up: Any, x: Any) -> Any:
    """Revolve (radius, height) points about the axis ``up`` through ``origin``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    poly = BRepBuilderAPI_MakePolygon()
    for r, z in profile:
        poly.Add(gp_Pnt(*(origin[i] + x[i] * r + up[i] * z for i in range(3))))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    maker = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(*origin), gp_Dir(*up)), 2 * math.pi)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("The fitting shape could not be made. Check the sizes.")
    return maker.Shape()


@register
class HoseFitting(FeatureType):
    """A hose barb or a luer fitting on a face."""

    type_name = "hose_fitting"
    makes_solid = True
    params = (
        ParamSpec("fitting", choices=FITTINGS),
        ParamSpec("hose_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("barb_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("ring_count", kind=Kind.NUMBER, optional=True),
        ParamSpec("ring_length", kind=Kind.LENGTH, optional=True),
        ParamSpec("body_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("shank_height", kind=Kind.LENGTH, optional=True),
        ParamSpec("bore_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("bore_depth", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the fitting, then cut its bore."""
        from fdcad.core.features import fastening as fx
        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.solids import check_result
        from fdcad.core.naming.names import NamedShape, faces_of

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        _check(feature)
        face, issues = fx.face_of(feature, ctx, "base_face")
        point, more = _point(feature, ctx, face)
        direction, found = fx.direction_ref(feature, ctx, "direction")
        origin, normal = fx.on_face(face, point, direction)
        up = fx.unit(direction) if direction is not None else normal
        if fx.dot(up, normal) < 0:
            up = fx.neg(up)
        f = fx.frame(origin, up)
        kind = str(feature.params.get("fitting", "barb"))
        shank = _value(feature, "shank_height", 2.0)
        if kind == "barb":
            hose = _value(feature, "hose_diameter", 6.0)
            widest = hose / 2
        else:
            widest = _value(feature, "body_diameter", 7.0) / 2
        ring = [
            (widest * math.cos(k * math.pi / 8), widest * math.sin(k * math.pi / 8))
            for k in range(16)
        ]
        reach = fx.reach_down(face, f, ring)
        bottom = -reach - 0.01 * widest if reach > 0 else 0.0
        socket: Profile | None = None
        if kind == "barb":
            barb = _value(feature, "barb_diameter", hose * 1.15)
            rings = round(_value(feature, "ring_count", 3))
            outside = barb_profile(
                hose, barb, rings, _value(feature, "ring_length", 3.0), shank, bottom
            )
        else:
            outside, socket = luer_profiles(
                kind == "luer_male", _value(feature, "body_diameter", 7.0), shank, bottom
            )
        top = max(z for _r, z in outside)
        solid = _revolve(outside, f.origin, f.up, f.x)
        tool = NamedShape(
            solid, [(f"{feature.id}/fitting/{j}", s) for j, s in enumerate(faces_of(solid), 1)]
        )
        result = boolean_named("fuse", ctx.body, tool, feature.id, name)
        cuts: list[Any] = []
        if socket is not None:
            cuts.append(_revolve(socket, f.origin, f.up, f.x))
        bore = _value(feature, "bore_diameter", 0.0)
        if bore > 0:
            depth = _value(feature, "bore_depth", 5.0)
            r = bore / 2
            cuts.append(
                _revolve(
                    [(0.0, -depth), (r, -depth), (r, top + 1.0), (0.0, top + 1.0)],
                    f.origin,
                    f.up,
                    f.x,
                )
            )
        for k, cut in enumerate(cuts, 1):
            named = NamedShape(
                cut, [(f"{feature.id}/bore/{k}/{j}", s) for j, s in enumerate(faces_of(cut), 1)]
            )
            result = boolean_named("cut", result, named, feature.id, name)
        issues = issues + more + found + check_result(feature.id, name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)
