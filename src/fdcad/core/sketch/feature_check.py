"""Check Sketch for Feature (TR36, DECISIONS D763).

Answers "will this sketch work for this feature?" before the feature is made.
It uses the same checks the features run (``topology.check``, PLAN.md section 5A
item 9) and adds what they do not say:

- open contours with the size of the gap to the nearest other open end,
- end points that nearly meet (closer than ``NEAR`` but not joined),
- the number of contours the feature kind takes.

Feature kinds take these contours (spec item 5): one open contour (rib, sweep
path, thin features), one closed contour (sweep profile, loft profile), separate
closed contours (boss, cut, revolve), or any mix (wrap, split). A flange takes one
contour, open or closed. Crossing curves are not a problem (D116 item 1) and
construction geometry is ignored. Pure Python.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from fdcad.core.sketch.model import Sketch, curve_ends
from fdcad.core.sketch.topology import _Nodes, check

Vec = tuple[float, float]

#: End points closer than this (mm) but not joined are a near miss.
NEAR = 0.05

#: Feature kind: (label, contour rule).
KINDS: dict[str, tuple[str, str]] = {
    "boss": ("Boss", "closed_many"),
    "cut": ("Cut", "closed_many"),
    "revolve": ("Revolve", "closed_many"),
    "sweep_profile": ("Sweep profile", "closed_one"),
    "sweep_path": ("Sweep path", "open_one"),
    "loft_profile": ("Loft profile", "closed_one"),
    "rib": ("Rib", "open_one"),
    "thin": ("Thin feature", "open_one"),
    "wrap": ("Wrap", "any"),
    "split": ("Split", "any"),
    "flange": ("Flange", "one"),
}


@dataclass
class Problem:
    """One row of the result: what is wrong, where, and which entities."""

    kind: str  # "open", "near_miss", "branch", "duplicate", "count", "empty"
    message: str
    entities: list[str] = field(default_factory=list)
    at: Vec | None = None  # where to zoom to


def _contours(sketch: Sketch, nodes: _Nodes) -> tuple[int, int]:
    """How many separate open chains and closed contours of curves there are. A
    circle or ellipse, which has no ends, is a closed contour on its own."""
    adjacency: dict[str, set[str]] = defaultdict(set)
    ends: dict[str, list[str]] = defaultdict(list)
    for c in sketch.curves():
        pair = curve_ends(c)
        if pair is None:
            continue
        a, b = nodes.find(pair[0]), nodes.find(pair[1])
        adjacency[a].add(b)
        adjacency[b].add(a)
        ends[a].append(c.id)
        ends[b].append(c.id)
    seen: set[str] = set()
    chains = 0
    closed = sum(1 for c in sketch.curves() if curve_ends(c) is None)
    for start in adjacency:
        if start in seen:
            continue
        stack, group = [start], set()
        while stack:
            node = stack.pop()
            if node in group:
                continue
            group.add(node)
            stack.extend(adjacency[node] - group)
        seen |= group
        if any(len(ends[n]) == 1 for n in group):
            chains += 1
        else:
            closed += 1
    return chains, closed


def check_for(sketch: Sketch, kind: str) -> list[Problem]:
    """Problems the feature ``kind`` cannot accept in ``sketch``; [] when it is fine."""
    if kind not in KINDS:
        raise ValueError(f"Unknown feature kind '{kind}'.")
    label, rule = KINDS[kind]
    curves = sketch.curves()
    if not curves:
        return [Problem("empty", "The sketch has no curves. Draw the shape first.")]
    nodes = _Nodes(sketch)
    out: list[Problem] = []
    open_ends: list[tuple[str, str]] = []  # (point id, curve id)
    for issue in check(sketch):
        if issue.kind == "open":
            curve = sketch.entities[issue.entities[0]]
            pair = curve_ends(curve)  # type: ignore[arg-type]
            if pair is None:
                continue
            for pid in pair:
                users = [
                    c.id
                    for c in curves
                    if (e := curve_ends(c)) is not None
                    and nodes.find(pid) in {nodes.find(p) for p in e}
                ]
                if len(users) == 1:
                    open_ends.append((pid, curve.id))
        elif issue.kind == "branch":
            out.append(
                Problem(
                    "branch",
                    "Three or more curves meet at one point. Trim or delete the extra curves.",
                    issue.entities,
                )
            )
        elif issue.kind == "duplicate":
            out.append(Problem("duplicate", issue.message, issue.entities))
    # One problem per open end point (an end shared by two curves of one issue is once).
    seen_nodes: set[str] = set()
    unique: list[tuple[str, str]] = []
    for pid, cid in open_ends:
        node = nodes.find(pid)
        if node not in seen_nodes:
            seen_nodes.add(node)
            unique.append((pid, cid))
    for i, (pid, cid) in enumerate(unique):
        here = sketch.xy(pid)
        others = [sketch.xy(q) for j, (q, _c) in enumerate(unique) if j != i]
        gap = min((math.dist(here, o) for o in others), default=None)
        if gap is not None and gap < NEAR:
            out.append(
                Problem(
                    "near_miss",
                    f"Two end points nearly meet ({gap:.4g} mm apart) but are not joined. "
                    "Drag one onto the other, or add a Coincident relation.",
                    [cid],
                    here,
                )
            )
        elif rule not in ("open_one", "any", "one"):
            size = f", {gap:.4g} mm from the nearest open end" if gap is not None else ""
            out.append(
                Problem(
                    "open",
                    f"The contour is open here{size}. {label} needs closed contours: "
                    "connect this end point to another curve.",
                    [cid],
                    here,
                )
            )
    # Near misses are reported once per pair.
    reported: set[frozenset[str]] = set()
    kept: list[Problem] = []
    for p in out:
        if p.kind == "near_miss":
            key = frozenset(p.entities)
            near = [q for q in out if q.kind == "near_miss" and q is not p and q.at is not None]
            partner = next(
                (q for q in near if p.at and q.at and math.dist(p.at, q.at) < NEAR), None
            )
            if partner is not None:
                key = frozenset([*p.entities, *partner.entities])
            if key in reported:
                continue
            reported.add(key)
        kept.append(p)
    out = kept
    chains, loops = _contours(sketch, nodes)
    if rule == "open_one" and (chains != 1 or loops):
        out.append(
            Problem(
                "count",
                f"{label} needs one open contour; the sketch has {chains} open and {loops} "
                "closed. Delete or join curves so one open contour is left.",
            )
        )
    elif rule == "closed_one" and (loops != 1 or chains):
        out.append(
            Problem(
                "count",
                f"{label} needs one closed contour; the sketch has {loops} closed and {chains} "
                "open. Close the contour, or delete the extra curves.",
            )
        )
    elif rule == "closed_many" and chains and not any(p.kind == "open" for p in out):
        out.append(
            Problem(
                "count",
                f"{label} needs closed contours; {chains} are open. Close them.",
            )
        )
    elif rule == "one" and loops + chains != 1:
        out.append(
            Problem(
                "count",
                f"{label} needs one contour; the sketch has {loops + chains}. "
                "Delete the extra curves.",
            )
        )
    return out
