"""Swap axis relations (TR124, D950).

Horizontal and Vertical relations on the picked lines become relations between the
lines: the first picked line with one is the reference, every other line that was
along the same axis becomes Parallel to it, and every line along the other axis
becomes Perpendicular to it. The reference loses its own relation, so the shape keeps
its square corners but can now turn. Relations switched off, relations between two
points, and lines with both Horizontal and Vertical are left as they are. No Qt; the
caller takes the undo checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fdcad.core.sketch.model import Line, Relation, Sketch

_AXES = ("horizontal", "vertical")


class SwapAxisError(ValueError):
    """Nothing to swap; the message says what to pick."""


@dataclass
class SwapResult:
    """What changed: the reference line, and the relations removed and added."""

    reference: str
    removed: list[Relation] = field(default_factory=list)
    added: list[Relation] = field(default_factory=list)


def _axis_relations(sketch: Sketch, lid: str) -> list[Relation]:
    return [r for r in sketch.relations if r.type in _AXES and not r.off and r.entities == [lid]]


def swap_axis_relations(sketch: Sketch, ids: list[str]) -> SwapResult:
    """Swap the Horizontal and Vertical relations of the picked lines."""
    lines = [i for i in dict.fromkeys(ids) if isinstance(sketch.entities.get(i), Line)]
    axis: dict[str, Relation] = {}
    for lid in lines:
        found = _axis_relations(sketch, lid)
        if len(found) == 1:  # both at once is a conflict the user fixes first
            axis[lid] = found[0]
    if not axis:
        raise SwapAxisError(
            "None of the picked lines has a Horizontal or Vertical relation. Pick the "
            "lines of a shape drawn square to the axes."
        )
    reference = next(iter(axis))
    ref_type = axis[reference].type
    result = SwapResult(reference)
    for lid, rel in axis.items():
        sketch.relations.remove(rel)
        result.removed.append(rel)
        if lid == reference:
            continue
        rtype = "parallel" if rel.type == ref_type else "perpendicular"
        result.added.append(sketch.relate(rtype, reference, lid))
    return result
