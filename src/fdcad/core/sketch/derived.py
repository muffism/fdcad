"""Derived sketch: a linked copy of another sketch (TUTORIAL_REVIEW_SPEC_2 TR49, D845).

A sketch feature with ``refs.derived_from`` (``{"feature": <sketch id>}``) does not
keep geometry of its own: on every rebuild it takes the solved geometry of that
sketch, moves it by ``data.derived_place`` (``dx``, ``dy`` in mm and ``angle`` in
radians, about the sketch origin, in its own plane) and holds every point with a
Fixed relation, so it cannot change shape but follows the original. Break Link
turns the copy into an ordinary sketch. No Qt.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from fdcad.core.sketch.model import Point, Relation, Sketch, entity_points


def placement(data: dict[str, Any]) -> tuple[float, float, float]:
    """``(dx, dy, angle)`` from a sketch's ``derived_place`` data (zeros when missing)."""
    raw = data.get("derived_place")
    if not isinstance(raw, dict):
        return 0.0, 0.0, 0.0
    out = []
    for key in ("dx", "dy", "angle"):
        value = raw.get(key, 0.0)
        out.append(
            float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0
        )
    return out[0], out[1], out[2]


def derived_copy(source: Sketch, dx: float, dy: float, angle: float) -> Sketch:
    """A copy of ``source`` turned by ``angle`` about the origin then moved by (dx, dy),
    every point held by a Fixed relation and no other relations or dimensions."""
    out = Sketch(entities=copy.deepcopy(source.entities))
    out.next_entity = source.next_entity
    c, s = math.cos(angle), math.sin(angle)
    for e in out.entities.values():
        if isinstance(e, Point):
            x, y = e.x, e.y
            e.x, e.y = x * c - y * s + dx, x * s + y * c + dy
    held = sorted({p for e in out.entities.values() for p in entity_points(e)})
    out.relations = [Relation("fixed", [pid]) for pid in held]
    return out
