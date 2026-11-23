"""Mesh repair and reduce (TR186, DECISIONS D1212).

Repair, in this order: drop repeated triangles, drop the extra triangles on edges
that more than two triangles share, drop tiny loose pieces, then fill every hole
with a fan of triangles to the middle of its rim. Reduce lowers the triangle count
by merging the vertices in each cell of a grid, the cell chosen so the count meets
a target, never moving a vertex further than a largest error, and optionally
keeping the vertices on open edges where they are. All whole array numpy work
(CLAUDE.md 5A rule 2); the few loops run over rounds of pointer jumping, not
over triangles.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from fdcad.core.io.mesh_import import Mesh

#: Rounds of label spreading at most when finding pieces and hole rims.
ROUNDS = 64


@dataclass(frozen=True)
class RepairReport:
    """What repair changed."""

    duplicates: int = 0
    overshared: int = 0
    pieces: int = 0
    holes: int = 0

    def sentence(self) -> str:
        """One plain sentence, or "" when nothing changed."""
        parts = []
        if self.holes:
            parts.append(f"filled {self.holes} hole{'s' if self.holes != 1 else ''}")
        if self.overshared:
            parts.append(f"removed {self.overshared} triangles on edges shared by more than two")
        if self.duplicates:
            parts.append(f"removed {self.duplicates} repeated triangles")
        if self.pieces:
            parts.append(f"removed {self.pieces} tiny piece{'s' if self.pieces != 1 else ''}")
        if not parts:
            return ""
        text = ", ".join(parts)
        return "Repair " + text + "."


def _edge_keys(tri: NDArray[np.int64], n: int) -> NDArray[np.int64]:
    """Undirected edge keys, (t, 3)."""
    a = tri[:, [0, 1, 2]]
    b = tri[:, [1, 2, 0]]
    return np.minimum(a, b) * n + np.maximum(a, b)


def _spread(labels: NDArray[np.int64], pairs: NDArray[np.int64]) -> NDArray[np.int64]:
    """Smallest label over connected items: ``pairs`` (m, 2) link items."""
    for _round in range(ROUNDS * 4):
        low = np.minimum(labels[pairs[:, 0]], labels[pairs[:, 1]])
        before = labels.copy()
        np.minimum.at(labels, pairs[:, 0], low)
        np.minimum.at(labels, pairs[:, 1], low)
        labels = labels[labels]  # jump: follow labels to their own labels
        if np.array_equal(labels, before):
            break
    return labels


def _area(v: NDArray[np.float64], tri: NDArray[np.int64]) -> NDArray[np.float64]:
    c = v[tri]
    return 0.5 * np.linalg.norm(np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0]), axis=1)


def repair(mesh: Mesh, tiny_share: float = 0.01) -> tuple[Mesh, RepairReport]:
    """The repaired mesh and what changed. Pieces with less area than ``tiny_share`` of
    the largest piece are tiny."""
    v = mesh.vertices.astype(np.float64)
    tri = mesh.triangles.astype(np.int64)
    n = max(len(v), 1)
    # 1. Repeated triangles (the same three corners in any order).
    key = np.sort(tri, axis=1)
    _u, first = np.unique(key[:, 0] * n * n + key[:, 1] * n + key[:, 2], return_index=True)
    keep = np.zeros(len(tri), dtype=bool)
    keep[first] = True
    duplicates = int((~keep).sum())
    tri = tri[np.sort(first)]
    # 2. Edges shared by more than two triangles: keep the first two on each.
    edges = _edge_keys(tri, n)
    flat = edges.ravel()
    order = np.argsort(flat, kind="stable")
    sorted_keys = flat[order]
    starts = np.r_[0, np.nonzero(np.diff(sorted_keys))[0] + 1]
    rank = np.arange(len(flat)) - np.repeat(starts, np.diff(np.r_[starts, len(flat)]))
    extra = np.zeros(len(flat), dtype=bool)
    extra[order[rank >= 2]] = True
    bad = extra.reshape(-1, 3).any(axis=1)
    overshared = int(bad.sum())
    tri = tri[~bad]
    # 3. Tiny pieces: label vertices by piece, sum the area of each piece.
    pieces = 0
    if len(tri):
        pairs = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]]])
        labels = _spread(np.arange(len(v), dtype=np.int64), pairs)
        piece = labels[tri[:, 0]]
        ids, inverse = np.unique(piece, return_inverse=True)
        area = np.bincount(inverse, weights=_area(v, tri), minlength=len(ids))
        small = area < tiny_share * area.max()
        pieces = int(small.sum())
        tri = tri[~small[inverse]]
    # 4. Holes: every open edge (used once) gets a triangle to its rim's middle.
    holes = 0
    if len(tri):
        directed = np.stack([tri[:, [0, 1, 2]].ravel(), tri[:, [1, 2, 0]].ravel()], 1)
        undirected = np.minimum(directed[:, 0], directed[:, 1]) * n + np.maximum(
            directed[:, 0], directed[:, 1]
        )
        _k, inverse, counts = np.unique(undirected, return_inverse=True, return_counts=True)
        rim = directed[counts[inverse] == 1]  # a to b, the triangle's own direction
        if len(rim):
            labels = _spread(np.arange(len(v), dtype=np.int64), rim)
            loop = labels[rim[:, 0]]
            ids, which = np.unique(loop, return_inverse=True)
            holes = len(ids)
            sums = np.zeros((holes, 3))
            np.add.at(sums, which, v[rim[:, 0]])
            middles = sums / np.bincount(which, minlength=holes)[:, None]
            centre = len(v) + which
            fill = np.stack([rim[:, 1], rim[:, 0], centre], 1)  # the rim's other side
            v = np.concatenate([v, middles])
            tri = np.concatenate([tri, fill])
    out = Mesh(v.astype(np.float32), tri.astype(np.int32))
    return out, RepairReport(duplicates, overshared, pieces, holes)


def _boundary_vertices(tri: NDArray[np.int64], n: int) -> NDArray[np.bool_]:
    keys = _edge_keys(tri, n).ravel()
    _k, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    open_edges = counts[inverse] == 1
    ends = np.stack([tri[:, [0, 1, 2]].ravel(), tri[:, [1, 2, 0]].ravel()], 1)[open_edges]
    out = np.zeros(n, dtype=bool)
    out[ends.ravel()] = True
    return out


def _cluster(
    v: NDArray[np.float64], tri: NDArray[np.int64], cell: float, fixed: NDArray[np.bool_]
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    lo = v.min(axis=0)
    cells = np.floor((v - lo) / cell).astype(np.int64)
    span = cells.max(axis=0) + 2
    key = (cells[:, 0] * span[1] + cells[:, 1]) * span[2] + cells[:, 2]
    key = np.where(fixed, -1 - np.arange(len(v)), key)  # kept vertices are their own cell
    _ids, group = np.unique(key, return_inverse=True)
    count = np.bincount(group)
    sums = np.zeros((len(count), 3))
    np.add.at(sums, group, v)
    nv = sums / count[:, None]
    nt = group[tri]
    ok = (nt[:, 0] != nt[:, 1]) & (nt[:, 1] != nt[:, 2]) & (nt[:, 0] != nt[:, 2])
    nt = nt[ok]
    key3 = np.sort(nt, axis=1)
    m = len(nv)
    _u, first = np.unique(key3[:, 0] * m * m + key3[:, 1] * m + key3[:, 2], return_index=True)
    return nv, nt[np.sort(first)]


def reduce(
    mesh: Mesh, target: int, largest_error: float = 0.0, keep_boundary: bool = False
) -> Mesh:
    """``mesh`` with about ``target`` triangles or fewer. ``largest_error`` (mm, 0 for
    none) limits how far a vertex may move, which can leave more triangles than the
    target. Raises ValueError for a target below 4."""
    if target < 4:
        raise ValueError("the target is below 4 triangles")
    v = mesh.vertices.astype(np.float64)
    tri = mesh.triangles.astype(np.int64)
    if len(tri) <= target:
        return mesh
    fixed = _boundary_vertices(tri, len(v)) if keep_boundary else np.zeros(len(v), dtype=bool)
    size = float(np.ptp(v, axis=0).max()) or 1.0
    lo, hi = 0.0, size  # cell sizes: lo meets nothing yet, hi surely meets the target
    most = largest_error / np.sqrt(3) if largest_error > 0 else hi
    hi = min(hi, most)
    best = _cluster(v, tri, hi, fixed)
    if len(best[1]) > target:
        nv, nt = best  # the largest error stops it short of the target
    else:
        for _step in range(30):
            mid = (lo + hi) / 2
            nv, nt = _cluster(v, tri, mid, fixed)
            if len(nt) <= target:
                hi, best = mid, (nv, nt)
            else:
                lo = mid
            if hi - lo < 1e-4 * size:
                break
        nv, nt = best
    return Mesh(nv.astype(np.float32), nt.astype(np.int32))
