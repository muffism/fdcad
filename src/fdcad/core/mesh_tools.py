"""Measuring and sectioning an imported mesh (PLAN Phase 3, PHASE3_SPEC P3.9, DECISIONS D412).

A reference mesh has no faces the kernel can measure, so its numbers come from
the triangles with whole array numpy work (CLAUDE.md 5A rule 2): no Python loop
touches a triangle or a vertex.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from fdcad.core.io.mesh_import import Mesh
from fdcad.core.measure import Measurement, Value

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class MeshMeasure:
    """Sizes of a mesh. ``volume`` is None when the mesh is not closed."""

    triangles: int
    area: float
    volume: float | None
    low: Vec3
    high: Vec3
    centre: Vec3

    @property
    def size(self) -> Vec3:
        """Size of the box around the mesh along X, Y and Z."""
        return (
            self.high[0] - self.low[0],
            self.high[1] - self.low[1],
            self.high[2] - self.low[2],
        )

    def measurement(self) -> Measurement:
        """The rows shown in the Measure box."""
        values = [
            Value("triangles", "count", float(self.triangles)),
            Value("size", "point", self.size),
            Value("area", "area", self.area),
        ]
        if self.volume is not None:
            values.append(Value("volume", "volume", self.volume))
        values.append(Value("centre", "point", self.centre))
        return Measurement(values)


@dataclass(frozen=True)
class MeshSection:
    """Where a plane cuts a mesh: segment count, outline length and the cut area
    (None when the mesh is not closed, so the outline need not close)."""

    segments: int
    length: float
    area: float | None


def _vec(a: NDArray[np.float64]) -> Vec3:
    return (float(a[0]), float(a[1]), float(a[2]))


def is_closed(mesh: Mesh) -> bool:
    """True when every triangle edge is shared by exactly two triangles.

    Each edge is one int64 key (low corner times the vertex count plus the high
    corner), and the sorted keys must come in pairs: a sort of one flat array is
    about 20 times quicker than ``np.unique`` over rows (D2660).
    """
    if mesh.triangle_count == 0:
        return False
    t = mesh.triangles.astype(np.int64)
    a = np.concatenate([t[:, 0], t[:, 1], t[:, 2]])
    b = np.concatenate([t[:, 1], t[:, 2], t[:, 0]])
    count = int(max(int(t.max()) + 1, len(mesh.vertices)))
    keys = np.minimum(a, b) * count + np.maximum(a, b)
    keys.sort()
    first, second = keys[0::2], keys[1::2]
    # Every key twice: the pairs match, and no key runs on into the next pair.
    return bool(np.array_equal(first, second) and np.all(second[:-1] != first[1:]))


def measure_mesh(mesh: Mesh) -> MeshMeasure:
    """Triangle count, area, volume (closed meshes), box and centre of ``mesh``."""
    corners = mesh.corners().astype(np.float64)
    a, b, c = corners[:, 0], corners[:, 1], corners[:, 2]
    cross = np.cross(b - a, c - a)
    area = 0.5 * float(np.linalg.norm(cross, axis=1).sum())
    verts = mesh.vertices.astype(np.float64)
    low = verts.min(axis=0) if len(verts) else np.zeros(3)
    high = verts.max(axis=0) if len(verts) else np.zeros(3)
    centre = (low + high) / 2.0
    volume: float | None = None
    if is_closed(mesh):
        parts = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
        signed = float(parts.sum())
        volume = abs(signed)
        if volume > 0:
            centre = ((a + b + c) / 4.0 * parts[:, None]).sum(axis=0) / signed
    return MeshMeasure(mesh.triangle_count, area, volume, _vec(low), _vec(high), _vec(centre))


def section_segments(mesh: Mesh, origin: Vec3, normal: Vec3) -> NDArray[np.float64]:
    """The cut of ``mesh`` by a plane as (k, 2, 3) segments.

    For a closed mesh with outward triangles, each segment runs anticlockwise
    round the cut seen from the ``normal`` side, so the cut area adds up.
    """
    n = np.asarray(normal, dtype=np.float64)
    n = n / (np.linalg.norm(n) or 1.0)
    o = np.asarray(origin, dtype=np.float64)
    corners = mesh.corners().astype(np.float64)
    dist = (corners - o) @ n
    dist[dist == 0.0] = 1e-12  # a corner on the plane counts as just above it
    crossing = (dist.min(axis=1) < 0) & (dist.max(axis=1) > 0)
    tri, d = corners[crossing], dist[crossing]
    if len(tri) == 0:
        return np.zeros((0, 2, 3))
    nxt = [1, 2, 0]
    d0, d1 = d, d[:, nxt]
    p0, p1 = tri, tri[:, nxt]
    cut = (d0 < 0) != (d1 < 0)  # two of the three edges of each triangle
    k = (d0 / (d0 - np.where(cut, d1, d0 - 1.0)))[..., None]
    points = p0 + (p1 - p0) * k
    seg = points[cut].reshape(-1, 2, 3)
    outward = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    along = np.cross(n, outward)
    flip = np.einsum("ij,ij->i", seg[:, 1] - seg[:, 0], along) < 0
    seg[flip] = seg[flip][:, ::-1]
    out: NDArray[np.float64] = seg
    return out


def section_mesh(mesh: Mesh, origin: Vec3, normal: Vec3) -> MeshSection:
    """Outline length and cut area of ``mesh`` on a plane."""
    seg = section_segments(mesh, origin, normal)
    length = float(np.linalg.norm(seg[:, 1] - seg[:, 0], axis=1).sum()) if len(seg) else 0.0
    area: float | None = None
    if is_closed(mesh):
        n = np.asarray(normal, dtype=np.float64)
        n = n / (np.linalg.norm(n) or 1.0)
        o = np.asarray(origin, dtype=np.float64)
        area = 0.5 * float((np.cross(seg[:, 0] - o, seg[:, 1] - o) @ n).sum()) if len(seg) else 0.0
    return MeshSection(len(seg), length, area)
