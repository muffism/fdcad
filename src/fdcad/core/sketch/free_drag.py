"""Drag without solving and its helpers (TUTORIAL_REVIEW_SPEC_2 TR112, D1716). No Qt.

- Item 1: a drag that moves points straight to the cursor, with no solve; after it,
  ``unmet`` names the relations and dimensions that no longer hold, which the user
  may delete.
- Item 2: ``rewrite_dimensions`` gives driving dimensions of dragged geometry their
  new measured values (a preference, off by default).
- Item 3: ``detach_end`` breaks a dragged end away from the curves it joins.
"""

from __future__ import annotations

import copy
import math

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Point, Sketch, Spline, entity_points
from fdcad.core.sketch.solver import SketchSolveError, measure, solve

#: How far (mm) a point may move when one item is solved alone for it to still hold.
HOLD = 1e-6


def _points(sketch: Sketch) -> dict[str, tuple[float, float]]:
    return {e.id: (e.x, e.y) for e in sketch.entities.values() if isinstance(e, Point)}


def _holds_alone(sketch: Sketch, relation: int | None, dimension: str | None) -> bool:
    trial = copy.deepcopy(sketch)
    trial.relations = [trial.relations[relation]] if relation is not None else []
    trial.dimensions = [d for d in trial.dimensions if d.id == dimension]
    before = _points(trial)
    try:
        result = solve(trial)
    except (SketchSolveError, KeyError, TypeError, ValueError):
        return False
    if not result.solved:
        return False
    after = _points(trial)
    return all(math.dist(xy, after[p]) <= HOLD for p, xy in before.items() if p in after)


def unmet(sketch: Sketch) -> list[str]:
    """Relations (``r<index>``) and driving dimensions that do not hold where the
    sketch stands: solving each alone would move something."""
    out: list[str] = []
    for i, rel in enumerate(sketch.relations):
        if rel.type == "fixed" or rel.off:
            continue  # Fix holds a point where it is; a switched off item holds nothing
        if not _holds_alone(sketch, i, None):
            out.append(f"r{i}")
    for dim in sketch.dimensions:
        if not dim.driving or dim.off:
            continue
        try:
            value = measure(sketch, dim)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(value - dim.param.value) > HOLD:
            out.append(dim.id)
    return out


def delete_items(sketch: Sketch, keys: list[str]) -> None:
    """Delete relations (``r<index>``) and dimensions by key."""
    gone = {int(k[1:]) for k in keys if k.startswith("r") and k[1:].isdigit()}
    sketch.relations = [r for i, r in enumerate(sketch.relations) if i not in gone]
    sketch.dimensions = [d for d in sketch.dimensions if d.id not in set(keys)]


def free_move(sketch: Sketch, targets: dict[str, tuple[float, float]]) -> bool:
    """Move points straight to ``targets`` with no solve. True when any moved."""
    moved = False
    for pid, (x, y) in targets.items():
        p = sketch.entities.get(pid)
        if isinstance(p, Point) and (p.x, p.y) != (x, y):
            p.x, p.y = x, y
            moved = True
    return moved


def dragged_dimensions(sketch: Sketch, points: set[str]) -> list[str]:
    """Driving dimensions that measure geometry using any of ``points``."""
    out = []
    for dim in sketch.dimensions:
        if not dim.driving:
            continue
        used: set[str] = set()
        for eid in dim.entities:
            ent = sketch.entities.get(eid)
            if ent is not None:
                used.update(entity_points(ent))
        if used & points:
            out.append(dim.id)
    return out


def rewrite_dimensions(sketch: Sketch, dims: list[str]) -> None:
    """Give dimensions ``dims`` their measured values (the drag decides, TR112 item 2)."""
    for dim in sketch.dimensions:
        if dim.id in dims:
            try:
                value = measure(sketch, dim)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
            unit = "deg" if dim.type == "angle" else "mm"
            shown = math.degrees(value) if dim.type == "angle" else value
            dim.param = Param(f"{shown:.6g}{unit}", value)


def detach_end(sketch: Sketch, pid: str, keep: str | None = None) -> list[str]:
    """Break point ``pid`` away from what it joins: curves other than ``keep`` (the
    curve that moves with the point; the first user when None) get their own point
    where ``pid`` is, and Coincident relations from ``pid`` to other points go.
    Returns the new point ids."""
    users = [
        e for e in sketch.entities.values() if not isinstance(e, Point) and pid in entity_points(e)
    ]
    if keep is None and users:
        keep = users[0].id
    made: list[str] = []
    x, y = sketch.xy(pid)
    for curve in users:
        if curve.id == keep:
            continue
        new = sketch.add_point(x, y, sketch.point(pid).construction)
        for attr in ("p1", "p2", "start", "end", "center"):
            if getattr(curve, attr, None) == pid:
                setattr(curve, attr, new)
        if isinstance(curve, Spline):
            curve.points = [new if q == pid else q for q in curve.points]
        made.append(new)
    sketch.relations = [
        r
        for r in sketch.relations
        if not (
            r.type == "coincident"
            and pid in r.entities
            and all(isinstance(sketch.entities.get(e), Point) for e in r.entities)
        )
    ]
    return made
