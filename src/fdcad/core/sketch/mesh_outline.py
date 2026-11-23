"""The outline of a part seen square to a sketch plane, from its mesh (D2618).

The kernel's exact hidden line removal took 37 s on the threads of the nut and bolt
seen from the side and more than eight minutes looking down the bolt, holding the
window (idea 74). On parts the kernel is slow on, the outline is found from the
part's triangles instead, all in numpy:

1. The part's triangles, laid flat on the sketch plane, cover its shadow; the
   outline is the edge of that shadow, holes included.
2. The shadow is filled into a grid of cells about one tolerance wide, and the
   grid's boundary is traced into closed loops (marching squares). Many mesh
   edges can lie on one outline (a thread seen along its axis); the grid joins
   them, so the loops never cross or double back.
3. Each loop point is moved onto the shadow's true edge: from the cell inside,
   along the step to the cell outside, as far as the triangles cover it.
4. Each loop is split where it leaves the tolerance and becomes lines, arcs and
   circles; two lines that meet at a corner meet where their lines cross.

The lines lie on the mesh, so they are as close to the part as the shaded view is.
Details narrower than one cell (about a thousandth of the part's size) are left
out. Kernel work (meshing): run in a kernel job.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.sketch.curve_convert import MIN_SIZE, CurvePiece, Vec
from fdcad.core.sketch.profiles import SketchPlane

F64 = NDArray[np.float64]
I64 = NDArray[np.int64]
#: Most cells of the shadow grid.
MOST_CELLS = 4_000_000
#: Most cells along each side of the lookup grid of ``Shadow``.
_LOOKUP = 256
#: Lines meeting at a turn below this (radians) follow a smooth curve.
SMOOTH = 0.35
#: A run turns at a corner when both halves are this much straighter than the whole
#: run (an arc's halves are about a quarter as bent, D2634).
CORNER_STRAIGHT = 0.1
#: Most points of one spline.
MOST_SPLINE_POINTS = 64


def outline_pieces(shape: TopoDS_Shape, plane: SketchPlane) -> list[CurvePiece]:
    """The outline of ``shape`` seen square to ``plane``, in sketch coordinates.

    Raises ValueError, with a message to show, when the part cannot be meshed (D2635).
    """
    from fdcad.core.features.solids import bounding_size
    from fdcad.core.printing.overhang import MIN_DEVIATION, RELATIVE_DEVIATION, triangles_by_face

    _faces, corners, _owner = triangles_by_face(shape)
    deviation = max(bounding_size(shape) * RELATIVE_DEVIATION, MIN_DEVIATION)
    return outline_of(shadow_triangles(corners, plane), 2.0 * deviation)


def shadow_triangles(corners: F64, plane: SketchPlane) -> F64:
    """The triangles ``corners`` (n, 3, 3) laid flat on ``plane``, in sketch
    coordinates (m, 3, 2); those seen edge on are left out. Their union is the part's
    shadow on the plane, for a surface body or a face turned the wrong way too."""
    o = np.asarray(plane.origin, dtype=np.float64)
    n = np.asarray(plane.normal, dtype=np.float64)
    n /= np.linalg.norm(n)
    x = np.asarray(plane.x_dir, dtype=np.float64)
    x -= (x @ n) * n
    x /= np.linalg.norm(x)
    y = np.cross(n, x)
    if len(corners) == 0:
        return np.zeros((0, 3, 2))
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    size = np.linalg.norm(cross, axis=1)
    seen = (np.abs(cross @ n) > 1e-9 * size) & (size > 1e-15)
    flat = corners[seen] - o
    return np.stack((flat @ x, flat @ y), axis=2)


class Shadow:
    """Which points lie inside a set of flat triangles, looked up on a grid."""

    def __init__(self, triangles: F64) -> None:
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        area = np.abs(
            (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
        )
        self.triangles = triangles[area > 1e-14]
        tri = self.triangles
        self.cells = 1
        self.origin = np.zeros(2)
        self.size = np.ones(2)
        self.held = np.zeros(0, dtype=np.int64)
        self.begin = np.zeros(1, dtype=np.int64)
        self.stop = np.zeros(1, dtype=np.int64)
        if len(tri) == 0:
            return
        low, high = tri.min(axis=1), tri.max(axis=1)
        self.origin = low.min(axis=0)
        cells = int(min(_LOOKUP, max(1, 2 * math.isqrt(len(tri)))))
        self.cells = cells
        self.size = np.maximum(high.max(axis=0) - self.origin, 1e-9) / cells
        owner, cx, cy = _covered(tri, self.origin, self.size, cells)
        slot = cy * cells + cx
        order = np.argsort(slot, kind="stable")
        self.held, slot = owner[order], slot[order]
        every = np.arange(cells * cells)
        self.begin = np.searchsorted(slot, every, side="left")
        self.stop = np.searchsorted(slot, every, side="right")

    def near(self, points: F64) -> tuple[I64, I64]:
        """Each of ``points`` (q, 2) paired with every triangle held by its lookup
        cell: the point indices and the triangle indices."""
        if len(points) == 0 or len(self.triangles) == 0:
            return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
        q = np.floor((points - self.origin) / self.size).astype(np.int64)
        which = np.nonzero(np.all((q >= 0) & (q < self.cells), axis=1))[0]
        slot = q[which, 1] * self.cells + q[which, 0]
        many = self.stop[slot] - self.begin[slot]
        step = np.arange(int(many.sum())) - np.repeat(np.cumsum(many) - many, many)
        return np.repeat(which, many), self.held[np.repeat(self.begin[slot], many) + step]

    def covers(self, points: F64) -> NDArray[np.bool_]:
        """True for each of ``points`` (q, 2) inside one of the triangles."""
        inside = np.zeros(len(points), dtype=bool)
        query, held = self.near(points)
        inside[query[_inside(self.triangles[held], points[query])]] = True
        return inside

    def reach(self, start: F64, end: F64) -> F64:
        """How far (0 to 1) each step from ``start`` (inside) to ``end`` stays covered
        without a break. Each step must lie within the lookup cells of its two ends.

        Each nearby triangle covers one stretch of the step; the reach is the end of
        the stretches that join up from the start with no gap between them."""
        reach = np.zeros(len(start))
        q0, t0 = self.near(start)
        q1, t1 = self.near(end)
        query, held = np.concatenate((q0, q1)), np.concatenate((t0, t1))
        if len(query) == 0:
            return reach
        tri, a = self.triangles[held], start[query]
        d = end[query] - a
        turn = np.sign(
            (tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1])
            - (tri[:, 1, 1] - tri[:, 0, 1]) * (tri[:, 2, 0] - tri[:, 0, 0])
        )
        low, high = np.zeros(len(query)), np.ones(len(query))
        for i, j in ((0, 1), (1, 2), (2, 0)):
            ex, ey = tri[:, j, 0] - tri[:, i, 0], tri[:, j, 1] - tri[:, i, 1]
            # Inside this side where s + t * ds >= 0.
            s = turn * (ex * (a[:, 1] - tri[:, i, 1]) - ey * (a[:, 0] - tri[:, i, 0]))
            ds = turn * (ex * d[:, 1] - ey * d[:, 0])
            at = -s / np.where(ds == 0, 1.0, ds)
            low = np.where(ds > 0, np.maximum(low, at), low)
            high = np.where(ds < 0, np.minimum(high, at), high)
            low = np.where((ds == 0) & (s < 0), np.inf, low)
        keep = low <= high
        query, low, high = query[keep], low[keep], high[keep]
        order = np.lexsort((low, query))
        query, low, high = query[order], low[order], high[order]
        if len(query) == 0:
            return reach
        first = np.nonzero(np.append(True, query[1:] != query[:-1]))[0]
        group = np.cumsum(np.append(False, query[1:] != query[:-1]))
        # Sweep each step's stretches in order of their start: the farthest end so far,
        # before each stretch, in one pass (each step's values are lifted by 2 per step
        # so that one running maximum serves them all).
        lift = 2.0 * group
        upto = np.maximum.accumulate(high + lift) - lift
        before = np.append(0.0, upto[:-1])
        before[first] = 0.0
        gap = low > before + 1e-12
        index = np.arange(len(query))
        first_gap = np.minimum.reduceat(np.where(gap, index, len(query)), first)
        last = np.append(first[1:], len(query)) - 1
        end = np.where(
            first_gap < len(query), before[np.minimum(first_gap, len(query) - 1)], upto[last]
        )
        reach[query[first]] = end
        return reach


def _repeat_index(counts: I64) -> tuple[I64, I64]:
    """For counts (n,): the index of each of their ``counts.sum()`` items and its place
    within its own count."""
    owner = np.repeat(np.arange(len(counts)), counts)
    local = np.arange(int(counts.sum())) - np.repeat(np.cumsum(counts) - counts, counts)
    return owner, local


def _covered(tri: F64, origin: F64, size: F64, cells: int) -> tuple[I64, I64, I64]:
    """The lookup cells each triangle of ``tri`` (n, 3, 2) overlaps: the triangle index
    and the cell's x and y, for every pair.

    Each row of cells takes only the span the triangle has inside that row, not the
    whole width of its box (D2634): a long thin triangle at an angle has a box over
    most of the grid but touches a few cells on each row it crosses."""
    span = size * 1e-9  # a point on a cell's side finds the triangles of both cells
    cell = (tri - origin) / size  # in cells
    r0 = np.clip(np.floor(cell[:, :, 1].min(axis=1)), 0, cells - 1).astype(np.int64)
    r1 = np.clip(np.floor(cell[:, :, 1].max(axis=1)), 0, cells - 1).astype(np.int64)
    which, local = _repeat_index(r1 - r0 + 1)
    row = r0[which] + local
    t = tri[which]
    low = origin[1] + row * size[1] - span[1]
    high = low + size[1] + 2 * span[1]
    left = np.full(len(row), np.inf)
    right = np.full(len(row), -np.inf)
    x, y = t[:, :, 0], t[:, :, 1]
    # The triangle's part in the row is bounded by its corners in the row and the
    # points where its sides cross the row's two edges.
    within = (y >= low[:, None]) & (y <= high[:, None])
    left = np.minimum(left, np.where(within, x, np.inf).min(axis=1))
    right = np.maximum(right, np.where(within, x, -np.inf).max(axis=1))
    for i, j in ((0, 1), (1, 2), (2, 0)):
        xi, yi, xj, yj = x[:, i], y[:, i], x[:, j], y[:, j]
        rise = np.where(yi == yj, 1.0, yj - yi)
        for level in (low, high):
            meets = (np.minimum(yi, yj) <= level) & (level <= np.maximum(yi, yj)) & (yi != yj)
            at = xi + (level - yi) * (xj - xi) / rise
            left = np.where(meets, np.minimum(left, at), left)
            right = np.where(meets, np.maximum(right, at), right)
    found = left <= right
    row, which = row[found], which[found]
    c0 = np.floor((left[found] - span[0] - origin[0]) / size[0])
    c1 = np.floor((right[found] + span[0] - origin[0]) / size[0])
    c0 = np.clip(c0, 0, cells - 1).astype(np.int64)
    c1 = np.clip(c1, 0, cells - 1).astype(np.int64)
    pair, step = _repeat_index(c1 - c0 + 1)
    return which[pair], c0[pair] + step, row[pair]


def _inside(tri: F64, p: F64) -> NDArray[np.bool_]:
    """True where point ``p[k]`` lies in triangle ``tri[k]`` (edges included)."""
    sides = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        ex, ey = tri[:, j, 0] - tri[:, i, 0], tri[:, j, 1] - tri[:, i, 1]
        sides.append(ex * (p[:, 1] - tri[:, i, 1]) - ey * (p[:, 0] - tri[:, i, 0]))
    s = np.stack(sides, axis=1)
    return np.asarray(np.all(s >= 0, axis=1) | np.all(s <= 0, axis=1))


def outline_of(triangles: F64, tol: float) -> list[CurvePiece]:
    """Lines, arcs and circles along the edge of the union of ``triangles`` (m, 3, 2),
    within ``tol``."""
    shadow = Shadow(triangles)
    if len(shadow.triangles) == 0:
        return []
    low = shadow.triangles.min(axis=(0, 1))
    high = shadow.triangles.max(axis=(0, 1))
    span = high - low
    cell = max(tol, math.sqrt(float(span[0] + tol) * float(span[1] + tol) / MOST_CELLS))
    return [piece for loop in boundary_loops(shadow, cell) for piece in fit_loop(loop, tol)]


def _fill(shadow: Shadow, origin: F64, cell: float, shape: tuple[int, int]) -> NDArray[np.bool_]:
    """The grid of cell centres (rows along y) that lie in the shadow. Each triangle
    is cut along every row of centres it spans and the span between its sides is
    marked, so a large triangle costs its rows, not its area."""
    rows, cols = shape
    tri = (shadow.triangles - origin) / cell  # in cells
    first = np.ceil(tri[:, :, 1].min(axis=1)).astype(np.int64)
    span = np.maximum(np.floor(tri[:, :, 1].max(axis=1)).astype(np.int64) - first + 1, 0)
    owner = np.repeat(np.arange(len(tri)), span)
    row = np.repeat(first, span) + (
        np.arange(int(span.sum())) - np.repeat(np.cumsum(span) - span, span)
    )
    t, y = tri[owner], row.astype(np.float64)
    left = np.full(len(row), np.inf)
    right = np.full(len(row), -np.inf)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        xi, yi, xj, yj = t[:, i, 0], t[:, i, 1], t[:, j, 0], t[:, j, 1]
        meets = (np.minimum(yi, yj) <= y) & (y <= np.maximum(yi, yj))
        level = yi == yj
        at = np.where(level, xi, xi + (y - yi) * (xj - xi) / np.where(level, 1.0, yj - yi))
        far = np.where(level, xj, at)
        left = np.where(meets, np.minimum(left, np.minimum(at, far)), left)
        right = np.where(meets, np.maximum(right, np.maximum(at, far)), right)
    c0 = np.clip(np.ceil(left), 0, cols).astype(np.int64)
    c1 = np.clip(np.floor(right) + 1, 0, cols).astype(np.int64)
    keep = (c0 < c1) & (row >= 0) & (row < rows)
    size = rows * (cols + 1)
    row = row[keep] * (cols + 1)
    marks = np.bincount(row + c0[keep], minlength=size) - np.bincount(
        row + c1[keep], minlength=size
    )
    return np.asarray(np.cumsum(marks.reshape(rows, cols + 1), axis=1)[:, :cols] > 0)


def boundary_loops(shadow: Shadow, cell: float) -> list[F64]:
    """The closed loops round the shadow, each point on its edge, the shadow on the
    left of each loop; a loop repeats its first point at its end."""
    low = shadow.triangles.min(axis=(0, 1))
    high = shadow.triangles.max(axis=(0, 1))
    origin = low - cell
    nx, ny = (np.ceil((high - low) / cell).astype(np.int64) + 3).tolist()
    grid = _fill(shadow, origin, cell, (ny, nx))
    # Marching squares. A square's corners counter clockwise are its cell centres
    # c00, c01, c11, c10; side k runs from corner k to corner k + 1.
    corner = [grid[:-1, :-1], grid[:-1, 1:], grid[1:, 1:], grid[1:, :-1]]
    out_of = [corner[k] & ~corner[(k + 1) % 4] for k in range(4)]
    into = [~corner[k] & corner[(k + 1) % 4] for k in range(4)]
    rows, cols = np.nonzero(np.logical_or.reduce(out_of))
    if len(rows) == 0:
        return []
    across = ny * nx  # crossings of rows come first, then those of columns
    side_id = np.stack(
        (
            rows * nx + cols,  # bottom: between (r, c) and (r, c + 1)
            across + rows * nx + cols + 1,  # right: between (r, c + 1) and (r + 1, c + 1)
            (rows + 1) * nx + cols,  # top: between (r + 1, c) and (r + 1, c + 1)
            across + rows * nx + cols,  # left: between (r, c) and (r + 1, c)
        )
    )
    leave = np.stack([f[rows, cols] for f in out_of])
    enter = np.stack([f[rows, cols] for f in into])
    starts, ends = [], []
    for k in range(4):
        pick = np.nonzero(leave[k])[0]
        # The loop leaving by side k came in by the nearest side back from k that it
        # can enter by: k - 1, else k - 2, else k - 3. A square with two inside
        # corners across from each other so holds two separate pieces.
        k1, k2, k3 = (k + 3) % 4, (k + 2) % 4, (k + 1) % 4
        back = np.where(enter[k1, pick], k1, np.where(enter[k2, pick], k2, k3))
        starts.append(side_id[k, pick])
        ends.append(side_id[back, pick])
    ids, compact = np.unique(np.concatenate(starts + ends), return_inverse=True)
    half = len(compact) // 2
    loops = chains(compact[:half].astype(np.int64), compact[half:].astype(np.int64))
    points = _on_edge(shadow, grid, ids, origin, cell, nx)
    return [points[loop] for loop in loops if len(loop) > 3]


def _on_edge(
    shadow: Shadow, grid: NDArray[np.bool_], ids: I64, origin: F64, cell: float, nx: int
) -> F64:
    """Where each crossing ``ids`` of the grid meets the shadow's edge, going from its
    inside cell centre towards its outside one."""
    across = grid.size
    by_column = ids >= across
    flat = np.where(by_column, ids - across, ids)
    r, c = flat // nx, flat % nx
    r2, c2 = np.where(by_column, r + 1, r), np.where(by_column, c, c + 1)
    first = origin + cell * np.stack((c, r), axis=1).astype(np.float64)
    second = origin + cell * np.stack((c2, r2), axis=1).astype(np.float64)
    first_in = grid[r, c][:, None]
    inside = np.where(first_in, first, second)
    outside = np.where(first_in, second, first)
    return np.asarray(inside + shadow.reach(inside, outside)[:, None] * (outside - inside))


def chains(starts: I64, ends: I64) -> list[I64]:
    """Join the edges ``starts[i] -> ends[i]`` into chains of point indices, end to
    start. A point where more or fewer than one edge leaves and arrives ends a chain;
    a closed chain repeats its first point at the end. All in numpy (binary lifting)."""
    count = len(starts)
    if count == 0:
        return []
    top = int(max(starts.max(), ends.max())) + 1
    leaving = np.bincount(starts, minlength=top)
    arriving = np.bincount(ends, minlength=top)
    by_start = np.full(top, -1, dtype=np.int64)
    by_start[starts] = np.arange(count)
    simple = (leaving[ends] == 1) & (arriving[ends] == 1)
    nxt = np.append(np.where(simple, by_start[ends], count), count)  # count: no next edge
    levels = max(1, int(count).bit_length() + 1)
    jumps = [nxt]
    least = [np.append(np.arange(count), count)]  # least edge of the next 2**k
    for _k in range(levels):
        j, m = jumps[-1], least[-1]
        least.append(np.minimum(m, m[j]))
        jumps.append(j[j])
    edges = np.arange(count)
    open_chain = jumps[-1][edges] == count
    # Open chains: the last edge of each, and how far each edge is from it.
    last, gap = edges.copy(), np.zeros(count, dtype=np.int64)
    for k in range(levels - 1, -1, -1):
        ahead = jumps[k][last]
        go = ahead != count
        last = np.where(go, ahead, last)
        gap = gap + np.where(go, 1 << k, 0)
    # Closed chains: the least edge of each, and how far each edge is from it.
    head = least[-1][edges]
    at, ring = edges.copy(), np.zeros(count, dtype=np.int64)
    for k in range(levels - 1, -1, -1):
        go = least[k][nxt[at]] != head
        at = np.where(go, jumps[k][at], at)
        ring = ring + np.where(go, 1 << k, 0)
    label = np.where(open_chain, last, head)
    rank = np.where(open_chain, gap, ring + 1)
    order = np.lexsort((-rank, label))
    cut = np.nonzero(np.diff(label[order]))[0] + 1
    return [np.append(starts[group], ends[group[-1]]) for group in np.split(order, cut)]


def _xy(row: F64) -> Vec:
    return float(row[0]), float(row[1])


def _off_chord(points: F64) -> F64:
    """How far each of ``points`` is from the line through the first and last."""
    a, b = points[0], points[-1]
    d = b - a
    length = float(np.hypot(*d))
    if length < 1e-12:
        return np.asarray(np.hypot(*(points - a).T), dtype=np.float64)
    off = np.abs((points[:, 0] - a[0]) * d[1] - (points[:, 1] - a[1]) * d[0]) / length
    return np.asarray(off, dtype=np.float64)


def _circle(points: F64) -> tuple[float, float, float] | None:
    """Centre and radius of the circle closest to ``points``, or None."""
    x, y = points[:, 0], points[:, 1]
    fit = np.column_stack((x, y, np.ones(len(points))))
    try:
        solved = np.linalg.lstsq(fit, x * x + y * y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    cx, cy = float(solved[0]) / 2, float(solved[1]) / 2
    r2 = float(solved[2]) + cx * cx + cy * cy
    return (cx, cy, math.sqrt(r2)) if r2 > 0 else None


def _arc(points: F64, tol: float) -> CurvePiece | None:
    """An arc through ``points`` (in order) when they lie within ``tol`` of one."""
    if len(points) < 5:
        return None
    found = _circle(points)
    if found is None:
        return None
    cx, cy, radius = found
    if radius > 20 * float(np.ptp(points, axis=0).max()):  # nearly straight
        return None
    if float(np.abs(np.hypot(points[:, 0] - cx, points[:, 1] - cy) - radius).max()) > tol:
        return None
    turn = np.unwrap(np.arctan2(points[:, 1] - cy, points[:, 0] - cx))
    sweep = float(turn[-1] - turn[0])
    if abs(sweep) >= math.tau - 1e-6 or abs(sweep) < 1e-9:
        return None
    first, last = (points[0], points[-1]) if sweep > 0 else (points[-1], points[0])
    a0 = math.atan2(float(first[1]) - cy, float(first[0]) - cx)
    return CurvePiece("arc", (_xy(first), _xy(last)), (cx, cy), radius, (a0, a0 + abs(sweep)))


def _corner(run: F64, k: int, off: F64, tol: float) -> bool:
    """True when ``run`` turns sharply at ``k`` between two straight pieces (D2634).

    An arc split at its middle leaves two halves bent about a quarter as far from
    their chords as the whole run; at a corner both halves are straight. Either can
    lie within ``tol`` of one circle, so the corner is looked for before the arc."""
    if k < 1 or k > len(run) - 2:
        return False
    bent = max(float(_off_chord(run[: k + 1]).max()), float(_off_chord(run[k:]).max()))
    if bent > min(tol, CORNER_STRAIGHT * float(off.max())):
        return False
    a, b = run[k] - run[0], run[-1] - run[k]
    turn = math.atan2(float(a[0] * b[1] - a[1] * b[0]), float(a @ b))
    return abs(turn) >= SMOOTH  # one mesh step of a curved face turns less than this


def _runs(points: F64, tol: float) -> list[tuple[int, int, CurvePiece | None]]:
    """Split ``points`` (an open chain) into runs that are a line (None) or an arc,
    each within ``tol``, splitting at the point farthest from the chord. A sharp
    corner is split there even when an arc would fit (D2634). Returns (first, last,
    arc or None) in order."""
    done: list[tuple[int, int, CurvePiece | None]] = []
    todo = [(0, len(points) - 1)]
    while todo:
        i, j = todo.pop()
        run = points[i : j + 1]
        off = _off_chord(run)
        if j - i < 2 or float(off.max()) <= tol:
            done.append((i, j, None))
            continue
        k = int(np.argmax(off))
        arc = None if _corner(run, k, off, tol) else _arc(run, tol)
        if arc is not None:
            done.append((i, j, arc))
            continue
        k += i
        todo += [(i, k), (k, j)]
    return sorted(done, key=lambda run: run[0])


def _line(points: F64) -> tuple[F64, F64]:
    """A point on and the direction of the line closest to ``points``; the ends are
    left out when there are enough, since they may lie past a corner."""
    inner = points[1:-1] if len(points) >= 5 else points
    centre = inner.mean(axis=0)
    _u, _s, vt = np.linalg.svd(inner - centre)
    return centre, vt[0]


def fit_loop(loop: F64, tol: float) -> list[CurvePiece]:
    """Lines, arcs or a circle along one closed loop of points (first point repeated
    at the end), within ``tol``."""
    points = loop[:-1]
    if len(points) < 3:
        return []
    found = _circle(points) if len(points) >= 8 else None
    if found is not None:
        cx, cy, radius = found
        off = np.abs(np.hypot(points[:, 0] - cx, points[:, 1] - cy) - radius)
        if float(off.max()) <= tol and radius > MIN_SIZE:
            return [CurvePiece("circle", (), (cx, cy), radius)]
    # Start where the loop is farthest from its middle: a corner, when it has one.
    k = int(np.argmax(np.hypot(*(points - points.mean(axis=0)).T)))
    points = np.vstack((points[k:], points[: k + 1]))
    far = int(np.argmax(np.hypot(*(points - points[0]).T)))
    runs = _runs(points[: far + 1], tol) + [
        (i + far, j + far, arc) for i, j, arc in _runs(points[far:], tol)
    ]
    ends = [points[i].copy() for i, _j, _a in runs] + [points[-1].copy()]
    lines = [None if arc is not None else _line(points[i : j + 1]) for i, j, arc in runs]
    for n in range(len(runs)):
        before, after = lines[n - 1], lines[n]  # the loop is closed: run -1 is the last
        if before is None or after is None:
            continue
        (p, u), (q, v) = before, after
        det = float(u[0] * v[1] - u[1] * v[0])
        if abs(det) < 0.05:  # nearly in line: keep the shared point
            continue
        t = float((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / det
        meet = p + t * u
        if float(np.hypot(*(meet - ends[n]))) <= 3 * tol:
            ends[n] = meet
            if n == 0:
                ends[-1] = meet
    count = len(runs)
    # Lines that meet at a slight turn follow a smooth curve: they become one spline.
    smooth = [False] * count  # at the start of each run
    for n in range(count):
        if lines[n - 1] is None or lines[n] is None:
            continue
        m = n or count  # the loop is closed: ends[count] is ends[0]
        a, b = ends[m] - ends[m - 1], ends[n + 1] - ends[n]
        turn = math.atan2(float(a[0] * b[1] - a[1] * b[0]), float(a @ b))
        smooth[n] = abs(turn) < SMOOTH
    if all(smooth) and count >= 3:
        return [_spline(points, tol, closed=True)]
    start = smooth.index(False) if not all(smooth) else 0
    groups: list[list[int]] = []
    for step in range(count):
        n = (start + step) % count
        if step and smooth[n]:
            groups[-1].append(n)
        else:
            groups.append([n])
    pieces = []
    for group in groups:
        first, last = group[0], group[-1]
        a, b = ends[first], ends[last + 1]
        arc = runs[first][2]
        if arc is not None:
            pieces.append(arc)
        elif len(group) > 1:
            body = np.vstack([points[runs[n][0] + 1 : runs[n][1] + 1] for n in group])
            chain = np.vstack((a[None, :], body[:-1], b[None, :]))
            if float(_off_chord(chain).max()) <= tol:  # lines in line: one line (D2634)
                pieces.append(CurvePiece("line", (_xy(a), _xy(b))))
            else:
                pieces.append(_spline(chain, tol, closed=False))
        elif float(np.hypot(*(b - a))) >= MIN_SIZE:
            pieces.append(CurvePiece("line", (_xy(a), _xy(b))))
    return pieces


def _spline(points: F64, tol: float, closed: bool) -> CurvePiece:
    """A spline through enough of ``points`` to stay within ``tol`` of them."""
    if closed:
        points = (
            np.vstack((points, points[:1])) if not np.allclose(points[0], points[-1]) else points
        )
    kept = _simplify(points, tol / 4)
    if len(kept) > MOST_SPLINE_POINTS:
        pick = np.linspace(0, len(kept) - 1, MOST_SPLINE_POINTS).round().astype(np.int64)
        kept = kept[np.unique(pick)]
    return CurvePiece("spline", tuple(_xy(p) for p in kept))


def _simplify(points: F64, tol: float) -> F64:
    """The points that keep the chain within ``tol``, first and last kept: each pass
    splits every span still too far at its farthest point (Douglas and Peucker)."""
    keep = np.zeros(len(points), dtype=bool)
    keep[[0, -1]] = True
    spans = [(0, len(points) - 1)]
    while spans:
        later = []
        for i, j in spans:
            if j - i < 2:
                continue
            off = _off_chord(points[i : j + 1])
            k = int(np.argmax(off))
            if off[k] > tol:
                keep[i + k] = True
                later += [(i, i + k), (i + k, j)]
        spans = later
    return points[keep]
