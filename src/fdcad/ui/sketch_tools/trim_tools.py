"""Trim and Extend tools (PHASE2_SPEC P2.8 items 2 and 3). Pure Python, no Qt."""

from __future__ import annotations

from collections.abc import Callable

from fdcad.core.sketch.model import Arc, Line
from fdcad.core.sketch.ops.geom import Vec, dist, geo
from fdcad.core.sketch.ops.pieces import Report
from fdcad.core.sketch.ops.trim import (
    TRIM_MODES,
    corner,
    drag_trim,
    extend,
    extend_target,
    trim_between,
    trim_nearest,
)
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import PickTool, add_curve_preview
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview

TRIM_MODE_LABELS = {
    "drag": "Drag trim",
    "corner": "Corner",
    "inside": "Trim inside",
    "outside": "Trim outside",
    "nearest": "Trim to nearest",
}
_PROMPTS = {
    "drag": "Hold and drag across curves to trim them, or click a piece.",
    "corner": "Click two curves. Both are trimmed or extended to meet.",
    "inside": "Click two boundary curves, then the curves to cut between them.",
    "outside": "Click two boundary curves, then the curves to keep between them.",
    "nearest": "Click a piece to remove it, or click past the end of a curve to extend it.",
}
NOTHING_TO_TRIM = "Nothing to trim there. Click a curve or a piece between crossings."
NOT_BETWEEN = "That curve does not cross both boundaries. Click a curve that crosses both."
NOTHING_AHEAD = (
    "There is no curve ahead to extend to. Draw a curve in its path, or click another curve."
)


class TrimTool(PickTool):
    """Trim in one of five modes (P2.8 item 2)."""

    name, label = "trim", "Trim"
    options = (
        Option("mode", "Mode", "choice", tuple((m, TRIM_MODE_LABELS[m]) for m in TRIM_MODES)),
        Option("keep_construction", "Keep Trimmed Pieces as Construction", "bool"),  # TR47
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.mode = "drag"
        #: Trimmed away parts stay as construction geometry (TR47, D893).
        self.keep_construction = False
        #: The drag path (drag mode) in sketch mm.
        self.path: list[Vec] = []
        #: Boundary or first corner picks: (curve id, where it was clicked).
        self.picks: list[tuple[str, Vec]] = []

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to click next in the current mode."""
        return _PROMPTS[self.mode]

    @property
    def busy(self) -> bool:
        """True while a drag or a pick sequence is in progress."""
        return bool(self.path) or bool(self.picks)

    def option_changed(self, key: str) -> bool:
        """A new mode starts over."""
        self.path, self.picks = [], []
        return False

    def apply(self, change: Callable[[], Report | None], refused: str = "") -> bool:
        """Trim; with Keep Trimmed Pieces as Construction the cut away parts come back as
        construction geometry in the same undo step."""
        if not self.keep_construction:
            return super().apply(change, refused)
        import copy

        from fdcad.core.sketch.ops.trim_keep import keep_trimmed

        before = copy.deepcopy(self.edit.sketch)

        def run() -> Report | None:
            report = change()
            if report is not None:
                keep_trimmed(before, self.edit.sketch)
            return report

        return super().apply(run, refused)

    def cancel(self) -> bool:
        """Escape drops the picks first, then ends the tool."""
        if self.busy:
            self.path, self.picks = [], []
            return False
        return True

    def hover(self, snap: Snap) -> Snap:
        """Track the curve under the cursor; extend the drag trail."""
        snap = super().hover(snap)
        if self.path and dist(self.path[-1], snap.xy) > 1e-9:
            self.path.append(snap.xy)
        return snap

    def click(self, snap: Snap) -> bool:
        """Handle a press in the current mode."""
        self.hover(snap)
        at = snap.xy
        if self.mode == "drag":
            self.path = [at]
            return False
        if self.mode == "nearest":
            return self._nearest(at)
        cid = self.hot
        if cid is None:
            self.message = NOTHING_TO_TRIM
            return False
        if self.mode == "corner":
            if not self.picks:
                self.picks = [(cid, at)]
                return False
            (a, pa), self.picks = self.picks[0], []
            return self.apply(
                lambda: corner(self.edit.sketch, a, pa, cid, at, self.edit.auto_relations),
                "These curves do not meet. Pick two lines or arcs that are not parallel.",
            )
        if len(self.picks) < 2:
            if not self.picks or self.picks[0][0] != cid:
                self.picks.append((cid, at))
            return False
        b1, b2 = self.picks[0][0], self.picks[1][0]
        inside = self.mode == "inside"
        return self.apply(
            lambda: trim_between(
                self.edit.sketch, cid, at, b1, b2, inside, self.edit.auto_relations
            ),
            NOT_BETWEEN,
        )

    def release(self, snap: Snap, moved: bool) -> bool:
        """The end of a press in drag mode: trim along the path, or the clicked piece."""
        if self.mode != "drag" or not self.path:
            return False
        self.hover(snap)
        path, self.path = self.path, []
        if not moved:
            return self._nearest(path[0])
        return self.apply(
            lambda: drag_trim(self.edit.sketch, path, self.tolerance, self.edit.auto_relations),
            NOTHING_TO_TRIM,
        )

    def _nearest(self, at: Vec) -> bool:
        cid = self.curve_at(at)
        if cid is not None:
            return self.apply(
                lambda: trim_nearest(self.edit.sketch, cid, at, self.edit.auto_relations),
                NOTHING_TO_TRIM,
            )
        past = _past_end(self, at)
        if past is None:
            self.message = NOTHING_TO_TRIM
            return False
        return self.apply(
            lambda: extend(self.edit.sketch, past, at, self.edit.auto_relations),
            NOTHING_AHEAD,
        )

    def preview(self) -> Preview:
        """The highlighted curve, the corner or boundary picks and the drag trail."""
        out = super().preview()
        sk = self.edit.sketch
        for cid, _at in self.picks:
            if cid in sk.entities:
                add_curve_preview(out, sk, cid)
        out.lines += list(zip(self.path, self.path[1:], strict=False))
        return out


def _past_end(tool: PickTool, at: Vec) -> str | None:
    """A line or arc whose path, carried on past one of its ends, runs under ``at``."""
    sk = tool.edit.sketch
    for c in sk.curves(True):
        if not isinstance(c, Line | Arc):
            continue
        g = geo(sk, c.id)
        t = g.param(at)
        if g.inside(t):
            continue
        on = dist(at, g.at(t)) <= tool.tolerance
        if on:
            return c.id
    return None


class ExtendTool(PickTool):
    """Extend (P2.8 item 3): hover previews, click extends, dragging on goes further."""

    name, label = "extend", "Extend"
    pickable = (Line, Arc)
    prompt = "Hover the half of a line or arc to extend, then click. Drag on to go further."

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        #: The curve being extended while the button is held.
        self.dragging: str | None = None

    @property
    def busy(self) -> bool:
        """True while the button is held after an extend."""
        return self.dragging is not None

    def cancel(self) -> bool:
        """Escape ends the tool."""
        self.dragging = None
        return True

    def click(self, snap: Snap) -> bool:
        """Extend the curve under the cursor."""
        self.hover(snap)
        cid = self.hot
        if cid is None:
            return False
        ok = self.apply(
            lambda: extend(self.edit.sketch, cid, snap.xy, self.edit.auto_relations),
            NOTHING_AHEAD,
        )
        self.dragging = cid if ok else None
        return ok

    def hover(self, snap: Snap) -> Snap:
        """While held, keep extending past further curves the cursor has passed."""
        snap = super().hover(snap)
        cid = self.dragging
        if cid is not None and cid in self.edit.sketch.entities:
            self._extend_on(cid, snap.xy)
        return snap

    def _extend_on(self, cid: str, at: Vec) -> None:
        sk = self.edit.sketch
        for _ in range(64):
            target = extend_target(sk, cid, at)
            if target is None:
                return
            high, hit = target
            g = geo(sk, cid)
            end = g.at(g.sweep if high else 0.0)
            # Only go on while the cursor is past the next curve, measured from the end.
            if dist(end, at) <= hit.t or dist(hit.at, at) > dist(end, at):
                return
            report: Report | None = extend(sk, cid, end, self.edit.auto_relations)
            if report is None:
                return

    def release(self, snap: Snap, moved: bool) -> bool:
        """The button is up: the extend is done."""
        changed = self.dragging is not None and moved
        self.dragging = None
        return changed

    def preview(self) -> Preview:
        """The extension the click would make."""
        out = Preview()
        cid, cursor = self.hot, self.cursor
        if cid is None or cursor is None or cid not in self.edit.sketch.entities:
            return out
        add_curve_preview(out, self.edit.sketch, cid)
        target = extend_target(self.edit.sketch, cid, cursor.xy)
        if target is not None:
            high, hit = target
            g = geo(self.edit.sketch, cid)
            if g.kind == "line":
                out.lines.append((g.at(1.0 if high else 0.0), hit.at))
            else:
                t = g.param(hit.at)
                if high:
                    out.arcs.append((g.a, g.r, g.a0 + g.sweep, g.a0 + t))
                else:
                    out.arcs.append((g.a, g.r, g.a0 + t - 6.283185307179586, g.a0))
        return out
