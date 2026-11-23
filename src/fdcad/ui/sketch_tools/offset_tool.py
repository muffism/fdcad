"""Offset tool (PHASE2_SPEC P2.8 item 1). Pure Python, no Qt."""

from __future__ import annotations

import copy
import math

from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.ops.geom import Geo, Vec, dist, geo
from fdcad.core.sketch.ops.offset import (
    CAPS,
    CORNERS,
    OffsetError,
    chain_from,
    chains,
    corner_arcs,
    distance_to,
    freeform_on_chain,
    offset,
    plan,
    side_of,
)
from fdcad.core.sketch.ops.pieces import Report
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.geometry import straight_polyline
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import PickTool, add_curve_preview
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview

CAP_LABELS = {"none": "None", "arcs": "Arcs", "lines": "Lines"}
CORNER_LABELS = {"sharp": "Sharp", "round": "Round"}  # TR391 (D945)

#: Select chain stopped at a spline or partial ellipse (D706).
OFFSET_LEAVES_FREEFORM = (
    "The chain goes on into a spline or ellipse, which Offset cannot use, so the offset "
    "stops there. Offset the spline by hand, or replace it with lines and arcs."
)


class OffsetTool(PickTool):
    """Click curves (or a straight part edge or round part edge), then click the side.

    The distance follows the cursor until a distance is typed in the panel.
    """

    name, label = "offset", "Offset"
    options = (
        Option("distance", "Distance", "length", tip="Type a distance to stop the drag."),
        Option("add_dimension", "Add dimension", "bool"),
        Option("reverse", "Reverse", "bool"),
        Option("select_chain", "Select chain", "bool"),
        Option("both", "Both directions", "bool"),
        Option("base_construction", "Make base construction", "bool"),
        Option("offset_construction", "Make offset construction", "bool"),
        Option("cap", "Cap ends", "choice", tuple((c, CAP_LABELS[c]) for c in CAPS)),
        Option(
            "corners",
            "Outside corners",
            "choice",
            tuple((c, CORNER_LABELS[c]) for c in CORNERS),
            tip="Sharp extends the curves to meet; Round puts an arc round each outside corner.",
        ),
        Option("place", "Place Offset", "button"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.distance = 5.0
        #: The distance was typed, so the cursor only picks the side.
        self.locked = False
        self.add_dimension = False
        self.reverse = False
        self.select_chain = True
        self.both = False
        self.base_construction = False
        self.offset_construction = False
        self.cap = "none"
        self.corners = "sharp"
        #: Picked sketch curves.
        self.picks: list[str] = []
        #: Picked part edges: straight ones as two points, round ones as centre and radius.
        self.model_picks: list[tuple[str, Vec, Vec | float]] = []
        #: Where the side was last shown.
        self.side_at: Vec | None = None

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to click next."""
        if not self.picks and not self.model_picks:
            return "Click the curves or part edges to offset."
        return "Move to the side and click to place, or click more curves."

    @property
    def busy(self) -> bool:
        """True while curves are picked."""
        return bool(self.picks or self.model_picks)

    def cancel(self) -> bool:
        """Escape drops the picks, then ends the tool."""
        if self.busy:
            self.picks, self.model_picks = [], []
            return False
        return True

    def option_changed(self, key: str) -> bool:
        """Typing a distance locks it; Place Offset uses the last side shown."""
        if key == "distance":
            self.locked = True
        if key == "place" and self.side_at is not None:
            return self._place(self.side_at)
        if key == "select_chain" and self.select_chain:
            self.picks = self._grow(self.picks)
        return False

    def _grow(self, ids: list[str]) -> list[str]:
        out: list[str] = []
        for cid in ids:
            for c in chain_from(self.edit.sketch, cid):
                if c not in out:
                    out.append(c)
        if freeform_on_chain(self.edit.sketch, out):
            self.message = OFFSET_LEAVES_FREEFORM
        return out

    def hover(self, snap: Snap) -> Snap:
        """Track the curve under the cursor and the dragged distance."""
        snap = super().hover(snap)
        if self.busy and self.hot is None:
            self.side_at = snap.xy
            if not self.locked:
                d = self._drag_distance(snap.xy)
                if d is not None and d > 1e-6:
                    self.distance = round(d, 6)
        return snap

    def _drag_distance(self, at: Vec) -> float | None:
        sk, ids = self._source()
        try:
            groups = chains(sk, ids)
        except OffsetError:
            return None
        if not groups:
            return None
        return min(distance_to(sk, chain, at) for chain, _c in groups)

    def _model_at(self, at: Vec) -> tuple[str, Vec, Vec | float] | None:
        for poly in self.model_lines:
            seg = straight_polyline(poly)
            if seg is None:
                continue
            a, b = seg
            g = Geo("line", a, b)
            t = g.param(at)
            if 0 <= t <= 1 and dist(at, g.at(t)) <= self.tolerance:
                return ("line", a, b)
        for c, r in self.model_circles:
            if abs(dist(at, c) - r) <= self.tolerance:
                return ("circle", c, r)
        return None

    def click(self, snap: Snap) -> bool:
        """Pick a curve, or place the offset on the clicked side."""
        self.hover(snap)
        cid = self.hot
        if cid is not None:
            new = self._grow([cid]) if self.select_chain else [cid]
            if cid in self.picks:
                self.picks = [p for p in self.picks if p not in new]
            else:
                self.picks += [n for n in new if n not in self.picks]
            return False
        model = self._model_at(snap.xy)
        if model is not None:
            self.model_picks.append(model)
            return False
        if not self.busy:
            return False
        return self._place(snap.xy)

    def _source(self) -> tuple[Sketch, list[str]]:
        """A scratch sketch with fixed copies of the picked part edges, and the ids to
        offset (for the preview)."""
        if not self.model_picks:
            return self.edit.sketch, list(self.picks)
        sk = copy.deepcopy(self.edit.sketch)
        return sk, list(self.picks) + _add_model(sk, self.model_picks)

    def _place(self, at: Vec) -> bool:
        def change() -> Report | None:
            sk = self.edit.sketch
            ids = list(self.picks) + _add_model(sk, self.model_picks)
            result = offset(
                sk,
                ids,
                self.distance,
                at,
                self.reverse,
                self.both,
                self.base_construction,
                self.offset_construction,
                self.cap,
                self.add_dimension,
                self.corners,
            )
            self.drawn = result.copies + result.caps
            return result.report

        error = ""
        self.edit.checkpoint()
        try:
            change()
        except OffsetError as exc:
            error = str(exc)
        if error:
            self.edit.discard_checkpoint()
            self.message = error
            return False
        self.picks, self.model_picks = [], []
        self.locked = False
        return True

    def preview(self) -> Preview:
        """The picks highlighted, and the offset at the cursor."""
        out = super().preview()
        sk, ids = self._source()
        for cid in ids:
            if cid in sk.entities:
                add_curve_preview(out, sk, cid)
        if not ids or self.side_at is None:
            return out
        try:
            for chain, closed in chains(sk, ids):
                side = side_of(sk, chain, self.side_at) * (-1.0 if self.reverse else 1.0)
                for sd in [side, -side] if self.both else [side]:
                    d = sd * self.distance
                    pieces = plan(sk, chain, closed, d, self.corners)
                    for g, s, e, _c in pieces:
                        _add_piece(out, g, s, e)
                    if pieces:  # TR341 item 2 (D1705): which side the offset goes
                        out.arrows += side_arrow(sk, [p.cid for p in chain], pieces[0][1])
                    if self.corners == "round":
                        for arc in corner_arcs(sk, chain, closed, d):
                            r = dist(arc.centre, arc.start)
                            _add_piece(
                                out, Geo("arc", arc.centre, r=r, sweep=math.pi), arc.start, arc.end
                            )
        except OffsetError:
            pass
        return out


def side_arrow(sk: Sketch, ids: list[str], to: Vec) -> list[tuple[Vec, Vec]]:
    """An arrow from the chain's nearest point to ``to`` (a point of the offset), so the
    offset side shows (TR341 item 2, D1705)."""
    best: tuple[float, Vec] | None = None
    for cid in ids:
        g = geo(sk, cid)
        t = g.param(to)
        ts = [t] if g.inside(t) else [0.0, g.sweep]
        p = min((g.at(u) for u in ts), key=lambda q: dist(q, to))
        d = dist(p, to)
        if best is None or d < best[0]:
            best = (d, p)
    if best is None or best[0] < 1e-9:
        return []
    foot = best[1]
    return [(foot, (to[0] - foot[0], to[1] - foot[1]))]


def _add_piece(out: Preview, g: Geo, s: Vec, e: Vec) -> None:
    if g.kind == "line":
        out.lines.append((s, e))
    elif g.kind == "circle":
        out.circles.append((g.a, g.r))
    else:
        a0 = math.atan2(s[1] - g.a[1], s[0] - g.a[0])
        a1 = math.atan2(e[1] - g.a[1], e[0] - g.a[0])
        lo, hi = (a0, a1) if (a1 - a0) % (2 * math.pi) <= g.sweep + 1e-6 else (a1, a0)
        sweep = (hi - lo) % (2 * math.pi)
        out.arcs.append((g.a, g.r, lo, lo + sweep))


def _add_model(sk: Sketch, picks: list[tuple[str, Vec, Vec | float]]) -> list[str]:
    """Fixed construction copies of part edges (D113, D116 item 3); returns their ids."""
    ids = []
    for kind, a, b in picks:
        if kind == "line":
            assert isinstance(b, tuple)
            lid = sk.add_line(a[0], a[1], b[0], b[1], True)
            sk.relate("fixed", lid)
            ids.append(lid)
        else:
            assert isinstance(b, float)
            cid = sk.add_circle(a[0], a[1], b, True)
            sk.relate("fixed", cid)
            ids.append(cid)
    return ids
