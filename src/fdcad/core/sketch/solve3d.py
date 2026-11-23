"""Relations and dimensions between the points of free 3D lines (TR7, D2206).

A 3D sketch's free lines (``data.lines``) may carry ``data.relations``, each a dict:

- ``type``: ``along_x``, ``along_y``, ``along_z`` (the segment between two points
  runs along that axis), ``coincident`` (two points at one place), ``fixed`` (a point
  held at ``at``, three numbers in mm) or ``length`` (the 3D distance between two
  points is ``value`` mm: a 3D dimension).
- ``points``: point references. ``"k.i"`` is point ``i`` of 3D line ``k`` (both from 1);
  ``"Pk:eN"`` is point ``eN`` of plane sketch part ``k``, already placed in space, so
  a line end can be tied to a sketch on a plane (relations between planes).

``solve`` moves the line points as little as it can (a least squares step of
smallest size, repeated) until every relation holds. Pure numpy; no Qt, no kernel.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

TYPES = ("along_x", "along_y", "along_z", "coincident", "fixed", "length")
#: How many points each relation type names.
ARITY = {"along_x": 2, "along_y": 2, "along_z": 2, "coincident": 2, "fixed": 1, "length": 2}
_LINE_REF = re.compile(r"^(\d+)\.(\d+)$")
_PART_REF = re.compile(r"^P(\d+):(e\d+)$")
TOLERANCE = 1e-9  # mm
MAX_STEPS = 60

Vec3 = tuple[float, float, float]


class Solve3DError(ValueError):
    """The relations cannot be met; the message says what to do."""


@dataclass
class Solved3D:
    """Solved line points (same shape as the input lists) and the free movements left."""

    lines: list[list[Vec3]]
    free: int


def _index(lines: list[list[Vec3]]) -> dict[str, int]:
    """Each line point reference to its row in the flat point array."""
    out: dict[str, int] = {}
    n = 0
    for k, pts in enumerate(lines, start=1):
        for i in range(1, len(pts) + 1):
            out[f"{k}.{i}"] = n
            n += 1
    return out


def check(relation: Any, lines: list[list[Vec3]], parts: dict[str, Vec3]) -> str | None:
    """Why ``relation`` is damaged or names a point that does not exist, else None."""
    if not isinstance(relation, dict) or relation.get("type") not in TYPES:
        return "a 3D relation has an unknown type"
    refs = relation.get("points")
    kind = str(relation["type"])
    if not isinstance(refs, list) or len(refs) != ARITY[kind]:
        return f"a {kind} relation needs {ARITY[kind]} points"
    rows = _index(lines)
    for ref in refs:
        if not isinstance(ref, str) or (ref not in rows and ref not in parts):
            return f"the 3D relation point {ref} does not exist"
    if all(ref in parts for ref in refs):
        return "a 3D relation needs at least one point of a 3D line"
    if kind == "length":
        value = relation.get("value")
        if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0:
            return "a 3D length needs a value above zero"
    if kind == "fixed":
        at = relation.get("at")
        if not isinstance(at, list) or len(at) != 3:
            return "a fixed 3D point needs its place"
    return None


def solve(
    lines: list[list[Vec3]], relations: list[dict[str, Any]], parts: dict[str, Vec3] | None = None
) -> Solved3D:
    """Move the line points until every relation holds. Raises Solve3DError."""
    parts = parts or {}
    rows = _index(lines)
    for rel in relations:
        why = check(rel, lines, parts)
        if why is not None:
            raise Solve3DError(f"{why.capitalize()}. Delete it and add it again.")
    x = np.array([p for pts in lines for p in pts], dtype=float).reshape(-1)
    if x.size == 0:
        return Solved3D([], 0)
    terms = [_term(rel, rows, parts) for rel in relations]
    if not terms:
        return Solved3D([list(pts) for pts in lines], x.size)
    for _ in range(MAX_STEPS):
        f, jac = _system(terms, x)
        if float(np.max(np.abs(f))) < TOLERANCE:
            break
        step, *_rest = np.linalg.lstsq(jac, -f, rcond=None)
        x = x + step
    f, jac = _system(terms, x)
    if float(np.max(np.abs(f))) > 1e-6:
        raise Solve3DError(
            "The 3D relations and dimensions conflict, so no shape meets them all. "
            "Delete a relation or change a 3D length."
        )
    free = int(x.size - np.linalg.matrix_rank(jac, tol=1e-8))
    pts = x.reshape(-1, 3)
    out: list[list[Vec3]] = []
    n = 0
    for line in lines:
        out.append([(float(p[0]), float(p[1]), float(p[2])) for p in pts[n : n + len(line)]])
        n += len(line)
    return Solved3D(out, free)


#: A relation as residual rows: (values, Jacobian rows) for the flat point array.
Term = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]


def _system(terms: list[Term], x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    parts = [t(x) for t in terms]
    return np.concatenate([p[0] for p in parts]), np.vstack([p[1] for p in parts])


def _term(rel: dict[str, Any], rows: dict[str, int], parts: dict[str, Vec3]) -> Term:
    kind = str(rel["type"])
    refs = [str(r) for r in rel["points"]]

    def place(x: np.ndarray, ref: str) -> np.ndarray:
        if ref in rows:
            return x[3 * rows[ref] : 3 * rows[ref] + 3]
        return np.array(parts[ref], dtype=float)

    def grad(x: np.ndarray, ref: str, g: np.ndarray) -> np.ndarray:
        """``g`` (rows by 3) placed in the columns of ``ref`` (zero for a part point)."""
        out = np.zeros((g.shape[0], x.size))
        if ref in rows:
            out[:, 3 * rows[ref] : 3 * rows[ref] + 3] = g
        return out

    if kind == "fixed":
        at = np.array([float(v) for v in rel["at"]])

        def fixed(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            return place(x, refs[0]) - at, grad(x, refs[0], np.eye(3))

        return fixed
    if kind == "length":
        value = float(rel["value"])

        def length(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            d = place(x, refs[1]) - place(x, refs[0])
            n = float(np.linalg.norm(d))
            u = d / n if n > 1e-12 else np.array([1.0, 0.0, 0.0])
            g = u.reshape(1, 3)
            return np.array([n - value]), grad(x, refs[1], g) - grad(x, refs[0], g)

        return length
    keep = {"along_x": [1, 2], "along_y": [0, 2], "along_z": [0, 1], "coincident": [0, 1, 2]}
    axes = keep[kind]
    pick = np.eye(3)[axes]

    def linear(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        d = place(x, refs[1]) - place(x, refs[0])
        return d[axes], grad(x, refs[1], pick) - grad(x, refs[0], pick)

    return linear


def describe(rel: dict[str, Any]) -> str:
    """A short text for a relation list row, such as ``length 1.1 1.2 = 25 mm``."""
    text = f"{rel.get('type', '?')} {' '.join(str(p) for p in rel.get('points') or [])}"
    if rel.get("type") == "length" and isinstance(rel.get("value"), int | float):
        text += f" = {float(rel['value']):.6g} mm"
    return text
