"""Triply periodic lattice sheets as closed triangle meshes (TR390, DECISIONS D2004).

A gyroid or diamond sheet of a wall thickness, clipped to a box, is the band within
half the wall of the periodic surface, by its signed distance (its value over its
gradient length, a first order distance), sampled on a grid. Each grid cube is split
into six tetrahedra along its main diagonal, so neighbouring cubes share their face
diagonals. In each tetrahedron the distance and the box are taken as linear, and the
band's two faces and the box are cut out and clipped by each other, so the mesh is
closed and a wall thinner than the grid is kept (D2674: the zero of the unsigned
distance less half the wall lost it). Points are shared by the grid edge or the
tetrahedron face they lie on. Everything is whole array work (CLAUDE.md 5A rule 2).
No Qt, no kernel.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

SURFACES = ("gyroid", "diamond")
#: Grid samples per lattice cell.
SAMPLES = 8
#: Most grid cubes one sheet may sample.
MOST_CUBES = 400_000

# The six tetrahedra of a unit cube (corners 0 to 7 as bits x, y, z), all along the
# main diagonal from corner 0 to corner 7.
_TETS = np.array(
    [[0, 1, 3, 7], [0, 1, 5, 7], [0, 2, 3, 7], [0, 2, 6, 7], [0, 4, 5, 7], [0, 4, 6, 7]]
)
_CORNERS = np.array([[(c >> 0) & 1, (c >> 1) & 1, (c >> 2) & 1] for c in range(8)])


def _surface(kind: str, x: NDArray[np.float64], y: NDArray[np.float64], z: NDArray[np.float64]):  # type: ignore[no-untyped-def]
    """The periodic field and its gradient (angles in radians of the cell)."""
    sx, cx, sy, cy, sz, cz = np.sin(x), np.cos(x), np.sin(y), np.cos(y), np.sin(z), np.cos(z)
    if kind == "gyroid":
        g = sx * cy + sy * cz + sz * cx
        gx = cx * cy - sz * sx
        gy = -sx * sy + cy * cz
        gz = -sy * sz + cz * cx
    else:  # Schwarz diamond
        g = sx * sy * sz + sx * cy * cz + cx * sy * cz + cx * cy * sz
        gx = cx * sy * sz + cx * cy * cz - sx * sy * cz - sx * cy * sz
        gy = sx * cy * sz - sx * sy * cz + cx * cy * cz - cx * sy * sz
        gz = sx * sy * cz - sx * cy * sz - cx * sy * sz + cx * cy * cz
    return g, np.sqrt(gx * gx + gy * gy + gz * gz)


def cube_count(lo: NDArray[np.float64], hi: NDArray[np.float64], cell: float) -> int:
    """How many grid cubes a sheet over the box ``lo`` to ``hi`` samples."""
    step = cell / SAMPLES
    counts = np.maximum(np.ceil((hi - lo) / step).astype(int), 1) + 2
    return int(np.prod(counts))


def field(
    kind: str,
    points: NDArray[np.float64],
    cell: float,
    wall: float,
    lo: NDArray[np.float64],
    hi: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Negative inside the sheet and the box, positive outside (about mm): the sheet
    that ``sheet_mesh`` meshes, for testing points against it."""
    sheet = np.abs(signed_distance(kind, points, cell)) - wall / 2.0
    box = np.max(np.maximum(lo - points, points - hi), axis=-1)
    return np.asarray(np.maximum(sheet, box), dtype=np.float64)


def far_outside(
    axes: list[NDArray[np.float64]], surface: NDArray[np.float64], margin: float
) -> NDArray[np.bool_]:
    """The grid points (axes as given) more than ``margin`` from the box of every
    triangle of ``surface`` (an (n, 3, 3) array, the closed surface of a body) and
    outside it: those reached from the edge of the grid without coming that near
    (DECISIONS D2624). Whole array work: the boxes are added into the grid with a
    difference array, and the outside grows from the edge one step at a time."""
    n = np.array([len(a) for a in axes])
    start = np.array([a[0] for a in axes])
    step = float(axes[0][1] - axes[0][0]) if n[0] > 1 else 1.0
    low = surface.min(axis=1) - margin
    high = surface.max(axis=1) + margin
    i0 = np.clip(np.ceil((low - start) / step), 0, n).astype(np.int64)
    i1 = np.clip(np.floor((high - start) / step) + 1, 0, n).astype(np.int64)
    good = np.all(i1 > i0, axis=1)
    i0, i1 = i0[good], i1[good]
    diff = np.zeros(tuple(n + 1), dtype=np.int32)
    for c in range(8):
        pick = [(c >> axis) & 1 for axis in range(3)]
        index = tuple((i1 if pick[axis] else i0)[:, axis] for axis in range(3))
        np.add.at(diff, index, -1 if sum(pick) % 2 else 1)
    near = diff.cumsum(0).cumsum(1).cumsum(2)[: n[0], : n[1], : n[2]] > 0
    out = np.zeros(tuple(n), dtype=bool)
    out[[0, -1], :, :] = True
    out[:, [0, -1], :] = True
    out[:, :, [0, -1]] = True
    out &= ~near
    while True:
        grown = out.copy()
        grown[1:] |= out[:-1]
        grown[:-1] |= out[1:]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        grown[:, :, 1:] |= out[:, :, :-1]
        grown[:, :, :-1] |= out[:, :, 1:]
        grown &= ~near
        if np.array_equal(grown, out):
            return out
        out = grown


def sheet_mesh(
    kind: str,
    lo: NDArray[np.float64],
    hi: NDArray[np.float64],
    cell: float,
    wall: float,
    surface: NDArray[np.float64] | None = None,
    pad: float = 0.0,
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """A closed mesh of the ``kind`` sheet, ``wall`` thick, filling the box. Raises
    ValueError for values that cannot work or a grid that would be too large.

    The sheet is the band within half the wall of the periodic surface, cut by the
    box. Its two faces are found as levels of the signed distance, not as the zero
    of the unsigned one, so a wall thinner than the grid step is kept (D2674).

    With ``surface``, the triangles of the body the sheet will be fitted to (within
    ``pad`` of its faces), the sheet is closed off three grid steps outside the
    body and nothing farther out is made (D2624). Inside the body the mesh is the
    same as without it: the parts left out are all outside."""
    if kind not in SURFACES:
        raise ValueError(f"unknown lattice {kind!r}")
    if cell <= 0 or wall <= 0:
        raise ValueError("the cell and the wall must be more than 0")
    if wall >= cell / 2:
        raise ValueError("the wall is too thick for the cell")
    if cube_count(lo, hi, cell) > MOST_CUBES:
        raise ValueError("the lattice is too fine for this size")
    step = cell / SAMPLES
    counts = np.maximum(np.ceil((hi - lo) / step).astype(int), 1) + 2
    start = lo - step
    axes = [start[i] + step * np.arange(counts[i] + 1) for i in range(3)]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1)
    signed = signed_distance(kind, grid, cell)
    # A grid point exactly on the box would put a mesh point on a grid point, where
    # triangles of no area meet; the box is taken a thousandth of a step smaller.
    box = np.max(np.maximum(lo - grid, grid - hi), axis=-1) + 1e-3 * step
    if surface is not None and len(surface):
        # A cube with a point left out is at least three steps less a diagonal from
        # the body, so every triangle that closes the sheet there is outside it.
        out = far_outside(axes, surface, 3.0 * step + pad)
        box[out] = np.maximum(box[out], step)
    points = grid.reshape(-1, 3)
    flat = signed.ravel()
    half = wall / 2.0
    # Inside the sheet all three are below zero: its two faces, then the box.
    fields = np.stack([flat - half, -flat - half, box.ravel()], axis=1)
    vertices, tri, levels, ends = _band_mesh(points, fields, _grid_tets(counts, signed.shape))
    _onto_surface(kind, cell, half, points, flat, vertices, levels, ends)
    return vertices, tri


def signed_distance(kind: str, points: NDArray[np.float64], cell: float) -> NDArray[np.float64]:
    """The first order distance from the periodic surface (its value over its gradient
    length), with a sign: one side is below zero (D2674)."""
    k = 2.0 * math.pi / cell
    g, grad = _surface(kind, points[..., 0] * k, points[..., 1] * k, points[..., 2] * k)
    return np.asarray(g / (k * np.maximum(grad, 0.25)), dtype=np.float64)


def _grid_tets(counts: NDArray[np.int64], shape: tuple[int, ...]) -> NDArray[np.int64]:
    """The four grid points of each tetrahedron of each grid cube: ``(cubes * 6, 4)``."""
    idx = np.arange(int(np.prod(counts))).reshape(*counts)
    ci, cj, ck = np.unravel_index(idx.ravel(), tuple(counts))
    base = np.stack([ci, cj, ck], 1)
    corner_ids = np.empty((len(base), 8), dtype=np.int64)
    for c in range(8):
        p = base + _CORNERS[c]
        corner_ids[:, c] = np.ravel_multi_index((p[:, 0], p[:, 1], p[:, 2]), shape)
    return np.asarray(corner_ids[:, _TETS].reshape(-1, 4), dtype=np.int64)


#: Of the band's three fields, the ones each face of the band is cut by: a face of the
#: sheet by the box, the box by both faces of the sheet. The two faces of the sheet are
#: parallel in every tetrahedron, so they never cut each other.
_CUT_BY = ((2,), (2,), (0, 1))


def _band_mesh(
    points: NDArray[np.float64], fields: NDArray[np.float64], tets: NDArray[np.int64]
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64], NDArray[np.int64]]:
    """The closed surface of the region where all three ``fields`` (one column each,
    at the grid ``points``) are below zero, over the tetrahedra ``tets``.

    In a tetrahedron each field is taken as linear, so the region is the tetrahedron
    cut by three planes. Each field's plane is cut out (marching tetrahedra) and then
    clipped by the other fields' planes; its pieces on the tetrahedron's faces are
    shared with the neighbour and so are left out. A mesh point is on a grid edge
    (one field's zero there) or on a tetrahedron face (two fields' zero there), and is
    shared by that key, so the mesh is closed. Also gives, for each mesh point, the
    field whose zero it is on along a grid edge, or -1 for a point on a face."""
    inside = fields[tets] < 0  # (tets, 4 corners, 3 fields)
    count = inside.sum(axis=1)
    mixed = (count > 0) & (count < 4)
    # A field above zero at every corner is above zero in the whole tetrahedron.
    keep = mixed.any(axis=1) & (count > 0).all(axis=1)
    tets, mixed = tets[keep], mixed[keep]
    n = len(points)
    keys: list[NDArray[np.int64]] = []  # per mesh point, with its kind in ``kinds``
    kinds: list[NDArray[np.int64]] = []
    where: list[NDArray[np.float64]] = []
    levels: list[NDArray[np.int64]] = []
    ends: list[NDArray[np.int64]] = []
    faces: list[NDArray[np.int64]] = []  # triangles as rows into the lists above
    flips: list[NDArray[np.bool_]] = []
    taken = 0
    for own in range(3):
        rows = np.nonzero(mixed[:, own])[0]
        if not len(rows):
            continue
        t, f = tets[rows], fields[tets[rows]]  # (P, 4), (P, 4, 3)
        weights, support, size = _cut_out(f[:, :, own])
        code = np.full(weights.shape[:2], own, dtype=np.int64)
        for other in _CUT_BY[own]:
            weights, support, code, size = _clip(
                weights, support, code, size, f[:, :, other], own, other
            )
        live = size >= 3
        t, f, weights, support, code, size = (
            t[live],
            f[live],
            weights[live],
            support[live],
            code[live],
            size[live],
        )
        if not len(t):
            continue
        width = weights.shape[1]
        valid = np.arange(width)[None, :] < size[:, None]
        corner = np.where(support, t[:, None, :], -1)
        corner.sort(axis=2)
        edge = support.sum(axis=2) == 2
        # Edge point: field and the two grid points. Face point: the two fields and the
        # three grid points (n cubed stays far below 2 ** 63 for MOST_CUBES).
        key = np.where(
            edge,
            (code * n + corner[:, :, 2]) * n + corner[:, :, 3],
            ((code * n + corner[:, :, 1]) * n + corner[:, :, 2]) * n + corner[:, :, 3],
        )
        position = np.einsum("pkc,pcd->pkd", weights, points[t])
        keys.append(key[valid])
        kinds.append(np.where(edge, 0, 1)[valid])
        where.append(position[valid])
        levels.append(np.where(edge, code, -1)[valid])
        ends.append(np.where(edge[:, :, None], corner[:, :, 2:], -1)[valid])
        row = np.full((len(t), width), -1, dtype=np.int64)
        row[valid] = taken + np.arange(int(valid.sum()))
        taken += int(valid.sum())
        # Outward is from the corners below zero toward those above it.
        below = f[:, :, own] < 0
        corners = points[t]
        out_dir = _mean(corners, ~below) - _mean(corners, below)
        for k in range(1, width - 1):
            fan = size > k + 1
            tri = np.stack([row[fan, 0], row[fan, k], row[fan, k + 1]], axis=1)
            p = position[fan]
            normal = np.cross(p[:, k] - p[:, 0], p[:, k + 1] - p[:, 0])
            faces.append(tri)
            flips.append(np.einsum("ij,ij->i", normal, out_dir[fan]) < 0)
    if not faces:
        none = np.zeros((0, 2), dtype=np.int64)
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), none[:, 0], none
    # Edge and face keys apart. A face key is below 9 n cubed, so twice it fits too.
    all_keys = np.concatenate(keys) * 2 + np.concatenate(kinds)
    _unique, first, inverse = np.unique(all_keys, return_index=True, return_inverse=True)
    vertices = np.concatenate(where)[first]
    level = np.concatenate(levels)[first]
    end = np.concatenate(ends)[first]
    tri = inverse.ravel()[np.concatenate(faces)]
    flip = np.concatenate(flips)
    tri[flip] = tri[flip][:, [0, 2, 1]]
    c = vertices[tri]
    area = np.linalg.norm(np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0]), axis=1)
    good = (area > 1e-14) & (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2])
    good &= tri[:, 0] != tri[:, 2]
    return vertices, tri[good], level, end


def _mean(corners: NDArray[np.float64], pick: NDArray[np.bool_]) -> NDArray[np.float64]:
    """The mean of the picked corners of each tetrahedron."""
    total = np.einsum("pc,pcd->pd", pick.astype(np.float64), corners)
    return np.asarray(total / np.maximum(pick.sum(axis=1), 1)[:, None], dtype=np.float64)


def _cut_out(
    values: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.bool_], NDArray[np.int64]]:
    """The polygon where one field is zero in each tetrahedron (marching tetrahedra):
    its corners as weights of the four tetrahedron corners, which corners each lies
    between, and how many it has (3 or 4)."""
    below = values < 0
    count = below.sum(axis=1)
    p = len(values)
    pairs = np.zeros((p, 4, 2), dtype=np.int64)
    size = np.where(count == 2, 4, 3)
    lone_rows = count != 2
    lone = np.where(count == 1, np.argmax(below, axis=1), np.argmax(~below, axis=1))
    rest = np.array([[j for j in range(4) if j != i] for i in range(4)])[lone]
    pairs[:, :3, 0] = lone[:, None]
    pairs[:, :3, 1] = rest
    # Two and two: a quad on the four edges between the pairs, in order round it.
    order = np.argsort(~below, axis=1, kind="stable")  # the two corners below first
    i0, i1, o0, o1 = order[:, 0], order[:, 1], order[:, 2], order[:, 3]
    quad = np.stack(
        [
            np.stack([i0, o0], 1),
            np.stack([i0, o1], 1),
            np.stack([i1, o1], 1),
            np.stack([i1, o0], 1),
        ],
        axis=1,
    )
    pairs = np.where(lone_rows[:, None, None], pairs, quad)
    a, b = pairs[:, :, 0], pairs[:, :, 1]
    va = np.take_along_axis(values, a, axis=1)
    vb = np.take_along_axis(values, b, axis=1)
    t = va / np.where(va == vb, 1.0, va - vb)
    weights = np.zeros((p, 4, 4))
    support = np.zeros((p, 4, 4), dtype=bool)
    rows = np.arange(p)[:, None]
    slot = np.arange(4)[None, :]
    weights[rows, slot, a] = 1.0 - t
    weights[rows, slot, b] += t
    support[rows, slot, a] = True
    support[rows, slot, b] = True
    weights[lone_rows, 3, :] = 0.0  # a triangle has three corners only
    support[lone_rows, 3, :] = False
    return weights, support, size


def _clip(
    weights: NDArray[np.float64],
    support: NDArray[np.bool_],
    code: NDArray[np.int64],
    size: NDArray[np.int64],
    values: NDArray[np.float64],
    own: int,
    other: int,
) -> tuple[NDArray[np.float64], NDArray[np.bool_], NDArray[np.int64], NDArray[np.int64]]:
    """Each polygon less its part where the field ``values`` (at the four corners of
    its tetrahedron) is not below zero, in order round it (Sutherland and Hodgman).
    A new corner lies where the polygon's edge on a tetrahedron face meets the
    field's zero; its code names both fields."""
    p, width = weights.shape[:2]
    if not p:
        return weights, support, code, size
    here = np.einsum("pkc,pc->pk", weights, values)
    slot = np.arange(width)[None, :]
    valid = slot < size[:, None]
    after = (slot + 1) % np.maximum(size, 1)[:, None]
    there = np.take_along_axis(here, after, axis=1)
    w_after = np.take_along_axis(weights, after[:, :, None], axis=1)
    s_after = np.take_along_axis(support, after[:, :, None], axis=1)
    keep = valid & (here < 0)
    cross = valid & ((here < 0) != (there < 0))
    t = here / np.where(cross, here - there, 1.0)
    new_w = weights + t[:, :, None] * (w_after - weights)
    new_s = support | s_after
    pair = min(own, other) * 3 + max(own, other) + 3  # face codes after the field codes
    out_w = np.stack([weights, new_w], axis=2).reshape(p, 2 * width, 4)
    out_s = np.stack([support, new_s], axis=2).reshape(p, 2 * width, 4)
    out_c = np.stack([code, np.full_like(code, pair)], axis=2).reshape(p, 2 * width)
    use = np.stack([keep, cross], axis=2).reshape(p, 2 * width)
    order = np.argsort(~use, axis=1, kind="stable")
    count = use.sum(axis=1)
    most = max(int(count.max()), 1)
    order = order[:, :most]
    return (
        np.take_along_axis(out_w, order[:, :, None], axis=1),
        np.take_along_axis(out_s, order[:, :, None], axis=1),
        np.take_along_axis(out_c, order, axis=1),
        count,
    )


def _onto_surface(
    kind: str,
    cell: float,
    half: float,
    points: NDArray[np.float64],
    signed: NDArray[np.float64],
    vertices: NDArray[np.float64],
    levels: NDArray[np.int64],
    ends: NDArray[np.int64],
) -> None:
    """Move each mesh point of a face of the sheet along its grid edge onto the face
    (D2674). The straight line between two grid points put it off the face, and the
    sheet came out about a tenth thin. Two steps of false position keep it inside
    its grid edge, so every triangle keeps its place in the mesh."""
    pick = np.nonzero(((levels == 0) | (levels == 1)) & (ends[:, 0] >= 0))[0]
    if not len(pick):
        return
    target = np.where(levels[pick] == 0, half, -half)
    a, b = points[ends[pick, 0]], points[ends[pick, 1]]
    lo_t, hi_t = np.zeros(len(pick)), np.ones(len(pick))
    lo_v = signed[ends[pick, 0]] - target
    hi_v = signed[ends[pick, 1]] - target
    for _ in range(2):
        t = lo_t + (hi_t - lo_t) * lo_v / np.where(lo_v == hi_v, 1.0, lo_v - hi_v)
        t = np.clip(t, lo_t, hi_t)
        value = signed_distance(kind, a + (b - a) * t[:, None], cell) - target
        same = (value < 0) == (lo_v < 0)
        lo_t, lo_v = np.where(same, t, lo_t), np.where(same, value, lo_v)
        hi_t, hi_v = np.where(same, hi_t, t), np.where(same, hi_v, value)
    t = lo_t + (hi_t - lo_t) * lo_v / np.where(lo_v == hi_v, 1.0, lo_v - hi_v)
    vertices[pick] = a + (b - a) * np.clip(t, 0.0, 1.0)[:, None]
