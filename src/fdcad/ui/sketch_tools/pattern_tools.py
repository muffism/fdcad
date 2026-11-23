"""Linear and circular sketch pattern tools (PHASE2_SPEC P2.8 items 8 and 9). No Qt."""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Line, Point
from fdcad.core.sketch.ops.geom import Vec, dist, distance, geo
from fdcad.core.sketch.ops.pattern import (
    PatternError,
    anchor_of,
    circular,
    instance_places_linear,
    linear,
)
from fdcad.core.sketch.ops.pieces import Report
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.geometry import straight_polyline
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import PickTool, add_curve_preview
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview


class _PatternTool(PickTool):
    """Shared picking: click curves to pattern, click an instance mark to skip it."""

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.picks: list[str] = []
        #: The next clicked item fills a panel pick ("direction1", "centre"), or "".
        self.pick_for = ""

    @property
    def busy(self) -> bool:
        """True while curves are picked."""
        return bool(self.picks)

    def cancel(self) -> bool:
        """Escape drops the picks, then ends the tool."""
        if self.picks:
            self.picks, self.pick_for = [], ""
            self.reset_skips()
            return False
        return True

    def reset_skips(self) -> None:
        """Forget the skipped instances."""

    def places(self) -> dict[object, Vec]:
        """Instance keys and where their anchors go; the original's key comes first."""
        return {}

    def toggle_skip(self, key: object) -> None:
        """Skip an instance, or bring it back."""

    def click(self, snap: Snap) -> bool:
        """Pick, fill a panel pick, or toggle an instance."""
        self.hover(snap)
        at = snap.xy
        if self.pick_for and self.fill_pick(at):
            self.pick_for = ""
            return False
        cid = self.hot
        # A curve closer than the mark wins: a mark can sit on the picked shape itself.
        on_curve = distance(self.edit.sketch, cid, at) if cid is not None else math.inf
        if self.picks:
            items = list(self.places().items())
            for key, place in items[1:]:
                d = dist(place, at)
                if d <= self.tolerance * 1.5 and d <= on_curve:
                    self.toggle_skip(key)
                    return False
        if cid is None:
            return False
        if cid in self.picks:
            self.picks.remove(cid)
        else:
            self.picks.append(cid)
        return False

    def fill_pick(self, at: Vec) -> bool:
        """Use the clicked item for the pending panel pick. False when it does not fit."""
        return False

    def make(self) -> Report | None:
        """Add the pattern."""
        return None

    def option_changed(self, key: str) -> bool:
        """Make Pattern adds it; the pick buttons wait for a click."""
        if key == "make":
            if not self.picks:
                self.message = "Pick the curves to pattern first."
                return False
            ok = self._apply()
            if ok:
                self.picks = []
                self.reset_skips()
            return ok
        if key.startswith("pick_"):
            self.pick_for = key[5:]
        if key.startswith("count"):
            self.reset_skips()
        return False

    def _apply(self) -> bool:
        error = ""
        self.edit.checkpoint()
        try:
            self.make()
        except PatternError as exc:
            error = str(exc)
        if error:
            self.edit.discard_checkpoint()
            self.message = error
            return False
        return True

    def preview(self) -> Preview:
        """The picks, the instances and a mark at each instance (crossed when skipped)."""
        out = super().preview()
        sk = self.edit.sketch
        seed = Preview()
        for cid in self.picks:
            if cid in sk.entities and not isinstance(sk.entities[cid], Point):
                add_curve_preview(seed, sk, cid)
        out.lines += seed.lines
        out.circles += seed.circles
        out.arcs += seed.arcs
        if not self.picks:
            return out
        items = list(self.places().items())
        for key, place in items[1:]:
            if self.skipped(key):
                r = self.tolerance
                out.lines += [
                    ((place[0] - r, place[1] - r), (place[0] + r, place[1] + r)),
                    ((place[0] - r, place[1] + r), (place[0] + r, place[1] - r)),
                ]
                continue
            out.points.append(place)
            self.add_instance(out, seed, items[0][1], key, place)
        # TR341 item 2 (D1705): the way each direction runs, from the original.
        places = dict(items)
        start = items[0][1] if items else None
        for key in self.arrow_keys():
            end = places.get(key)
            if start is not None and end is not None and dist(end, start) > 1e-9:
                out.arrows.append((start, (end[0] - start[0], end[1] - start[1])))
        return out

    def arrow_keys(self) -> list[object]:
        """The instances the direction arrows point at."""
        return []

    def skipped(self, key: object) -> bool:
        """True for a skipped instance."""
        return False

    def add_instance(
        self, out: Preview, seed: Preview, origin: Vec, key: object, place: Vec
    ) -> None:
        """Draw one instance of the seed."""


class LinearPatternTool(_PatternTool):
    """Linear sketch pattern (P2.8 item 8)."""

    name, label = "linear_pattern", "Linear Sketch Pattern"
    options = (
        Option("count1", "Direction 1 instances", "int", low=1, high=500),
        Option("spacing1", "Direction 1 spacing", "length"),
        Option("angle1", "Direction 1 angle", "angle"),
        Option("reverse1", "Reverse direction 1", "bool"),
        Option("pick_direction1", "Pick Direction 1", "button"),
        Option("count2", "Direction 2 instances", "int", low=1, high=500),
        Option("spacing2", "Direction 2 spacing", "length"),
        Option("angle2", "Direction 2 angle", "angle"),
        Option("reverse2", "Reverse direction 2", "bool"),
        Option("add_dimensions", "Add spacing dimension", "bool"),
        Option("fix_direction", "Fix direction", "bool"),
        Option("make", "Make Pattern", "button"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.count1, self.spacing1, self.angle1, self.reverse1 = 3, 10.0, 0.0, False
        self.count2, self.spacing2, self.angle2, self.reverse2 = 1, 10.0, math.pi / 2, False
        self.add_dimensions = True
        self.fix_direction = True
        self.direction_line: str | None = None
        #: A straight model edge picked for Direction 1 (TR107, D1308): its two ends.
        self.direction_model: tuple[Vec, Vec] | None = None
        self.skip: set[tuple[int, int]] = set()

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to do next."""
        if self.pick_for:
            return "Click a line for the direction."
        if not self.picks:
            return "Click the curves to pattern."
        return "Set the panel values, click an instance mark to skip it, then Make Pattern."

    def _angles(self) -> tuple[float, float]:
        a1 = self.angle1 + (math.pi if self.reverse1 else 0.0)
        a2 = self.angle2 + (math.pi if self.reverse2 else 0.0)
        return a1, a2

    def places(self) -> dict[object, Vec]:
        """Grid places, (0, 0) first."""
        if not self.picks or not all(p in self.edit.sketch.entities for p in self.picks):
            return {}
        anchor = self.edit.sketch.xy(anchor_of(self.edit.sketch, self.picks))
        a1, a2 = self._angles()
        grid = instance_places_linear(
            anchor, self.count1, self.spacing1, a1, self.count2, self.spacing2, a2
        )
        return {key: place for key, place in grid.items()}

    def reset_skips(self) -> None:
        """Forget skipped places."""
        self.skip = set()

    def toggle_skip(self, key: object) -> None:
        """Skip a grid place or bring it back."""
        assert isinstance(key, tuple)
        self.skip ^= {key}

    def skipped(self, key: object) -> bool:
        """True for a skipped grid place."""
        return key in self.skip

    def arrow_keys(self) -> list[object]:
        """Direction 1 and, with more than one row, Direction 2."""
        return [(1, 0), (0, 1)]

    def fill_pick(self, at: Vec) -> bool:
        """A clicked line sets Direction 1; so does a straight model edge (TR107)."""
        cid = self.curve_at(at)
        if cid is None or not isinstance(self.edit.sketch.entities[cid], Line):
            edge = self._model_edge(at)
            if edge is None:
                return False
            a, b = edge
            self.angle1 = math.atan2(b[1] - a[1], b[0] - a[0])
            self.direction_line, self.direction_model = None, edge
            return True
        g = geo(self.edit.sketch, cid)
        self.angle1 = math.atan2(g.b[1] - g.a[1], g.b[0] - g.a[0])
        self.direction_line, self.direction_model = cid, None
        return True

    def _model_edge(self, at: Vec) -> tuple[Vec, Vec] | None:
        """The straight model edge (projected onto the sketch) under ``at``, or None."""
        for poly in self.model_lines:
            seg = straight_polyline(poly)
            if seg is None:
                continue
            a, b = seg
            length = dist(a, b)
            if length < 1e-9:
                continue
            ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            t = (at[0] - a[0]) * ux + (at[1] - a[1]) * uy
            foot = (a[0] + ux * t, a[1] + uy * t)
            if -self.tolerance <= t <= length + self.tolerance and dist(foot, at) <= self.tolerance:
                return seg
        return None

    def make(self) -> Report | None:
        """Add the grid."""
        a1, a2 = self._angles()
        if self.direction_model is not None and self.fix_direction:
            # A model edge direction is held by a fixed copy of the edge (D116 item 3).
            self.direction_line = self.edit.reference_line(*self.direction_model)
        result = linear(
            self.edit.sketch,
            self.picks,
            self.count1,
            self.spacing1,
            a1,
            self.count2,
            self.spacing2,
            a2,
            self.skip,
            self.add_dimensions,
            self.fix_direction,
            self.direction_line,
        )
        self.drawn = result.copies
        return Report()

    def add_instance(
        self, out: Preview, seed: Preview, origin: Vec, key: object, place: Vec
    ) -> None:
        """A shifted copy of the seed."""
        dx, dy = place[0] - origin[0], place[1] - origin[1]
        out.lines += [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)) for a, b in seed.lines]
        out.circles += [((c[0] + dx, c[1] + dy), r) for c, r in seed.circles]
        out.arcs += [((c[0] + dx, c[1] + dy), r, a0, a1) for c, r, a0, a1 in seed.arcs]


class CircularPatternTool(_PatternTool):
    """Circular sketch pattern (P2.8 item 9)."""

    name, label = "circular_pattern", "Circular Sketch Pattern"
    options = (
        Option("cx", "Center X", "length"),
        Option("cy", "Center Y", "length"),
        Option("pick_centre", "Pick Center Point", "button"),
        Option("radius", "Radius", "length"),  # TR107 (D1308)
        Option("start_angle", "Angle from center", "angle"),
        Option("count", "Instances", "int", low=2, high=500),
        Option("total", "Total angle", "angle"),
        Option("equal_spacing", "Equal spacing", "bool"),
        Option("reverse", "Reverse", "bool"),
        Option("add_dimensions", "Add radius and angle dimensions", "bool"),
        Option("make", "Make Pattern", "button"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.cx, self.cy = 0.0, 0.0
        #: A picked point the centre is tied to; the sketch origin by default.
        self.centre_point: str | None = _origin(edit)
        self.count = 4
        self.total = 2 * math.pi
        self.equal_spacing = True
        self.reverse = False
        self.add_dimensions = True
        self.skip: set[int] = set()
        #: The seed's distance and direction from the centre (TR107, D1308).
        self.radius = 0.0
        self.start_angle = 0.0

    def _sync_polar(self) -> None:
        """Radius and Angle from center follow the centre and the picks."""
        sk = self.edit.sketch
        if not self.picks or not all(p in sk.entities for p in self.picks):
            return
        ax, ay = sk.xy(anchor_of(sk, self.picks))
        self.radius = math.hypot(ax - self.cx, ay - self.cy)
        self.start_angle = math.atan2(ay - self.cy, ax - self.cx)

    def click(self, snap: Snap) -> bool:
        """Pick as the other pattern tools; then show the radius and angle."""
        out = super().click(snap)
        self._sync_polar()
        return out

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to do next."""
        if self.pick_for:
            return "Click the center point."
        if not self.picks:
            return "Click the curves to pattern."
        return "Set the panel values, click an instance mark to skip it, then Make Pattern."

    def option_changed(self, key: str) -> bool:
        """Typed centre values let go of a picked centre point. A typed radius or angle
        moves the centre so the picks sit there (TR107)."""
        if key in ("cx", "cy"):
            self.centre_point = None
            self._sync_polar()
        if key in ("radius", "start_angle"):
            sk = self.edit.sketch
            if not self.picks or not all(p in sk.entities for p in self.picks):
                self.message = "Pick the curves to pattern first."
                return False
            if float(self.radius) <= 0:
                self.message = "The radius must be greater than zero. Enter a positive length."
                self._sync_polar()
                return False
            ax, ay = sk.xy(anchor_of(sk, self.picks))
            self.cx = ax - float(self.radius) * math.cos(float(self.start_angle))
            self.cy = ay - float(self.radius) * math.sin(float(self.start_angle))
            self.centre_point = None
        return super().option_changed(key)

    def _step(self) -> float:
        full = abs(abs(self.total) - 2 * math.pi) < 1e-9
        if self.equal_spacing:
            step = self.total / (self.count if full else max(self.count - 1, 1))
        else:
            step = self.total
        return -step if self.reverse else step

    def places(self) -> dict[object, Vec]:
        """Instance anchors, the original first."""
        sk = self.edit.sketch
        if not self.picks or not all(p in sk.entities for p in self.picks):
            return {}
        ax, ay = sk.xy(anchor_of(sk, self.picks))
        step = self._step()
        out: dict[object, Vec] = {}
        for k in range(self.count):
            c, s = math.cos(k * step), math.sin(k * step)
            x, y = ax - self.cx, ay - self.cy
            out[k] = (self.cx + c * x - s * y, self.cy + s * x + c * y)
        return out

    def reset_skips(self) -> None:
        """Forget skipped instances."""
        self.skip = set()

    def toggle_skip(self, key: object) -> None:
        """Skip an instance or bring it back."""
        assert isinstance(key, int)
        self.skip ^= {key}

    def skipped(self, key: object) -> bool:
        """True for a skipped instance."""
        return key in self.skip

    def arrow_keys(self) -> list[object]:
        """The next instance, so the turning direction shows."""
        return [1]

    def fill_pick(self, at: Vec) -> bool:
        """A clicked point (or a circle's centre) becomes the centre."""
        sk = self.edit.sketch
        best: tuple[float, str] | None = None
        for e in sk.entities.values():
            if isinstance(e, Point):
                d = dist((e.x, e.y), at)
                if d <= self.tolerance and (best is None or d < best[0]):
                    best = (d, e.id)
        if best is None:
            return False
        self.centre_point = best[1]
        self.cx, self.cy = sk.xy(best[1])
        self._sync_polar()
        return True

    def make(self) -> Report | None:
        """Add the instances."""
        centre = self.centre_point if self.centre_point in self.edit.sketch.entities else None
        result = circular(
            self.edit.sketch,
            self.picks,
            (self.cx, self.cy),
            self.count,
            self.total,
            self.equal_spacing,
            self.reverse,
            self.skip,
            self.add_dimensions,
            centre,
        )
        self.drawn = result.copies
        return Report()

    def add_instance(
        self, out: Preview, seed: Preview, origin: Vec, key: object, place: Vec
    ) -> None:
        """A turned copy of the seed."""
        assert isinstance(key, int)
        ang = key * self._step()
        c, s = math.cos(ang), math.sin(ang)

        def turn(p: Vec) -> Vec:
            x, y = p[0] - self.cx, p[1] - self.cy
            return self.cx + c * x - s * y, self.cy + s * x + c * y

        out.lines += [(turn(a), turn(b)) for a, b in seed.lines]
        out.circles += [(turn(cc), r) for cc, r in seed.circles]
        out.arcs += [(turn(cc), r, a0 + ang, a1 + ang) for cc, r, a0, a1 in seed.arcs]


def _origin(edit: SketchEdit) -> str | None:
    sk = edit.sketch
    fixed = {r.entities[0] for r in sk.relations if r.type == "fixed" and len(r.entities) == 1}
    for e in sk.entities.values():
        if isinstance(e, Point) and e.id in fixed and abs(e.x) < 1e-12 and abs(e.y) < 1e-12:
            return e.id
    return None
