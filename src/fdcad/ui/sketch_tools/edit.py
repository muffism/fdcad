"""The sketch being edited: changes, local undo, solving and selection rules.

A sketch is edited as a copy. Every change is a step on the sketch's own undo
list while it is open; OK writes the whole sketch back to the document as one
undoable command (CLAUDE.md rule 3). Pure Python, no Qt.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from fdcad.core.document.model import Feature, Param
from fdcad.core.sketch.freeform import sample
from fdcad.core.sketch.links import (
    LinkUpdate,
    ModelCircle,
    ModelLine,
    SourceKey,
    apply_links,
    source_data,
)
from fdcad.core.sketch.model import (
    DIMENSION_TYPES,
    MEASURE_TO,
    Arc,
    Circle,
    Curve,
    Dimension,
    Line,
    Point,
    Relation,
    Sketch,
    Spline,
    entity_points,
    sketch_from_data,
    sketch_to_data,
)
from fdcad.core.sketch.solver import (
    SketchSolveError,
    SketchStatus,
    SolveResult,
    defined_entities,
    drag,
    measure,
    solve,
)
from fdcad.core.sketch.topology import SketchIssue, check
from fdcad.core.units import Kind
from fdcad.ui.sketch_tools.geometry import Vec, arc_angles, dist
from fdcad.ui.sketch_tools.inference import Snap

#: The warning when a change flips geometry to another solution (TR338, D1302).
JUMP_NOTE = (
    "The sketch jumped to another solution at {items}. "
    "Use Undo to go back, or right click and use Keep This Side."
)
#: A change refused because it flipped a locked item (TR338, D1302).
LOCK_NOTE = (
    "Change undone: it would flip {items}, which Keep This Side holds. "
    "Use Remove Side Locks in the right click menu to allow it."
)

#: Automatic relations removed because a later one conflicted (TR362, D1310).
WEAK_NOTE = "Replaced the automatic relation ({items}) with yours. Use Undo to get it back."

#: Sketch data keys that ``sketch_to_data`` writes.
_SKETCH_KEYS = (
    "next_entity",
    "entities",
    "relations",
    "dimensions",
    "pictures",
    "texts",
    "layers",
    "layer_of",
    "keep_sides",
)


def new_sketch_data() -> dict[str, object]:
    """Data for a new sketch: a fixed construction point at the origin."""
    sketch = Sketch()
    origin = sketch.add_point(0.0, 0.0, construction=True)
    sketch.relate("fixed", origin)
    return sketch_to_data(sketch)


def dimension_kind(dim_type: str) -> Kind:
    """Angle dimensions take angles; every other dimension takes a length."""
    return Kind.ANGLE if dim_type == "angle" else Kind.LENGTH


@dataclass
class Status:
    """What the status bar and colours show after a solve."""

    state: SketchStatus
    dof: int
    message: str
    conflicting: set[str]
    issues: list[SketchIssue]
    #: What the status bar shows (TR38, D1301): under, full or over, or dangling,
    #: invalid or no_solution (``core.sketch.problems.STATES``).
    display: str = ""


class SketchEdit:
    """A sketch open for editing."""

    def __init__(self, feature: Feature) -> None:
        self.feature = copy.deepcopy(feature)
        self.sketch = sketch_from_data(feature.data)
        self._undo: list[dict[str, object]] = []
        self._redo: list[dict[str, object]] = []
        self.result: SolveResult | None = None
        self.defined: set[str] = set()
        self.error = ""
        #: Relations (``r<index>``) and dimensions that name deleted items (TR38).
        self.dangling: list[str] = []
        #: Items the last change flipped to another solution, with the side each had
        #: before (TR338, D1302); cleared by the next change, undo or redo.
        self.jump_sides: dict[str, int] = {}
        #: A jump warning not shown yet (read once with :meth:`take_jump_note`).
        self.jump_note = ""
        #: Locked items (Keep This Side) on the other side after the last solve.
        self.broken_locks: list[str] = []
        #: Add relations where clicks land on snaps (T1.3.3). Shape joins always stay.
        self.auto_relations = True
        #: Kinds of automatic relation switched off in the preferences (TR231, D1309).
        self.auto_off: set[str] = set()
        #: Dimensions whose value was changed since the sketch opened, and whether a
        #: drag holds their geometry still (TR238, D1706).
        self.changed_dimensions: set[str] = set()
        self.lock_changed = False
        #: TR112 (D1716): drags move points with no solve (item 1), and drags give the
        #: dragged geometry's driving dimensions their new sizes (item 2, a preference).
        self.free_drag = False
        self.drag_changes_dimensions = False
        #: Tab while drawing: the next click adds no automatic relations (TR231).
        self.skip_next = False
        #: Embedded image blocks the sketch pictures use, by block id (P2.9). Blocks
        #: added while the sketch is open go into the document on OK.
        self.blocks: dict[str, dict[str, object]] = {}
        #: Dynamic mirror (P2.8 item 4, D514): new shapes are mirrored about this line.
        #: View state of the open sketch, never saved.
        self.mirror_axis: str | None = None
        #: A status note left by a change (read once with :meth:`take_note`).
        self.note = ""
        self.refresh()

    def take_note(self) -> str:
        """The status note left by the last change, once."""
        note, self.note = self.note, ""
        return note

    # Undo -------------------------------------------------------------------------

    def checkpoint(self) -> None:
        """Remember the sketch before a change."""
        self._undo.append(copy.deepcopy(sketch_to_data(self.sketch)))
        self._redo.clear()
        self.jump_sides = {}

    def discard_checkpoint(self) -> None:
        """Forget the last checkpoint (the change was abandoned)."""
        if self._undo:
            self.sketch = sketch_from_data(self._undo.pop())

    def drop_if_unchanged(self) -> bool:
        """Forget the last checkpoint when nothing changed since (a drag that could not
        move fully defined geometry). True when it was dropped."""
        if not self._undo or not same_sketch(sketch_from_data(self._undo[-1]), self.sketch):
            return False
        self._undo.pop()
        return True

    @property
    def undo_depth(self) -> int:
        """How many changes can be undone; pass it to :meth:`rollback`."""
        return len(self._undo)

    def rollback(self, depth: int) -> None:
        """Drop every change made since the undo stack was ``depth`` deep."""
        while len(self._undo) > depth:
            self.discard_checkpoint()
        self.refresh()

    @property
    def can_undo(self) -> bool:
        """True when there is a change to undo."""
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        """True when there is a change to redo."""
        return bool(self._redo)

    def undo(self) -> None:
        """Undo the last change inside the sketch."""
        if self._undo:
            self._redo.append(sketch_to_data(self.sketch))
            self.sketch = sketch_from_data(self._undo.pop())
            self.refresh()
            self.jump_sides = {}

    def redo(self) -> None:
        """Redo the last undone change."""
        if self._redo:
            self._undo.append(sketch_to_data(self.sketch))
            self.sketch = sketch_from_data(self._redo.pop())
            self.refresh()
            self.jump_sides = {}

    @property
    def changed(self) -> bool:
        """True when the sketch differs from the document's copy."""
        return bool(self._undo)

    # Solving ------------------------------------------------------------------------

    def refresh(self, full: bool = True) -> None:
        """Solve and update status. ``full`` also works out which entities are defined."""
        from fdcad.core.sketch.problems import solve_around
        from fdcad.core.sketch.sides import broken_locks, signature

        before = signature(self.sketch)
        try:
            # Dangling items are left out so the rest still solves (TR38, D1301).
            self.result, self.dangling = solve_around(self.sketch)
            self.error = ""
        except SketchSolveError as exc:
            self.result = None
            self.dangling = []
            self.error = str(exc)
        if self.result is not None and self.result.solved:
            follow_references(self.sketch, self.result.measured)
            after = signature(self.sketch)
            self._note_jumps(before, after)
            self.broken_locks = broken_locks(self.sketch, after)
        else:
            self.broken_locks = []
        if full:
            over = self.result is not None and self.result.status is SketchStatus.OVER
            self.defined = set() if over or self.result is None else defined_entities(self.sketch)

    def status(self) -> Status:
        """Current sketch status, conflicting entities and sketch check issues."""
        from fdcad.core.sketch.problems import invalid_items, state_of

        conflicting: set[str] = set()
        if self.result is None:
            return Status(SketchStatus.OVER, 0, self.error, conflicting, [], "over")
        for ref in [*self.result.conflicting, *self.result.redundant]:
            if ref.kind == "relation" and isinstance(ref.key, int):
                if ref.key < len(self.sketch.relations):
                    conflicting.update(self.sketch.relations[ref.key].entities)
            else:
                dim = next((d for d in self.sketch.dimensions if d.id == ref.key), None)
                if dim is not None:
                    conflicting.update(dim.entities)
                    conflicting.add(dim.id)
        issues = check(self.sketch)
        invalid = [eid for eid, _reason in invalid_items(self.sketch)]
        display = state_of(self.result, self.dangling, invalid)
        message = self.result.message
        if display == "dangling":
            message = f"{len(self.dangling)} relations or dimensions name deleted items."
        return Status(self.result.status, self.result.dof, message, conflicting, issues, display)

    def conflicting_items(self) -> tuple[set[int], set[str]]:
        """Indexes of conflicting relations and ids of conflicting dimensions."""
        rels: set[int] = set()
        dims: set[str] = set()
        if self.result is not None:
            for ref in [*self.result.conflicting, *self.result.redundant]:
                if ref.kind == "relation" and isinstance(ref.key, int):
                    rels.add(ref.key)
                else:
                    dims.add(str(ref.key))
        return rels, dims

    # Building -------------------------------------------------------------------------

    def place_point(self, snap: Snap, construction: bool = False) -> str:
        """Add a point at a snap, with the snap's relations."""
        pid = self.sketch.add_point(snap.x, snap.y, construction)
        self.attach(pid, snap)
        return pid

    def attach(self, pid: str, snap: Snap, keep: bool = False) -> None:
        """Add a snap's relations to point ``pid`` (skipping ones that name it twice).

        With automatic relations off nothing is added, unless ``keep`` marks a join
        that is part of the shape, such as the next segment of a line chain.
        A snap to a part's circle centre ties the point to a fixed construction
        copy of that centre (D116 item 3).
        """
        if not (self.auto_relations or keep):
            return
        if not keep and self.skip_next:  # Tab while drawing (TR231)
            return
        off = set() if keep else self.auto_off
        if snap.model is not None and "coincident" not in off:
            ref = self.reference_point(snap.model, snap.model_source)
            if ref != pid:
                self.sketch.relate("coincident", pid, ref)
        if snap.model_relation in off:
            pass
        elif isinstance(snap.model_curve, ModelLine):
            lid = self.reference_line(
                snap.model_curve.a, snap.model_curve.b, snap.model_curve.source
            )
            self.sketch.relate(snap.model_relation, pid, lid)
        elif isinstance(snap.model_curve, ModelCircle):
            c = snap.model_curve
            self.sketch.relate(
                "coincident", pid, self.reference_circle(c.centre, c.radius, c.source)
            )
        for rtype, others in snap.relations:
            if pid in others or not all(o in self.sketch.entities for o in others):
                continue
            if rtype in off:
                continue  # that kind is switched off in the preferences (TR231)
            rel = self.sketch.relate(rtype, pid, *others)
            rel.weak = not keep  # TR362: an automatic relation gives way to the user's

    def add_line(
        self, start: Snap, end: Snap, construction: bool = False, keep_start: bool = False
    ) -> str:
        """Add a line between two snaps. Returns the line id.

        ``keep_start`` keeps the start's join even with automatic relations off.
        """
        lid = self.sketch.add_line(start.x, start.y, end.x, end.y, construction)
        line = self.line(lid)
        self.attach(line.p1, start, keep_start)
        self.attach(line.p2, end)
        return lid

    def add_circle(self, center: Snap, radius: float, construction: bool = False) -> str:
        """Add a circle around a snapped center."""
        cid = self.sketch.add_circle(center.x, center.y, radius, construction)
        circle = self.sketch.entities[cid]
        assert isinstance(circle, Circle)
        other = round_of_centre(self.sketch, center.target) if center.target else None
        if center.kind == "center" and other is not None and other != cid:
            # Drawn from another circle's or arc's centre: Concentric (T1.3.1).
            self.sketch.relate("concentric", cid, other)
        else:
            self.attach(circle.center, center)
        return cid

    def add_arc(
        self,
        center: Vec,
        start: Snap,
        end: Snap,
        ccw: bool,
        construction: bool = False,
        center_snap: Snap | None = None,
        keep_start: bool = False,
    ) -> str:
        """Add an arc from ``start`` to ``end`` around ``center``, in the given turn direction."""
        r = dist(center, start.xy)
        a0 = math.atan2(start.y - center[1], start.x - center[0])
        a1 = math.atan2(end.y - center[1], end.x - center[0])
        if not ccw:
            a0, a1 = a1, a0
        aid = self.sketch.add_arc(center[0], center[1], r, a0, a1, construction)
        arc = self.sketch.entities[aid]
        assert isinstance(arc, Arc)
        # add_arc places the end on the circle; put it where the user clicked.
        first, second = (arc.start, arc.end) if ccw else (arc.end, arc.start)
        p1, p2 = self.sketch.point(first), self.sketch.point(second)
        p1.x, p1.y = start.x, start.y
        p2.x, p2.y = end.x, end.y
        self.attach(first, start, keep_start)
        self.attach(second, end)
        if center_snap is not None:
            self.attach(arc.center, center_snap)
        return aid

    def _fixed(self) -> set[str]:
        return {e for r in self.sketch.relations if r.type == "fixed" for e in r.entities}

    @staticmethod
    def _remember(entity: Point | Line | Circle, source: SourceKey | None) -> None:
        """Note where a copy came from, so a later part change can be found (D250)."""
        if source is not None and entity.source is None:
            entity.source = source_data(source)

    def reference_line(self, a: Vec, b: Vec, source: SourceKey | None = None) -> str:
        """A fixed construction line on a part edge, so dimensions can measure to it.

        Reuses one already on that edge. The caller checkpoints. The line is a copy:
        it does not move when the part changes; with ``source`` the sketch warns
        then and offers to update it (D113, D116 item 3, D250).
        """
        sk = self.sketch
        fixed = self._fixed()
        for e in sk.entities.values():
            if isinstance(e, Line) and e.construction and e.id in fixed:
                ends = {sk.xy(e.p1), sk.xy(e.p2)}
                if all(min(dist(q, p) for q in ends) < 1e-6 for p in (a, b)):
                    self._remember(e, source)
                    return e.id
        lid = sk.add_line(a[0], a[1], b[0], b[1], True)
        sk.relate("fixed", lid)
        line = sk.entities[lid]
        assert isinstance(line, Line)
        self._remember(line, source)
        return lid

    def reference_circle(self, centre: Vec, radius: float, source: SourceKey | None = None) -> str:
        """A fixed construction circle on a round part edge (D250). Reuses one already there."""
        sk = self.sketch
        fixed = self._fixed()
        for e in sk.entities.values():
            if not (isinstance(e, Circle) and e.construction and e.id in fixed):
                continue
            if dist(sk.xy(e.center), centre) < 1e-6 and abs(e.radius - radius) < 1e-6:
                self._remember(e, source)
                return e.id
        cid = sk.add_circle(centre[0], centre[1], radius, True)
        sk.relate("fixed", cid)
        circle = sk.entities[cid]
        assert isinstance(circle, Circle)
        self._remember(circle, source)
        return cid

    def reference_point(self, at: Vec, source: SourceKey | None = None) -> str:
        """A fixed construction point on a part point (D113, D116 item 3, D250).

        Reuses a fixed construction point already there (the origin counts).
        The caller checkpoints. The point is a copy: it does not move when the
        part changes; with ``source`` the sketch warns then and offers to update it.
        The sketch origin never gets a source: it is the sketch's own.
        """
        sk = self.sketch
        fixed = self._fixed()
        for e in sk.entities.values():
            close = isinstance(e, Point) and dist((e.x, e.y), at) < 1e-6
            if close and isinstance(e, Point) and e.construction and e.id in fixed:
                if not _is_origin(sk, e.id):
                    self._remember(e, source)
                return e.id
        pid = sk.add_point(at[0], at[1], True)
        sk.relate("fixed", pid)
        self._remember(sk.point(pid), source)
        return pid

    def link_updates(self, updates: list[LinkUpdate]) -> int:
        """Move out of date part copies onto the part, as one undoable step (D250).

        Only called from the Update button: the user confirms (CLAUDE.md rule 12).
        """
        if not any(not u.lost and u.entity in self.sketch.entities for u in updates):
            return 0
        self.checkpoint()
        moved = apply_links(self.sketch, updates)
        self.refresh()
        return moved

    def line(self, eid: str) -> Line:
        """Line ``eid``."""
        ent = self.sketch.entities[eid]
        assert isinstance(ent, Line)
        return ent

    def relate(self, rtype: str, ids: list[str]) -> None:
        """Add a relation (the caller checkpoints). Merge joins two points into one
        (TR40, D822): the first picked stays, unless only the second came from part
        geometry."""
        if rtype == "merge":
            from fdcad.core.sketch.model import Point
            from fdcad.core.sketch.ops.merge import merge_points

            keep, drop = ids[0], ids[1]
            a, b = self.sketch.entities.get(keep), self.sketch.entities.get(drop)
            if isinstance(a, Point) and isinstance(b, Point) and b.source and not a.source:
                keep, drop = drop, keep
            merge_points(self.sketch, keep, drop)
            return
        if rtype in GROUP_TYPES and join_group(self.sketch, rtype, ids):
            return  # TR108 (D1303): joined an existing group of the same relation
        rel = self.sketch.relate(rtype, *ids)
        if rtype in ("length_ratio", "length_difference"):  # TR226: hold today's value
            from fdcad.core.sketch.solver import length_value

            rel.value = length_value(self.sketch, rtype, ids)

    def relate_value(self, rtype: str, ids: list[str], value: float) -> None:
        """Add a relation that carries a value: Length Ratio or Difference (TR226)."""
        self.sketch.relate(rtype, *ids).value = value

    def auto_relate(self, rtype: str, ids: list[str]) -> None:
        """Add an automatic relation, unless automatic relations, or that kind of them
        (TR231), are off, or Tab skipped them for this click."""
        if self.auto_relations and rtype not in self.auto_off and not self.skip_next:
            before = len(self.sketch.relations)
            self.relate(rtype, ids)
            for rel in self.sketch.relations[before:]:
                rel.weak = True  # TR362 (D1310)

    def replace_weak(self) -> str:
        """Remove automatic (weak) relations that conflict with the others and solve
        again (TR362, D1310). Returns a note naming what was removed, or ""."""
        result = self.result
        if result is None or not result.conflicting:
            return ""
        weak = sorted(
            {
                int(r.key)
                for r in result.conflicting
                if r.kind == "relation"
                and isinstance(r.key, int)
                and r.key < len(self.sketch.relations)
                and self.sketch.relations[r.key].weak
            },
            reverse=True,
        )
        if not weak:
            return ""
        names = []
        for index in weak:
            rel = self.sketch.relations.pop(index)
            names.append(f"{rel.type.replace('_', ' ')} on {', '.join(rel.entities)}")
        self.refresh(full=False)
        return WEAK_NOTE.format(items="; ".join(names))

    def make_strong(self, indexes: list[int]) -> bool:
        """Keep Relation: automatic relations become ordinary ones (the caller
        checkpoints). False when none of them was automatic."""
        found = False
        for i in indexes:
            if 0 <= i < len(self.sketch.relations) and self.sketch.relations[i].weak:
                self.sketch.relations[i].weak = False
                found = True
        return found

    def add_dimension(
        self,
        dtype: str,
        ids: list[str],
        param: Param | None,
        place: Vec | None = None,
        keep_label: bool = False,
    ) -> Dimension:
        """Add a driving dimension. With no value it keeps the current size.

        ``place`` is where the text goes: for an angle it picks which angle (T4.1);
        for a doubled distance the ids are put in [line, centerline] order. With
        ``keep_label`` the text stays at ``place`` (T4.2.1, stored, D150).
        """
        if dtype not in DIMENSION_TYPES:
            raise ValueError(f"Unknown dimension type '{dtype}'.")
        dim = Dimension(f"d{self.sketch.next_dimension}", dtype, [], Param("0", 0.0))
        dim = setup_dimension(self.sketch, dim, ids, place)
        if param is not None:
            dim.param = param
        self.sketch.next_dimension += 1
        self.sketch.dimensions.append(dim)
        if keep_label and place is not None:
            self.set_label(dim.id, place)
        return dim

    def dimension(self, did: str) -> Dimension | None:
        """Dimension ``did``, or None."""
        return next((d for d in self.sketch.dimensions if d.id == did), None)

    def set_label(self, did: str, place: Vec | None) -> None:
        """Put the text of dimension ``did`` at ``place`` (sketch mm), or None for
        automatic placement (T4.4.2). The caller checkpoints."""
        dim = self.dimension(did)
        if dim is None:
            return
        if place is None:
            dim.label = None
            return
        anchor = label_anchor(self.sketch, dim)
        dim.label = (round(place[0] - anchor[0], 6), round(place[1] - anchor[1], 6))
        if dim.display and dim.display.get("style") == "ordinate":
            from fdcad.ui.sketch_tools.datum_dimensions import move_group

            move_group(self, did, place)  # TR45: the group's texts move together

    def over_defines(self, did: str) -> bool:
        """True when dimension ``did`` leaves the sketch over defined or unsolvable and
        making it a reference dimension clears that (T1.4.4)."""
        dim = self.dimension(did)
        if dim is None or not dim.driving or not self._over():
            return False
        dim.driving = False
        clears = not self._over()
        dim.driving = True
        self.refresh(full=False)
        return clears

    def make_reference_if_over(self, did: str) -> bool:
        """Turn dimension ``did`` into a reference one when it over defines the sketch.

        Returns True when it did (T11.5 "Always make reference"). A dimension that is
        not the cause stays driving.
        """
        if not self.over_defines(did):
            return False
        self.set_driving(did, False)
        return True

    def set_driving(self, did: str, driving: bool) -> bool:
        """Make dimension ``did`` driving or a reference (T4.2.5). The caller checkpoints.

        A reference dimension takes the measured value. Making one driving keeps the
        geometry as it is; it is refused (returns False) when that would over define
        the sketch, since the user would otherwise get a red sketch for a toggle.
        """
        dim = self.dimension(did)
        if dim is None:
            return False
        if dim.driving == driving:
            return True
        dim.driving = driving
        if not driving:
            self.refresh(full=False)
            return True
        if self._over():
            dim.driving = False
            self.refresh(full=False)
            return False
        return True

    def _over(self) -> bool:
        self.refresh(full=False)
        return self.result is None or self.result.status is SketchStatus.OVER

    def set_measure(self, did: str, rid: str, side: str) -> None:
        """Measure a distance to the ``center``, ``nearest`` or ``farthest`` side of a
        circle or arc (T4.3.2). The value becomes the current size; nothing moves."""
        dim = next((d for d in self.sketch.dimensions if d.id == did), None)
        ent = self.sketch.entities.get(rid)
        if dim is None or not isinstance(ent, Circle | Arc):
            return
        dim.entities = [rid if e in (rid, ent.center) else e for e in dim.entities]
        dim.measure_to.pop(rid, None)
        if side == "center":
            dim.entities = [ent.center if e == rid else e for e in dim.entities]
        else:
            apply_sides(self.sketch, dim, {rid: side})
        value = measure(self.sketch, dim)
        dim.param = Param(f"{value:.6g}mm", value)

    def set_dimension(self, did: str, param: Param, keep_proportions: bool = False) -> None:
        """Change a dimension's value. With ``keep_proportions`` the first length
        dimension of an unsized sketch scales the whole sketch (TR119, D938)."""
        self.changed_dimensions.add(did)  # TR238 (D1706)
        for dim in self.sketch.dimensions:
            if dim.id == did:
                if keep_proportions:
                    from fdcad.core.sketch.proportions import set_keeping_proportions

                    set_keeping_proportions(self.sketch, dim, param, measure(self.sketch, dim))
                else:
                    dim.param = param
                from fdcad.core.sketch.links_values import follow

                follow(self.sketch, dim)  # TR193: linked dimensions take the value too

    def delete(self, ids: set[str]) -> None:
        """Delete entities, relations and dimensions.

        ``ids`` holds entity ids, dimension ids and ``r<index>`` for relations.
        Curves take their own points with them unless another curve uses them;
        deleting a point deletes the curves that use it. The sketch origin and its
        Fix stay: every sketch keeps them.
        """
        sk = self.sketch
        rel_index = {int(i[1:]) for i in ids if i.startswith("r") and i[1:].isdigit()}
        rel_index = {
            i for i in rel_index if i < len(sk.relations) and not _origin_fix(sk, sk.relations[i])
        }
        ents = {i for i in ids if i in sk.entities and not _is_origin(sk, i)}
        for eid in list(ents):
            ent = sk.entities[eid]
            if isinstance(ent, Point):
                ents |= {c.id for c in sk.curves(True) if eid in _points_of(c)}
        users: dict[str, int] = {}
        for c in sk.curves(True):
            if c.id not in ents:
                for p in _points_of(c):
                    users[p] = users.get(p, 0) + 1
        for eid in list(ents):
            ent = sk.entities[eid]
            if not isinstance(ent, Point):
                ents |= {
                    p for p in _points_of(ent) if users.get(p, 0) == 0 and not _is_origin(sk, p)
                }
        for eid in ents:
            sk.entities.pop(eid, None)
        sk.relations = [
            r
            for i, r in enumerate(sk.relations)
            if i not in rel_index and not set(r.entities) & ents
        ]
        sk.dimensions = [d for d in sk.dimensions if d.id not in ids and not set(d.entities) & ents]
        if sk.blocks:  # TR34: a block copy whose curves all went goes too
            from fdcad.core.sketch.blocks import prune

            prune(sk)

    def toggle_off(self, ids: list[str]) -> bool:
        """Switch relations (``r<index>``) and dimensions (``d<n>``) off, or on again when
        all of them are off (TR109, D829). The caller checkpoints. Returns the new state."""
        items: list[Relation | Dimension] = []
        for item in ids:
            if item.startswith("r") and item[1:].isdigit():
                index = int(item[1:])
                if index < len(self.sketch.relations):
                    items.append(self.sketch.relations[index])
            else:
                dim = self.dimension(item)
                if dim is not None:
                    items.append(dim)
        off = not all(i.off for i in items)
        for i in items:
            i.off = off
        return off

    def toggle_construction(self, ids: set[str]) -> None:
        """Switch curves (and their points) between normal and construction."""
        curves = [e for e in self.sketch.curves(True) if e.id in ids]
        if not curves:
            return
        make = not all(c.construction for c in curves)
        for c in curves:
            c.construction = make
            for p in _points_of(c):
                self.sketch.point(p).construction = make

    # Typed parameters (T7.3, T2.1.4, T2.4.3, T14.1.3) ------------------------------------
    # Each goes through the solver, never by moving points directly. They return False
    # when relations or dimensions hold the value; the caller then rolls back.

    def set_point(self, pid: str, x: float, y: float) -> bool:
        """Move point ``pid`` to (x, y), keeping every relation. The caller checkpoints."""
        if not isinstance(self.sketch.entities.get(pid), Point):
            return False
        self.drag_to({pid: (x, y)})
        self.refresh(full=False)
        return self._solved() and dist(self.sketch.xy(pid), (x, y)) < 1e-6

    def set_length(self, lid: str, length: float) -> bool:
        """Give line ``lid`` a new length (T2.1.4)."""
        if length <= 0 or not isinstance(self.sketch.entities.get(lid), Line):
            return False
        return self._solve_with("distance", [lid], length)

    def set_angle(self, lid: str, angle: float) -> bool:
        """Turn line ``lid`` about its start to ``angle`` (radians from sketch X, T2.1.4)."""
        line = self.sketch.entities.get(lid)
        if not isinstance(line, Line):
            return False
        (x1, y1), (x2, y2) = self.sketch.xy(line.p1), self.sketch.xy(line.p2)
        length = math.hypot(x2 - x1, y2 - y1)
        target = (x1 + length * math.cos(angle), y1 + length * math.sin(angle))
        self.drag_to({line.p1: (x1, y1), line.p2: target})
        self.refresh(full=False)
        return self._solved() and dist(self.sketch.xy(line.p2), target) < 1e-6

    def set_radius(self, rid: str, radius: float) -> bool:
        """Give a circle or arc a new radius (T2.4.3)."""
        if radius <= 0 or not isinstance(self.sketch.entities.get(rid), Circle | Arc):
            return False
        return self._solve_with("radius", [rid], radius)

    def _solve_with(self, dtype: str, ids: list[str], value: float) -> bool:
        """Solve with a passing dimension of ``value`` on ``ids``, then drop it.

        The solver moves the geometry the least it can while every relation holds.
        False when the sketch cannot take the value (something else sets it).
        """
        sk = self.sketch
        number = sk.next_dimension
        dim = sk.dimension(dtype, ids, Param(f"{value:.6g}", value))
        try:
            result = solve(sk)
        except SketchSolveError:
            result = None
        sk.dimensions.remove(dim)
        sk.next_dimension = number
        ok = (
            result is not None
            and result.solved
            and not result.conflicting
            and not result.redundant
            and abs(measure(sk, dim) - value) < 1e-6
        )
        self.refresh(full=False)
        return ok and self._solved()

    def _solved(self) -> bool:
        return self.result is not None and self.result.solved

    def drag_to(self, targets: dict[str, Vec]) -> bool:
        """Drag points toward targets, keeping relations. No full refresh. A corner or
        arc away from the dragged points that flips side is a jump (TR338)."""
        from fdcad.core.sketch import free_drag as fd
        from fdcad.core.sketch.sides import signature

        if self.free_drag:  # TR112 item 1: no solve
            return fd.free_move(self.sketch, targets)
        before = signature(self.sketch)
        rewrite = (
            fd.dragged_dimensions(self.sketch, set(targets)) if self.drag_changes_dimensions else []
        )
        for dim in self.sketch.dimensions:
            if dim.id in rewrite:
                dim.driving = False  # TR112 item 2: the drag decides these sizes
        try:
            ok = drag(self.sketch, targets, self.held_points())
        finally:
            for dim in self.sketch.dimensions:
                if dim.id in rewrite:
                    dim.driving = True
        if rewrite:
            fd.rewrite_dimensions(self.sketch, rewrite)
        moved = {c.id for c in self.sketch.curves(True) if set(_points_of(c)) & set(targets)}
        self._note_jumps(before, signature(self.sketch), moved)
        return ok

    # Solution jumps (TR338, D1302) ------------------------------------------------------

    def _note_jumps(
        self, before: dict[str, int], after: dict[str, int], skip: set[str] | None = None
    ) -> None:
        """Remember items that flipped side, and leave a warning for the status bar."""
        from fdcad.core.sketch.sides import describe, flipped

        jumps = [k for k in flipped(before, after, skip or set()) if k not in self.jump_sides]
        if not jumps:
            return
        for key in jumps:
            self.jump_sides[key] = before[key]
        self.jump_note = JUMP_NOTE.format(items=describe(list(self.jump_sides)))

    def take_jump_note(self) -> str:
        """The jump warning not yet shown, once."""
        note, self.jump_note = self.jump_note, ""
        return note

    def keep_this_side(self) -> bool:
        """Undo the change that jumped, and lock the items that flipped on the side they
        had before it. The lock is its own undo step. False when nothing jumped."""
        sides = dict(self.jump_sides)
        if not sides or not self._undo:
            return False
        self.undo()
        self.checkpoint()
        self.sketch.keep_sides.update(sides)
        self.refresh()
        return True

    def remove_side_locks(self) -> bool:
        """Remove every Keep This Side lock (one undo step). False when there are none."""
        if not self.sketch.keep_sides:
            return False
        self.checkpoint()
        self.sketch.keep_sides.clear()
        self.refresh()
        return True

    def refuse_broken_locks(self) -> bool:
        """Undo the last change when it flipped a locked item. True when it did."""
        from fdcad.core.sketch.sides import describe

        broken = list(self.broken_locks)
        if not broken or not self._undo:
            return False
        self.discard_checkpoint()
        self.refresh()
        self.jump_sides = {}
        self.jump_note = LOCK_NOTE.format(items=describe(broken))
        return True

    def held_points(self) -> set[str]:
        """Points a drag keeps still: with Lock changed dimensions while dragging on,
        those of the dimensions changed since the sketch opened (TR238, D1706)."""
        if not self.lock_changed:
            return set()
        from fdcad.core.sketch.model import entity_points

        out: set[str] = set()
        for dim in self.sketch.dimensions:
            if dim.id not in self.changed_dimensions:
                continue
            for eid in dim.entities:
                ent = self.sketch.entities.get(eid)
                if ent is not None:
                    out.update(entity_points(ent))
        return out

    def drag_radius(self, cid: str, radius: float) -> bool:
        """Drag a circle's edge. A dimension or relation that sets the radius wins."""
        circle = self.sketch.entities[cid]
        if not isinstance(circle, Circle) or radius <= 0:
            return False
        before = circle.radius
        circle.radius = radius
        try:
            result = solve(self.sketch)
        except SketchSolveError:
            result = None
        if result is None or not result.solved:
            circle.radius = before
            return False
        return True

    # Writing back ---------------------------------------------------------------------

    def to_feature(self) -> Feature:
        """The edited sketch feature."""
        feature = copy.deepcopy(self.feature)
        for key in _SKETCH_KEYS:
            feature.data.pop(key, None)
        feature.data.update(sketch_to_data(self.sketch))
        return feature


def same_sketch(a: Sketch, b: Sketch, tol: float = 1e-9) -> bool:
    """True when two sketches hold the same items, with points within ``tol`` mm."""
    if a.entities.keys() != b.entities.keys():
        return False
    for eid, ea in a.entities.items():
        eb = b.entities[eid]
        if isinstance(ea, Point) and isinstance(eb, Point):
            if abs(ea.x - eb.x) > tol or abs(ea.y - eb.y) > tol:
                return False
            if (ea.construction, ea.source) != (eb.construction, eb.source):
                return False
        elif ea != eb:
            return False
    return (
        a.relations == b.relations
        and a.dimensions == b.dimensions
        and a.pictures == b.pictures
        and a.texts == b.texts
        and a.keep_sides == b.keep_sides
    )


def follow_references(sketch: Sketch, measured: dict[str, float]) -> None:
    """Reference (driven) dimensions show the measured size (T1.4.4)."""
    for dim in sketch.dimensions:
        value = measured.get(dim.id)
        if dim.driving or value is None or abs(value - dim.param.value) < 1e-9:
            continue
        text = f"{math.degrees(value):.6g}deg" if dim.type == "angle" else f"{value:.6g}mm"
        dim.param = Param(text, value)


def setup_dimension(sketch: Sketch, dim: Dimension, ids: list[str], place: Vec | None) -> Dimension:
    """Fill ``dim`` for ``ids`` and a text position, with the measured value.

    Used both for a new dimension and for the preview that follows the cursor
    before placement (T4.2.1). ``sketch`` is not changed.
    """
    dtype = dim.type
    if dtype == "doubled_distance":
        ids = doubled_order(sketch, ids, place) or list(ids)
    if dtype == "arc_length":
        arc = arc_length_arc(sketch, ids) or (ids[0] if len(ids) == 1 else None)
        if arc is None:
            raise ValueError("An arc length needs an arc and its two end points.")
        ids = [arc]
    dim.entities = list(ids)
    if dtype == "angle":
        symmetric = symmetric_order(sketch, ids, place)
        if symmetric is not None:  # TR111 (D2200): the full angle about a centerline
            dim.entities, dim.symmetric, dim.supplement = symmetric, True, False
        else:
            dim.supplement = place is not None and angle_supplement(sketch, ids[0], ids[1], place)
    value = measure(sketch, dim)
    text = f"{math.degrees(value):.6g}deg" if dtype == "angle" else f"{value:.6g}mm"
    dim.param = Param(text, value)
    return dim


def preview_dimension(
    sketch: Sketch,
    picks: list[str],
    place: Vec,
    sides: dict[str, str] | None = None,
    diameter_axis: str | None = None,
    locked: str | None = None,
) -> Dimension | None:
    """The dimension the picks would give with its text at ``place``, not added to the
    sketch (T4.2.1). None when the picks give no dimension. ``sides`` are Shift click
    sides of circles and arcs (:func:`shift_sides`). ``diameter_axis`` keeps diameter
    mode on (TR361). ``locked`` is a type locked by a right click (TR111, D1707)."""
    sticky = sticky_diameter(sketch, picks, diameter_axis)
    ids = sticky or centres_for_distance(sketch, picks)
    dtype = "doubled_distance" if sticky else smart_dimension(sketch, ids, place)
    dtype = locked_type(dtype, locked)
    if dtype is None:
        return None
    try:
        dim = setup_dimension(sketch, Dimension("preview", dtype, [], Param("0", 0.0)), ids, place)
        if sides and apply_sides(sketch, dim, sides):
            value = measure(sketch, dim)
            dim.param = Param(f"{value:.6g}mm", value)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    anchor = label_anchor(sketch, dim)
    dim.label = (place[0] - anchor[0], place[1] - anchor[1])
    return dim


def label_anchor(sketch: Sketch, dim: Dimension) -> Vec:
    """The point a stored label offset is measured from (FDEF_SPEC 6 item 5).

    Linear dimensions: the middle of the two measured points. Radius and
    diameter: the centre. Angles: the middle of the two lines' midpoints. Arc
    length: the middle of the arc.
    """
    if dim.type in ("radius", "diameter"):
        ent = sketch.entities[dim.entities[0]]
        assert isinstance(ent, Circle | Arc)
        return sketch.xy(ent.center)
    if dim.type == "arc_length":
        return arc_middle(sketch, dim.entities[0])
    if dim.type == "path_length":  # TR45: the middle of the middle curve
        mid = sketch.entities[dim.entities[len(dim.entities) // 2]]
        if isinstance(mid, Arc):
            return arc_middle(sketch, mid.id)
        if isinstance(mid, Spline):  # TR115 (D2201): the middle sample
            pts = sample(sketch, mid)
            return pts[len(pts) // 2]
        assert isinstance(mid, Line)
        (x1, y1), (x2, y2) = sketch.xy(mid.p1), sketch.xy(mid.p2)
        return (x1 + x2) / 2, (y1 + y2) / 2
    if dim.type == "angle":
        mids = []
        for eid in dim.entities:
            line = sketch.entities[eid]
            assert isinstance(line, Line)
            (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
            mids.append(((x1 + x2) / 2, (y1 + y2) / 2))
        return (mids[0][0] + mids[1][0]) / 2, (mids[0][1] + mids[1][1]) / 2
    a, b = distance_ends(sketch, dim)
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def arc_middle(sketch: Sketch, aid: str) -> Vec:
    """The point halfway along arc ``aid``."""
    arc = sketch.entities[aid]
    assert isinstance(arc, Arc)
    a0, a1 = arc_angles(sketch, arc)
    c, r = sketch.xy(arc.center), sketch.radius(aid)
    mid = (a0 + a1) / 2
    return c[0] + r * math.cos(mid), c[1] + r * math.sin(mid)


def _arc_and_ends(sketch: Sketch, ids: list[str]) -> tuple[Arc, set[str]] | None:
    arcs = [sketch.entities[i] for i in ids if isinstance(sketch.entities.get(i), Arc)]
    if len(arcs) != 1:
        return None
    arc = arcs[0]
    assert isinstance(arc, Arc)
    return arc, {i for i in ids if i != arc.id}


def arc_length_arc(sketch: Sketch, ids: list[str]) -> str | None:
    """The arc when ``ids`` are an arc and both its end points, in any order (T4.1, D515)."""
    found = _arc_and_ends(sketch, ids) if len(ids) == 3 else None
    if found is None:
        return None
    arc, rest = found
    return arc.id if rest == {arc.start, arc.end} else None


def arc_length_started(sketch: Sketch, ids: list[str], nxt: str) -> bool:
    """True when ``nxt`` after the two picks ``ids`` completes an arc length: the arc and
    its two end points, picked in any order (T4.1, D515)."""
    picks = [*ids, nxt]
    if len(picks) != 3 or len(set(picks)) != 3:
        return False
    return arc_length_arc(sketch, picks) is not None


def label_position(sketch: Sketch, dim: Dimension) -> Vec | None:
    """Where the stored label of ``dim`` sits in sketch mm, or None when automatic."""
    if dim.label is None:
        return None
    anchor = label_anchor(sketch, dim)
    return anchor[0] + dim.label[0], anchor[1] + dim.label[1]


def _points_of(c: Curve) -> list[str]:
    return entity_points(c)


def _is_origin(sketch: Sketch, pid: str) -> bool:
    p = sketch.entities.get(pid)
    return (
        isinstance(p, Point)
        and p.construction
        and any(r.type == "fixed" and r.entities == [pid] for r in sketch.relations)
        and abs(p.x) < 1e-12
        and abs(p.y) < 1e-12
    )


def _origin_fix(sketch: Sketch, rel: Relation) -> bool:
    """True for the Fix that holds the sketch origin in place."""
    return rel.type == "fixed" and len(rel.entities) == 1 and _is_origin(sketch, rel.entities[0])


# Selection rules --------------------------------------------------------------------------


def kinds_of(sketch: Sketch, ids: list[str]) -> list[str]:
    """Entity kinds (point, line, circle, arc) of the selected entities."""
    return [type(sketch.entities[i]).__name__.lower() for i in ids if i in sketch.entities]


#: Relations in the order the panel lists them.
RELATION_ORDER = (
    "horizontal",
    "vertical",
    "coincident",
    "collinear",
    "parallel",
    "perpendicular",
    "tangent",
    "concentric",
    "coradial",
    "equal",
    "midpoint",
    "symmetric",
    "intersection",
    "length_ratio",
    "length_difference",
    "equal_angle",
    "equal_distance",
    "merge",
    "on_segment",
    "fixed",
)


def symmetry_axis(sketch: Sketch, ids: list[str]) -> str | None:
    """The mirror line of a Symmetric selection (T3.1), or None when it does not fit.

    Two points, arcs or circles with one line: that line. Three lines: the one
    construction line (a centerline) among them.
    """
    if len(ids) != 3 or not all(i in sketch.entities for i in ids):
        return None
    lines = [i for i in ids if isinstance(sketch.entities[i], Line)]
    rest = [sketch.entities[i] for i in ids if i not in lines]
    if len(lines) == 1 and len(rest) == 2 and type(rest[0]) is type(rest[1]):
        return lines[0]
    if len(lines) == 3:
        centre = [i for i in lines if sketch.entities[i].construction]
        if len(centre) == 1:
            return centre[0]
    return None


def relations_for(sketch: Sketch, ids: list[str]) -> list[str]:
    """Relations that can be added to the selected entities, in menu order (T3.1)."""
    kinds = kinds_of(sketch, ids)
    if len(kinds) != len(ids) or not ids:
        return []
    n = len(kinds)
    lines = kinds.count("line")
    arcs = kinds.count("arc")
    rounds = kinds.count("circle") + arcs
    points = kinds.count("point")
    # TR41 (D1304): ellipses, partial ellipses and splines.
    ells = kinds.count("ellipse") + kinds.count("ellipsearc")
    splines = kinds.count("spline")
    out: set[str] = {"fixed"}
    if n == 2 and ells >= 1 and lines + rounds + ells == 2:
        out.add("tangent")
    if n == 2 and splines == 1 and lines + rounds + ells == 1:
        out.add("tangent")  # at the spline end, from its handle
    if n >= 2 and ells >= 1 and (rounds + ells == n or (points == 1 and rounds + ells == n - 1)):
        out.add("concentric")
    if n >= 2 and ells == n:
        out.add("equal")  # the same axes
    if n == 2 and points == 1 and kinds.count("ellipsearc") == 1:
        out.add("midpoint")
    if lines == n or (points == n and n >= 2):
        out |= {"horizontal", "vertical"}
    if n == 2 and points >= 1:
        out.add("coincident")
    if n >= 2 and lines == n:
        out |= {"collinear", "parallel"}
    if n == 2 and lines == 2:
        out.add("perpendicular")
    if n == 2 and rounds >= 1 and lines + rounds == 2:
        out.add("tangent")
    if (n >= 2 and rounds == n) or (n == 2 and points == 1 and rounds == 1):
        out.add("concentric")
    if n >= 2 and rounds == n:
        out.add("coradial")
    if n >= 2 and (lines == n or rounds == n or lines + arcs == n):
        out.add("equal")  # lines and arcs together: equal length (TR108, D1303)
    if n == 2 and points == 1 and (lines == 1 or arcs == 1):
        out.add("midpoint")
    if n == 2 and points == 1 and lines == 1:
        out.add("on_segment")  # TR342 (D1311)
    if symmetry_axis(sketch, ids) is not None:
        out.add("symmetric")
    if n == 3 and points == 1 and lines == 2:
        out |= {"intersection", "equal_distance"}  # TR226
    if n == 2 and lines + arcs == 2:
        out |= {"length_ratio", "length_difference"}  # TR226
    if n == 4 and lines == 4:
        out.add("equal_angle")  # TR226
    if n == 2 and points == 2:
        from fdcad.core.sketch.ops.merge import merge_problem

        if merge_problem(sketch, ids[0], ids[1]) is None:
            out.add("merge")  # TR40
    return [r for r in RELATION_ORDER if r in out]


def ordered_for(sketch: Sketch, rtype: str, ids: list[str]) -> list[str]:
    """Selected ids in the order the solver expects for ``rtype``."""
    if rtype == "symmetric":
        axis = symmetry_axis(sketch, ids)
        rest = [i for i in ids if i != axis]
        return rest + ([axis] if axis is not None else [])
    if rtype in ("coincident", "intersection", "concentric", "midpoint", "equal_distance"):
        return sorted(ids, key=lambda i: not isinstance(sketch.entities[i], Point))
    return list(ids)


def centres_for_distance(sketch: Sketch, ids: list[str]) -> list[str]:
    """A circle or arc picked with another item measures to its centre (T4.1, T4.3.1).

    Two picks where at least one is a circle or arc: each circle or arc is
    swapped for its centre point. The other item may be a point (including the
    origin and model point copies), a line (including model edge copies) or
    another circle or arc. A circle or arc alone keeps its id (diameter or radius).
    """
    if len(ids) != 2 or not all(i in sketch.entities for i in ids):
        return list(ids)
    if not any(isinstance(sketch.entities[i], Circle | Arc) for i in ids):
        return list(ids)
    out = []
    for eid in ids:
        ent = sketch.entities[eid]
        out.append(ent.center if isinstance(ent, Circle | Arc) else eid)
    if out[0] == out[1]:
        return list(ids)  # a circle and its own centre: nothing to measure
    return out


def shift_sides(sketch: Sketch, picks: list[str], clicks: dict[str, Vec]) -> dict[str, str]:
    """Nearest or farthest for each circle or arc clicked with Shift (T4.3.3, D516).

    ``clicks`` maps a picked circle or arc to where it was clicked. The side is
    ``nearest`` when the click is closer to the other item than the circle's centre
    is, else ``farthest``. The other item is measured as a line (square to it) or
    a circle or arc (its centre); with a point there is no side (T4.3.2, D123).
    """
    if len(picks) != 2:
        return {}
    out: dict[str, str] = {}
    for i, rid in enumerate(picks):
        ent, other = sketch.entities.get(rid), sketch.entities.get(picks[1 - i])
        click = clicks.get(rid)
        if click is None or not isinstance(ent, Circle | Arc):
            continue
        c = sketch.xy(ent.center)
        if isinstance(other, Line):
            click_gap = dist(click, _foot(sketch, other, click))
            centre_gap = dist(c, _foot(sketch, other, c))
        elif isinstance(other, Circle | Arc):
            o = sketch.xy(other.center)
            click_gap, centre_gap = dist(click, o), dist(c, o)
        else:
            continue
        out[rid] = "nearest" if click_gap < centre_gap else "farthest"
    return out


def apply_sides(sketch: Sketch, dim: Dimension, sides: dict[str, str]) -> bool:
    """Measure a distance to the given sides of its circles and arcs. True when changed."""
    if dim.type != "distance":
        return False
    changed = False
    for rid, side in sides.items():
        ent = sketch.entities.get(rid)
        if not isinstance(ent, Circle | Arc) or side not in MEASURE_TO:
            continue
        if not any(e in (rid, ent.center) for e in dim.entities):
            continue
        dim.entities = [rid if e in (rid, ent.center) else e for e in dim.entities]
        dim.measure_to[rid] = side
        changed = True
    return changed


def angle_supplement(sketch: Sketch, l1: str, l2: str, place: Vec) -> bool:
    """Which angle between two lines the text at ``place`` names (T4.1).

    The lines cross at a point; ``place`` lies in one of the four angles around
    it. Between both line directions, or both reversed, gives False (the angle
    between the directions). Either other angle gives True (180 degrees less).
    """
    a, b = sketch.entities[l1], sketch.entities[l2]
    assert isinstance(a, Line) and isinstance(b, Line)
    a1, a2 = sketch.xy(a.p1), sketch.xy(a.p2)
    b1, b2 = sketch.xy(b.p1), sketch.xy(b.p2)
    u = (a2[0] - a1[0], a2[1] - a1[1])
    v = (b2[0] - b1[0], b2[1] - b1[1])
    det = u[0] * v[1] - u[1] * v[0]
    if abs(det) < 1e-12:
        return False
    # Crossing point of the two infinite lines.
    t = ((b1[0] - a1[0]) * v[1] - (b1[1] - a1[1]) * v[0]) / det
    x = (a1[0] + t * u[0], a1[1] + t * u[1])
    w = (place[0] - x[0], place[1] - x[1])
    # w = s u + r v: same signs mean the angle between the directions.
    s_ = (w[0] * v[1] - w[1] * v[0]) / det
    r_ = (u[0] * w[1] - u[1] * w[0]) / det
    return s_ * r_ < 0


def _side(sketch: Sketch, axis: Line, p: Vec) -> float:
    (x1, y1), (x2, y2) = sketch.xy(axis.p1), sketch.xy(axis.p2)
    return (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1)


def doubled_order(sketch: Sketch, ids: list[str], place: Vec | None) -> list[str] | None:
    """[line, centerline] when the text sits beyond the centerline from the line, else None.

    That is the doubled distance of revolve profiles (T4.1 last row): two parallel
    lines, exactly one of them a centerline (construction line), or a point and a
    centerline (D123 item 5).
    """
    if place is None or len(ids) != 2:
        return None
    ents = [sketch.entities.get(i) for i in ids]
    lines = [e for e in ents if isinstance(e, Line)]
    points = [e for e in ents if isinstance(e, Point)]
    if len(lines) == 2:
        axes = [e for e in lines if e.construction]
        if len(axes) != 1 or not _parallel(sketch, lines[0], lines[1]):
            return None
        axis = axes[0]
        other: Line | Point = lines[1] if lines[0] is axis else lines[0]
    elif len(lines) == 1 and len(points) == 1 and lines[0].construction:
        axis, other = lines[0], points[0]
    else:
        return None
    here = _side(sketch, axis, sketch.xy(other.p1 if isinstance(other, Line) else other.id))
    there = _side(sketch, axis, place)
    if abs(here) < 1e-12 or here * there >= 0:
        return None
    return [other.id, axis.id]


def symmetric_order(sketch: Sketch, ids: list[str], place: Vec | None) -> list[str] | None:
    """[line, centerline] when the text of an angle sits beyond the centerline from the
    line, else None (TR111, D2200).

    Two crossing lines, exactly one a centerline (construction line): text on the
    line's side gives the half angle (a plain angle), text across the centerline gives
    the full symmetric angle, twice the line's angle to it.
    """
    if place is None or len(ids) != 2:
        return None
    ents = [sketch.entities.get(i) for i in ids]
    if not all(isinstance(e, Line) for e in ents):
        return None
    lines = [e for e in ents if isinstance(e, Line)]
    axes = [e for e in lines if e.construction]
    if len(axes) != 1 or _parallel(sketch, lines[0], lines[1]):
        return None
    axis = axes[0]
    other = lines[1] if lines[0] is axis else lines[0]
    (x1, y1), (x2, y2) = sketch.xy(other.p1), sketch.xy(other.p2)
    here = _side(sketch, axis, ((x1 + x2) / 2, (y1 + y2) / 2))
    there = _side(sketch, axis, place)
    if abs(here) < 1e-12 or here * there >= 0:
        return None
    return [other.id, axis.id]


def mirrored_middle(sketch: Sketch, dim: Dimension) -> Vec | None:
    """The middle of a symmetric angle's line mirrored about its centerline (TR111,
    D2200), where the canvas draws a third leader; None for other dimensions."""
    if dim.type != "angle" or not dim.symmetric or len(dim.entities) != 2:
        return None
    line, axis = (sketch.entities.get(e) for e in dim.entities)
    if not isinstance(line, Line) or not isinstance(axis, Line):
        return None
    (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
    mid = ((x1 + x2) / 2, (y1 + y2) / 2)
    foot = _foot(sketch, axis, mid)
    return 2 * foot[0] - mid[0], 2 * foot[1] - mid[1]


def sticky_diameter(sketch: Sketch, ids: list[str], axis: str | None) -> list[str] | None:
    """[line, axis] when diameter mode is on for ``axis`` (TR361, D951) and the one pick
    is a line parallel to it, so the dimension is a diameter wherever its text goes;
    else None. ``axis`` is the centerline of the last diameter the tool placed."""
    if axis is None or len(ids) != 1 or ids[0] == axis:
        return None
    line, centre = sketch.entities.get(ids[0]), sketch.entities.get(axis)
    if not isinstance(line, Line) or line.construction or not isinstance(centre, Line):
        return None
    if not centre.construction or not _parallel(sketch, line, centre):
        return None
    if abs(_side(sketch, centre, sketch.xy(line.p1))) < 1e-9:
        return None  # on the centerline: no diameter
    return [line.id, axis]


#: Point to point types the cursor switches between, which a right click can lock
#: (TR111 item 1, D1707).
LOCKABLE = ("distance", "horizontal_distance", "vertical_distance")


def locked_type(dtype: str | None, locked: str | None) -> str | None:
    """``dtype``, or the ``locked`` type when both are point to point distances."""
    if locked is not None and dtype in LOCKABLE and locked in LOCKABLE:
        return locked
    return dtype


def smart_dimension(sketch: Sketch, ids: list[str], place: Vec | None = None) -> str | None:
    """The dimension type for the selected entities and label position, or None (T4.1).

    ``ids`` are the picks after ``centres_for_distance``.
    """
    if len(ids) == 3:
        return "arc_length" if arc_length_arc(sketch, ids) is not None else None
    kinds = kinds_of(sketch, ids)
    if len(kinds) != len(ids):
        return None
    if kinds == ["circle"]:
        return "diameter"
    if kinds == ["arc"]:
        return "radius"
    if kinds == ["line"]:
        return "distance"  # a single line gives its length
    if kinds == ["line", "line"]:
        a, b = (sketch.entities[i] for i in ids)
        assert isinstance(a, Line) and isinstance(b, Line)
        if not _parallel(sketch, a, b):
            return "angle"
        return "doubled_distance" if doubled_order(sketch, ids, place) else "distance"
    if sorted(kinds) == ["line", "point"]:
        return "doubled_distance" if doubled_order(sketch, ids, place) else "distance"
    if kinds == ["point", "point"]:
        p1, p2 = sketch.xy(ids[0]), sketch.xy(ids[1])
        if place is None:
            return "distance"
        lo_x, hi_x = sorted((p1[0], p2[0]))
        lo_y, hi_y = sorted((p1[1], p2[1]))
        if (place[0] < lo_x or place[0] > hi_x) and lo_y <= place[1] <= hi_y:
            return "vertical_distance"
        if (place[1] < lo_y or place[1] > hi_y) and lo_x <= place[0] <= hi_x:
            return "horizontal_distance"
        return "distance"
    return None


def distance_ends(sketch: Sketch, dim: Dimension) -> tuple[Vec, Vec]:
    """The two measured points of a linear dimension, in sketch mm (for drawing it)."""
    ents = [sketch.entities[e] for e in dim.entities]
    if dim.type == "doubled_distance":
        first, axis = ents
        assert isinstance(axis, Line)
        p = sketch.xy(first.p1) if isinstance(first, Line) else sketch.xy(first.id)
        foot = _foot(sketch, axis, p)
        return p, (2 * foot[0] - p[0], 2 * foot[1] - p[1])
    if len(ents) == 1 and isinstance(ents[0], Line):
        return sketch.xy(ents[0].p1), sketch.xy(ents[0].p2)
    anchors: list[Vec | Line] = []
    for e in ents:
        if isinstance(e, Point):
            anchors.append((e.x, e.y))
        elif isinstance(e, Circle | Arc):
            anchors.append(sketch.xy(e.center))
        else:
            assert isinstance(e, Line)
            anchors.append(e)
    a, b = anchors
    if isinstance(a, Line) and isinstance(b, Line):
        p = sketch.xy(b.p1)
        ends = (p, _foot(sketch, a, p))
    elif isinstance(a, Line):
        assert not isinstance(b, Line)
        ends = (_foot(sketch, a, b), b)
    elif isinstance(b, Line):
        ends = (a, _foot(sketch, b, a))
    else:
        ends = (a, b)
    out = list(ends)
    for i, e in enumerate(ents):
        side = dim.measure_to.get(e.id) if isinstance(e, Circle | Arc) else None
        if side is None:
            continue
        c, other = out[i], out[1 - i]
        length = dist(c, other) or 1.0
        r = sketch.radius(e.id) * (1 if side == "nearest" else -1)
        out[i] = (c[0] + (other[0] - c[0]) / length * r, c[1] + (other[1] - c[1]) / length * r)
    return out[0], out[1]


def _foot(sketch: Sketch, line: Line, p: Vec) -> Vec:
    """Foot of the perpendicular from ``p`` to the infinite line."""
    (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
    dx, dy = x2 - x1, y2 - y1
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return x1, y1
    t = ((p[0] - x1) * dx + (p[1] - y1) * dy) / length2
    return x1 + t * dx, y1 + t * dy


def round_of_centre(sketch: Sketch, pid: str) -> str | None:
    """The circle or arc whose centre is point ``pid``, or None."""
    for e in sketch.entities.values():
        if isinstance(e, Circle | Arc) and e.center == pid:
            return e.id
    return None


def measure_options(sketch: Sketch, dim: Dimension) -> dict[str, str]:
    """Circles and arcs of a distance that offer Measure to, with their current side (T4.3.2).

    Offered for a circle or arc measured with a line or with another circle or arc.
    Keys are circle or arc ids; values are ``center``, ``nearest`` or ``farthest``.
    """
    if dim.type != "distance" or len(dim.entities) != 2:
        return {}
    rounds: list[str | None] = []
    for eid in dim.entities:
        ent = sketch.entities.get(eid)
        if isinstance(ent, Circle | Arc):
            rounds.append(eid)
        elif isinstance(ent, Point):
            rounds.append(round_of_centre(sketch, eid))
        else:
            rounds.append(None)
    kinds = kinds_of(sketch, dim.entities)
    out: dict[str, str] = {}
    for i, rid in enumerate(rounds):
        other = 1 - i
        other_fits = rounds[other] is not None or kinds[other] == "line"
        if rid is not None and other_fits:
            out[rid] = dim.measure_to.get(rid, "center")
    return out


def _parallel(sketch: Sketch, a: Line, b: Line) -> bool:
    (ax1, ay1), (ax2, ay2) = sketch.xy(a.p1), sketch.xy(a.p2)
    (bx1, by1), (bx2, by2) = sketch.xy(b.p1), sketch.xy(b.p2)
    cross = (ax2 - ax1) * (by2 - by1) - (ay2 - ay1) * (bx2 - bx1)
    la = math.hypot(ax2 - ax1, ay2 - ay1)
    lb = math.hypot(bx2 - bx1, by2 - by1)
    return la > 0 and lb > 0 and abs(cross) / (la * lb) < 1e-6


#: Relations that join many entities at once as one group (TR108, D1303).
GROUP_TYPES = ("parallel", "equal", "collinear", "coradial")


def join_group(sketch: Sketch, rtype: str, ids: list[str]) -> bool:
    """Add ``ids`` to the relations of type ``rtype`` that already hold one of them,
    as one relation (TR108, D1303). Several such groups merge into the first. False
    when there is no such group, or the joined group would not fit the solver."""
    from fdcad.core.sketch.solver import SketchSolveError, _Builder

    found = [
        i
        for i, r in enumerate(sketch.relations)
        if r.type == rtype and not r.off and set(r.entities) & set(ids)
    ]
    if not found:
        return False
    members = list(dict.fromkeys(e for i in found for e in sketch.relations[i].entities))
    members += [e for e in ids if e not in members]
    trial = Relation(rtype, members)
    builder = _Builder(sketch)
    try:
        builder.add_geometry()
        builder.add_relation(found[0], trial)
    except (SketchSolveError, KeyError):
        return False
    sketch.relations[found[0]].entities = members
    for i in reversed(found[1:]):
        del sketch.relations[i]
    return True


def group_numbers(sketch: Sketch) -> dict[int, int]:
    """The number of each relation group (three or more entities of a group type), by
    relation index, counted per type in sketch order (TR108, D1303)."""
    out: dict[int, int] = {}
    counts: dict[str, int] = {}
    for i, r in enumerate(sketch.relations):
        if r.type in GROUP_TYPES and len(r.entities) >= 3:
            counts[r.type] = counts.get(r.type, 0) + 1
            out[i] = counts[r.type]
    return out
