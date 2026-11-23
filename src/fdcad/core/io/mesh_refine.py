"""Refine an export mesh by largest edge length, and measure its aspect ratios
(TR336, D1200).

The kernel's mesher has no edge length limit, so the triangles it makes are
split afterwards. Each round marks every edge longer than the limit, then
splits all marked edges at their middles by longest edge bisection: a triangle
with a split edge is halved across its longest edge first, so it never gets
thinner, and a split edge is split for both triangles that share it, so the
mesh stays closed. Everything is whole
array work (CLAUDE.md 5A rule 2).

TR336 (D2001): refining by aspect ratio. Before each round, edges between two
triangles in one plane are flipped where the other diagonal makes the worse of
the two triangles rounder, which mends wide flat triangles without new points
(the Delaunay test is not used: points on a circle all pass it). Then, in every
triangle still thinner than the limit, the long edges that a flip cannot mend
(sharp edges, colour seams) are split at their middles, with no longest edge
rule, so a long thin strip is cut across into short pieces that the next
round's flips turn into round triangles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

#: Rounds of splitting at most: each round halves the longest edges.
ROUNDS = 16
#: The refined mesh may hold at most this many triangles.
TRIANGLE_LIMIT = 4_000_000

_EDGES = np.array([[0, 1], [1, 2], [2, 0]])


@dataclass(frozen=True)
class Refined:
    """A refined mesh: vertices, triangles, and each triangle's source triangle."""

    vertices: NDArray[np.float64]
    triangles: NDArray[np.int64]
    parent: NDArray[np.int64]
    #: False when the triangle limit or the round limit stopped the splitting early.
    complete: bool = True


def edge_lengths(vertices: NDArray[np.float64], tri: NDArray[np.int64]) -> NDArray[np.float64]:
    """The three edge lengths of every triangle, as an (n, 3) array."""
    c = vertices[tri]
    return np.linalg.norm(c[:, [1, 2, 0]] - c, axis=2)


def aspect_ratios(vertices: NDArray[np.float64], tri: NDArray[np.int64]) -> NDArray[np.float64]:
    """Each triangle's aspect ratio: 1 for an equilateral one, larger for thinner ones.

    It is the longest edge over the height on it, scaled so the equilateral
    triangle gives 1. Triangles with no area give infinity."""
    c = vertices[tri]
    area = 0.5 * np.linalg.norm(np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0]), axis=1)
    longest = edge_lengths(vertices, tri).max(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = longest * longest * np.sqrt(3.0) / (4.0 * area)
    return np.where(area > 1e-15, out, np.inf)


def quality(vertices: NDArray[np.float64], tri: NDArray[np.int64]) -> tuple[float, float]:
    """The longest edge and the worst finite aspect ratio of a mesh (0, 0 when empty)."""
    if len(tri) == 0:
        return 0.0, 0.0
    longest = float(edge_lengths(vertices, tri).max())
    ratios = aspect_ratios(vertices, tri)
    finite = ratios[np.isfinite(ratios)]
    return longest, float(finite.max()) if len(finite) else 0.0


def _rolled(a: NDArray[np.int64], r: NDArray[np.int64]) -> NDArray[np.int64]:
    """Each row of ``a`` (n, 3) turned left by its ``r``."""
    idx = (np.arange(3)[None, :] + r[:, None]) % 3
    return np.take_along_axis(a, idx, axis=1)


def _marks(
    vertices: NDArray[np.float64], tri: NDArray[np.int64], max_edge: float
) -> NDArray[np.bool_]:
    return edge_lengths(vertices, tri) > max_edge


def _split(
    vertices: NDArray[np.float64],
    tri: NDArray[np.int64],
    parent: NDArray[np.int64],
    mark: NDArray[np.bool_],
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]:
    """One round of longest edge bisection: split every marked edge for every triangle
    that holds it. A triangle with any split edge also has its longest edge split, and
    is halved across that edge first, so triangles never get thinner."""
    ends = np.sort(tri[:, _EDGES], axis=2)  # (n, 3, 2)
    keys = ends[:, :, 0].astype(np.int64) * len(vertices) + ends[:, :, 1]
    unique, inverse = np.unique(keys.ravel(), return_inverse=True)
    inverse = inverse.reshape(tri.shape)
    split = np.zeros(len(unique), dtype=bool)
    split[inverse[mark]] = True
    longest = edge_lengths(vertices, tri).argmax(axis=1)
    rows = np.arange(len(tri))
    while True:  # close the marks: a touched triangle splits its longest edge too
        flags = split[inverse]
        need = flags.any(axis=1) & ~flags[rows, longest]
        if not need.any():
            break
        split[inverse[need, longest[need]]] = True
    chosen = np.nonzero(split)[0]
    a = (unique[chosen] // len(vertices)).astype(np.int64)
    b = (unique[chosen] % len(vertices)).astype(np.int64)
    middles = 0.5 * (vertices[a] + vertices[b])
    number = np.full(len(unique), -1, dtype=np.int64)
    number[chosen] = len(vertices) + np.arange(len(chosen))
    mid = number[inverse]  # (n, 3): the middle vertex of edge j, or -1
    touched = flags.any(axis=1)
    out_tri = [tri[~touched]]
    out_parent = [parent[~touched]]
    pick = np.nonzero(touched)[0]
    r = longest[pick]  # the longest edge becomes edge 0 (a to b), split at m0
    t, m, f = _rolled(tri[pick], r), _rolled(mid[pick], r), _rolled(flags[pick], r)
    p = parent[pick]
    a_, b_, c_ = t[:, 0], t[:, 1], t[:, 2]
    m0, m1, m2 = m[:, 0], m[:, 1], m[:, 2]
    # The half on the a side: (a, m0, c), or split again across c to a at m2.
    left_whole = ~f[:, 2]
    right_whole = ~f[:, 1]
    pieces = [
        (left_whole, (a_, m0, c_)),
        (~left_whole, (a_, m0, m2)),
        (~left_whole, (m0, c_, m2)),
        (right_whole, (m0, b_, c_)),
        (~right_whole, (m0, b_, m1)),
        (~right_whole, (m0, m1, c_)),
    ]
    for keep, corners in pieces:
        out_tri.append(np.stack([x[keep] for x in corners], 1))
        out_parent.append(p[keep])
    return (
        np.concatenate([vertices, middles]),
        np.concatenate(out_tri).astype(np.int64),
        np.concatenate(out_parent).astype(np.int64),
    )


#: Rounds at most when refining by aspect ratio, where each round may split one
#: edge per triangle.
ASPECT_ROUNDS = 40
#: The aspect ratio limit cannot be set below this (an equilateral triangle is 1).
LOWEST_ASPECT = 2.0
#: Two triangles count as in one plane when their normals differ by less than this
#: (radians), so flipping their shared edge does not change the surface.
FLAT = 1e-6
#: Flip rounds at most per refining round.
FLIP_ROUNDS = 200
#: A thin triangle has its edges longer than this times its shortest edge split.
_ASPECT_SPLIT = 1.5


def _unit_normals(vertices: NDArray[np.float64], tri: NDArray[np.int64]) -> NDArray[np.float64]:
    c = vertices[tri]
    n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    length = np.linalg.norm(n, axis=1, keepdims=True)
    return np.asarray(n / np.where(length > 0, length, 1.0), dtype=np.float64)


def _angle_at(p: NDArray[np.float64], a: NDArray[np.float64], b: NDArray[np.float64]) -> Any:
    u, w = a - p, b - p
    cross = np.linalg.norm(np.cross(u, w), axis=1)
    return np.arctan2(cross, np.einsum("ij,ij->i", u, w))


def flip_flat(
    vertices: NDArray[np.float64],
    tri: NDArray[np.int64],
    group: NDArray[np.int64] | None = None,
    rounds: int = FLIP_ROUNDS,
) -> NDArray[np.int64]:
    """Flip edges between two triangles in one plane where the other diagonal lowers
    the worse aspect ratio of the two, until none is left (or ``rounds``). Each flip
    lowers the list of ratios sorted from the worst, so the flipping ends. Triangles of different
    ``group`` values (such as colours) are never flipped together. The surface, the
    points and the mesh's closedness do not change."""
    faces = np.array(tri, dtype=np.int64, copy=True)
    n = len(faces)
    if n < 2:
        return faces
    labels = np.zeros(n, dtype=np.int64) if group is None else np.asarray(group, np.int64)
    width = np.int64(len(vertices))
    cos_flat = np.cos(FLAT)
    for _round in range(rounds):
        a = faces[:, _EDGES[:, 0]].ravel()
        b = faces[:, _EDGES[:, 1]].ravel()
        c = faces[:, [2, 0, 1]].ravel()  # the corner opposite each edge
        owner = np.repeat(np.arange(n), 3)
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        key = lo * width + hi
        order = np.argsort(key, kind="stable")
        ks = key[order]
        pair = np.nonzero(ks[1:] == ks[:-1])[0]
        if len(pair) == 0:
            return faces
        lone = np.ones(len(pair), dtype=bool)  # exactly two triangles on the edge
        lone &= (pair + 2 >= len(ks)) | (ks[np.minimum(pair + 2, len(ks) - 1)] != ks[pair])
        lone &= (pair == 0) | (ks[np.maximum(pair - 1, 0)] != ks[pair])
        pair = pair[lone]
        h1, h2 = order[pair], order[pair + 1]
        t1, t2 = owner[h1], owner[h2]
        ea, eb, ec, ed = a[h1], b[h1], c[h1], c[h2]
        ok = (a[h2] == eb) & (b[h2] == ea) & (t1 != t2) & (ec != ed)  # same direction
        ok &= labels[t1] == labels[t2]
        normals = _unit_normals(vertices, faces)
        ok &= np.einsum("ij,ij->i", normals[t1], normals[t2]) > cos_flat
        new1 = np.stack([ea, ed, ec], 1)
        new2 = np.stack([ed, eb, ec], 1)
        pa, pb = vertices[ea], vertices[eb]
        scale = np.linalg.norm(pa - pb, axis=1) ** 2
        for new in (new1, new2):  # both new triangles keep the side and have area
            q = vertices[new]
            m = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0])
            size = np.linalg.norm(m, axis=1)
            ok &= (np.einsum("ij,ij->i", m, normals[t1]) > 0) & (size > 1e-12 * scale)
        ratio = aspect_ratios(vertices, faces)
        before = np.maximum(ratio[t1], ratio[t2])
        after = np.maximum(aspect_ratios(vertices, new1), aspect_ratios(vertices, new2))
        gain = before - after
        ok &= gain > 1e-9 * before
        cd = np.minimum(ec, ed) * width + np.maximum(ec, ed)
        ok &= ~np.isin(cd, ks)  # the new edge must not exist already
        pick = np.nonzero(ok)[0]
        if len(pick) == 0:
            return faces
        rank = np.empty(len(pick), dtype=np.int64)  # largest gain first
        rank[np.argsort(gain[pick], kind="stable")] = np.arange(len(pick))
        claim = np.full(n, -1, dtype=np.int64)
        np.maximum.at(claim, t1[pick], rank)
        np.maximum.at(claim, t2[pick], rank)
        free = (claim[t1[pick]] == rank) & (claim[t2[pick]] == rank)
        pick = pick[free]
        faces[t1[pick]] = new1[pick]
        faces[t2[pick]] = new2[pick]
    return faces


def _flat_edges(
    vertices: NDArray[np.float64], tri: NDArray[np.int64], labels: NDArray[np.int64]
) -> NDArray[np.bool_]:
    """(n, 3): True where the edge lies between two triangles in one plane with the same
    label, so a flip can mend it; False on sharp edges, seams and open borders."""
    n = len(tri)
    a = tri[:, _EDGES[:, 0]].ravel()
    b = tri[:, _EDGES[:, 1]].ravel()
    key = np.minimum(a, b) * np.int64(len(vertices)) + np.maximum(a, b)
    order = np.argsort(key, kind="stable")
    ks = key[order]
    out = np.zeros(3 * n, dtype=bool)
    pair = np.nonzero(ks[1:] == ks[:-1])[0]
    if len(pair):
        h1, h2 = order[pair], order[pair + 1]
        t1, t2 = h1 // 3, h2 // 3
        normals = _unit_normals(vertices, tri)
        flat = np.einsum("ij,ij->i", normals[t1], normals[t2]) > np.cos(FLAT)
        flat &= labels[t1] == labels[t2]
        out[h1[flat]] = True
        out[h2[flat]] = True
    return out.reshape(n, 3)


def _aspect_marks(
    vertices: NDArray[np.float64],
    tri: NDArray[np.int64],
    max_aspect: float,
    size: NDArray[np.float64],
    labels: NDArray[np.int64],
) -> NDArray[np.bool_]:
    """The edges to split for triangles thinner than ``max_aspect``: their long edges
    (longer than ``size``, one and a half times the shortest edge of the triangle they
    came from) that a flip cannot mend. A long edge inside a flat region is left to the
    flips: splitting it at its middle would leave two needles."""
    lengths = edge_lengths(vertices, tri)
    thin = aspect_ratios(vertices, tri) > max_aspect
    long = thin[:, None] & (lengths > size[:, None])
    return long & ~_flat_edges(vertices, tri, labels)


def _split_marked(
    vertices: NDArray[np.float64],
    tri: NDArray[np.int64],
    parent: NDArray[np.int64],
    mark: NDArray[np.bool_],
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]:
    """Split exactly the marked edges at their middles (no longest edge rule): a triangle
    with one split edge becomes two, with two becomes three, with three becomes four.
    Each edge is split for both triangles that share it, so the mesh stays closed."""
    ends = np.sort(tri[:, _EDGES], axis=2)
    keys = ends[:, :, 0].astype(np.int64) * len(vertices) + ends[:, :, 1]
    unique, inverse = np.unique(keys.ravel(), return_inverse=True)
    inverse = inverse.reshape(tri.shape)
    split = np.zeros(len(unique), dtype=bool)
    split[inverse[mark]] = True
    chosen = np.nonzero(split)[0]
    a = (unique[chosen] // len(vertices)).astype(np.int64)
    b = (unique[chosen] % len(vertices)).astype(np.int64)
    number = np.full(len(unique), -1, dtype=np.int64)
    number[chosen] = len(vertices) + np.arange(len(chosen))
    mid = number[inverse]
    flags = mid >= 0
    count = flags.sum(axis=1)
    out_tri = [tri[count == 0]]
    out_parent = [parent[count == 0]]
    for k in (1, 2, 3):
        pick = np.nonzero(count == k)[0]
        if len(pick) == 0:
            continue
        f = flags[pick]
        if k == 1:  # the split edge becomes edge 0
            r = f.argmax(axis=1)
        elif k == 2:  # the whole edge becomes edge 2
            r = (np.argmin(f, axis=1) + 1) % 3
        else:
            r = np.zeros(len(pick), dtype=np.int64)
        t, m = _rolled(tri[pick], r), _rolled(mid[pick], r)
        p = parent[pick]
        ta, tb, tc = t[:, 0], t[:, 1], t[:, 2]
        m0, m1, m2 = m[:, 0], m[:, 1], m[:, 2]
        if k == 1:
            pieces = [(ta, m0, tc), (m0, tb, tc)]
        elif k == 2:
            pieces = [(m0, tb, m1), (ta, m0, m1), (ta, m1, tc)]
        else:
            pieces = [(ta, m0, m2), (m0, tb, m1), (m2, m1, tc), (m0, m1, m2)]
        for corners in pieces:
            out_tri.append(np.stack(corners, 1))
            out_parent.append(p)
    middles = 0.5 * (vertices[a] + vertices[b])
    return (
        np.concatenate([vertices, middles]),
        np.concatenate(out_tri).astype(np.int64),
        np.concatenate(out_parent).astype(np.int64),
    )


def refine(
    vertices: NDArray[np.float64],
    tri: NDArray[np.int64],
    max_edge: float = 0.0,
    limit: int = TRIANGLE_LIMIT,
    max_aspect: float = 0.0,
    group: NDArray[np.int64] | None = None,
) -> Refined:
    """Split triangles until no edge is longer than ``max_edge`` (0 for no limit) and,
    with ``max_aspect`` (0 for no limit, else at least :data:`LOWEST_ASPECT`), until no
    triangle is thinner than it, as far as the round and triangle limits allow.
    ``group`` labels each input triangle (such as by colour) so flips keep the labels
    apart (TR336, D2001)."""
    verts = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(tri, dtype=np.int64).reshape(-1, 3)
    parent = np.arange(len(faces), dtype=np.int64)
    if (max_edge <= 0 and max_aspect <= 0) or len(faces) == 0:
        return Refined(verts, faces, parent)
    aspect = max(max_aspect, LOWEST_ASPECT) if max_aspect > 0 else 0.0
    labels = np.zeros(len(faces), np.int64) if group is None else np.asarray(group, np.int64)
    first = edge_lengths(verts, faces)
    floor = 1e-6 * max(float(first.max()), 1e-12)  # needles from tiny faces stay as they are
    shortest = first.min(axis=1)
    size = np.where(shortest > floor, _ASPECT_SPLIT * shortest, np.inf)

    def marks() -> NDArray[np.bool_]:
        found = _marks(verts, faces, max_edge) if max_edge > 0 else np.zeros(faces.shape, bool)
        if aspect:
            found |= _aspect_marks(verts, faces, aspect, size[parent], labels[parent])
        return found

    def flipped() -> NDArray[np.int64]:
        return flip_flat(verts, faces, labels[parent])

    for _round in range(ASPECT_ROUNDS if aspect else ROUNDS):
        if aspect:
            faces = flipped()
        mark = marks()
        if not mark.any():
            return Refined(verts, faces, parent)
        if len(faces) + 3 * int(mark.any(axis=1).sum()) > limit:  # about
            return Refined(verts, faces, parent, complete=False)
        if aspect:  # no longest edge rule, so thin strips are cut across, not halved along
            verts, faces, parent = _split_marked(verts, faces, parent, mark)
        else:
            verts, faces, parent = _split(verts, faces, parent, mark)
    if aspect:
        faces = flipped()
    return Refined(verts, faces, parent, complete=not marks().any())
