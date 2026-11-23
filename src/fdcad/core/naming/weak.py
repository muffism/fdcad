"""Weak names and how their faces, edges and vertices are checked (DECISIONS D720).

Most names come from where a face was made (``f6/cap/end``, ``f6/side/e3``) and
keep pointing at the same face through edits. Four kinds are numbers handed out
by position or by file order, so an upstream edit can give the number to another
face without the name failing:

1. Split pieces: ``<name>#1``, ``<name>#2``, ordered by centre position.
2. Position fallback names: ``<feature>/face#k`` (for example the rings a
   revolve makes from profile lines square to its axis).
3. Imported faces: ``<feature>/face/<k>``, the face's index in the file.
4. Faces a feature numbers by position: ``<feature>/indent/<k>`` and
   ``<feature>/lap/<k>`` (D1068).

A reference on a weak name is checked against its stored snapshot. Its family
is every face (edge, vertex) whose name is the same once the numbers are taken
out. This module holds the geometric rules on snapshot dictionaries; the kernel
work is in ``fdcad.core.naming.resolve``.
"""

from __future__ import annotations

import math
import re
from typing import Any

_NUMBER = re.compile(r"#\d+")
_INDEX = re.compile(r"/face/\d+")
#: Faces a feature numbers in position order: Indent and Half Lap (D1068).
_PLACED = re.compile(r"/(indent/w?|lap/)\d+")

#: Two snapshot centres closer than this are the same place (mm).
POINT_TOL = 1e-3
#: The named face is kept silently only while its centre is within this share of
#: its size from where it was picked. Ordinary dimension edits move a face's
#: centre by well under half its size; a renumbered face is usually farther.
SIZE_SHARE = 0.5
#: The nearest member of a family is a clear choice only when every other member
#: is at least this many times farther away.
CLEAR_RATIO = 1.0 / 0.75
#: Faces and lines whose directions differ by more than about 45 degrees are
#: never the same face or edge.
MIN_ALIGN = math.cos(math.radians(45))


def is_weak(name: str) -> bool:
    """True when ``name`` holds a number given by position or by file order."""
    return bool(_NUMBER.search(name) or _INDEX.search(name) or _PLACED.search(name))


def family_root(name: str) -> str:
    """``name`` with its position and file numbers taken out."""
    plain = _INDEX.sub("/face/*", _NUMBER.sub("", name))
    return _PLACED.sub(lambda found: f"/{found.group(1)}*", plain)


def _dot(a: Any, b: Any) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b, strict=False))


def _place(snap: dict[str, Any]) -> list[float] | None:
    point = snap.get("point", snap.get("midpoint"))
    return [float(v) for v in point] if isinstance(point, list) and len(point) == 3 else None


def compatible(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    """True when ``current`` could be the face or edge ``stored`` was taken from."""
    kind = "surface" if "surface" in stored else "curve"
    if stored.get(kind) != current.get(kind):
        return False
    if "normal" in stored:  # flat faces: same side
        return "normal" in current and _dot(stored["normal"], current["normal"]) >= MIN_ALIGN
    if "direction" in stored:  # straight edges: either way along
        return "direction" in current and abs(_dot(stored["direction"], current["direction"])) >= (
            MIN_ALIGN
        )
    if "axis" in stored and "axis" in current:  # round faces and edges
        return abs(_dot(stored["axis"][3:], current["axis"][3:])) >= MIN_ALIGN
    return True


def distance(stored: dict[str, Any], current: dict[str, Any]) -> float:
    """How far the snapshot's centre (or edge midpoint) has moved."""
    a, b = _place(stored), _place(current)
    return math.inf if a is None or b is None else math.dist(a, b)


def size(stored: dict[str, Any]) -> float:
    """A length that says how big the picked face or edge was."""
    if "area" in stored:
        return math.sqrt(max(float(stored["area"]), 0.0))
    if "radius" in stored:
        return float(stored["radius"])
    return float(stored.get("length", 0.0))


def nearest(stored: dict[str, Any], snaps: list[dict[str, Any]]) -> int | None:
    """Index of the clearly nearest compatible snapshot, or None when none is clear."""
    ranked = sorted((distance(stored, s), i) for i, s in enumerate(snaps) if compatible(stored, s))
    if not ranked or math.isinf(ranked[0][0]):
        return None
    best, index = ranked[0]
    if len(ranked) == 1 or best <= POINT_TOL or ranked[1][0] >= CLEAR_RATIO * best:
        return index
    return None


def close(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    """True when ``current`` is near enough to where ``stored`` was picked to keep silently.

    A vertex has no size, so being the clearly nearest member is enough for it.
    """
    extent = size(stored)
    if extent <= 0:
        return True
    return distance(stored, current) <= max(POINT_TOL, SIZE_SHARE * extent)


def same_place(stored: dict[str, Any], snaps: list[dict[str, Any]]) -> list[int]:
    """Indexes of compatible snapshots whose centre has not moved."""
    return [
        i for i, s in enumerate(snaps) if compatible(stored, s) and distance(stored, s) <= POINT_TOL
    ]


__all__ = [
    "CLEAR_RATIO",
    "MIN_ALIGN",
    "POINT_TOL",
    "SIZE_SHARE",
    "close",
    "compatible",
    "distance",
    "family_root",
    "is_weak",
    "nearest",
    "same_place",
    "size",
]
