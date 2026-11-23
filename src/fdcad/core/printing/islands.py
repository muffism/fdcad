"""Suction cups and floating islands in the print orientation (TR409, DECISIONS D1213).

The part, as it lies on the bed, is seen from below on a grid: each cell holds the
height of the lowest surface above it. All numpy (CLAUDE.md 5A rule 2): the
surfaces facing down are sampled densely and the lowest sample wins in each cell.

A suction cup is a hollow that opens toward the bed: turned upside down it would
hold water. Air or resin trapped there cannot get out, so the print sticks, tears
or fails. The grid is filled the way water fills pits (each cell rises to the
lowest rim it can spill over; cells with no part over them drain), and cells that
rise more than a tolerance belong to cups.

A floating island is a local lowest point that is not on the bed: printing it
starts in mid air, so it needs support.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from OCP.TopoDS import TopoDS_Shape

#: Cells along the longer side of the part's footprint.
CELLS = 160
#: Height a cup must hold, and the height counted as on the bed, in mm.
CUP_DEPTH = 0.5
BED = 0.05
#: Rounds of the pit filling at most.
ROUNDS = 2000


@dataclass(frozen=True)
class Found:
    """Cups (count, deepest in mm, the middle of each) and islands (their lowest points)."""

    cups: int
    deepest: float
    cup_points: list[tuple[float, float, float]]
    islands: list[tuple[float, float, float]]


def _down_triangles(shape: TopoDS_Shape) -> NDArray[np.float64]:
    from fdcad.core.io.export import MeshSettings, triangles

    c = triangles(shape, MeshSettings(0.05, 0.5)).astype(np.float64)
    n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    return c[n[:, 2] < -1e-12]


def heightmap(
    shape: TopoDS_Shape, cells: int = CELLS
) -> tuple[NDArray[np.float64], float, tuple[float, float]]:
    """The lowest surface height over each cell (inf where nothing is over it), the cell
    size and the grid's corner, with the part's lowest point at height 0."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    size = max(hi.X() - lo.X(), hi.Y() - lo.Y()) / cells or 1.0
    nx = int(np.ceil((hi.X() - lo.X()) / size)) + 3
    ny = int(np.ceil((hi.Y() - lo.Y()) / size)) + 3
    corner = (lo.X() - size, lo.Y() - size)
    grid = np.full((nx, ny), np.inf)
    tris = _down_triangles(shape)
    if len(tris):
        e1, e2 = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
        flat = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])  # footprint area
        k = np.clip(np.ceil(np.sqrt(flat / (size * size)) * 3).astype(np.int64), 1, 200)
        # k x k barycentric samples per triangle, made for all triangles at once.
        count = (k + 1) * (k + 2) // 2
        owner = np.repeat(np.arange(len(tris)), count)
        start = np.repeat(np.cumsum(count) - count, count)
        local = np.arange(owner.size) - start
        kk = k[owner]
        # The local index walks rows i = 0..k with k - i + 1 entries each.
        i = np.floor(((2 * kk + 3) - np.sqrt((2 * kk + 3) ** 2 - 8 * local)) / 2).astype(np.int64)
        row_start = i * (2 * kk + 3 - i) // 2
        j = local - row_start
        a = i / kk
        b = j / kk
        p = tris[owner, 0] + a[:, None] * e1[owner] + b[:, None] * e2[owner]
        cx = np.clip(((p[:, 0] - corner[0]) / size).astype(np.int64), 0, nx - 1)
        cy = np.clip(((p[:, 1] - corner[1]) / size).astype(np.int64), 0, ny - 1)
        np.minimum.at(grid, (cx, cy), p[:, 2])
    return grid - lo.Z(), size, corner


def _neighbours(a: NDArray[np.float64], fill: float) -> list[NDArray[np.float64]]:
    return _shifts(a, fill)


def _labels(
    mask: NDArray[np.bool_], heights: NDArray[np.float64] | None = None
) -> tuple[NDArray[np.int64], int]:
    """Connected groups of ``mask`` cells (4 neighbours): a label per cell, -1 outside.
    With ``heights``, only neighbours of the same height join."""
    big = np.iinfo(np.int64).max
    index = np.arange(mask.size, dtype=np.int64).reshape(mask.shape)
    lab = np.where(mask, index, big)
    h = np.where(mask, heights, 0.0) if heights is not None else None
    steps = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for _round in range(ROUNDS):
        low = lab.copy()
        for (dx, dy), other in zip(steps, _shifts(lab, big), strict=True):
            joins = other != big
            if h is not None:
                same = np.abs(_shift(h, dx, dy, np.inf) - h) < 1e-6
                joins &= same
            low = np.where(joins & mask, np.minimum(low, other), low)
        if np.array_equal(low, lab):
            break
        lab = low
    ids = np.unique(lab[mask])
    out = np.full(mask.shape, -1, dtype=np.int64)
    out[mask] = np.searchsorted(ids, lab[mask])
    return out, len(ids)


def _shift(a: NDArray[Any], dx: int, dy: int, fill: Any) -> NDArray[Any]:
    """``a`` moved so each cell holds its neighbour at (+dx, +dy)."""
    out = np.full_like(a, fill)
    xs = slice(max(dx, 0), a.shape[0] + min(dx, 0))
    ys = slice(max(dy, 0), a.shape[1] + min(dy, 0))
    xd = slice(max(-dx, 0), a.shape[0] + min(-dx, 0))
    yd = slice(max(-dy, 0), a.shape[1] + min(-dy, 0))
    out[xd, yd] = a[xs, ys]
    return out


def _shifts(a: NDArray[Any], fill: Any) -> list[NDArray[Any]]:
    return [_shift(a, dx, dy, fill) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]


def find(shape: TopoDS_Shape, cells: int = CELLS) -> Found:
    """Cups and islands of ``shape`` as it lies on the bed (Z up)."""
    grid, size, corner = heightmap(shape, cells)
    over = np.isfinite(grid)
    # Upside down the bottom surface is a landscape of height -grid; water fills its
    # pits up to the lowest rim. Cells with nothing over them, and the border, drain.
    land = np.where(over, -grid, -np.inf)
    level = np.where(over, np.inf, -np.inf)
    level[0, :] = level[-1, :] = level[:, 0] = level[:, -1] = -np.inf
    for _round in range(ROUNDS):
        lowest = np.minimum.reduce(_neighbours(level, -np.inf))
        new = np.maximum(land, np.minimum(level, lowest))
        if np.array_equal(new, level):
            break
        level = new
    depth = np.where(over & np.isfinite(level), level - np.where(over, land, 0.0), 0.0)
    cup_cells = depth > CUP_DEPTH
    labels, cups = _labels(cup_cells)
    cup_points = []
    for k in range(cups):  # a few cups: one point each
        xs, ys = np.nonzero(labels == k)
        m = np.argmax(depth[xs, ys])
        x, y = xs[m], ys[m]
        cup_points.append(
            (corner[0] + (x + 0.5) * size, corner[1] + (y + 0.5) * size, float(grid[x, y]))
        )
    # Islands: flat groups of one height off the bed with no lower cell next to them.
    finite = np.where(over, grid, np.inf)
    regions, count = _labels(over, finite)
    lower = np.zeros(count, dtype=bool)
    for other, owner in zip(_shifts(finite, np.inf), _shifts(regions, -1), strict=True):
        steps_down = over & (other < finite - 1e-6) & (owner != regions)
        np.logical_or.at(lower, regions[steps_down], True)
    islands = []
    heights = np.full(count, np.inf)
    np.minimum.at(heights, regions[over], finite[over])
    for r in np.nonzero(~lower & (heights > BED))[0]:  # a few islands: one point each
        xs, ys = np.nonzero(regions == r)
        x, y = xs[len(xs) // 2], ys[len(ys) // 2]
        islands.append(
            (corner[0] + (x + 0.5) * size, corner[1] + (y + 0.5) * size, float(heights[r]))
        )
    return Found(cups, float(depth.max()) if cups else 0.0, cup_points, islands)
