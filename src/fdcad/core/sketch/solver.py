"""The only bridge to the planegcs solver (CLAUDE.md rule 6).

``solve`` turns a :class:`Sketch` into planegcs geometry and constraints,
solves it, writes solved positions back, and reports the sketch status with
the user's own relations and dimensions named as the cause of any conflict.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import planegcs

from fdcad.core.sketch.freeform import LENGTH_DEPTH, Vec, arc_params, axes, spline_length
from fdcad.core.sketch.model import (
    RELATION_TYPES,
    Arc,
    Circle,
    Dimension,
    Ellipse,
    EllipseArc,
    Entity,
    Line,
    Point,
    Relation,
    Sketch,
    Spline,
    entity_points,
)


class SketchStatus(Enum):
    """How well a sketch is defined. Drives the sketch colours in the UI."""

    UNDER = "under"
    FULL = "full"
    OVER = "over"


@dataclass(frozen=True)
class ConstraintRef:
    """Points at the user's item behind a solver constraint.

    ``kind`` is ``"relation"`` (``key`` is the index in ``Sketch.relations``) or
    ``"dimension"`` (``key`` is the dimension id).
    """

    kind: str
    key: int | str


@dataclass
class SolveResult:
    """Outcome of a solve."""

    solved: bool
    status: SketchStatus
    dof: int
    conflicting: list[ConstraintRef] = field(default_factory=list)
    redundant: list[ConstraintRef] = field(default_factory=list)
    measured: dict[str, float] = field(default_factory=dict)
    message: str = ""


class SketchSolveError(ValueError):
    """A relation or dimension does not fit the entities it names."""


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length > 0 else (1.0, 0.0)


class _Builder:
    def __init__(
        self,
        sketch: Sketch,
        start: dict[str, tuple[float, float]] | None = None,
        active: set[str] | frozenset[str] = frozenset(),
    ) -> None:
        self.sk = sketch
        self.start = start or {}
        #: Limits and segment ends the solver holds this time (TR342, D1311).
        self.active = active
        self.s = planegcs.Sketch()
        self.points: dict[str, Any] = {}
        self.lines: dict[str, Any] = {}
        self.circles: dict[str, Any] = {}
        self.arcs: dict[str, Any] = {}
        #: The full ellipse of each ellipse and partial ellipse (D278).
        self.ellipses: dict[str, Any] = {}
        #: Radius parameter of each circle and arc, for distances to the curve.
        self.radii: dict[str, Any] = {}
        self.tags: dict[int, ConstraintRef] = {}

    # Geometry -------------------------------------------------------------

    def add_geometry(self) -> None:
        for e in self.sk.entities.values():
            if isinstance(e, Point):
                x, y = self.start.get(e.id, (e.x, e.y))
                self.points[e.id] = self.s.add_point(x, y)
        for e in self.sk.entities.values():
            if isinstance(e, Line):
                self.lines[e.id] = self.s.add_line(self.points[e.p1], self.points[e.p2])
            elif isinstance(e, Circle):
                radius = self.s.add_param(e.radius)
                self.radii[e.id] = radius
                self.circles[e.id] = self.s.add_circle(self.points[e.center], radius)
            elif isinstance(e, Arc):
                self.arcs[e.id] = self._add_arc(e)
            elif isinstance(e, Ellipse | EllipseArc):
                self._add_ellipse(e)

    def _add_ellipse(self, e: Ellipse | EllipseArc) -> None:
        """A planegcs ellipse on the centre, held by its major and minor axis ends. A
        partial ellipse adds an arc of ellipse on the same centre and focus whose
        start lies on that ellipse, so both are the same ellipse (D278)."""
        s = self.s
        c, a, b, phi = axes(self.sk, e)
        f = math.sqrt(max(a * a - b * b, 0.0))
        focus = s.add_point(c[0] + f * math.cos(phi), c[1] + f * math.sin(phi))
        centre = self.points[e.center]
        ell = s.add_ellipse(centre, focus, b)
        types = planegcs.InternalAlignmentType
        for pid, tx, ty in (
            (e.major, types.EllipsePositiveMajorX, types.EllipsePositiveMajorY),
            (e.minor, types.EllipsePositiveMinorX, types.EllipsePositiveMinorY),
        ):
            s.internal_alignment_point2ellipse(ell, self.points[pid], tx)
            s.internal_alignment_point2ellipse(ell, self.points[pid], ty)
        self.ellipses[e.id] = ell
        if isinstance(e, EllipseArc):
            t0, sweep = arc_params(self.sk, e)
            start, end = self.points[e.start], self.points[e.end]
            s.add_arc_of_ellipse(centre, focus, b, t0, t0 + sweep, start, end)
            s.point_on_ellipse(start, ell)

    def _add_arc(self, e: Arc) -> Any:
        start, end = (e.start, e.end) if e.ccw else (e.end, e.start)
        cx, cy = self.sk.xy(e.center)
        sx, sy = self.sk.xy(start)
        ex, ey = self.sk.xy(end)
        a0 = math.atan2(sy - cy, sx - cx)
        a1 = math.atan2(ey - cy, ex - cx)
        if a1 <= a0:
            a1 += 2 * math.pi
        radius = self.s.add_param(math.hypot(sx - cx, sy - cy))
        self.radii[e.id] = radius
        arc = self.s.add_arc(
            self.points[e.center],
            self.points[start],
            self.points[end],
            radius,
            self.s.add_param(a0),
            self.s.add_param(a1),
        )
        self.s.arc_rules(arc)
        return arc

    # Helpers --------------------------------------------------------------

    def kind(self, eid: str) -> str:
        if eid not in self.sk.entities:
            raise SketchSolveError(
                f"Entity {eid} does not exist. Delete the relation or dimension that names it."
            )
        return type(self.sk.entities[eid]).__name__.lower()

    def line(self, eid: str) -> Line:
        ent = self.sk.entities[eid]
        if not isinstance(ent, Line):
            raise SketchSolveError(f"{eid} must be a line. Pick a line instead.")
        return ent

    def center(self, eid: str) -> str:
        ent = self.sk.entities[eid]
        if isinstance(ent, Circle | Arc):
            return ent.center
        raise SketchSolveError(
            f"{eid} must be a circle or an arc. Pick a circle or an arc instead."
        )

    def round_id(self, eid: str) -> Any:
        return self.circles.get(eid) or self.arcs.get(eid)

    def record(self, ref: ConstraintRef, result: Any) -> None:
        tags = result if isinstance(result, tuple) else (result,)
        for tag in tags:
            self.tags[int(tag)] = ref

    # Relations ------------------------------------------------------------

    def add_relation(self, index: int, rel: Relation) -> None:
        # Only the known types: a name such as "offset_of" matched a helper method
        # (audit D12 item 10, D745).
        handler = getattr(self, f"rel_{rel.type}", None) if rel.type in RELATION_TYPES else None
        if handler is None:
            raise SketchSolveError(f"Unknown relation '{rel.type}'. Delete it and add it again.")
        ref = ConstraintRef("relation", index)
        if rel.type == "on_segment":
            for tag in self.rel_on_segment_at(index, rel.entities):
                self.record(ref, tag)
            return
        if rel.type == "offset":
            tags = self.rel_offset_of(rel)
        elif rel.type in ("length_ratio", "length_difference"):
            tags = self.rel_length_value(rel)
        else:
            tags = handler(rel.entities)
        for tag in tags:
            self.record(ref, tag)

    def rel_horizontal(self, ents: list[str]) -> list[Any]:
        return self._orient(ents, self.s.horizontal, self.s.horizontal_points, "Horizontal")

    def rel_vertical(self, ents: list[str]) -> list[Any]:
        return self._orient(ents, self.s.vertical, self.s.vertical_points, "Vertical")

    def _orient(
        self,
        ents: list[str],
        on_line: Callable[..., Any],
        on_points: Callable[..., Any],
        name: str,
    ) -> list[Any]:
        kinds = [self.kind(e) for e in ents]
        if kinds and all(k == "line" for k in kinds):
            return [on_line(self.lines[e]) for e in ents]
        if len(kinds) >= 2 and all(k == "point" for k in kinds):
            first = self.points[ents[0]]
            return [on_points(first, self.points[e]) for e in ents[1:]]
        raise SketchSolveError(
            f"{name} needs lines, or two or more points. Select lines or points and add it again."
        )

    def rel_coincident(self, ents: list[str]) -> list[Any]:
        if len(ents) != 2:
            raise SketchSolveError(
                "Coincident needs two entities. Select two items and add Coincident again."
            )
        a, b = ents
        if self.kind(a) != "point":
            a, b = b, a
        if self.kind(a) != "point":
            raise SketchSolveError(
                "Coincident needs a point and a point, line, circle or arc. "
                "Select a point first and add Coincident again."
            )
        pa = self.points[a]
        kb = self.kind(b)
        if kb == "point":
            return [self.s.coincident(pa, self.points[b])]
        if kb == "line":
            return [self.s.point_on_line(pa, self.lines[b])]
        if kb == "circle":
            return [self.s.point_on_circle(pa, self.circles[b])]
        if kb in ("ellipse", "ellipsearc"):
            return [self.s.point_on_ellipse(pa, self.ellipses[b])]
        if kb != "arc":
            raise SketchSolveError(
                "A point can lie on a line, circle, arc or ellipse. "
                "Pick one of those for the point."
            )
        return [self.s.point_on_arc(pa, self.arcs[b])]

    def rel_collinear(self, ents: list[str]) -> list[Any]:
        if len(ents) < 2 or any(self.kind(e) != "line" for e in ents):
            raise SketchSolveError(
                "Collinear needs two or more lines. "
                "Select two or more lines and add Collinear again."
            )
        target = self.lines[ents[0]]
        tags: list[Any] = []
        for eid in ents[1:]:
            other = self.line(eid)
            tags.append(self.s.point_on_line(self.points[other.p1], target))
            tags.append(self.s.point_on_line(self.points[other.p2], target))
        return tags

    def rel_parallel(self, ents: list[str]) -> list[Any]:
        return self._pairwise_lines(ents, self.s.parallel, "Parallel")

    def rel_perpendicular(self, ents: list[str]) -> list[Any]:
        if len(ents) != 2:
            raise SketchSolveError(
                "Perpendicular needs two lines. Select two lines and add Perpendicular again."
            )
        return self._pairwise_lines(ents, self.s.perpendicular, "Perpendicular")

    def _pairwise_lines(self, ents: list[str], fn: Callable[..., Any], name: str) -> list[Any]:
        if len(ents) < 2 or any(self.kind(e) != "line" for e in ents):
            raise SketchSolveError(
                f"{name} needs two or more lines. Select two or more lines and add it again."
            )
        return [fn(self.lines[ents[0]], self.lines[e]) for e in ents[1:]]

    def rel_tangent(self, ents: list[str]) -> list[Any]:
        if len(ents) != 2:
            raise SketchSolveError(
                "Tangent needs two curves. Select two curves and add Tangent again."
            )
        order = {"line": 0, "circle": 1, "arc": 2}
        a, b = sorted(ents, key=lambda e: order.get(self.kind(e), 9))
        pair = (self.kind(a), self.kind(b))
        s = self.s
        if "spline" in pair:  # TR41 (D1304): from the end handle's direction
            return self._spline_tangent(a, b)
        if set(pair) & _ELLIPSES:
            return self._ellipse_tangent(a, b)
        table: dict[tuple[str, str], Callable[[], Any]] = {
            ("line", "circle"): lambda: s.tangent_line_circle(self.lines[a], self.circles[b]),
            ("line", "arc"): lambda: s.tangent_line_arc(self.lines[a], self.arcs[b]),
            ("circle", "circle"): lambda: s.tangent_circle_circle(self.circles[a], self.circles[b]),
            ("circle", "arc"): lambda: s.tangent_circle_arc(self.circles[a], self.arcs[b]),
            ("arc", "arc"): lambda: s.tangent_arc_arc(self.arcs[a], self.arcs[b]),
        }
        if pair not in table:
            raise SketchSolveError(
                "Tangent needs a circle or an arc and another curve. "
                "Select a circle or an arc first and add Tangent again."
            )
        shared = _shared_end(self.sk, a, b)
        if shared is not None:
            # Curves that use the same end point (slots, D277): tangent at that point.
            # A distance based tangency there would be one relation too many.
            crv = [self.lines.get(e) or self.round_id(e) for e in (a, b)]
            here = s.calculate_angle_via_point(crv[0], crv[1], self.points[shared])
            target = min(
                (0.0, math.pi, -math.pi), key=lambda t: abs(math.remainder(here - t, 2 * math.pi))
            )
            return [
                s.angle_via_point(crv[0], crv[1], self.points[shared], s.add_fixed_param(target))
            ]
        return [table[pair]()]

    # Ellipses and splines (TR41, D1304) -----------------------------------------------

    def _curve_obj(self, eid: str) -> Any:
        kind = self.kind(eid)
        if kind == "line":
            return self.lines[eid]
        if kind in _ELLIPSES:
            return self.ellipses[eid]
        return self.round_id(eid)

    def _on_curve(self, point: Any, eid: str) -> Any:
        kind = self.kind(eid)
        if kind == "line":
            return self.s.point_on_line(point, self.lines[eid])
        if kind == "circle":
            return self.s.point_on_circle(point, self.circles[eid])
        if kind == "arc":
            return self.s.point_on_arc(point, self.arcs[eid])
        return self.s.point_on_ellipse(point, self.ellipses[eid])

    def _ellipse_tangent(self, a: str, b: str) -> list[Any]:
        """An ellipse or partial ellipse tangent to a line, circle, arc or ellipse."""
        kinds = {self.kind(a), self.kind(b)}
        if not kinds <= {"line", "circle", "arc", *_ELLIPSES}:
            raise SketchSolveError(
                "Tangent to an ellipse needs a line, circle, arc or ellipse. "
                "Select one of those with the ellipse and add Tangent again."
            )
        s = self.s
        shared = _shared_end(self.sk, a, b)
        if shared is not None:
            crv = [self._curve_obj(e) for e in (a, b)]
            here = s.calculate_angle_via_point(crv[0], crv[1], self.points[shared])
            target = min(
                (0.0, math.pi, -math.pi), key=lambda t: abs(math.remainder(here - t, 2 * math.pi))
            )
            return [
                s.angle_via_point(crv[0], crv[1], self.points[shared], s.add_fixed_param(target))
            ]
        if self.kind(a) == "line":
            other = b if self.kind(b) in _ELLIPSES else a
            return [s.tangent_line_ellipse(self.lines[a], self.ellipses[other])]
        return self._tangent_via_point(a, b)

    def _tangent_via_point(self, a: str, b: str) -> list[Any]:
        """Two curves tangent where a helper point lies on both, starting where they come
        closest (the way the solver joins curves with no shared point)."""
        import numpy as np

        from fdcad.core.sketch.topology import curve_points

        ea, eb = self.sk.entities[a], self.sk.entities[b]
        pa = np.array(curve_points(self.sk, ea), dtype=np.float64)  # type: ignore[arg-type]
        pb = np.array(curve_points(self.sk, eb), dtype=np.float64)  # type: ignore[arg-type]
        d = np.hypot(pa[:, None, 0] - pb[None, :, 0], pa[:, None, 1] - pb[None, :, 1])
        i, j = np.unravel_index(int(np.argmin(d)), d.shape)
        mx, my = (pa[i] + pb[j]) / 2
        s = self.s
        helper = s.add_point(float(mx), float(my))
        ca, cb = self._curve_obj(a), self._curve_obj(b)
        here = s.calculate_angle_via_point(ca, cb, helper)
        target = min(
            (0.0, math.pi, -math.pi), key=lambda t: abs(math.remainder(here - t, 2 * math.pi))
        )
        return [
            self._on_curve(helper, a),
            self._on_curve(helper, b),
            s.angle_via_point(ca, cb, helper, s.add_fixed_param(target)),
        ]

    def _spline_tangent(self, a: str, b: str) -> list[Any]:
        """A spline end tangent to a line, circle, arc or ellipse: the line through the
        end point and its handle is parallel or tangent to the other curve."""
        spline_id, other = (a, b) if self.kind(a) == "spline" else (b, a)
        kind = self.kind(other)
        if kind not in ("line", "circle", "arc", *_ELLIPSES):
            raise SketchSolveError(
                "Tangent to a spline needs a line, circle, arc or ellipse. "
                "Select one of those with the spline and add Tangent again."
            )
        spline = self.sk.entities[spline_id]
        assert isinstance(spline, Spline)
        point, handle = spline_end_near(self.sk, spline, other)
        s = self.s
        helper = s.add_line(self.points[point], self.points[handle])
        if kind == "line":
            return [s.parallel(helper, self.lines[other])]
        if kind == "circle":
            return [s.tangent_line_circle(helper, self.circles[other])]
        if kind == "arc":
            return [s.tangent_line_arc(helper, self.arcs[other])]
        return [s.tangent_line_ellipse(helper, self.ellipses[other])]

    def rel_concentric(self, ents: list[str]) -> list[Any]:
        kinds = [self.kind(e) for e in ents]
        rounds = {"circle", "arc", *_ELLIPSES}
        if len(ents) < 2 or kinds.count("point") > 1 or not rounds & set(kinds):
            raise SketchSolveError(
                "Concentric needs two or more circles, arcs or ellipses, or a point and one "
                "of those. Select those items and add Concentric again."
            )
        centers = [
            e
            if k == "point"
            else self.sk.entities[e].center  # type: ignore[union-attr]
            if k in _ELLIPSES
            else self.center(e)
            for e, k in zip(ents, kinds, strict=True)
        ]
        first = self.points[centers[0]]
        return [self.s.coincident(first, self.points[c]) for c in centers[1:]]

    def rel_coradial(self, ents: list[str]) -> list[Any]:
        if len(ents) < 2 or any(self.kind(e) not in ("circle", "arc") for e in ents):
            raise SketchSolveError(
                "Coradial needs two or more circles or arcs. "
                "Select two or more circles or arcs and add Coradial again."
            )
        tags = self.rel_concentric(ents)
        return tags + [self._equal_radius(ents[0], e) for e in ents[1:]]

    def rel_intersection(self, ents: list[str]) -> list[Any]:
        if len(ents) != 3 or [self.kind(e) for e in ents] != ["point", "line", "line"]:
            raise SketchSolveError(
                "Intersection needs a point and two lines, in that order. "
                "Select them in that order and add Intersection again."
            )
        point = self.points[ents[0]]
        return [
            self.s.point_on_line(point, self.lines[ents[1]]),
            self.s.point_on_line(point, self.lines[ents[2]]),
        ]

    def rel_equal(self, ents: list[str]) -> list[Any]:
        if len(ents) < 2:
            raise SketchSolveError(
                "Equal needs two or more entities. Select two or more items and add Equal again."
            )
        kinds = {self.kind(e) for e in ents}
        if kinds == {"line"}:
            return [self.s.equal_length(self.lines[ents[0]], self.lines[e]) for e in ents[1:]]
        if kinds <= {"circle", "arc"}:
            return [self._equal_radius(ents[0], e) for e in ents[1:]]
        if kinds <= _ELLIPSES:  # TR41 (D1304): the same axes
            first = self.ellipses[ents[0]]
            return [self.s.equal_radii_ee(first, self.ellipses[e]) for e in ents[1:]]
        if kinds == {"line", "arc"}:
            # Equal Length of lines and arcs together (TR108, D1303): same curve length.
            first, tags = self._length_param(ents[0])
            for e in ents[1:]:
                other, more = self._length_param(e)
                tags += [*more, self.s.proportional(first, other, 1.0)]
            return tags
        raise SketchSolveError(
            "Equal needs only lines, only circles and arcs, or lines and arcs (same length). "
            "Select items of one kind and add Equal again."
        )

    def _equal_radius(self, a: str, b: str) -> Any:
        ka, kb = self.kind(a), self.kind(b)
        if ka == kb == "circle":
            return self.s.equal_radius_cc(self.circles[a], self.circles[b])
        if ka == kb == "arc":
            return self.s.equal_radius_aa(self.arcs[a], self.arcs[b])
        circle, arc = (a, b) if ka == "circle" else (b, a)
        return self.s.equal_radius_ca(self.circles[circle], self.arcs[arc])

    # Ratio, difference, equal angle and equal distance (TR226, D870) ------------------

    def _length_param(self, eid: str) -> tuple[Any, list[Any]]:
        """A free parameter held to the length of line or arc ``eid``."""
        kind = self.kind(eid)
        if kind == "line":
            line = self.line(eid)
            a, b = self.sk.xy(line.p1), self.sk.xy(line.p2)
            pid = self.s.add_param(math.dist(a, b))
            return pid, [self.s.p2p_distance(self.points[line.p1], self.points[line.p2], pid)]
        if kind == "arc":
            pid = self.s.add_param(arc_length(self.sk, eid))
            return pid, [self.s.arc_length(self.arcs[eid], pid)]
        if kind == "spline":
            return self._spline_length_param(eid)
        raise SketchSolveError(
            "Length Ratio and Length Difference need two lines or arcs. "
            "Select two lines or arcs and add the relation again."
        )

    def _spline_length_param(self, eid: str) -> tuple[Any, list[Any]]:
        """A free parameter held to the length of spline ``eid`` (TR115, D2201).

        Each cubic piece is halved ``LENGTH_DEPTH`` times with helper points held at
        midpoints (``symmetric_point``), the same split as ``freeform.spline_length``;
        the length is the sum over the parts of half their chord plus half their
        control polygon, each a distance parameter.
        """
        s = self.s
        spline = self.sk.entities[eid]
        assert isinstance(spline, Spline)
        tags: list[Any] = []

        def xy(pid: str) -> Vec:
            return self.start.get(pid, self.sk.xy(pid))

        def helper(a: tuple[Any, Vec], b: tuple[Any, Vec]) -> tuple[Any, Vec]:
            at = ((a[1][0] + b[1][0]) / 2, (a[1][1] + b[1][1]) / 2)
            point = s.add_point(at[0], at[1])
            tags.append(s.symmetric_point(a[0], b[0], point))
            return point, at

        def mirrored(handle: str, through: str) -> tuple[Any, Vec]:
            (hx, hy), (px, py) = xy(handle), xy(through)
            at = (2 * px - hx, 2 * py - hy)
            point = s.add_point(at[0], at[1])
            tags.append(s.symmetric_point(self.points[handle], point, self.points[through]))
            return point, at

        def distance(a: tuple[Any, Vec], b: tuple[Any, Vec]) -> Any:
            pid = s.add_param(math.dist(a[1], b[1]))
            tags.append(s.p2p_distance(a[0], b[0], pid))
            return pid, math.dist(a[1], b[1])

        parts: list[tuple[Any, float]] = []

        def split(poles: list[tuple[Any, Vec]], depth: int) -> None:
            if depth == 0:
                parts.append(distance(poles[0], poles[3]))
                parts.extend(distance(poles[i], poles[i + 1]) for i in range(3))
                return
            a, b, c = (
                helper(poles[0], poles[1]),
                helper(poles[1], poles[2]),
                helper(poles[2], poles[3]),
            )
            d, e = helper(a, b), helper(b, c)
            f = helper(d, e)
            split([poles[0], a, d, f], depth - 1)
            split([f, e, c, poles[3]], depth - 1)

        def own(pid: str) -> tuple[Any, Vec]:
            return self.points[pid], xy(pid)

        for i in range(len(spline.points) - 1):
            p, q = spline.points[i], spline.points[i + 1]
            poles = [own(p), own(spline.handles[i]), mirrored(spline.handles[i + 1], q), own(q)]
            split(poles, LENGTH_DEPTH)
        total, acc = parts[0]
        for part, size in parts[1:]:
            acc += size
            nxt = s.add_param(acc)
            tags.append(s.difference(total, nxt, part))
            total = nxt
        length = s.add_param(acc / 2)
        tags.append(s.difference(length, total, length))  # the sum is twice the length
        return length, tags

    def rel_length_ratio(self, ents: list[str]) -> list[Any]:
        raise SketchSolveError("Length Ratio needs a value. Delete it and add it again.")

    def rel_length_difference(self, ents: list[str]) -> list[Any]:
        raise SketchSolveError("Length Difference needs a value. Delete it and add it again.")

    def rel_length_value(self, rel: Relation) -> list[Any]:
        """A over B equals the value (ratio), or A minus B equals it (difference)."""
        if len(rel.entities) != 2 or rel.value is None:
            raise SketchSolveError(
                "This relation needs two lines or arcs and a value. Delete it and add it again."
            )
        if rel.type == "length_ratio" and rel.value <= 0:
            raise SketchSolveError(
                "A length ratio must be greater than zero. Edit the relation's value."
            )
        pa, ta = self._length_param(rel.entities[0])
        pb, tb = self._length_param(rel.entities[1])
        if rel.type == "length_ratio":
            tag = self.s.proportional(pa, pb, rel.value)
        else:
            tag = self.s.difference(pb, pa, self.s.add_fixed_param(rel.value))
        return [*ta, *tb, tag]

    def rel_equal_angle(self, ents: list[str]) -> list[Any]:
        if len(ents) != 4 or any(self.kind(e) != "line" for e in ents):
            raise SketchSolveError(
                "Equal Angle needs four lines: the first pair and the second pair. "
                "Select four lines and add Equal Angle again."
            )
        t = self.s.add_param(measure_angle(self.sk, ents[0], ents[1]))
        return [
            self.s.l2l_angle(self.lines[ents[0]], self.lines[ents[1]], t),
            self.s.l2l_angle(self.lines[ents[2]], self.lines[ents[3]], t),
        ]

    def rel_equal_distance(self, ents: list[str]) -> list[Any]:
        if len(ents) != 3 or [self.kind(e) for e in ents] != ["point", "line", "line"]:
            raise SketchSolveError(
                "Equal Distance needs a point and two lines, in that order. "
                "Select them and add Equal Distance again."
            )
        d = self.s.add_param(_point_line_distance(self.sk, ents[0], ents[1]))
        point = self.points[ents[0]]
        return [
            self.s.p2l_distance(point, self.lines[ents[1]], d),
            self.s.p2l_distance(point, self.lines[ents[2]], d),
        ]

    def rel_midpoint(self, ents: list[str]) -> list[Any]:
        kinds = sorted((self.kind(e), e) for e in ents)
        names = [k for k, _ in kinds]
        if names == ["line", "point"]:
            line = self.line(kinds[0][1])
            point = kinds[1][1]
            return [
                self.s.symmetric_point(
                    self.points[line.p1], self.points[line.p2], self.points[point]
                )
            ]
        if names == ["arc", "point"]:
            # On the arc's circle and on the bisector of its chord: the arc's middle
            # (the solver keeps the point on the side it starts on).
            arc = self.sk.entities[kinds[0][1]]
            assert isinstance(arc, Arc)
            point = self.points[kinds[1][1]]
            chord = self.s.add_line(self.points[arc.start], self.points[arc.end])
            return [
                self.s.point_on_arc(point, self.arcs[arc.id]),
                self.s.point_on_perp_bisector(point, chord),
            ]
        if names == ["ellipsearc", "point"]:
            # TR41 (D1304): on the ellipse, as far from both ends of the partial ellipse.
            part = self.sk.entities[kinds[0][1]]
            assert isinstance(part, EllipseArc)
            point = self.points[kinds[1][1]]
            chord = self.s.add_line(self.points[part.start], self.points[part.end])
            return [
                self.s.point_on_ellipse(point, self.ellipses[part.id]),
                self.s.point_on_perp_bisector(point, chord),
            ]
        raise SketchSolveError(
            "Midpoint needs a point and a line, an arc or a partial ellipse. "
            "Select a point and one of those and add Midpoint again."
        )

    def rel_symmetric(self, ents: list[str]) -> list[Any]:
        """Two points, lines, arcs or circles mirrored about a line (stored last)."""
        if len(ents) != 3 or self.kind(ents[2]) != "line":
            raise SketchSolveError(
                "Symmetric needs two points, lines, arcs or circles and a line, in that order. "
                "Select them in that order and add Symmetric again."
            )
        a, b, axis_id = ents
        ka, kb = self.kind(a), self.kind(b)
        axis = self.lines[axis_id]
        mirror = self.s.symmetric_line
        if ka == kb == "point":
            return [mirror(self.points[a], self.points[b], axis)]
        if ka == kb == "line":
            la, lb = self.line(a), self.line(b)
            pairs = self._mirror_pairs(axis_id, [la.p1, la.p2], [lb.p1, lb.p2])
            return [mirror(self.points[p], self.points[q], axis) for p, q in pairs]
        if ka == kb == "circle":
            ca, cb = self.center(a), self.center(b)
            return [mirror(self.points[ca], self.points[cb], axis), self._equal_radius(a, b)]
        if ka == kb == "arc":
            ea, eb = self.sk.entities[a], self.sk.entities[b]
            assert isinstance(ea, Arc) and isinstance(eb, Arc)
            pairs = self._mirror_pairs(axis_id, [ea.start, ea.end], [eb.start, eb.end])
            pairs.append((ea.center, eb.center))
            return [mirror(self.points[p], self.points[q], axis) for p, q in pairs]
        raise SketchSolveError(
            "Symmetric needs two items of the same kind and a line. "
            "Select two items of one kind and a line, then add Symmetric again."
        )

    def _mirror_pairs(self, axis: str, a: list[str], b: list[str]) -> list[tuple[str, str]]:
        """Pair two end points of ``a`` with those of ``b`` so mirrored ends lie closest."""
        line = self.line(axis)
        p, q = self.sk.xy(line.p1), self.sk.xy(line.p2)

        def mirrored(pid: str) -> tuple[float, float]:
            x, y = self.sk.xy(pid)
            ux, uy = _unit(q[0] - p[0], q[1] - p[1])
            t = (x - p[0]) * ux + (y - p[1]) * uy
            fx, fy = p[0] + t * ux, p[1] + t * uy
            return 2 * fx - x, 2 * fy - y

        def gap(x: str, y: str) -> float:
            mx, my = mirrored(x)
            bx, by = self.sk.xy(y)
            return math.hypot(mx - bx, my - by)

        straight = gap(a[0], b[0]) + gap(a[1], b[1])
        crossed = gap(a[0], b[1]) + gap(a[1], b[0])
        if straight <= crossed:
            return [(a[0], b[0]), (a[1], b[1])]
        return [(a[0], b[1]), (a[1], b[0])]

    def rel_offset(self, ents: list[str]) -> list[Any]:
        raise SketchSolveError("Offset is added with its distance. Use the Offset tool to add it.")

    def rel_offset_of(self, rel: Relation) -> list[Any]:
        """Offset copies follow their sources (PHASE2_SPEC P2.8 item 1, DECISIONS D272).

        ``entities`` holds (source, copy) pairs that share one distance: the stored
        ``value``, or a free distance a dimension sets. A line copy is parallel at
        that distance; a circle or arc copy is concentric with its radius larger or
        smaller by it. A copy end that no relation joins to another curve and that
        sits square across from the source end stays there.
        """
        ents = rel.entities
        if len(ents) < 2 or len(ents) % 2:
            raise SketchSolveError(
                "Offset needs pairs of a curve and its copy. Use the Offset tool to add it again."
            )
        s = self.s
        pairs = list(zip(ents[0::2], ents[1::2], strict=True))
        start = rel.value if rel.value is not None else _offset_distance(self.sk, *pairs[0])
        t = s.add_fixed_param(rel.value) if rel.value is not None else s.add_param(start)
        joined = _joined_points(self.sk)
        tags: list[Any] = []
        for src, copy in pairs:
            ks, kc = self.kind(src), self.kind(copy)
            if ks == kc == "line":
                a, b = self.line(src), self.line(copy)
                tags.append(s.parallel(self.lines[src], self.lines[copy]))
                tags.append(s.p2l_distance(self.points[b.p1], self.lines[src], t))
                for ps, pc in ((a.p1, b.p1), (a.p2, b.p2)):
                    if pc not in joined and _square(self.sk, a, ps, pc):
                        helper = s.add_line(self.points[ps], self.points[pc])
                        tags.append(s.perpendicular(helper, self.lines[src]))
            elif ks in ("circle", "arc") and kc in ("circle", "arc"):
                cs, cc = self.center(src), self.center(copy)
                if cs != cc:
                    tags.append(s.coincident(self.points[cs], self.points[cc]))
                rs, rc = self.radii[src], self.radii[copy]
                if self.sk.radius(copy) >= self.sk.radius(src):
                    tags.append(s.difference(rs, rc, t))
                else:
                    tags.append(s.difference(rc, rs, t))
                ea, eb = self.sk.entities[src], self.sk.entities[copy]
                if isinstance(ea, Arc) and isinstance(eb, Arc):
                    for ps, pc in ((ea.start, eb.start), (ea.end, eb.end)):
                        if pc not in joined and _radial(self.sk, cs, ps, pc):
                            helper = s.add_line(self.points[cs], self.points[ps])
                            tags.append(s.point_on_line(self.points[pc], helper))
            else:
                raise SketchSolveError(
                    "An offset pairs a line with a line, or arcs and circles. "
                    "Use the Offset tool to add it again."
                )
        return tags

    def rel_fixed(self, ents: list[str]) -> list[Any]:
        tags: list[Any] = []
        for eid in ents:
            ent = self.sk.entities[eid]
            if isinstance(ent, Point):
                pts = [ent.id]
            elif isinstance(ent, Line):
                pts = [ent.p1, ent.p2]
            elif isinstance(ent, Circle):
                pts = [ent.center]
                tags.append(self.s.set_circle_radius(self.circles[ent.id], ent.radius))
            else:
                pts = entity_points(ent)
            for pid in pts:
                x, y = self.sk.xy(pid)
                tags.extend(self.s.fix_point(self.points[pid], x, y))
        return tags

    # Dimensions -----------------------------------------------------------

    def rel_on_segment(self, ents: list[str]) -> list[Any]:
        return self.rel_on_segment_at(-1, ents)

    def rel_on_segment_at(self, index: int, ents: list[str]) -> list[Any]:
        """A point on a line, held at the nearer end when it would leave the segment
        (TR342, D1311: the end is held only when ``solve`` finds it outside)."""
        if len(ents) != 2 or [self.kind(e) for e in ents] != ["point", "line"]:
            raise SketchSolveError(
                "Point on Segment needs a point and a line, in that order. "
                "Select them and add it again."
            )
        point = self.points[ents[0]]
        line = self.line(ents[1])
        tags = [self.s.point_on_line(point, self.lines[ents[1]])]
        for end in (line.p1, line.p2):
            if f"r{index}:{end}" in self.active:
                tags.append(self.s.coincident(point, self.points[end]))
        return tags

    def add_dimension(self, dim: Dimension) -> None:
        if not dim.driving or dim.off:
            return
        if dim.limit and dim.id not in self.active:
            return  # TR342: a limit acts only once the size passes it
        ref = ConstraintRef("dimension", dim.id)
        value = dim.param.value
        ents = dim.entities
        kinds = [self.kind(e) for e in ents]
        if dim.type == "path_length":  # TR45 (D1307)
            for one in self._path_length(ents, value):
                self.record(ref, one)
            return
        s = self.s
        tag: Any
        if dim.type == "distance" and {"circle", "arc"} & set(kinds):
            tag = self._curve_distance(dim, value)
        elif dim.type == "doubled_distance":
            point, axis = _doubled_parts(self.sk, ents)
            tag = s.set_p2l_distance(self.points[point], self.lines[axis], value / 2)
        elif dim.type == "distance":
            if kinds == ["line"]:
                line = self.line(ents[0])
                ents, kinds = [line.p1, line.p2], ["point", "point"]
            if kinds == ["point", "point"]:
                tag = s.set_p2p_distance(self.points[ents[0]], self.points[ents[1]], value)
            elif sorted(kinds) == ["line", "point"]:
                pt, ln = (ents[0], ents[1]) if kinds[0] == "point" else (ents[1], ents[0])
                tag = s.set_p2l_distance(self.points[pt], self.lines[ln], value)
            elif kinds == ["line", "line"]:
                other = self.line(ents[1])
                tag = s.set_p2l_distance(self.points[other.p1], self.lines[ents[0]], value)
            else:
                raise SketchSolveError(
                    "Distance needs points or lines. "
                    "Select points or lines and dimension them again."
                )
        elif dim.type in ("horizontal_distance", "vertical_distance"):
            tag = self._axis_distance(dim, value)
        elif dim.type == "angle":
            if kinds != ["line", "line"]:
                raise SketchSolveError(
                    "An angle dimension needs two lines. Select two lines and dimension them again."
                )
            if dim.symmetric:  # TR111 (D2200): the full angle about a centerline
                if not 0 < value < math.pi:
                    raise SketchSolveError(
                        "A symmetric angle must be between 0 and 180 degrees. "
                        "Enter a smaller angle."
                    )
                target = self._nearest_angle(ents[0], ents[1], value / 2, None)
            else:
                target = self._nearest_angle(ents[0], ents[1], value, dim.supplement)
            tag = s.set_l2l_angle(self.lines[ents[0]], self.lines[ents[1]], target)
        elif dim.type in ("radius", "diameter"):
            radius = value if dim.type == "radius" else value / 2
            if kinds == ["circle"]:
                tag = s.set_circle_radius(self.circles[ents[0]], radius)
            elif kinds == ["arc"]:
                tag = s.set_arc_radius(self.arcs[ents[0]], radius)
            else:
                raise SketchSolveError(
                    "A radius or diameter needs a circle or an arc. "
                    "Select a circle or an arc and dimension it again."
                )
        elif dim.type == "arc_length":
            if kinds != ["arc"]:
                raise SketchSolveError(
                    "An arc length dimension needs an arc. Select an arc and dimension it again."
                )
            tag = s.arc_length(self.arcs[ents[0]], s.add_fixed_param(value))
        else:
            raise SketchSolveError(
                f"Unknown dimension type '{dim.type}'. Delete it and add it again."
            )
        self.record(ref, tag)

    def _path_length(self, ents: list[str], value: float) -> list[Any]:
        """The lengths of the lines and arcs ``ents`` add up to ``value`` (TR45): a
        running sum parameter per curve, the last one held to the value."""
        if not ents or any(self.kind(e) not in ("line", "arc", "spline") for e in ents):
            raise SketchSolveError(
                "A path length needs lines, arcs or splines. "
                "Select a chain of them and dimension it again."
            )
        s = self.s
        total, tags = self._length_param(ents[0])
        for k, eid in enumerate(ents[1:], start=2):
            part, more = self._length_param(eid)
            tags += more
            nxt = s.add_param(path_length(self.sk, ents[:k]))
            tags.append(s.difference(total, nxt, part))
            total = nxt
        tags.append(s.equal(total, s.add_fixed_param(value)))
        return tags

    def _axis_points(self, ents: list[str]) -> tuple[str, str]:
        if len(ents) == 1 and self.kind(ents[0]) == "line":
            line = self.line(ents[0])
            return line.p1, line.p2
        if len(ents) == 2 and all(self.kind(e) == "point" for e in ents):
            return ents[0], ents[1]
        raise SketchSolveError(
            "A horizontal or vertical distance needs two points or a line. "
            "Select two points or a line and dimension them again."
        )

    def _axis_distance(self, dim: Dimension, value: float) -> Any:
        a, b = self._axis_points(dim.entities)
        axis = 0 if dim.type == "horizontal_distance" else 1
        current = self.sk.xy(b)[axis] - self.sk.xy(a)[axis]
        if dim.side is None:
            # The side is set once from the geometry and then kept, so later edits never
            # flip the point to the mirror solution; a negative value flips it (TR337).
            dim.side = 1 if current >= 0 else -1
        signed = dim.side * value
        pa = self.s.get_point_param_ids(self.points[a])[axis]
        pb = self.s.get_point_param_ids(self.points[b])[axis]
        return self.s.difference(pa, pb, self.s.add_fixed_param(signed))

    def _curve_distance(self, dim: Dimension, value: float) -> tuple[Any, ...]:
        """A distance that meets circles or arcs at their nearest or farthest side (T4.3).

        The distance between the centres (or a centre and a line, or a point) is
        ``value`` minus the radius for each farthest side and plus it for each nearest.
        """
        s = self.s
        parts = [_curve_part(self.sk, dim, e) for e in dim.entities]
        anchors = [a for a, _sign in parts]
        kinds = [self.kind(a) for a in anchors]
        base = s.add_param(_base_distance(self.sk, anchors))
        if kinds == ["point", "point"]:
            tags: list[Any] = [
                s.p2p_distance(self.points[anchors[0]], self.points[anchors[1]], base)
            ]
        elif sorted(kinds) == ["line", "point"]:
            pt, ln = anchors if kinds[0] == "point" else anchors[::-1]
            tags = [s.p2l_distance(self.points[pt], self.lines[ln], base)]
        else:
            raise SketchSolveError(
                "A distance to a circle needs a point, a line or a circle. "
                "Select one of those and dimension it again."
            )
        acc = base
        for (_anchor, sign), eid in zip(parts, dim.entities, strict=True):
            if sign == 0:
                continue
            nxt = s.add_param(s.get_param(acc) + sign * self.sk.radius(eid))
            radius = self.radii[eid]
            # nxt = acc + sign * radius
            tags.append(
                s.difference(acc, nxt, radius) if sign > 0 else s.difference(nxt, acc, radius)
            )
            acc = nxt
        tags.append(s.equal(acc, s.add_fixed_param(value)))
        return tuple(tags)

    def _nearest_angle(
        self, l1: str, l2: str, value: float, supplement: bool | None = None
    ) -> float:
        """Signed target angle closest to the current one, so lines do not flip.

        With ``supplement`` set, the measured side is kept: False holds the angle
        between the line directions at ``value``, True holds it at 180 degrees less.
        """
        current = measure_angle(self.sk, l1, l2)
        if supplement is None:
            candidates = [value, -value, math.pi - value, value - math.pi]
        else:
            direct = math.pi - value if supplement else value
            candidates = [direct, -direct]
        return min(candidates, key=lambda c: abs(math.remainder(c - current, 2 * math.pi)))

    # Results --------------------------------------------------------------

    def refs(self, tags: list[Any]) -> list[ConstraintRef]:
        out: list[ConstraintRef] = []
        for tag in tags:
            ref = self.tags.get(int(tag))
            if ref is not None and ref not in out:
                out.append(ref)
        return out

    def write_back(self) -> None:
        for eid, pid in self.points.items():
            info = self.s.get_point(pid)
            point = self.sk.point(eid)
            point.x, point.y = float(info[0]), float(info[1])
        for eid, cid in self.circles.items():
            circle = self.sk.entities[eid]
            assert isinstance(circle, Circle)
            circle.radius = float(self.s.get_circle(cid).radius)


#: Solver kinds of ellipses and partial ellipses (TR41, D1304).
_ELLIPSES = frozenset({"ellipse", "ellipsearc"})


def spline_end_near(sketch: Sketch, spline: Spline, other: str) -> tuple[str, str]:
    """The end point and handle of ``spline`` that meets curve ``other``: an end the
    other curve uses or a coincident relation ties to it, else the nearer end."""
    ends = [(spline.points[0], spline.handles[0]), (spline.points[-1], spline.handles[-1])]
    other_e = sketch.entities[other]
    used = set(entity_points(other_e))
    for rel in sketch.relations:
        if rel.type == "coincident" and other in rel.entities:
            used |= set(rel.entities)
    for pid, hid in ends:
        tied = {
            e
            for r in sketch.relations
            if r.type == "coincident" and pid in r.entities
            for e in r.entities
        }
        if pid in used or tied & used:
            return pid, hid
    from fdcad.core.sketch.topology import curve_points

    samples = curve_points(sketch, other_e)  # type: ignore[arg-type]

    def gap(pid: str) -> float:
        x, y = sketch.xy(pid)
        return min(math.hypot(x - u, y - v) for u, v in samples)

    return min(ends, key=lambda pair: gap(pair[0]))


def _shared_end(sketch: Sketch, a: str, b: str) -> str | None:
    """An end point id that curves ``a`` and ``b`` both use, or None."""

    def ends(eid: str) -> set[str]:
        e = sketch.entities[eid]
        if isinstance(e, Line):
            return {e.p1, e.p2}
        if isinstance(e, Arc | EllipseArc):
            return {e.start, e.end}
        return set()

    common = ends(a) & ends(b)
    return min(common) if common else None


def _offset_distance(sketch: Sketch, src: str, copy: str) -> float:
    """Current distance between an offset copy and its source."""
    a, b = sketch.entities[src], sketch.entities[copy]
    if isinstance(a, Line) and isinstance(b, Line):
        return _point_line_distance(sketch, b.p1, a.id)
    return abs(sketch.radius(copy) - sketch.radius(src))


def _joined_points(sketch: Sketch) -> set[str]:
    """Points that a coincident relation ties to another point."""
    out: set[str] = set()
    for rel in sketch.relations:
        if (
            rel.type == "coincident"
            and not rel.off
            and all(isinstance(sketch.entities.get(e), Point) for e in rel.entities)
        ):
            out.update(rel.entities)
    return out


def _square(sketch: Sketch, line: Line, ps: str, pc: str) -> bool:
    """True when ``pc`` lies square across ``line`` from its end ``ps``."""
    (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
    ux, uy = _unit(x2 - x1, y2 - y1)
    (px, py), (qx, qy) = sketch.xy(ps), sketch.xy(pc)
    return abs((qx - px) * ux + (qy - py) * uy) < 1e-6


def _radial(sketch: Sketch, centre: str, ps: str, pc: str) -> bool:
    """True when ``pc`` lies on the ray from ``centre`` through ``ps``."""
    (cx, cy), (px, py), (qx, qy) = sketch.xy(centre), sketch.xy(ps), sketch.xy(pc)
    ux, uy = _unit(px - cx, py - cy)
    return abs((qx - cx) * uy - (qy - cy) * ux) < 1e-6 and (qx - cx) * ux + (qy - cy) * uy > 0


def arc_length(sketch: Sketch, aid: str) -> float:
    """Length along arc ``aid``: radius times its sweep (TOOL_SPEC T4.1, D515)."""
    arc = sketch.entities[aid]
    if not isinstance(arc, Arc):
        raise SketchSolveError(
            "An arc length dimension needs an arc. Select an arc and dimension it again."
        )
    start, end = (arc.start, arc.end) if arc.ccw else (arc.end, arc.start)
    (cx, cy), (sx, sy), (ex, ey) = sketch.xy(arc.center), sketch.xy(start), sketch.xy(end)
    sweep = (math.atan2(ey - cy, ex - cx) - math.atan2(sy - cy, sx - cx)) % (2 * math.pi)
    return math.hypot(sx - cx, sy - cy) * (sweep or 2 * math.pi)


def measure_angle(sketch: Sketch, l1: str, l2: str) -> float:
    """Signed angle in radians from line ``l1`` to line ``l2``."""
    a, b = sketch.entities[l1], sketch.entities[l2]
    assert isinstance(a, Line) and isinstance(b, Line)
    (ax1, ay1), (ax2, ay2) = sketch.xy(a.p1), sketch.xy(a.p2)
    (bx1, by1), (bx2, by2) = sketch.xy(b.p1), sketch.xy(b.p2)
    ux, uy = _unit(ax2 - ax1, ay2 - ay1)
    vx, vy = _unit(bx2 - bx1, by2 - by1)
    return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)


def measure(sketch: Sketch, dim: Dimension) -> float:
    """Current value of ``dim`` from the sketch geometry (mm or radians)."""
    ents = dim.entities
    ent = [sketch.entities[e] for e in ents]
    if dim.type in ("radius", "diameter"):
        r = sketch.radius(ents[0])
        return r if dim.type == "radius" else 2 * r
    if dim.type == "arc_length":
        return arc_length(sketch, ents[0])
    if dim.type == "path_length":
        return path_length(sketch, ents)
    if dim.type == "angle":
        angle = abs(measure_angle(sketch, ents[0], ents[1]))
        if dim.symmetric:  # TR111 (D2200): twice the smaller angle to the centerline
            return 2 * min(angle, math.pi - angle)
        return math.pi - angle if dim.supplement else angle
    if dim.type == "doubled_distance":
        measured, axis_line = _doubled_parts(sketch, ents)
        return 2 * _point_line_distance(sketch, measured, axis_line)
    if dim.type == "distance" and any(isinstance(e, Circle | Arc) for e in ent):
        parts = [_curve_part(sketch, dim, e) for e in ents]
        base = _base_distance(sketch, [a for a, _sign in parts])
        return base + sum(
            sign * sketch.radius(e) for (_a, sign), e in zip(parts, ents, strict=True) if sign
        )
    if len(ent) == 1 and isinstance(ent[0], Line):
        ents = [ent[0].p1, ent[0].p2]
        ent = [sketch.entities[e] for e in ents]
    if dim.type in ("horizontal_distance", "vertical_distance"):
        axis = 0 if dim.type == "horizontal_distance" else 1
        return abs(sketch.xy(ents[1])[axis] - sketch.xy(ents[0])[axis])
    if all(isinstance(e, Point) for e in ent):
        (x1, y1), (x2, y2) = sketch.xy(ents[0]), sketch.xy(ents[1])
        return math.hypot(x2 - x1, y2 - y1)
    # Point to line, or line to line (measured from the second line's first point).
    points = [e for e in ent if isinstance(e, Point)]
    lines = [e for e in ent if isinstance(e, Line)]
    point = points[0] if points else sketch.point(lines[1].p1)
    line = lines[0]
    (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
    ux, uy = _unit(x2 - x1, y2 - y1)
    return abs((point.x - x1) * uy - (point.y - y1) * ux)


def limit_violations(sketch: Sketch, tol: float = 1e-7) -> set[str]:
    """Limit dimensions (``d<n>``) and segment ends (``r<index>:<end>``) the sketch
    passes now (TR342, D1311)."""
    out: set[str] = set()
    for d in sketch.dimensions:
        if not d.limit or not d.driving or d.off:
            continue
        try:
            m = measure(sketch, d)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        if (d.limit == "min" and m < d.param.value - tol) or (
            d.limit == "max" and m > d.param.value + tol
        ):
            out.add(d.id)
    for i, r in enumerate(sketch.relations):
        if r.type != "on_segment" or r.off or len(r.entities) != 2:
            continue
        p, line = sketch.entities.get(r.entities[0]), sketch.entities.get(r.entities[1])
        if not isinstance(p, Point) or not isinstance(line, Line):
            continue
        (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
        length2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
        if length2 < 1e-18:
            continue
        t = ((p.x - x1) * (x2 - x1) + (p.y - y1) * (y2 - y1)) / length2
        if t < -tol:
            out.add(f"r{i}:{line.p1}")
        elif t > 1 + tol:
            out.add(f"r{i}:{line.p2}")
    return out


def path_length(sketch: Sketch, ids: list[str]) -> float:
    """The total length of lines, arcs and splines ``ids`` (TR45, D1307; TR115, D2201)."""
    total = 0.0
    for eid in ids:
        e = sketch.entities[eid]
        if isinstance(e, Line):
            total += math.dist(sketch.xy(e.p1), sketch.xy(e.p2))
        elif isinstance(e, Arc):
            total += arc_length(sketch, eid)
        elif isinstance(e, Spline):  # TR115 (D2201)
            total += spline_length(sketch, e)
    return total


def length_value(sketch: Sketch, rtype: str, ids: list[str]) -> float:
    """Today's ratio (A over B) or difference (A minus B) of two lines or arcs (TR226)."""

    def length(eid: str) -> float:
        e = sketch.entities[eid]
        if isinstance(e, Line):
            return math.dist(sketch.xy(e.p1), sketch.xy(e.p2))
        return arc_length(sketch, eid)

    a, b = length(ids[0]), length(ids[1])
    if rtype == "length_ratio":
        return a / b if b > 1e-12 else 1.0
    return a - b


def _point_line_distance(sketch: Sketch, pid: str, lid: str) -> float:
    line = sketch.entities[lid]
    assert isinstance(line, Line)
    (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
    px, py = sketch.xy(pid)
    ux, uy = _unit(x2 - x1, y2 - y1)
    return abs((px - x1) * uy - (py - y1) * ux)


def _doubled_parts(sketch: Sketch, ents: list[str]) -> tuple[str, str]:
    """The measured point and the axis line of a doubled distance (T4.1, revolve profiles)."""
    if len(ents) != 2:
        raise SketchSolveError(
            "A doubled distance needs a line or point and an axis line. "
            "Select a line or point and an axis line, then dimension them again."
        )
    first, axis = (sketch.entities.get(e) for e in ents)
    if not isinstance(axis, Line):
        raise SketchSolveError(
            "A doubled distance is measured to an axis line. Pick a line as the axis."
        )
    if isinstance(first, Line):
        return first.p1, axis.id
    if isinstance(first, Point):
        return first.id, axis.id
    raise SketchSolveError(
        "A doubled distance needs a line or point and an axis line. "
        "Select a line or point and an axis line, then dimension them again."
    )


def _curve_part(sketch: Sketch, dim: Dimension, eid: str) -> tuple[str, int]:
    """Where a distance meets ``eid``: (point or line id, sign of the radius to add)."""
    ent = sketch.entities.get(eid)
    if ent is None:
        raise SketchSolveError(
            f"Entity {eid} does not exist. Delete the relation or dimension that names it."
        )
    if isinstance(ent, Circle | Arc):
        side = dim.measure_to.get(eid)
        return ent.center, {"nearest": -1, "farthest": 1}.get(side or "", 0)
    return eid, 0


def _base_distance(sketch: Sketch, anchors: list[str]) -> float:
    """Distance between two points, or a point and a line."""
    ents = [sketch.entities[a] for a in anchors]
    if all(isinstance(e, Point) for e in ents):
        (x1, y1), (x2, y2) = sketch.xy(anchors[0]), sketch.xy(anchors[1])
        return math.hypot(x2 - x1, y2 - y1)
    points = [a for a, e in zip(anchors, ents, strict=True) if isinstance(e, Point)]
    lines = [a for a, e in zip(anchors, ents, strict=True) if isinstance(e, Line)]
    if len(points) == 1 and len(lines) == 1:
        return _point_line_distance(sketch, points[0], lines[0])
    raise SketchSolveError(
        "A distance to a circle needs a point, a line or a circle. "
        "Select one of those and dimension it again."
    )


def _build(
    sketch: Sketch,
    start: dict[str, tuple[float, float]] | None = None,
    active: set[str] | frozenset[str] = frozenset(),
) -> _Builder:
    b = _Builder(sketch, start, active)
    b.add_geometry()
    for index, rel in enumerate(sketch.relations):
        if not rel.off:  # switched off: kept, but no effect (TR109); indexes stay
            b.add_relation(index, rel)
    for dim in sketch.dimensions:
        b.add_dimension(dim)
    return b


def _solved(code: Any) -> bool:
    return code in (planegcs.SolveStatus.Success, planegcs.SolveStatus.Converged)


def drag(
    sketch: Sketch,
    targets: dict[str, tuple[float, float]],
    hold: Iterable[str] = (),
) -> bool:
    """Move points toward ``targets`` (point id to x, y) while keeping every relation.

    First the points are held at their targets. If that conflicts with the
    sketch (the points are not free to go there), the solver starts from the
    targets instead and finds the nearest valid position. Positions change
    only when a solve succeeds. Returns True when anything moved. Points in
    ``hold`` stay where they are (TR238, D1706).
    """
    group = _group_of(sketch, set(targets))
    held = [p for p in hold if p not in targets]
    b = _build(group)
    for pid, (x, y) in targets.items():
        b.s.fix_point(b.points[pid], x, y)
    _fix_held(b, group, held)
    diagnosis = b.s.diagnose()
    # Only redundancy in the user's relations counts, as in ``solve``: the solver's own
    # helper rules (an arc's end on its circle beside a pinned offset end) can repeat
    # one another without anything being wrong (TR391, D945).
    redundant = b.refs(list(diagnosis.redundant))
    if not diagnosis.conflicting and not redundant and _solved(b.s.solve()):
        b.write_back()
        _hold_limits(group)
        return True
    b = _build(group, targets)
    _fix_held(b, group, held)
    if not _solved(b.s.solve()):
        return False
    b.write_back()
    _hold_limits(group)
    return True


def _fix_held(b: Any, group: Sketch, held: list[str]) -> None:
    """Pin the ``held`` points of the drag's group where they are now."""
    for pid in held:
        if pid in b.points and pid in group.entities:
            x, y = group.xy(pid)
            b.s.fix_point(b.points[pid], x, y)


def _hold_limits(sketch: Sketch) -> None:
    """After a drag, pull back what passed a limit or a segment end (TR342)."""
    passed = limit_violations(sketch)
    if passed:
        b = _build(sketch, active=passed)
        if _solved(b.s.solve()):
            b.write_back()


def _points_of(e: Entity) -> list[str]:
    return entity_points(e)


def _components(sketch: Sketch) -> list[Sketch]:
    """Split a sketch into groups that no relation or dimension connects."""
    parent = {eid: eid for eid in sketch.entities}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(ids: list[str]) -> None:
        known = [i for i in ids if i in parent]
        for other in known[1:]:
            parent[find(other)] = find(known[0])

    for e in sketch.entities.values():
        if not isinstance(e, Point):
            join([e.id, *_points_of(e)])
    for rel in sketch.relations:
        join(rel.entities)
    for dim in sketch.dimensions:
        join(dim.entities)
    groups: dict[str, set[str]] = {}
    for eid in sketch.entities:
        groups.setdefault(find(eid), set()).add(eid)
    out = []
    for ids in groups.values():
        out.append(
            Sketch(
                entities={k: v for k, v in sketch.entities.items() if k in ids},
                relations=[r for r in sketch.relations if set(r.entities) <= ids],
                dimensions=[d for d in sketch.dimensions if set(d.entities) <= ids],
            )
        )
    return out


def _group_of(sketch: Sketch, ids: set[str]) -> Sketch:
    """The connected groups that contain ``ids``, sharing the sketch's entity objects."""
    parts = [p for p in _components(sketch) if ids & set(p.entities)]
    if len(parts) == 1:
        return parts[0]
    return Sketch(
        entities={k: v for p in parts for k, v in p.entities.items()},
        relations=[r for p in parts for r in p.relations],
        dimensions=[d for p in parts for d in p.dimensions],
    )


def _coincident_groups(sketch: Sketch) -> dict[str, str]:
    """Each point id mapped to one representative of its coincident group."""
    parent = {e.id: e.id for e in sketch.entities.values() if isinstance(e, Point)}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for rel in sketch.relations:
        if rel.type == "coincident" and not rel.off and len(rel.entities) == 2:
            a, b = rel.entities
            if a in parent and b in parent:
                parent[find(b)] = find(a)
    return {pid: find(pid) for pid in parent}


def defined_entities(sketch: Sketch) -> set[str]:
    """Ids of entities whose position and size the sketch fully sets.

    A point is fully defined when holding it in place removes no freedom.
    A curve is fully defined when all its points are (and a circle's radius).
    Each connected group is checked on its own, which keeps this fast.
    """
    out: set[str] = set()
    for part in _components(sketch):
        out |= _defined_in(part)
    return out


def _defined_in(sketch: Sketch) -> set[str]:
    if not any(not r.off for r in sketch.relations) and not any(
        d.driving and not d.off for d in sketch.dimensions
    ):
        return set()
    try:
        base = _build(sketch).s.diagnose().dof
    except SketchSolveError:
        return set()
    if base <= 0:
        return set(sketch.entities)
    # Items that can be held: points (two freedoms) and circle radii (one).
    # Points joined by a coincident relation move together, so one stands for all.
    alias = _coincident_groups(sketch)
    items: list[tuple[str, str, int]] = [
        ("point", e.id, 2)
        for e in sketch.entities.values()
        if isinstance(e, Point) and alias[e.id] == e.id
    ]
    items += [("radius", e.id, 1) for e in sketch.entities.values() if isinstance(e, Circle)]

    def removed(group: list[tuple[str, str, int]]) -> int:
        b = _build(sketch)
        for kind, eid, _ in group:
            if kind == "point":
                x, y = sketch.xy(eid)
                b.s.fix_point(b.points[eid], x, y)
            else:
                circle = sketch.entities[eid]
                assert isinstance(circle, Circle)
                b.s.set_circle_radius(b.circles[eid], circle.radius)
        return int(base - b.s.diagnose().dof)

    held: set[str] = set()

    def classify(group: list[tuple[str, str, int]]) -> None:
        # Holding a group removes no freedom: every item in it is already set.
        # Holding it removes all of its freedom: none of it is set.
        r = removed(group)
        if r == 0:
            held.update(f"{kind}:{eid}" for kind, eid, _ in group)
        elif r == sum(w for _, _, w in group) or len(group) == 1:
            return
        else:
            half = len(group) // 2
            classify(group[:half])
            classify(group[half:])

    classify(items)
    roots = {key[6:] for key in held if key.startswith("point:")}
    points = {pid for pid, root in alias.items() if root in roots}
    out = set(points)
    for e in sketch.entities.values():
        if isinstance(e, Point):
            continue
        if set(_points_of(e)) <= points and (not isinstance(e, Circle) or f"radius:{e.id}" in held):
            out.add(e.id)
    return out


def solve(sketch: Sketch) -> SolveResult:
    """Solve ``sketch`` in place and report its status.

    Positions are written back only when the solver succeeds. Raises
    SketchSolveError when a relation or dimension names unsuitable entities.
    """
    active: set[str] = set()
    for _round in range(8):
        b = _build(sketch, active=active)
        diagnosis = b.s.diagnose()
        conflicting = b.refs(list(diagnosis.conflicting))
        redundant = b.refs(list(diagnosis.redundant))
        solved = _solved(b.s.solve())
        if solved:
            b.write_back()
        # TR342 (D1311): limits and segment ends the result passes are held, then the
        # sketch is solved again from there.
        passed = limit_violations(sketch) - active if solved else set()
        if not passed:
            break
        active |= passed

    if conflicting or redundant or not solved:
        status = SketchStatus.OVER  # unsolvable shows like over defined (TOOL_SPEC T1.4.1)
    elif diagnosis.dof == 0:
        status = SketchStatus.FULL
    else:
        status = SketchStatus.UNDER

    message = ""
    if conflicting:
        message = "Some relations or dimensions conflict. Delete or change the highlighted items."
    elif redundant:
        message = "Some relations or dimensions are not needed. Delete the highlighted items."
    elif not solved:
        message = "The sketch could not be solved. Undo the last change or adjust the dimensions."

    return SolveResult(
        solved=solved,
        status=status,
        dof=max(diagnosis.dof, 0),
        conflicting=conflicting,
        redundant=redundant,
        measured={d.id: measure(sketch, d) for d in sketch.dimensions},
        message=message,
    )
