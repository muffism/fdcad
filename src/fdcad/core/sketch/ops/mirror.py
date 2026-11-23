"""Mirror (PHASE2_SPEC P2.8 item 4).

Copies curves to the other side of a mirror line. Each pair of mirrored points
gets a Symmetric relation about the line, so the copy follows the original.
"""

from __future__ import annotations

from fdcad.core.sketch.model import Arc, Circle, Line, Point, Sketch
from fdcad.core.sketch.ops.geom import Vec
from fdcad.core.sketch.ops.pieces import Report, delete_curves

#: Relations that still hold after a mirror when all their items are mirrored.
_KEPT_BY_MIRROR = frozenset(
    {
        "coincident",
        "collinear",
        "concentric",
        "coradial",
        "equal",
        "intersection",
        "midpoint",
        "parallel",
        "perpendicular",
        "tangent",
    }
)


def reflect(p: Vec, a: Vec, b: Vec) -> Vec:
    """``p`` mirrored about the line through ``a`` and ``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2
    fx, fy = a[0] + t * dx, a[1] + t * dy
    return 2 * fx - p[0], 2 * fy - p[1]


def mirror(sketch: Sketch, ids: list[str], axis: str, copy: bool = True) -> Report | None:
    """Mirror the curves and points ``ids`` about line ``axis``.

    With ``copy`` off the originals are deleted, so the mirrored curves replace
    them (without Symmetric relations, since nothing is left to mirror). Returns
    None when nothing can be mirrored.
    """
    line = sketch.entities.get(axis)
    if not isinstance(line, Line):
        return None
    a, b = sketch.xy(line.p1), sketch.xy(line.p2)
    if a == b:
        return None
    picked = [i for i in dict.fromkeys(ids) if i != axis and i in sketch.entities]
    if not picked:
        return None
    mapped: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []

    def twin(pid: str) -> str:
        if pid in mapped:
            return mapped[pid]
        p = sketch.point(pid)
        q = reflect((p.x, p.y), a, b)
        if abs(q[0] - p.x) < 1e-9 and abs(q[1] - p.y) < 1e-9:
            mapped[pid] = pid  # on the mirror line: the copy shares the point
            return pid
        new = sketch.add_point(q[0], q[1], p.construction)
        mapped[pid] = new
        pairs.append((pid, new))
        return new

    made: list[str] = []
    #: The picked curves, in the order of ``made``.
    picked_curves: list[str] = []
    rounds: list[tuple[str, str, str]] = []
    #: Arcs: their ends are mirrored and the radius kept with Equal; mirroring the
    #: centre as well would be one relation too many (D273).
    arcs: list[tuple[str, str, str]] = []
    for eid in picked:
        ent = sketch.entities[eid]
        if isinstance(ent, Point):
            twin(eid)
        elif isinstance(ent, Line):
            nid = sketch.new_id()
            sketch.entities[nid] = Line(nid, twin(ent.p1), twin(ent.p2), ent.construction)
            made.append(nid)
            picked_curves.append(eid)
        elif isinstance(ent, Circle):
            nid = sketch.new_id()
            sketch.entities[nid] = Circle(nid, twin(ent.center), ent.radius, ent.construction)
            made.append(nid)
            picked_curves.append(eid)
            rounds.append((eid, nid, ent.center))
        elif isinstance(ent, Arc):
            nid = sketch.new_id()
            # A mirror turns the arc the other way round.
            sketch.entities[nid] = Arc(
                nid, twin(ent.center), twin(ent.start), twin(ent.end), not ent.ccw, ent.construction
            )
            made.append(nid)
            picked_curves.append(eid)
            arcs.append((eid, nid, ent.center))
    report = Report()
    if copy:
        centres = {centre for _c, _n, centre in rounds + arcs}
        for p, q in pairs:
            if p in centres:
                continue
            sketch.relate("symmetric", p, q, axis)
        for c, n, _centre in rounds:
            sketch.relate("symmetric", c, n, axis)
        for c, n, _centre in arcs:
            sketch.relate("equal", c, n)
    else:
        # The copies take over the relations among the picks that a mirror keeps
        # true, so a replaced shape stays joined; the rest go with the originals.
        twins = {**mapped, **dict(zip(picked_curves, made, strict=True))}
        for rel in sketch.relations:
            if rel.type in _KEPT_BY_MIRROR and all(e in twins for e in rel.entities):
                rel.entities = [twins[e] for e in rel.entities]
        delete_curves(sketch, set(picked), report)
    report.entities = made
    return report
