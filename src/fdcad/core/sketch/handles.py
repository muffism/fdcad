"""Spline handles: pin, reset and handle lines (TUTORIAL_REVIEW_SPEC_2 TR43, D1305).

A spline keeps one handle point per through point (D278): the curve leaves the
point toward the handle, so the handle sets the tangent direction and its
distance sets how far the tangent reaches. Handles are ordinary construction
points, so they can be dragged and dimensioned. This module adds:

* ``pin_handle``: a Fixed relation on the handle, so it stays put while other
  points move; ``reset_handle`` removes it.
* ``handle_line``: a construction line from the through point to its handle,
  sharing both points, so the handle's angle and length take angle and length
  dimensions and line relations (for example Parallel or Collinear to a line).

Pure Python, no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

from fdcad.core.sketch.model import Line, Sketch, Spline


@dataclass(frozen=True)
class HandleRef:
    """A through point of a spline and its handle."""

    spline: str
    index: int
    point: str
    handle: str


def handle_of(sketch: Sketch, pid: str) -> HandleRef | None:
    """The spline handle that point ``pid`` is (or whose through point it is)."""
    for e in sketch.entities.values():
        if not isinstance(e, Spline):
            continue
        for i, (p, h) in enumerate(zip(e.points, e.handles, strict=True)):
            if pid in (p, h):
                return HandleRef(e.id, i, p, h)
    return None


def is_pinned(sketch: Sketch, pid: str) -> bool:
    """True when the handle of ``pid`` has a switched on Fixed relation."""
    ref = handle_of(sketch, pid)
    return ref is not None and any(
        r.type == "fixed" and r.entities == [ref.handle] and not r.off for r in sketch.relations
    )


def pin_handle(sketch: Sketch, pid: str) -> bool:
    """Fix the handle of ``pid`` where it is. False when it is not a spline handle or
    is pinned already."""
    ref = handle_of(sketch, pid)
    if ref is None or is_pinned(sketch, pid):
        return False
    sketch.relate("fixed", ref.handle)
    return True


def reset_handle(sketch: Sketch, pid: str) -> bool:
    """Remove the pin (every Fixed relation) of the handle of ``pid``. False when
    there was none."""
    ref = handle_of(sketch, pid)
    if ref is None:
        return False
    before = len(sketch.relations)
    sketch.relations = [
        r for r in sketch.relations if not (r.type == "fixed" and r.entities == [ref.handle])
    ]
    return len(sketch.relations) < before


def handle_line(sketch: Sketch, pid: str) -> str | None:
    """A construction line from the through point of ``pid`` to its handle (the one
    already there, or a new one). None when ``pid`` is not on a spline."""
    ref = handle_of(sketch, pid)
    if ref is None:
        return None
    for e in sketch.entities.values():
        if isinstance(e, Line) and {e.p1, e.p2} == {ref.point, ref.handle}:
            return e.id
    lid = sketch.new_id()
    sketch.entities[lid] = Line(lid, ref.point, ref.handle, construction=True)
    return lid


def handle_lines(sketch: Sketch) -> list[tuple[str, str, bool]]:
    """Every (through point, handle, pinned) of every spline, for drawing."""
    pinned = {
        r.entities[0]
        for r in sketch.relations
        if r.type == "fixed" and len(r.entities) == 1 and not r.off
    }
    out = []
    for e in sketch.entities.values():
        if isinstance(e, Spline):
            for p, h in zip(e.points, e.handles, strict=True):
                if p in sketch.entities and h in sketch.entities:
                    out.append((p, h, h in pinned))
    return out
