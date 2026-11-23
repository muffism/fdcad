"""Corner ears (TUTORIAL_REVIEW_SPEC TR189 item 2, DECISIONS D1005).

Type ``corner_ears``. Pick the flat face that lies on the print bed (``refs.face``).
A thin round disc, ``ear_diameter`` across and ``ear_thickness`` thick, is centred on
each outer corner of that face whose inside angle is at most ``max_angle`` (120
degrees by default, so square and sharper corners get ears). The discs lie on the
face's plane and grow into the part, so they hold the corners down against warping
and are cut or snapped off after printing. Inside (concave) corners get none. New
faces are ``<fid>/ear/<k>/...``.
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

Vec3 = tuple[float, float, float]
_SAMPLES = 8  # points per edge for the winding of the outline


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def corners(face: Any, max_angle: float) -> list[Vec3]:
    """The outer corners of a flat ``face`` with an inside angle up to ``max_angle``
    (radians), in order round the outline."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
    from OCP.TopAbs import TopAbs_REVERSED

    wire = BRepTools.OuterWire_s(face)
    walk = BRepTools_WireExplorer(wire, face)
    # Each edge as (start point, end point, start tangent, end tangent, samples).
    edges: list[tuple[Vec3, Vec3, Vec3, Vec3, list[Vec3]]] = []
    while walk.More():
        edge = walk.Current()
        curve = BRepAdaptor_Curve(edge)
        first, last = curve.FirstParameter(), curve.LastParameter()
        flip = edge.Orientation() == TopAbs_REVERSED
        a, b = (last, first) if flip else (first, last)
        sign = -1.0 if flip else 1.0

        def point(t: float, c: Any = curve) -> Vec3:
            p = c.Value(t)
            return (p.X(), p.Y(), p.Z())

        def tangent(t: float, c: Any = curve, s: float = sign) -> Vec3:
            d = c.DN(t, 1)
            return _unit((s * d.X(), s * d.Y(), s * d.Z()))

        samples = [point(a + (b - a) * k / _SAMPLES) for k in range(_SAMPLES)]
        edges.append((point(a), point(b), tangent(a), tangent(b), samples))
        walk.Next()
    if len(edges) < 2:
        return []
    outline = [p for e in edges for p in e[4]]
    # The outline's winding about any axis: the sum of crosses of the points.
    winding = (0.0, 0.0, 0.0)
    for k, p in enumerate(outline):
        q = outline[(k + 1) % len(outline)]
        c = _cross(p, q)
        winding = (winding[0] + c[0], winding[1] + c[1], winding[2] + c[2])
    up = _unit(winding)
    out: list[Vec3] = []
    for k, edge in enumerate(edges):
        after = edges[(k + 1) % len(edges)]
        d_in, d_out = edge[3], after[2]
        turn = math.acos(max(-1.0, min(1.0, _dot(d_in, d_out))))
        if turn < 1e-3 or _dot(_cross(d_in, d_out), up) <= 0:
            continue  # smooth, or an inside (concave) corner
        if math.pi - turn <= max_angle + 1e-9:
            out.append(edge[1])
    return out


@register
class CornerEars(FeatureType):
    """Thin discs at the sharp outer corners of the bed face, against warping."""

    type_name = "corner_ears"
    makes_solid = True
    params = (
        ParamSpec("ear_diameter", kind=Kind.LENGTH),
        ParamSpec("ear_thickness", kind=Kind.LENGTH),
        ParamSpec("max_angle", kind=Kind.ANGLE, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the ears."""
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        from OCP.GeomAbs import GeomAbs_Plane
        from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
        from OCP.TopAbs import TopAbs_REVERSED

        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.solids import check_result, compound
        from fdcad.core.naming.names import NamedShape, faces_of
        from fdcad.core.naming.resolve import resolve_face

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        refs = feature.refs.get("face")
        ref = refs[0] if isinstance(refs, list) and refs else refs
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: pick the flat face that lies on the print bed.")
        face = resolve_face(ctx.body, ref, name)[0]
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            raise FeatureError(f"{name}: the picked face is not flat. Pick the bed face.")
        diameter = _value(feature, "ear_diameter", 10.0)
        thickness = _value(feature, "ear_thickness", 0.4)
        if diameter <= 0 or thickness <= 0:
            raise FeatureError(
                f"{name}: the ear diameter and thickness must be above zero. Enter them."
            )
        limit = _value(feature, "max_angle", math.radians(120))
        found = corners(face, limit)
        if not found:
            raise FeatureError(
                f"{name}: the face has no outer corner of {math.degrees(limit):g} degrees or "
                "sharper. Enter a larger corner angle, or pick another face."
            )
        normal = surface.Plane().Axis().Direction()
        if face.Orientation() == TopAbs_REVERSED:
            normal.Reverse()
        inward = gp_Dir(-normal.X(), -normal.Y(), -normal.Z())  # from the bed into the part
        ears = [
            BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*p), inward), diameter / 2, thickness).Shape()
            for p in found
        ]
        names = [
            (f"{feature.id}/ear/{k + 1}/{j}", f)
            for k, ear in enumerate(ears)
            for j, f in enumerate(faces_of(ear), 1)
        ]
        result = boolean_named(
            "fuse", ctx.body, NamedShape(compound(ears), names), feature.id, name
        )
        return FeatureResult(
            body=result, issues=check_result(feature.id, name, ctx.body, result, None)
        )
