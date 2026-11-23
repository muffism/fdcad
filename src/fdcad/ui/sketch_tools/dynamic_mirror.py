"""Dynamic mirror while drawing (PHASE2_SPEC P2.8 item 4, DECISIONS D514).

While a mirror line is set on the open sketch (``SketchEdit.mirror_axis``),
each shape a drawing tool makes is mirrored about it at once with the core
mirror operation, so the copies get Symmetric relations to the originals. The
tool calls :func:`mirror_new` inside the shape's undo checkpoint. Pure Python,
no Qt.
"""

from __future__ import annotations

from fdcad.core.sketch.model import Arc, Circle, Line, Point, Sketch, entity_points
from fdcad.core.sketch.ops.mirror import mirror
from fdcad.ui.sketch_tools import tool_text
from fdcad.ui.sketch_tools.edit import SketchEdit

#: Entity types the core mirror operation copies.
MIRRORABLE = (Point, Line, Circle, Arc)


def axis_of(edit: SketchEdit) -> str | None:
    """The mirror line of the open sketch, or None when it is off or the line is gone."""
    axis = edit.mirror_axis
    if axis is None or not isinstance(edit.sketch.entities.get(axis), Line):
        return None
    return axis


def new_shape(sketch: Sketch, before: set[str]) -> tuple[list[str], bool]:
    """The entities added since ``before`` that the mirror copies, and whether any
    added curve cannot be mirrored (splines and ellipses).

    Fixed reference copies of part geometry and the points that belong to an added
    curve are left out: the curve brings its points.
    """
    fixed = {e for r in sketch.relations if r.type == "fixed" for e in r.entities}
    added = [eid for eid in sketch.entities if eid not in before and eid not in fixed]
    used: set[str] = set()
    for eid in added:
        ent = sketch.entities[eid]
        if not isinstance(ent, Point):
            used.update(entity_points(ent))
    ids: list[str] = []
    skipped = False
    left_out: set[str] = set()  # the points of curves that cannot be mirrored
    for eid in added:
        ent = sketch.entities[eid]
        if isinstance(ent, Point):
            if eid not in used:
                ids.append(eid)
        elif isinstance(ent, MIRRORABLE):
            ids.append(eid)
        else:
            skipped = True
            left_out.update(entity_points(ent))
    if left_out:
        # Helpers tied to a skipped curve (an ellipse's construction axes, TR114) are
        # skipped with it, so no half of a shape is mirrored.
        tied: set[str] = set()
        for rel in sketch.relations:
            if any(e in left_out for e in rel.entities):
                tied.update(rel.entities)
        tied |= {
            i
            for i in ids
            if not isinstance(sketch.entities[i], Point)
            and any(p in tied for p in entity_points(sketch.entities[i]))
        }
        ids = [i for i in ids if i not in tied]
    return ids, skipped


def mirror_new(edit: SketchEdit, before: set[str]) -> list[str]:
    """Mirror what was added since ``before`` about the sketch's mirror line.

    Returns the new copies. Leaves a status note on the edit when something could
    not be mirrored. The caller checkpoints.
    """
    axis = axis_of(edit)
    if axis is None:
        return []
    ids, skipped = new_shape(edit.sketch, before)
    ids = [i for i in ids if i != axis]
    if skipped:
        edit.note = tool_text.MIRROR_SKIPPED
    if not ids:
        return []
    report = mirror(edit.sketch, ids, axis, copy=True)
    return list(report.entities) if report is not None else []
