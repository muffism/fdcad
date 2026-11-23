"""Local deform modes: Deform Point, Curve to Curve and Surface Push (TR67, D2412).

These move part of a body and leave the rest, unlike the triad tools (bend, twist,
taper, stretch, flow), so they ignore the triad and trim planes. They share the same
NURBS deformation, tolerance check and approximate warning (feature.py, nurbs.py).
Every map works on whole arrays of points (CLAUDE.md 5A item 2). No Qt.

- ``deform_point``: refs ``point`` (where), ``direction`` (optional: a direction;
  default the normal of the face the point is on, or +Z) and ``fixed`` (optional
  faces or edges that stay put). Params ``distance``, ``radius`` (of influence) and
  ``stiffness`` (0 to 1: the part of the radius that moves the full distance).
- ``deform_curve``: refs ``initial`` and ``target`` (sketches or curves) and
  ``fixed``. Param ``radius``: how far from the initial curve the body follows.
  Points on the initial curve move to the matching point of the target curve (by
  length along each), and the movement fades out over the radius.
- ``surface_push``: refs ``point`` (where the tool first touches) and ``direction``
  (the push, into the face). Params ``tool`` (sphere, ellipsoid or rectangle),
  ``depth``, ``tool_x`` and ``tool_y`` (half sizes across; a sphere uses
  ``tool_x``) and ``reach`` (how deep into the body the dent fades out; default
  three times the depth).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from fdcad.core.deform.feature import COMMON_PARAMS, DeformFeature
from fdcad.core.deform.maps import Frame, PointMap
from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, ParamSpec, register
from fdcad.core.units import Kind

Points = NDArray[np.float64]
TOOLS = ("sphere", "ellipsoid", "rectangle")
#: Samples along each curve of Curve to Curve, and on the fixed items.
CURVE_SAMPLES = 96
_CHUNK = 20000


def _unit(v: Any) -> Points:
    a = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(a))
    if n < 1e-12:
        raise ValueError("the direction has no length. Pick another direction")
    return a / n


def _point(feature: Feature, ctx: BuildContext, key: str) -> Points:
    from fdcad.core.features.geometry_refs import resolve_placement

    ref = feature.refs.get(key)
    ref = ref[0] if isinstance(ref, list) and ref else ref
    if not isinstance(ref, dict):
        raise FeatureError(f"{feature.name}: pick the point to move.")
    if isinstance(ref.get("feature"), str) and len(ref) == 1:
        datum = ctx.result(ref["feature"]).datum
        if datum is not None and datum.kind == "point":
            return np.asarray(datum.origin, dtype=float)
    return np.asarray(resolve_placement(ctx, ref, feature.name, "point").point, dtype=float)


def _direction(feature: Feature, ctx: BuildContext, at: Points) -> Points:
    """The picked direction, or the normal of the part's face nearest ``at`` (outward)."""
    from fdcad.core.features.geometry_refs import resolve_placement

    ref = feature.refs.get("direction")
    ref = ref[0] if isinstance(ref, list) and ref else ref
    if isinstance(ref, dict):
        return _unit(resolve_placement(ctx, ref, feature.name, "direction").direction)
    if ctx.body is None:
        return np.array([0.0, 0.0, 1.0])
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt

    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, at))).Vertex()
    dist = BRepExtrema_DistShapeShape(vertex, ctx.body.shape)
    if dist.IsDone() and dist.NbSolution() and dist.SupportTypeShape2(1) == 2:  # on a face
        from OCP.BRepGProp import BRepGProp_Face
        from OCP.gp import gp_Vec
        from OCP.TopoDS import TopoDS

        face = TopoDS.Face(dist.SupportOnShape2(1))
        u, v = dist.ParOnFaceS2(1)
        p, n = gp_Pnt(), gp_Vec()
        BRepGProp_Face(face).Normal(u, v, p, n)
        if n.Magnitude() > 1e-12:
            return _unit((n.X(), n.Y(), n.Z()))
    return np.array([0.0, 0.0, 1.0])


def _fixed_points(feature: Feature, ctx: BuildContext) -> tuple[Points, float] | None:
    """Points sampled on the fixed faces and edges, and the largest gap a point on them
    can have to the nearest sample; None without any."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools

    from fdcad.core.features.direct import resolve_faces
    from fdcad.core.features.modify import resolve_edges

    refs = feature.refs.get("fixed")
    if not isinstance(refs, list) or not refs or ctx.body is None:
        return None
    faces = [r for r in refs if isinstance(r, dict) and r.get("kind") == "face"]
    edges = [r for r in refs if isinstance(r, dict) and r.get("kind") == "edge"]
    out: list[Points] = []
    gap = 0.0
    if faces:
        found, _names, _issues = resolve_faces(ctx, faces, feature.name, "fixed faces")
        for face in found:  # a grid over each face's parameters (bounded: 24 x 24)
            u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
            surface = BRepAdaptor_Surface(face)
            grid = np.array(
                [
                    surface.Value(u0 + (u1 - u0) * i / 23, v0 + (v1 - v0) * j / 23).Coord()
                    for i in range(24)
                    for j in range(24)
                ]
            )
            out.append(grid)
            step_u = np.linalg.norm(np.diff(grid.reshape(24, 24, 3), axis=0), axis=2).max()
            step_v = np.linalg.norm(np.diff(grid.reshape(24, 24, 3), axis=1), axis=2).max()
            gap = max(gap, 0.5 * float(np.hypot(step_u, step_v)))
    if edges:
        holder = Feature(feature.id, feature.type, feature.name, refs={"e": edges})
        for _name, edge in resolve_edges(holder, ctx, "e")[0]:
            curve = BRepAdaptor_Curve(edge)
            ts = np.linspace(curve.FirstParameter(), curve.LastParameter(), 32)
            out.append(np.array([curve.Value(float(t)).Coord() for t in ts]))
    pts = [p for p in out if len(p)]
    return (np.concatenate(pts), gap) if pts else None


def _nearest(points: Points, cloud: Points) -> Points:
    """The distance from each point to the nearest point of ``cloud``, in chunks."""
    out = np.empty(len(points))
    step = max(1, _CHUNK // max(len(cloud), 1))
    for k in range(0, len(points), step):
        d = np.linalg.norm(points[k : k + step, None, :] - cloud[None, :, :], axis=2)
        out[k : k + step] = d.min(axis=1)
    return out


def _held(fixed: tuple[Points, float] | None, reach: float) -> Any:
    """A factor from 0 on the fixed items to 1 a ``reach`` away from them (the samples'
    own spacing is taken off, so every point of a fixed face stays put)."""
    if fixed is None:
        return lambda pts: 1.0
    cloud, gap = fixed
    return lambda pts: np.clip((_nearest(pts, cloud) - gap) / reach, 0.0, 1.0)[:, None]


def falloff(t: Points) -> Points:
    """1 at 0, 0 at 1 and beyond, smooth at both ends: (1 - t^2)^2."""
    s = np.clip(t, 0.0, 1.0)
    return (1.0 - s * s) ** 2


@register
class DeformPoint(DeformFeature):
    """Pulls the body round a point along a direction, fading over a radius."""

    type_name = "deform_point"
    main_value = "distance"
    params = (
        *COMMON_PARAMS,
        ParamSpec("distance", kind=Kind.LENGTH),
        ParamSpec("radius", kind=Kind.LENGTH),
        ParamSpec("stiffness", kind=Kind.NUMBER, optional=True),
    )

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """Move points near the point along the direction."""
        centre = _point(feature, ctx, "point")
        way = _direction(feature, ctx, centre)
        distance = self.number(feature, "distance")
        radius = self.number(feature, "radius")
        stiff = self._value(feature, "stiffness", 0.0)
        if radius <= 0:
            raise ValueError("the radius must be above zero. Enter a larger radius")
        if not 0.0 <= stiff < 1.0:
            raise ValueError("the stiffness must be from 0 up to but not 1. Enter another")
        held = _held(_fixed_points(feature, ctx), radius)

        def fmap(pts: Points) -> Points:
            d = np.linalg.norm(pts - centre, axis=1)
            t = (d - stiff * radius) / ((1.0 - stiff) * radius)
            w = falloff(t)[:, None] * held(pts)
            out: Points = pts + way[None, :] * distance * w
            return out

        return fmap


@register
class DeformCurve(DeformFeature):
    """Moves the body near one curve onto another curve."""

    type_name = "deform_curve"
    main_value = "radius"
    params = (*COMMON_PARAMS, ParamSpec("radius", kind=Kind.LENGTH))

    def _samples(self, feature: Feature, ctx: BuildContext, key: str) -> Points:
        from fdcad.core.deform.flow import sample_curve
        from fdcad.core.features.sweep import path_wire

        holder = Feature(feature.id, feature.type, feature.name, refs={"path": feature.refs[key]})
        wire, _issues = path_wire(holder, ctx)
        samples = sample_curve(wire, (0.0, 0.0, 1.0))
        s, pts = np.asarray(samples.s), np.asarray(samples.points)
        even = np.linspace(0.0, float(s[-1]), CURVE_SAMPLES)
        out: Points = np.stack([np.interp(even, s, pts[:, k]) for k in range(3)], axis=1)
        return out

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """Each point follows the nearby moves from the initial to the target curve."""
        for key in ("initial", "target"):
            if not feature.refs.get(key):
                raise FeatureError(f"{feature.name}: pick the {key} curve.")
        start = self._samples(feature, ctx, "initial")
        end = self._samples(feature, ctx, "target")
        moves = end - start
        radius = self.number(feature, "radius")
        if radius <= 0:
            raise ValueError("the radius must be above zero. Enter a larger radius")
        held = _held(_fixed_points(feature, ctx), radius)
        spacing = float(np.linalg.norm(np.diff(start, axis=0), axis=1).mean()) or radius

        def fmap(pts: Points) -> Points:
            out = np.empty_like(pts)
            step = max(1, _CHUNK // len(start))
            for k in range(0, len(pts), step):
                chunk = pts[k : k + step]
                d = np.linalg.norm(chunk[:, None, :] - start[None, :, :], axis=2)
                weights = np.exp(-((d / max(spacing, 1e-9)) ** 2))
                total = weights.sum(axis=1, keepdims=True)
                local = weights @ moves / np.maximum(total, 1e-300)
                fade = falloff(d.min(axis=1) / radius)[:, None]
                out[k : k + step] = chunk + local * fade * held(chunk)
            return out

        return fmap


@register
class SurfacePush(DeformFeature):
    """Presses a tool shape into a face: a dent that fades into the body."""

    type_name = "surface_push"
    main_value = "depth"
    params = (
        *COMMON_PARAMS,
        ParamSpec("tool", choices=TOOLS, default="sphere", optional=True),
        ParamSpec("depth", kind=Kind.LENGTH),
        ParamSpec("tool_x", kind=Kind.LENGTH),
        ParamSpec("tool_y", kind=Kind.LENGTH, optional=True),
        ParamSpec("reach", kind=Kind.LENGTH, optional=True),
    )

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """Move points under the tool along the push, less and less deeper in."""
        touch = _point(feature, ctx, "point")
        if feature.refs.get("direction"):
            push = _direction(feature, ctx, touch)
        else:
            push = -_direction(feature, ctx, touch)  # into the face
        depth = self.number(feature, "depth")
        a = self.number(feature, "tool_x")
        b = self._value(feature, "tool_y", a)
        reach = self._value(feature, "reach", 3.0 * depth)
        tool = str(feature.params.get("tool", "sphere"))
        if depth <= 0 or a <= 0 or b <= 0 or reach <= 0:
            raise ValueError("the depth, tool sizes and reach must be above zero. Enter them")
        if tool == "sphere" and depth > a:
            raise ValueError("a sphere cannot push deeper than its radius. Reduce the depth")
        helper = np.array([1.0, 0.0, 0.0]) if abs(push[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        ux = _unit(np.cross(push, helper))
        uy = np.cross(push, ux)

        def profile(x: Points, y: Points) -> Points:
            if tool == "rectangle":  # flat bottom with rounded sides a fifth of the size
                edge = 0.2 * min(a, b)
                tx = (np.abs(x) - (a - edge)) / edge
                ty = (np.abs(y) - (b - edge)) / edge
                out: Points = depth * falloff(np.maximum(tx, 0.0)) * falloff(np.maximum(ty, 0.0))
                return out
            r2 = (x / a) ** 2 + (y / (a if tool == "sphere" else b)) ** 2
            c = a  # the tool's depth: a sphere's radius, an ellipsoid as deep as tool_x
            sag = c - c * np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))
            return np.clip(depth - sag, 0.0, None)

        def fmap(pts: Points) -> Points:
            rel = pts - touch
            x, y, s = rel @ ux, rel @ uy, rel @ push
            fade = np.clip(1.0 - s / reach, 0.0, 1.0)
            fade = np.where(s < 0, 1.0, fade)
            move = profile(x, y) * fade
            out: Points = pts + push[None, :] * move[:, None]
            return out

        return fmap
