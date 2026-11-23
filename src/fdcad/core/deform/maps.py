"""Deformation maps: where each point of space goes (PLAN Phase 4, PHASE4_SPEC P4.9).

Every map works on whole arrays of points at once (CLAUDE.md 5A item 2). Points
are first written in the triad's frame: ``x`` along the first axis, ``y``
along the second and ``z`` along the third. Only the region between the trim
planes ``z0`` and ``z1`` deforms; beyond ``z1`` the part moves rigidly with the
end of the deformed region, and below ``z0`` it stays where it is, so the
result has no gaps. Pure numpy: no kernel and no Qt.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Points = NDArray[np.float64]
Vec3 = tuple[float, float, float]
PointMap = Callable[[Points], Points]


def _unit(v: Vec3) -> NDArray[np.float64]:
    a = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(a))
    if n < 1e-12:
        raise ValueError("A direction has no length.")
    return a / n


@dataclass(frozen=True)
class Frame:
    """The triad: an origin and three perpendicular unit axes (right handed)."""

    origin: Vec3
    x: Vec3
    y: Vec3
    z: Vec3

    @classmethod
    def from_axes(cls, origin: Vec3, third: Vec3, first: Vec3) -> Frame:
        """A frame from the third axis and a first axis direction (made perpendicular)."""
        z = _unit(third)
        f = np.asarray(first, dtype=float)
        x = f - z * float(np.dot(f, z))
        if np.linalg.norm(x) < 1e-9:
            raise ValueError("The first axis cannot be parallel to the third axis.")
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        return cls(
            tuple(float(c) for c in origin),  # type: ignore[arg-type]
            tuple(float(c) for c in x),  # type: ignore[arg-type]
            tuple(float(c) for c in y),  # type: ignore[arg-type]
            tuple(float(c) for c in z),  # type: ignore[arg-type]
        )

    @property
    def matrix(self) -> NDArray[np.float64]:
        """Rows are the axes: local = matrix @ (world - origin)."""
        return np.array([self.x, self.y, self.z], dtype=float)

    def to_local(self, pts: Points) -> Points:
        """World points to triad coordinates."""
        out: Points = (pts - np.asarray(self.origin)) @ self.matrix.T
        return out

    def to_world(self, pts: Points) -> Points:
        """Triad coordinates to world points."""
        out: Points = pts @ self.matrix + np.asarray(self.origin)
        return out


def _framed(frame: Frame, local: Callable[[Points], Points]) -> PointMap:
    def apply(pts: Points) -> Points:
        return frame.to_world(local(frame.to_local(np.asarray(pts, dtype=float))))

    return apply


def _fraction(z: NDArray[np.float64], z0: float, z1: float) -> NDArray[np.float64]:
    """0 below the start plane, 1 beyond the end plane, linear between."""
    span = z1 - z0
    if span <= 0:
        raise ValueError("The end trim plane must lie beyond the start trim plane.")
    return np.clip((z - z0) / span, 0.0, 1.0)


def twist(frame: Frame, z0: float, z1: float, angle: float) -> PointMap:
    """Turn about the third axis, from 0 at the start plane to ``angle`` at the end plane."""

    def local(p: Points) -> Points:
        a = angle * _fraction(p[:, 2], z0, z1)
        c, s = np.cos(a), np.sin(a)
        out = p.copy()
        out[:, 0] = p[:, 0] * c - p[:, 1] * s
        out[:, 1] = p[:, 0] * s + p[:, 1] * c
        return out

    return _framed(frame, local)


def taper(frame: Frame, z0: float, z1: float, factor: float) -> PointMap:
    """Scale across the third axis, from 1 at the start plane to ``factor`` at the end plane."""
    if factor <= 0:
        raise ValueError("The taper factor must be above zero.")

    def local(p: Points) -> Points:
        s = 1.0 + (factor - 1.0) * _fraction(p[:, 2], z0, z1)
        out = p.copy()
        out[:, 0] *= s
        out[:, 1] *= s
        return out

    return _framed(frame, local)


def stretch(frame: Frame, z0: float, z1: float, distance: float) -> PointMap:
    """Lengthen the region between the planes by ``distance`` along the third axis."""
    span = z1 - z0
    if span + distance <= 0:
        raise ValueError("The stretch distance would shrink the region to nothing.")

    def local(p: Points) -> Points:
        out = p.copy()
        out[:, 2] = p[:, 2] + distance * _fraction(p[:, 2], z0, z1)
        return out

    return _framed(frame, local)


def bend_radius(length: float, angle: float) -> float:
    """The radius that bends ``length`` through ``angle`` (the bent length stays the same)."""
    if abs(angle) < 1e-12:
        return math.inf
    return length / angle


def bend(frame: Frame, z0: float, z1: float, angle: float) -> PointMap:
    """Bend the region about an axis along the first axis, through ``angle``.

    The bend centre lies on the second axis at the signed radius ``(z1 - z0) /
    angle``, so a positive angle bends towards the second axis. Lengths along
    the third axis at ``y = 0`` stay the same.
    """
    length = z1 - z0
    if length <= 0:
        raise ValueError("The end trim plane must lie beyond the start trim plane.")
    if abs(angle) < 1e-12:
        return lambda pts: np.asarray(pts, dtype=float).copy()
    radius = length / angle

    def local(p: Points) -> Points:
        z = p[:, 2]
        y = p[:, 1]
        inside = np.clip(z, z0, z1)
        phi = (inside - z0) / radius
        beyond = np.maximum(z - z1, 0.0)
        before = np.minimum(z - z0, 0.0)
        arm = radius - y
        out = p.copy()
        out[:, 2] = z0 + arm * np.sin(phi) + beyond * np.cos(phi) + before
        out[:, 1] = radius - arm * np.cos(phi) + beyond * np.sin(phi)
        return out

    return _framed(frame, local)


@dataclass(frozen=True)
class CurveSamples:
    """A curve sampled by arc length: points, unit tangents and a turning free normal."""

    s: NDArray[np.float64]
    points: NDArray[np.float64]
    tangents: NDArray[np.float64]
    normals: NDArray[np.float64]

    @property
    def length(self) -> float:
        """The curve's length."""
        return float(self.s[-1])


def rotation_minimizing(
    s: NDArray[np.float64],
    points: NDArray[np.float64],
    tangents: NDArray[np.float64],
    start_normal: Vec3,
) -> CurveSamples:
    """Carry ``start_normal`` along the curve without twisting it (double reflection)."""
    t = tangents / np.linalg.norm(tangents, axis=1)[:, None]
    n0 = np.asarray(start_normal, dtype=float)
    n0 = n0 - t[0] * float(np.dot(n0, t[0]))
    if np.linalg.norm(n0) < 1e-9:
        raise ValueError("The triad's first axis is along the curve's start. Turn the triad.")
    normals = np.zeros_like(points)
    normals[0] = n0 / np.linalg.norm(n0)
    # The frame recurrence depends on the previous normal, so it runs once per sample.
    for i in range(len(points) - 1):
        v1 = points[i + 1] - points[i]
        c1 = float(np.dot(v1, v1))
        if c1 < 1e-24:
            normals[i + 1] = normals[i]
            continue
        r_l = normals[i] - (2.0 / c1) * float(np.dot(v1, normals[i])) * v1
        t_l = t[i] - (2.0 / c1) * float(np.dot(v1, t[i])) * v1
        v2 = t[i + 1] - t_l
        c2 = float(np.dot(v2, v2))
        r = r_l - (2.0 / c2) * float(np.dot(v2, r_l)) * v2 if c2 > 1e-24 else r_l
        normals[i + 1] = r / np.linalg.norm(r)
    return CurveSamples(s, points, t, normals)


def flow(frame: Frame, z0: float, z1: float, curve: CurveSamples, scale: float) -> PointMap:
    """Lay the region between the planes along ``curve``.

    The start plane goes to the curve's start; ``scale`` curve millimetres
    follow each millimetre along the third axis. The first axis follows the
    curve's normal and the second its binormal. Beyond the curve's end the part
    goes on straight along the end tangent, and below the start plane it goes
    on straight backwards from the start.
    """
    if scale <= 0:
        raise ValueError("The flow scale must be above zero.")
    binormals = np.cross(curve.tangents, curve.normals)
    length = curve.length

    def _at(values: NDArray[np.float64], d: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.stack([np.interp(d, curve.s, values[:, k]) for k in range(3)], axis=1)

    def local(p: Points) -> Points:
        along = (p[:, 2] - z0) * scale
        d = np.clip(along, 0.0, length)
        extra = (along - d)[:, None]
        base = _at(curve.points, d)
        tangent = _at(curve.tangents, d)
        normal = _at(curve.normals, d)
        binormal = _at(binormals, d)
        for arr in (tangent, normal, binormal):
            arr /= np.linalg.norm(arr, axis=1)[:, None]
        world = base + tangent * extra + normal * p[:, [0]] + binormal * p[:, [1]]
        # Back into triad coordinates, so _framed's to_world gives the world points.
        return frame.to_local(world)

    return _framed(frame, local)
