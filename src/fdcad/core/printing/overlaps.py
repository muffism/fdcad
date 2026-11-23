"""Overlapping bodies on export (TUTORIAL_REVIEW_SPEC_2 TR411, DECISIONS D907).

Bodies that overlap print the shared volume twice. :func:`find` lists the
overlapping pairs; :func:`resolve` joins them (``join``) or lets the earlier body
keep the shared volume (``first``: later bodies are cut by earlier ones). ``warn``
leaves the bodies as they are, and the export says which ones overlap. No Qt;
kernel work, run it off the UI thread.
"""

from __future__ import annotations

from typing import Any

MODES = ("warn", "join", "first")


def find(shape: Any) -> list[tuple[int, int, float]]:
    """(first body, second body, shared volume in mm3) for every overlapping pair, with
    bodies counted from 1."""
    from fdcad.core.features.solids import solids
    from fdcad.core.interference import check

    bodies = solids(shape)
    if len(bodies) < 2:
        return []
    return [(r.first + 1, r.second + 1, r.volume) for r in check(bodies) if r.kind == "overlap"]


def resolve(shape: Any, mode: str) -> Any:
    """``shape`` with overlaps joined or given to the earlier body; unchanged for "warn"."""
    from fdcad.core.features.solids import compound, solids
    from fdcad.core.occ import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse

    if mode == "warn":
        return shape
    bodies = list(solids(shape))
    pairs = find(shape)
    if not pairs:
        return shape
    if mode == "join":
        groups: list[set[int]] = []
        for a, b, _v in pairs:
            hit = [g for g in groups if a - 1 in g or b - 1 in g]
            merged = {a - 1, b - 1}.union(*hit) if hit else {a - 1, b - 1}
            groups = [g for g in groups if g not in hit] + [merged]
        joined = set().union(*groups) if groups else set()
        out = [bodies[i] for i in range(len(bodies)) if i not in joined]
        for g in groups:
            members = sorted(g)
            fused = bodies[members[0]]
            for i in members[1:]:
                fused = BRepAlgoAPI_Fuse(fused, bodies[i]).Shape()
            out.extend(solids(fused))
        return compound(out)
    # "first": each body loses what earlier bodies already hold.
    overlapping = {(a - 1, b - 1) for a, b, _v in pairs}
    out = []
    for j, body in enumerate(bodies):
        for i in range(j):
            if (i, j) in overlapping:
                body = BRepAlgoAPI_Cut(body, bodies[i]).Shape()
        out.extend(solids(body))
    return compound(out)


def warning(pairs: list[tuple[int, int, float]]) -> str:
    """What the export says about overlaps ("" when none)."""
    if not pairs:
        return ""
    listed = ", ".join(f"{a} and {b} ({v:.3g} mm3)" for a, b, v in pairs[:3])
    more = f" and {len(pairs) - 3} more pairs" if len(pairs) > 3 else ""
    return (
        f"Bodies {listed}{more} overlap, so the overlap prints twice. Set Overlapping "
        "bodies in the export options to join them or let the first body win."
    )
