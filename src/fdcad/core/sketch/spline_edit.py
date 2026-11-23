"""Spline edit tools (TUTORIAL_REVIEW_SPEC_2 TR42, D1306). Pure Python and numpy.

A spline is a chain of cubic pieces through its points, each point with one
handle: the curve leaves toward the handle and arrives from the mirrored side
(``freeform.bezier_poles``, D278).

* ``insert_point`` adds a through point where a spline was clicked. The new
  handle is chosen so the curve stays as close as it can to its old shape.
* ``fit_chain`` replaces a connected open chain of lines, arcs and splines with
  one spline within a tolerance.
* ``simplify`` refits a spline with as few points as the tolerance allows.

The fit adds through points one at a time where the curve is furthest from the
target until every target sample is within the tolerance.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from fdcad.core.sketch.freeform import bezier_poles
from fdcad.core.sketch.model import Point, Sketch, Spline, curve_ends, entity_points

Vec = tuple[float, float]
Arr = NDArray[np.float64]
#: Samples per cubic piece when measuring a spline.
_PER_PIECE = 24
#: The most through points a fit may use.
MAX_POINTS = 200


def _cubic(poles: Arr, n: int) -> Arr:
    """``n`` + 1 points along each cubic piece of ``poles`` (3k + 1 rows)."""
    t = np.linspace(0.0, 1.0, n + 1)[:, None]
    u = 1.0 - t
    pieces = (len(poles) - 1) // 3
    out = [poles[:1]]
    for k in range(pieces):
        p0, p1, p2, p3 = poles[3 * k : 3 * k + 4]
        pts = u**3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t**3 * p3
        out.append(pts[1:])
    return np.concatenate(out)


def _poles(points: Arr, handles: Arr) -> Arr:
    rows = [points[0]]
    for i in range(len(points) - 1):
        q = points[i + 1]
        rows += [handles[i], 2 * q - handles[i + 1], q]
    return np.array(rows, dtype=np.float64)


def _distances(targets: Arr, polyline: Arr) -> Arr:
    """Distance from each target to the nearest segment of ``polyline``."""
    a, b = polyline[:-1], polyline[1:]
    ab = b - a
    length2 = np.maximum((ab * ab).sum(axis=1), 1e-30)
    rel = targets[:, None, :] - a[None, :, :]
    t = np.clip((rel * ab[None, :, :]).sum(axis=2) / length2[None, :], 0.0, 1.0)
    near = a[None, :, :] + t[:, :, None] * ab[None, :, :]
    d = np.hypot(*(targets[:, None, :] - near).transpose(2, 0, 1))
    return np.asarray(d.min(axis=1), dtype=np.float64)


def deviation(target: Arr, points: Arr, handles: Arr) -> tuple[float, Arr]:
    """The largest gap between the target polyline and the spline both ways, and the
    gap at each target sample."""
    curve = _cubic(_poles(points, handles), _PER_PIECE)
    there = _distances(target, curve)
    back = _distances(curve, target)
    return float(max(there.max(initial=0.0), back.max(initial=0.0))), there


# Fitting --------------------------------------------------------------------------------


def _resample(poly: Arr, count: int) -> Arr:
    """``count`` points evenly spaced along a polyline."""
    seg = np.hypot(*np.diff(poly, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] <= 0:
        return np.repeat(poly[:1], count, axis=0)
    at = np.linspace(0.0, s[-1], count)
    return np.stack([np.interp(at, s, poly[:, 0]), np.interp(at, s, poly[:, 1])], axis=1)


def _handles_for(dense: Arr, idx: list[int]) -> Arr:
    """Handles at the chosen samples: along the target's direction there, a third of
    the shorter neighbouring chord long."""
    pts = dense[idx]
    out = np.empty_like(pts)
    last = len(dense) - 1
    for k, i in enumerate(idx):
        a, b = dense[max(i - 1, 0)], dense[min(i + 1, last)]
        d = b - a
        norm = math.hypot(d[0], d[1]) or 1.0
        chords = []
        if k > 0:
            chords.append(math.dist(pts[k], pts[k - 1]))
        if k < len(idx) - 1:
            chords.append(math.dist(pts[k], pts[k + 1]))
        reach = min(chords) / 3 if chords else 0.0
        out[k] = pts[k] + d / norm * reach
    return out


@dataclass
class Fit:
    """A fitted spline: through points and handles in mm, and its largest gap from
    the target."""

    points: list[Vec]
    handles: list[Vec]
    gap: float


def fit(target: Arr, tolerance: float) -> Fit:
    """A spline through the first and last target points that stays within
    ``tolerance`` mm of the target polyline, adding points where it is furthest."""
    dense = _resample(target, max(200, min(2000, len(target) * 4)))
    idx = [0, len(dense) - 1]
    gap = math.inf
    handles = _handles_for(dense, idx)
    while True:
        handles = _handles_for(dense, idx)
        gap, there = deviation(dense, dense[idx], handles)
        if gap <= tolerance or len(idx) >= MAX_POINTS:
            break
        order = np.argsort(-there)
        new = next((int(i) for i in order if int(i) not in idx), None)
        if new is None:
            break
        idx = sorted([*idx, new])
    pts = [(float(x), float(y)) for x, y in dense[idx]]
    hs = [(float(x), float(y)) for x, y in handles]
    return Fit(pts, hs, gap)


# Chains ---------------------------------------------------------------------------------


def chain_polyline(sketch: Sketch, ids: list[str]) -> tuple[Arr, str, str]:
    """The points along a connected open chain of curves, in order, with the point
    ids at its start and end. Raises ValueError with what to do."""
    from fdcad.core.sketch.topology import _Nodes, curve_points

    curves = [sketch.entities.get(i) for i in ids]
    if not curves or any(c is None or isinstance(c, Point) for c in curves):
        raise ValueError("Pick lines, arcs or splines that form one chain.")
    nodes = _Nodes(sketch)
    ends: dict[str, tuple[str, str]] = {}
    at: dict[str, list[str]] = defaultdict(list)
    for c in curves:
        pair = curve_ends(c)  # type: ignore[arg-type]
        if pair is None:
            raise ValueError(
                "Circles and full ellipses cannot be part of a chain. Pick open curves."
            )
        ends[c.id] = pair  # type: ignore[union-attr]
        for pid in pair:
            at[nodes.find(pid)].append(c.id)  # type: ignore[union-attr]
    if any(len(v) > 2 for v in at.values()):
        raise ValueError("The chain branches. Pick curves that join end to end.")
    starts = [n for n, v in at.items() if len(v) == 1]
    if not starts:
        raise ValueError("The chain is closed. Pick an open chain.")
    node = starts[0]
    used: set[str] = set()
    rows: list[Vec] = []
    first = ""
    last = ""
    while True:
        nxt = [c for c in at[node] if c not in used]
        if not nxt:
            break
        cid = nxt[0]
        used.add(cid)
        a, b = ends[cid]
        reverse = nodes.find(a) != node
        pts = curve_points(sketch, sketch.entities[cid], reverse)  # type: ignore[arg-type]
        if not first:
            first = b if reverse else a
        rows += pts if not rows else pts[1:]
        last = a if reverse else b
        node = nodes.find(last)
    if len(used) != len(curves):
        raise ValueError("The curves do not join into one chain. Pick curves that join end to end.")
    return np.array(rows, dtype=np.float64), first, last


def _drop_unused(sketch: Sketch, pids: set[str]) -> None:
    users = {
        p for e in sketch.entities.values() if not isinstance(e, Point) for p in entity_points(e)
    }
    gone = {p for p in pids if p in sketch.entities and p not in users}
    for p in gone:
        del sketch.entities[p]
    sketch.relations = [r for r in sketch.relations if not set(r.entities) & gone]
    sketch.dimensions = [d for d in sketch.dimensions if not set(d.entities) & gone]


def _new_spline(sketch: Sketch, result: Fit, first: str, last: str, construction: bool) -> str:
    ids = [first]
    for x, y in result.points[1:-1]:
        ids.append(sketch.add_point(x, y, construction))
    ids.append(last)
    hids = [sketch.add_point(x, y, True) for x, y in result.handles]
    sid = sketch.new_id()
    sketch.entities[sid] = Spline(sid, ids, hids, construction)
    return sid


def fit_chain(
    sketch: Sketch, ids: list[str], tolerance: float, keep_construction: bool
) -> tuple[str, Fit]:
    """Replace the chain ``ids`` with one spline within ``tolerance`` mm. The originals
    are removed, or kept as construction geometry. Returns the spline id and fit."""
    if tolerance <= 0:
        raise ValueError("The tolerance must be greater than zero. Enter a positive length.")
    target, first, last = chain_polyline(sketch, ids)
    result = fit(target, tolerance)
    construction = all(getattr(sketch.entities[i], "construction", False) for i in ids)
    old_points = {p for i in ids for p in entity_points(sketch.entities[i])} - {first, last}
    if keep_construction:
        for i in ids:
            sketch.entities[i].construction = True
    else:
        for i in ids:
            del sketch.entities[i]
        gone = set(ids)
        sketch.relations = [r for r in sketch.relations if not set(r.entities) & gone]
        sketch.dimensions = [d for d in sketch.dimensions if not set(d.entities) & gone]
    sid = _new_spline(sketch, result, first, last, construction)
    if not keep_construction:
        _drop_unused(sketch, old_points)
    return sid, result


def simplified(sketch: Sketch, sid: str, tolerance: float) -> Fit:
    """The spline ``sid`` refitted with as few points as ``tolerance`` mm allows."""
    from fdcad.core.sketch.freeform import sample

    spline = sketch.entities[sid]
    if not isinstance(spline, Spline):
        raise ValueError("Pick a spline to simplify.")
    target = np.array(sample(sketch, spline, 64 * len(spline.points)), dtype=np.float64)
    return fit(target, tolerance)


def simplify(sketch: Sketch, sid: str, result: Fit) -> int:
    """Give spline ``sid`` the points and handles of ``result`` (keeping its two end
    points). Returns how many through points were removed."""
    spline = sketch.entities[sid]
    assert isinstance(spline, Spline)
    before = len(spline.points)
    old = set(spline.points[1:-1]) | set(spline.handles)
    first, last = spline.points[0], spline.points[-1]
    del sketch.entities[sid]
    new = _new_spline(sketch, result, first, last, spline.construction)
    made = sketch.entities.pop(new)
    assert isinstance(made, Spline)
    sketch.entities[sid] = Spline(sid, made.points, made.handles, spline.construction)
    _drop_unused(sketch, old)
    return before - len(made.points)


# Insert a point ---------------------------------------------------------------------------


def insert_point(sketch: Sketch, sid: str, at: Vec) -> str:
    """Add a through point to spline ``sid`` on the curve nearest ``at``. The new
    handle follows the curve's direction there, with the length that keeps the two
    new pieces closest to the old one. Returns the new point id."""
    spline = sketch.entities.get(sid)
    if not isinstance(spline, Spline):
        raise ValueError("Click a spline to add a point to it.")
    poles = np.array(bezier_poles(sketch, spline), dtype=np.float64)
    n = 64
    curve = _cubic(poles, n)
    k = int(np.argmin(np.hypot(*(curve - np.array(at)).T)))
    piece = min(max((k - 1) // n, 0), len(spline.points) - 2)
    t = (k - piece * n) / n
    if t <= 0.02 or t >= 0.98:
        raise ValueError("A point is already there. Click the spline between its points.")
    p0, p1, p2, p3 = poles[3 * piece : 3 * piece + 4]
    u = 1 - t
    q = u**3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t**3 * p3
    tangent = 3 * (u * u * (p1 - p0) + 2 * u * t * (p2 - p1) + t * t * (p3 - p2))
    norm = math.hypot(tangent[0], tangent[1])
    if norm < 1e-12:
        raise ValueError("The spline has no direction there. Click another place on it.")
    unit = tangent / norm
    old = _cubic(poles[3 * piece : 3 * piece + 4], 96)
    pts = np.array([p0, q, p3])
    a = np.array(sketch.xy(spline.handles[piece]))
    c = np.array(sketch.xy(spline.handles[piece + 1]))
    # A handle used by this piece only (the spline's first or last point) takes its
    # exact split value (de Casteljau), so the curve keeps its shape there.
    first, last = piece == 0, piece + 1 == len(spline.points) - 1
    if first:
        a = p0 + t * (p1 - p0)
    if last:
        c = 2 * p3 - (p3 + u * (p2 - p3))
    best: tuple[float, float] = (math.inf, 0.0)
    span = math.dist(p0, p3) or 1.0
    for reach in np.linspace(0.01, 1.0, 100) * span:
        hs = np.array([a, q + unit * reach, c])
        gap, _ = deviation(old, pts, hs)
        if gap < best[0]:
            best = (gap, float(reach))
    hx, hy = q + unit * best[1]
    for moved, hid_old in ((first, spline.handles[piece]), (last, spline.handles[piece + 1])):
        if moved:
            target = a if hid_old == spline.handles[piece] else c
            handle = sketch.point(hid_old)
            handle.x, handle.y = float(target[0]), float(target[1])
    pid = sketch.add_point(float(q[0]), float(q[1]), spline.construction)
    hid = sketch.add_point(float(hx), float(hy), True)
    spline.points.insert(piece + 1, pid)
    spline.handles.insert(piece + 1, hid)
    return pid


# Relax --------------------------------------------------------------------------------


def relax(sketch: Sketch, sid: str) -> int:
    """Smooth spline ``sid`` with its ends fixed (TR115 item 4, D1314): every through
    point but the two ends gets the even handle a fresh spline through the same points
    would have; the end handles and every point stay. Pinned handles (TR43) stay.
    Returns how many handles moved."""
    from fdcad.core.sketch.freeform import default_handles

    spline = sketch.entities.get(sid)
    if not isinstance(spline, Spline):
        raise ValueError("Pick a spline to relax.")
    pinned = {
        r.entities[0]
        for r in sketch.relations
        if r.type == "fixed" and len(r.entities) == 1 and not r.off
    }
    pts = [sketch.xy(p) for p in spline.points]
    even = default_handles(pts)
    moved = 0
    for i in range(1, len(pts) - 1):
        hid = spline.handles[i]
        if hid in pinned:
            continue
        handle = sketch.point(hid)
        if math.dist((handle.x, handle.y), even[i]) > 1e-9:
            handle.x, handle.y = even[i]
            moved += 1
    return moved
