"""Mirror tool (PHASE2_SPEC P2.8 item 4). Pure Python, no Qt."""

from __future__ import annotations

import math
from collections.abc import Callable

from fdcad.core.sketch.model import Line
from fdcad.core.sketch.ops.geom import Geo, Vec, dist
from fdcad.core.sketch.ops.mirror import mirror, reflect
from fdcad.core.sketch.ops.pieces import Report
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.geometry import straight_polyline
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import PickTool, add_curve_preview
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview


class MirrorTool(PickTool):
    """Click the curves to mirror, then the mirror line.

    A click on a centerline (a construction line) or a straight part edge, once
    something is picked, is taken as the mirror line. Pick Mirror Line makes the
    next clicked line the mirror line, whatever it is.
    """

    name, label = "mirror", "Mirror"
    options = (
        Option("copy", "Copy", "bool", tip="Off replaces the picked curves."),
        Option("pick_axis", "Pick Mirror Line", "button"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.copy = True
        self.picks: list[str] = []
        #: The next clicked line is the mirror line.
        self.axis_next = False

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to click next."""
        if not self.picks:
            return "Click the curves to mirror."
        if self.axis_next:
            return "Click the mirror line."
        return "Click more curves, or a centerline or straight part edge to mirror about."

    @property
    def busy(self) -> bool:
        """True while curves are picked."""
        return bool(self.picks)

    def cancel(self) -> bool:
        """Escape drops the picks, then ends the tool."""
        if self.picks:
            self.picks, self.axis_next = [], False
            return False
        return True

    def option_changed(self, key: str) -> bool:
        """Pick Mirror Line: the next clicked line is the mirror line."""
        if key == "pick_axis" and self.picks:
            self.axis_next = True
        return False

    def _model_line(self, at: Vec) -> tuple[Vec, Vec] | None:
        for poly in self.model_lines:
            seg = straight_polyline(poly)
            if seg is None:
                continue
            g = Geo("line", *seg)
            t = g.param(at)
            if 0 <= t <= 1 and dist(at, g.at(t)) <= self.tolerance:
                return seg
        return None

    def click(self, snap: Snap) -> bool:
        """Pick a curve, or mirror about the clicked line."""
        self.hover(snap)
        cid = self.hot
        sk = self.edit.sketch
        if cid is not None:
            ent = sk.entities[cid]
            is_axis = isinstance(ent, Line) and (ent.construction or self.axis_next)
            if self.picks and is_axis and cid not in self.picks:
                return self._mirror(lambda: cid)
            if cid in self.picks:
                self.picks.remove(cid)
            else:
                self.picks.append(cid)
            return False
        model = self._model_line(snap.xy) if self.picks else None
        if model is not None:
            a, b = model
            return self._mirror(lambda: self.edit.reference_line(a, b))
        return False

    def _mirror(self, axis_of: Callable[[], str]) -> bool:
        picks = list(self.picks)

        def change() -> Report | None:
            axis = axis_of()
            report = mirror(self.edit.sketch, picks, axis, self.copy)
            if report is not None:
                self.drawn = list(report.entities)
            return report

        ok = self.apply(change, "Pick a straight line to mirror about.")
        if ok:
            self.picks, self.axis_next = [], False
        return ok

    def preview(self) -> Preview:
        """The picks, and their mirror image about the hovered line."""
        out = super().preview()
        sk = self.edit.sketch
        for cid in self.picks:
            if cid in sk.entities:
                add_curve_preview(out, sk, cid)
        hot = self.hot
        axis: tuple[Vec, Vec] | None = None
        if hot is not None and hot not in self.picks and isinstance(sk.entities[hot], Line):
            line = sk.entities[hot]
            assert isinstance(line, Line)
            if line.construction or self.axis_next:
                axis = (sk.xy(line.p1), sk.xy(line.p2))
        elif self.cursor is not None and self.picks:
            axis = self._model_line(self.cursor.xy)
        if axis is None:
            return out
        a, b = axis
        mirrored = Preview()
        for cid in self.picks:
            if cid in sk.entities:
                add_curve_preview(mirrored, sk, cid)
        out.lines += [(reflect(p, a, b), reflect(q, a, b)) for p, q in mirrored.lines]
        out.circles += [(reflect(c, a, b), r) for c, r in mirrored.circles]
        for c, r, a0, a1 in mirrored.arcs:
            mc = reflect(c, a, b)
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            out.arcs.append((mc, r, 2 * ang - a1, 2 * ang - a0))
        return out
