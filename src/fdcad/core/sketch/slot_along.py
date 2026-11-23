"""Slot along picked curves (TR225, D946).

The picked lines and arcs (one chain, or several) are the centre line. A slot of
one width is made round them: both sides are offsets that share one distance, the
ends are round caps, and joins along a chain meet as the offset makes them. The
centre line becomes construction geometry. The width is one dimension across the
slot. No Qt; the caller takes the undo checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Ellipse, EllipseArc, Line, Sketch, Spline
from fdcad.core.sketch.ops.offset import OffsetError, chains, offset


class SlotAlongError(ValueError):
    """The slot cannot be made; the message says why and what to do."""


@dataclass
class SlotAlongResult:
    """What the slot made: its outline curves and the width dimension, if any."""

    curves: list[str] = field(default_factory=list)
    dimension: str | None = None


def slot_along(sketch: Sketch, ids: list[str], width: float) -> SlotAlongResult:
    """Make a slot of ``width`` mm round the picked lines and arcs."""
    if width <= 1e-6:
        raise SlotAlongError("Type a slot width larger than zero.")
    picked = [i for i in dict.fromkeys(ids) if i in sketch.entities]
    if any(isinstance(sketch.entities[i], Ellipse | EllipseArc | Spline) for i in picked):
        raise SlotAlongError(
            "A slot can follow lines and arcs only. Pick lines and arcs, or replace the "
            "spline or ellipse with lines and arcs first."
        )
    curves = [i for i in picked if isinstance(sketch.entities[i], Line | Arc)]
    if not curves:
        raise SlotAlongError("Pick the lines or arcs the slot should follow.")
    try:
        groups = chains(sketch, curves)
    except OffsetError as exc:
        raise SlotAlongError(str(exc)) from exc
    if any(closed for _chain, closed in groups):
        raise SlotAlongError(
            "The picked curves make a closed loop, so the slot has no ends. Use Offset with "
            "Both directions for a closed loop."
        )
    first = sketch.entities[groups[0][0][0].cid]
    assert isinstance(first, Line | Arc)  # chains hold the picked lines and arcs only
    side = first.p1 if isinstance(first, Line) else first.start
    toward = sketch.xy(side)
    # Any point works for the side, since the slot goes both ways.
    toward = (toward[0] + 1.0, toward[1] + 1.0)
    try:
        made = offset(
            sketch,
            curves,
            width / 2,
            toward,
            both=True,
            base_construction=True,
            cap="arcs",
        )
    except OffsetError as exc:
        raise SlotAlongError(str(exc)) from exc
    result = SlotAlongResult(made.copies + made.caps)
    # The width across the slot drives the shared offset distance.
    n = len(groups[0][0])
    a, b = made.copies[0], made.copies[n]
    if isinstance(sketch.entities[a], Line) and isinstance(sketch.entities[b], Line):
        rel = next(r for r in reversed(sketch.relations) if r.type == "offset")
        rel.value = None
        dim = sketch.dimension("distance", [a, b], Param(f"{width:.6g}mm", width))
        result.dimension = dim.id
    return result
