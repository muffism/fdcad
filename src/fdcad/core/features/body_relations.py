"""Move and Copy Body by relations (TR268 item 1, DECISIONS D2415).

Move and Copy Body with ``mode`` "relations". ``refs.rel_from`` holds picks on the
body and ``refs.rel_to`` the matching picks on the target (faces, edges, planes or
axes), in pairs. ``relations`` is text with one relation per pair, separated by
semicolons, such as "coincident; distance 5; angle 90":

- ``coincident``: two flat faces or planes lie on each other, facing each other;
  two axes (round faces or edges, straight edges, axes) line up.
- ``distance <d>``: two flat faces face each other ``d`` apart (mm).
- ``angle <a>``: the normals or axes of the pair are ``a`` degrees apart.
- ``parallel``: the normals or axes point the same way.

All relations are solved together for one rigid move of the body (six numbers:
a turn vector and a shift, about the body's centre) by damped least squares,
started from no move and from half turns about the three axes; the best result
must meet every relation to within 1e-6, else it is a feature error. No Qt.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from OCP.gp import gp_Trsf

from fdcad.core.features.base import BuildContext, FeatureError, Issue, Vec3

Array = NDArray[np.float64]
KINDS = ("coincident", "distance", "angle", "parallel")
_TOL = 1e-6


@dataclass(frozen=True)
class Geom:
    """A resolved pick: a plane (point, normal) or an axis (point, direction)."""

    kind: str  # "plane" or "axis"
    point: Array
    direction: Array


@dataclass(frozen=True)
class Relation:
    """One relation between a body pick and a target pick."""

    kind: str
    value: float
    body: Geom
    target: Geom


def parse(text: str, owner: str) -> list[tuple[str, float]]:
    """The relation list: (kind, value) per item. Raises FeatureError for bad text."""
    out: list[tuple[str, float]] = []
    for part in re.split(r"[;,]+", text or ""):
        item = part.strip().lower()
        if not item:
            continue
        found = re.fullmatch(r"([a-z]+)(?:\s+([-+]?[0-9.]+))?", item)
        if found is None or found.group(1) not in KINDS:
            raise FeatureError(
                f"{owner}: the relations must read like coincident; distance 5; angle 90. "
                f"Fix '{part.strip()}'."
            )
        kind = found.group(1)
        if kind in ("distance", "angle") and found.group(2) is None:
            raise FeatureError(f"{owner}: enter a value after {kind}, such as {kind} 5.")
        value = float(found.group(2) or 0.0)
        out.append((kind, math.radians(value) if kind == "angle" else value))
    return out


def _geom(ctx: BuildContext, ref: Any, owner: str) -> tuple[Geom, list[Issue]]:
    """A flat face or plane is a plane; anything with an axis is an axis."""
    from fdcad.core.features.geometry_refs import resolve_placement

    try:
        place = resolve_placement(ctx, ref, owner, "plane")
        return Geom("plane", np.array(place.point), np.array(place.direction)), place.issues
    except FeatureError:
        place = resolve_placement(ctx, ref, owner, "axis")
        return Geom("axis", np.array(place.point), np.array(place.direction)), place.issues


def relations(
    ctx: BuildContext, refs: dict[str, Any], text: str, owner: str
) -> tuple[list[Relation], list[Issue]]:
    """The relations of ``refs`` and ``text``, resolved."""
    raw_from, raw_to = refs.get("rel_from"), refs.get("rel_to")
    picks_from: list[Any] = raw_from if isinstance(raw_from, list) else []
    picks_to: list[Any] = raw_to if isinstance(raw_to, list) else []
    kinds = parse(text, owner)
    if not kinds:
        raise FeatureError(f"{owner}: add a relation, such as coincident, for the picked pair.")
    if len(picks_from) != len(kinds) or len(picks_to) != len(kinds):
        raise FeatureError(
            f"{owner}: pick one body item and one target item for each of the {len(kinds)} "
            "relations."
        )
    out: list[Relation] = []
    issues: list[Issue] = []
    for (kind, value), a, b in zip(kinds, picks_from, picks_to, strict=True):
        body, more = _geom(ctx, a, owner)
        target, found = _geom(ctx, b, owner)
        issues += more + found
        if kind in ("coincident", "distance") and body.kind != target.kind:
            raise FeatureError(
                f"{owner}: {kind} needs two flat faces or two axes. Pick a matching pair."
            )
        if kind == "distance" and body.kind != "plane":
            raise FeatureError(f"{owner}: a distance needs two flat faces. Pick flat faces.")
        out.append(Relation(kind, value, body, target))
    return out, issues


def _rotation(r: Array) -> Array:
    """The rotation matrix of the turn vector ``r`` (Rodrigues)."""
    angle = float(np.linalg.norm(r))
    if angle < 1e-15:
        return np.eye(3)
    k = r / angle
    kx = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    out: Array = np.eye(3) + math.sin(angle) * kx + (1 - math.cos(angle)) * kx @ kx
    return out


def residuals(x: Array, rels: list[Relation], centre: Array) -> Array:
    """How far each relation is from holding after the move ``x``."""
    rot = _rotation(x[:3])
    out: list[float] = []
    for rel in rels:
        p = rot @ (rel.body.point - centre) + centre + x[3:]
        d = rot @ rel.body.direction
        tp, td = rel.target.point, rel.target.direction
        if rel.kind == "parallel":
            out += list(np.cross(d, td))
            out.append(min(0.0, float(np.dot(d, td))))
        elif rel.kind == "angle":
            out.append(float(np.dot(d, td)) - math.cos(rel.value))
        elif rel.body.kind == "plane":  # coincident or distance: faces face each other
            out += list(d + td)
            gap = rel.value if rel.kind == "distance" else 0.0
            out.append(float(np.dot(p - tp, td)) - gap)
        else:  # coincident axes: the same line
            out += list(np.cross(d, td))
            off = p - tp
            out += list(off - np.dot(off, td) * td)
    return np.array(out)


def solve(rels: list[Relation], centre: Vec3) -> Array | None:
    """The move (turn vector, shift) meeting every relation, or None."""
    c = np.asarray(centre, dtype=float)
    best: tuple[float, Array] | None = None
    for start in (np.zeros(3), *(np.pi * np.eye(3))):
        x = np.concatenate([start, np.zeros(3)])
        damping = 1e-3
        r = residuals(x, rels, c)
        for _ in range(200):  # bounded: six unknowns, a few dozen steps converge
            if float(r @ r) < 1e-24:
                break
            jac = np.empty((len(r), 6))
            for k in range(6):
                step = np.zeros(6)
                step[k] = 1e-7
                jac[:, k] = (residuals(x + step, rels, c) - r) / 1e-7
            lhs = jac.T @ jac + damping * np.eye(6)
            dx = np.linalg.solve(lhs, -jac.T @ r)
            trial = x + dx
            rt = residuals(trial, rels, c)
            if float(rt @ rt) < float(r @ r):
                x, r, damping = trial, rt, max(damping / 3, 1e-12)
            else:
                damping *= 4
                if damping > 1e8:
                    break
        error = float(np.abs(r).max()) if len(r) else 0.0
        if best is None or error < best[0]:
            best = (error, x)
        if error < _TOL:
            break
    if best is None or best[0] > _TOL:
        return None
    return best[1]


def relation_move(
    ctx: BuildContext, refs: dict[str, Any], text: str, owner: str, centre: Vec3
) -> tuple[gp_Trsf, list[Issue]]:
    """The rigid move that makes every relation hold."""
    rels, issues = relations(ctx, refs, text, owner)
    x = solve(rels, centre)
    if x is None:
        raise FeatureError(
            f"{owner}: the relations cannot all hold at once. Remove one, or change a "
            "distance or angle."
        )
    rot = _rotation(x[:3])
    c = np.asarray(centre, dtype=float)
    shift = c + x[3:] - rot @ c
    trsf = gp_Trsf()
    trsf.SetValues(*(float(v) for v in (*rot[0], shift[0], *rot[1], shift[1], *rot[2], shift[2])))
    return trsf, issues
