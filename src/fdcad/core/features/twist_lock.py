"""Twist lock (bayonet) joint for printed lids (TR357, DECISIONS D1024).

Type ``twist_lock``. Pick the outer round face of the inner part, the plug
(``refs.face``). Lugs stand out of that face; every other body that the lugs' paths
reach (the socket) gets an L shaped slot for each lug: a straight entry from the
open end down to the lugs, then a turn round the axis, so the lid pushes in and
twists to lock.

Params: ``lug_count`` lugs, evenly round; ``lug_width`` (round the face), ``lug_height``
(along the axis) and ``lug_depth`` (how far they stand out); ``lock_depth``, from the
plug's open end to the lugs' centre; ``twist``, the turn to lock; ``lock_clearance``, the
gap left round each lug in the slot; ``other_end`` takes the other end of the face as
the open end; ``clockwise`` turns the other way. New faces are ``<fid>/lug/<k>`` on
the plug and ``<fid>/slot/<k>`` in the socket.
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

DEFAULTS = {
    "lug_count": 3.0,
    "lug_width": 4.0,
    "lug_height": 2.0,
    "lug_depth": 1.5,
    "lock_depth": 4.0,
    "twist": math.radians(30),
    "lock_clearance": 0.2,
}


def _value(feature: Feature, key: str) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else DEFAULTS[key]


def sector(frame: Any, r0: float, r1: float, z0: float, z1: float, a0: float, a1: float) -> Any:
    """The solid between radii ``r0`` and ``r1``, heights ``z0`` and ``z1`` along the
    frame's Z, and angles ``a0`` to ``a1`` from the frame's X (radians)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Pnt

    from fdcad.core.occ import BRepAlgoAPI_Cut

    loc, z = frame.Location(), frame.Direction()
    base = gp_Pnt(loc.X() + z.X() * z0, loc.Y() + z.Y() * z0, loc.Z() + z.Z() * z0)
    x = frame.XDirection().Rotated(gp_Ax1(loc, z), a0)
    ax = gp_Ax2(base, z, x)
    outer = BRepPrimAPI_MakeCylinder(ax, r1, z1 - z0, a1 - a0).Shape()
    inner = BRepPrimAPI_MakeCylinder(ax, r0, z1 - z0).Shape()
    return BRepAlgoAPI_Cut(outer, inner).Shape()


def _union(shapes: list[Any]) -> Any:
    from fdcad.core.occ import BRepAlgoAPI_Fuse

    out = shapes[0]
    for s in shapes[1:]:
        out = BRepAlgoAPI_Fuse(out, s).Shape()
    return out


@register
class TwistLock(FeatureType):
    """Lugs on a plug and L shaped slots in the part round it."""

    type_name = "twist_lock"
    makes_solid = True
    params = (
        ParamSpec("lug_count", kind=Kind.NUMBER, optional=True),
        ParamSpec("lug_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("lug_height", kind=Kind.LENGTH, optional=True),
        ParamSpec("lug_depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("lock_depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("twist", kind=Kind.ANGLE, optional=True),
        ParamSpec("lock_clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("other_end", default=False, optional=True),
        ParamSpec("clockwise", default=False, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the lugs and cut the slots."""
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.GeomAbs import GeomAbs_Cylinder
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_IN

        from fdcad.core.features.bodies import join, rest_of, solid_of_face, sub_body
        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.lookup import resolve_face
        from fdcad.core.features.solids import bounding_size, check_result, solids, volume_of
        from fdcad.core.naming.names import NamedShape, faces_of
        from fdcad.core.occ import BRepAlgoAPI_Common

        name, fid = feature.name, feature.id
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add the lid and the box first.")
        ref = feature.refs.get("face")
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: pick the outer round face of the inner part.")
        face, issues = resolve_face(ctx.body, ref, name)
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder:
            raise FeatureError(f"{name}: the face is not round. Pick a cylinder face.")
        cylinder = surface.Cylinder()
        frame, radius = cylinder.Position(), cylinder.Radius()
        v0, v1 = surface.FirstVParameter(), surface.LastVParameter()
        all_solids = solids(ctx.body.shape)
        plug_index = solid_of_face(ctx.body.shape, face)
        if plug_index < 0:
            raise FeatureError(f"{name}: the picked face was lost. Pick it again.")
        plug = all_solids[plug_index]
        # The plug is inside its round face: a point just outside must not be in it.
        mid_u = (surface.FirstUParameter() + surface.LastUParameter()) / 2
        on = surface.Value(mid_u, (v0 + v1) / 2)
        loc = frame.Location()
        axis = frame.Direction()
        radial = gp_Pnt(on.X() - loc.X(), on.Y() - loc.Y(), on.Z() - loc.Z())
        along = radial.X() * axis.X() + radial.Y() * axis.Y() + radial.Z() * axis.Z()
        out = (
            radial.X() - along * axis.X(),
            radial.Y() - along * axis.Y(),
            radial.Z() - along * axis.Z(),
        )
        size = math.sqrt(sum(c * c for c in out)) or 1.0
        probe = gp_Pnt(
            on.X() + out[0] / size * 0.05,
            on.Y() + out[1] / size * 0.05,
            on.Z() + out[2] / size * 0.05,
        )
        if BRepClass3d_SolidClassifier(plug, probe, 1e-7).State() == TopAbs_IN:
            raise FeatureError(
                f"{name}: the face is a bore. Pick the outer round face of the inner part."
            )

        count = round(_value(feature, "lug_count"))
        width, height = _value(feature, "lug_width"), _value(feature, "lug_height")
        stand, depth = _value(feature, "lug_depth"), _value(feature, "lock_depth")
        twist, gap = _value(feature, "twist"), _value(feature, "lock_clearance")
        if count < 1 or count > 12:
            raise FeatureError(f"{name}: use 1 to 12 lugs. Enter another number of lugs.")
        for label, v in (("lug width", width), ("lug height", height), ("lug depth", stand)):
            if not v > 0:
                raise FeatureError(f"{name}: the {label} must be more than 0. Enter a size.")
        if gap < 0 or twist <= 0:
            raise FeatureError(
                f"{name}: the twist must be more than 0 and the clearance not below 0. "
                "Enter other values."
            )
        half = (width / 2 + gap) / radius
        if twist + 2 * half >= 2 * math.pi / count:
            raise FeatureError(
                f"{name}: the slots would run into each other. Use fewer lugs, narrower lugs "
                "or a smaller twist."
            )
        mouth = -1.0 if feature.params.get("other_end") is True else 1.0
        end = v0 if mouth < 0 else v1
        centre = end - mouth * depth
        low_v, high_v = min(v0, v1), max(v0, v1)
        if not (low_v + height / 2 <= centre <= high_v - height / 2):
            raise FeatureError(
                f"{name}: the lugs do not fit on the face at that depth. Enter a depth between "
                f"{height / 2:.4g} and {high_v - low_v - height / 2:.4g}."
            )
        turn = (-1.0 if feature.params.get("clockwise") is True else 1.0) * mouth
        reach = 2 * bounding_size(ctx.body.shape) + 10.0
        inner = radius - min(stand, radius / 2) / 2
        lugs, slots = [], []
        for k in range(count):
            a = 2 * math.pi * k / count
            lug_half = (width / 2) / radius
            lugs.append(
                sector(
                    frame, inner, radius + stand, centre - height / 2, centre + height / 2,
                    a - lug_half, a + lug_half,
                )
            )  # fmt: skip
            z_in = centre - mouth * (height / 2 + gap)
            z_out = end + mouth * reach
            entry = sector(
                frame, inner, radius + stand + gap, min(z_in, z_out), max(z_in, z_out),
                a - half, a + half,
            )  # fmt: skip
            a_end = a + turn * twist
            ring = sector(
                frame, inner, radius + stand + gap, centre - height / 2 - gap,
                centre + height / 2 + gap, min(a, a_end) - half, max(a, a_end) + half,
            )  # fmt: skip
            slots.append(_union([entry, ring]))
        lug_shape, slot_shape = _union(lugs), _union(slots)
        sockets = [
            i
            for i, s in enumerate(all_solids)
            if i != plug_index and volume_of(BRepAlgoAPI_Common(s, slot_shape).Shape()) > 1e-6
        ]
        if not sockets:
            raise FeatureError(
                f"{name}: no other body is round the plug where the slots go. Add a box body "
                "round the lid's plug, or change the depth."
            )
        lug_tool = NamedShape(
            lug_shape, [(f"{fid}/lug/{k}", f) for k, f in enumerate(faces_of(lug_shape), 1)]
        )
        slot_tool = NamedShape(
            slot_shape, [(f"{fid}/slot/{k}", f) for k, f in enumerate(faces_of(slot_shape), 1)]
        )
        parts: list[NamedShape | None] = [rest_of(ctx.body, [plug_index, *sockets], fid)]
        parts.append(
            boolean_named("fuse", sub_body(ctx.body, [plug_index], fid), lug_tool, fid, name)
        )
        for index in sockets:
            parts.append(
                boolean_named("cut", sub_body(ctx.body, [index], fid), slot_tool, fid, name)
            )
        result = join(parts, fid)
        assert result is not None
        found = [
            i for i in check_result(fid, name, ctx.body, result, None) if i.code != "separate_body"
        ]
        return FeatureResult(body=result, issues=[*issues, *found])
