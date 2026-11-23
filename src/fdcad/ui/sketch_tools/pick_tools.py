"""Base class for sketch tools that work on curves the user clicks (PHASE2_SPEC P2.8).

Pick tools take the raw cursor (they pick curves, they do not place points),
keep the curve under the cursor in ``hot`` for highlighting, and leave a
status bar note in ``message`` after each change. Pure Python, no Qt.
"""

from __future__ import annotations

from collections.abc import Callable

from fdcad.core.sketch import freeform
from fdcad.core.sketch.model import Arc, Circle, Ellipse, EllipseArc, Line, Sketch, Spline
from fdcad.core.sketch.ops.geom import Vec, distance, geo, nearest_curve
from fdcad.core.sketch.ops.pieces import Report
from fdcad.core.sketch.ops.trim import describe
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool

#: Part outline polylines and circles in sketch mm (as in ``core.sketch.reference``).
Polyline = list[tuple[float, float]]
RefCircle = tuple[tuple[float, float], float]

#: Relation names for status notes (kept here so this module needs no Qt strings).
RELATION_LABELS = {
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "coincident": "Coincident",
    "collinear": "Collinear",
    "parallel": "Parallel",
    "perpendicular": "Perpendicular",
    "tangent": "Tangent",
    "concentric": "Concentric",
    "equal": "Equal",
    "midpoint": "Midpoint",
    "symmetric": "Symmetric",
    "coradial": "Coradial",
    "intersection": "Intersection",
    "fixed": "Fix",
    "offset": "Offset",
}


def add_curve_preview(out: Preview, sketch: Sketch, cid: str) -> None:
    """Draw curve ``cid`` into a preview (used to highlight a pick)."""
    g = geo(sketch, cid)
    if g.kind == "line":
        out.lines.append((g.a, g.b))
    elif g.kind == "circle":
        out.circles.append((g.a, g.r))
    else:
        out.arcs.append((g.a, g.r, g.a0, g.a0 + g.sweep))


class PickTool(Tool):
    """A tool that acts on clicked curves."""

    #: The canvas hands the raw cursor instead of a snap.
    raw_cursor = True
    #: No For construction tick box in the tool options.
    construction_option = False
    #: Fields of the tool's own panel.
    options: tuple[Option, ...] = ()
    #: Curve types the tool can pick.
    pickable: tuple[type, ...] = (Line, Circle, Arc)
    #: One line telling the user what to click next.
    prompt = ""

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        #: The curve under the cursor.
        self.hot: str | None = None
        #: A curve under the cursor that this tool cannot pick.
        self.wrong: str | None = None
        #: A note for the status bar, taken by the canvas after each click.
        self.message = ""
        #: Part outline projected onto the sketch plane (set by the canvas).
        self.model_lines: list[Polyline] = []
        self.model_circles: list[RefCircle] = []

    def curve_at(self, p: Vec) -> str | None:
        """The pickable curve under ``p``."""
        return nearest_curve(self.edit.sketch, p, self.tolerance, self.pickable)

    def unpickable_at(self, p: Vec) -> str | None:
        """A curve under ``p`` that this tool cannot pick (a spline, an ellipse, or a
        kind outside ``pickable``), or None."""
        sk = self.edit.sketch
        found: tuple[float, str] | None = None
        for e in sk.curves():
            if isinstance(e, self.pickable):
                continue
            if isinstance(e, Ellipse | EllipseArc | Spline):
                d = freeform.distance(sk, e, p)
            else:
                d = distance(sk, e.id, p)
            if d <= self.tolerance and (found is None or d < found[0]):
                found = (d, e.id)
        return found[1] if found else None

    def hover(self, snap: Snap) -> Snap:
        """Track the curve under the cursor."""
        self.cursor = snap
        self.hot = self.curve_at(snap.xy)
        self.wrong = None if self.hot is not None else self.unpickable_at(snap.xy)
        return snap

    def wrong_kind_note(self) -> str:
        """What to say when the click hit a curve this tool cannot use (audit D2
        items 2 and 4, D706)."""
        kinds = {Line: "lines", Circle: "circles", Arc: "arcs"}
        names = [kinds[k] for k in self.pickable if k in kinds]
        what = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        label = getattr(self, "label", "This tool")
        other = f"a {names[0][:-1]}" if len(names) == 1 else "one of those"
        return f"{label} works on {what} only, so it cannot use that curve. Pick {other} instead."

    def take_message(self) -> str:
        """The status note, cleared once read. A click on a curve the tool cannot use
        says so instead of doing nothing silently."""
        msg, self.message = self.message, ""
        if self.wrong is not None and self.hot is None:
            self.wrong = None
            return self.wrong_kind_note()
        return msg

    def apply(self, change: Callable[[], Report | None], refused: str = "") -> bool:
        """Run ``change`` as one undo step. False (and ``refused`` as the note) when it
        did nothing."""
        self.edit.checkpoint()
        try:
            report = change()
        except (ValueError, ZeroDivisionError, KeyError, TypeError):
            report = None
        if report is None:
            self.edit.discard_checkpoint()
            self.message = refused
            return False
        self.message = describe(report, RELATION_LABELS)
        return True

    def option_changed(self, key: str) -> bool:
        """A panel field changed or a panel button was pressed. True when the sketch
        changed."""
        return False

    def preview(self) -> Preview:
        """Highlight the curve under the cursor."""
        out = Preview()
        if self.hot is not None and self.hot in self.edit.sketch.entities:
            add_curve_preview(out, self.edit.sketch, self.hot)
        return out
