"""Wall thickness analysis (PLAN Phase 4, DECISIONS D414): which faces sit on walls thinner
than the printer profile's minimum wall.

The part is triangulated once (as for the overhang analysis). From the middle of
every triangle a ray goes straight into the material, against the outward
normal; the wall there is as thick as the distance to where the ray leaves the
material again. Only walls thinner than the minimum matter, so each ray is
tested only against triangles near its short path. All tests are whole array
numpy work in blocks of rays (CLAUDE.md 5A rule 2): no Python loop runs per
triangle or per ray.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.printing.overhang import FULL_SHARE, PARTIAL_SHARE, triangles_by_face

#: Pairs of rays and triangles tested at once; bounds the memory of one block.
BLOCK_PAIRS = 4_000_000
#: Rays start this far inside the surface, so they never hit their own triangle.
_START = 1e-6


@dataclass(frozen=True)
class FaceThickness:
    """One face on a thin wall: its share of area thinner than the minimum, the area,
    and the thinnest wall found on it."""

    face: TopoDS_Face
    share: float
    area: float
    thinnest: float

    @property
    def full(self) -> bool:
        """True when (nearly) the whole face is on a thin wall."""
        return self.share >= FULL_SHARE


def ray_thickness(
    corners: NDArray[np.float64], limit: float, block_pairs: int = BLOCK_PAIRS
) -> NDArray[np.float64]:
    """Wall thickness under the middle of each triangle of a closed mesh, or inf where
    it is ``limit`` or more. ``corners`` is (n, 3, 3) with outward winding."""
    n = len(corners)
    out = np.full(n, np.inf)
    if n == 0 or limit <= 0:
        return out
    v0, v1, v2 = corners[:, 0], corners[:, 1], corners[:, 2]
    e1, e2 = v1 - v0, v2 - v0
    cross = np.cross(e1, e2)
    length = np.linalg.norm(cross, axis=1)
    good = length > 1e-15
    normal = np.zeros_like(cross)
    normal[good] = cross[good] / length[good, None]
    inward = -normal
    origin = corners.mean(axis=1) + inward * _START
    reach = limit + _START
    # Triangles sorted by their lowest X: a block of rays only meets triangles that
    # start before the block's highest X plus the reach (one search, no loop per item).
    tri_lo, tri_hi = corners.min(axis=1), corners.max(axis=1)
    order = np.argsort(tri_lo[:, 0], kind="stable")
    sorted_lo_x = tri_lo[order, 0]
    ray_end = origin + inward * reach
    ray_lo, ray_hi = np.minimum(origin, ray_end), np.maximum(origin, ray_end)
    rays = np.nonzero(good)[0]
    rays = rays[np.argsort(ray_lo[rays, 0], kind="stable")]
    start = 0
    while start < len(rays):
        # A block of rays sized so the tested pairs stay within ``block_pairs``.
        size = max(32, block_pairs // n)
        block = rays[start : start + size]
        start += size
        top = np.searchsorted(sorted_lo_x, ray_hi[block, 0].max(), side="right")
        cand = order[:top]
        cand = cand[tri_hi[cand, 0] >= ray_lo[block, 0].min()]
        if len(cand) == 0:
            continue
        near = np.all(
            (tri_lo[cand][None, :, :] <= ray_hi[block][:, None, :])
            & (tri_hi[cand][None, :, :] >= ray_lo[block][:, None, :]),
            axis=2,
        )
        ri, ci = np.nonzero(near)
        ti = cand[ci]
        ray = block[ri]
        keep = ti != ray
        ray, ti = ray[keep], ti[keep]
        if len(ray) == 0:
            continue
        d = inward[ray]
        a, b = e1[ti], e2[ti]
        p = np.cross(d, b)
        det = np.einsum("ij,ij->i", a, p)
        ok = np.abs(det) > 1e-15
        inv = np.zeros_like(det)
        inv[ok] = 1.0 / det[ok]
        tv = origin[ray] - v0[ti]
        u = np.einsum("ij,ij->i", tv, p) * inv
        q = np.cross(tv, a)
        v = np.einsum("ij,ij->i", d, q) * inv
        t = np.einsum("ij,ij->i", b, q) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0) & (t < reach)
        np.minimum.at(out, ray[hit], t[hit] + _START)
    out[out >= limit] = np.inf
    return out


def thin_walls(shape: TopoDS_Shape, min_wall: float) -> list[FaceThickness]:
    """Faces on walls thinner than ``min_wall`` (mm), largest share first.

    Kernel work (meshing): run it in a kernel job, not on the UI thread.
    """
    faces, corners, owner = triangles_by_face(shape)
    if len(corners) == 0:
        return []
    thick = ray_thickness(corners, min_wall)
    area = (
        np.linalg.norm(
            np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1
        )
        / 2.0
    )
    thin = np.isfinite(thick)
    face_area = np.bincount(owner, weights=area, minlength=len(faces))
    thin_area = np.bincount(owner, weights=area * thin, minlength=len(faces))
    share = np.divide(thin_area, face_area, out=np.zeros_like(thin_area), where=face_area > 0)
    thinnest = np.full(len(faces), np.inf)
    np.minimum.at(thinnest, owner[thin], thick[thin])
    picked = np.nonzero(share >= PARTIAL_SHARE)[0]
    picked_order = picked[np.argsort(-share[picked], kind="stable")]
    return [
        FaceThickness(faces[i], float(share[i]), float(face_area[i]), float(thinnest[i]))
        for i in picked_order
    ]
