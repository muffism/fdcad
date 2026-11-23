"""Spline edit tools (TUTORIAL_REVIEW_SPEC_2 TR42, D1306). Pure Python, no Qt.

* Insert Spline Point: click a spline to add a through point there.
* Fit Spline: pick a connected chain of lines, arcs and splines (selected before
  the tool or clicked in it), type a tolerance and press Fit.
* Simplify Spline: pick a spline, type a tolerance, press Preview to see the
  result and the points left, then Apply.

Each change is one sketch undo step (``core.sketch.spline_edit``).
"""

from __future__ import annotations

import itertools

from fdcad.core.sketch import freeform
from fdcad.core.sketch.model import Arc, EllipseArc, Line, Spline
from fdcad.core.sketch.spline_edit import Fit, fit_chain, insert_point, simplified, simplify
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.pick_tools import PickTool
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview

DEFAULT_TOLERANCE = 0.05


class _SplinePick(PickTool):
    """Picks splines (freeform curves are measured on their samples)."""

    pickable = (Spline,)

    def curve_at(self, p: tuple[float, float]) -> str | None:
        """The spline under ``p``."""
        sk = self.edit.sketch
        found: tuple[float, str] | None = None
        for e in sk.curves(True):
            if isinstance(e, Spline):
                d = freeform.distance(sk, e, p)
                if d <= self.tolerance and (found is None or d < found[0]):
                    found = (d, e.id)
        return found[1] if found else None

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg


class InsertSplinePointTool(_SplinePick):
    """Click a spline to add a through point there."""

    name, label = "insert_spline_point", "Insert Spline Point"
    prompt = "Click a spline where the new point goes."

    def click(self, snap: Snap) -> bool:
        """Add a point on the clicked spline."""
        self.hover(snap)
        if self.hot is None:
            self.message = "Click on a spline to add a point to it."
            return False
        self.edit.checkpoint()
        try:
            insert_point(self.edit.sketch, self.hot, snap.xy)
        except ValueError as exc:
            self.edit.discard_checkpoint()
            self.message = str(exc)
            return False
        self.message = "Added a spline point. Drag it to change the curve."
        return True


class FitSplineTool(PickTool):
    """Replace a chain of curves with one spline."""

    name, label = "fit_spline", "Fit Spline"
    pickable = (Line, Arc, EllipseArc, Spline)
    options = (
        Option("gap", "Tolerance", "length", tip="How far the spline may differ."),
        Option("keep", "Keep originals as construction", "bool"),
        Option("fit", "Fit", "button"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.gap = DEFAULT_TOLERANCE
        self.keep = False
        self.picked: list[str] = []

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to do next."""
        if not self.picked:
            return "Click the lines, arcs and splines of one chain, then press Fit."
        return f"{len(self.picked)} curves picked. Press Fit, or click more curves."

    def take_selection(self, ids: list[str]) -> None:
        """Curves selected before the tool started are picked."""
        sk = self.edit.sketch
        self.picked = [i for i in ids if isinstance(sk.entities.get(i), self.pickable)]

    def click(self, snap: Snap) -> bool:
        """A click picks a curve, or drops it when it is picked already."""
        self.hover(snap)
        if self.hot is None:
            return False
        if self.hot in self.picked:
            self.picked.remove(self.hot)
        else:
            self.picked.append(self.hot)
        return False

    def curve_at(self, p: tuple[float, float]) -> str | None:
        """A line, arc, partial ellipse or spline under ``p``."""
        from fdcad.core.sketch.ops.geom import nearest_curve

        sk = self.edit.sketch
        best = nearest_curve(sk, p, self.tolerance, (Line, Arc))
        if best is not None:
            return best
        found: tuple[float, str] | None = None
        for e in sk.curves(True):
            if isinstance(e, EllipseArc | Spline):
                d = freeform.distance(sk, e, p)
                if d <= self.tolerance and (found is None or d < found[0]):
                    found = (d, e.id)
        return found[1] if found else None

    def option_changed(self, key: str) -> bool:
        """Fit replaces the picked chain. True when the sketch changed."""
        if key != "fit":
            return False
        if not self.picked:
            self.message = "Nothing is picked. Click the curves of a chain first."
            return False
        self.edit.checkpoint()
        try:
            _sid, result = fit_chain(
                self.edit.sketch, list(self.picked), float(self.gap), bool(self.keep)
            )
        except ValueError as exc:
            self.edit.discard_checkpoint()
            self.message = f"Fit Spline failed: {exc}"
            return False
        self.picked = []
        self.message = (
            f"Made a spline through {len(result.points)} points, within {result.gap:.3g} mm."
        )
        return True

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """The picked curves' end points."""
        out = Preview()
        sk = self.edit.sketch
        for cid in self.picked:
            e = sk.entities.get(cid)
            if isinstance(e, Line):
                out.lines.append((sk.xy(e.p1), sk.xy(e.p2)))
            elif isinstance(e, Arc | EllipseArc | Spline):
                from fdcad.core.sketch.topology import curve_points

                out.lines += list(itertools.pairwise(curve_points(sk, e)))
        return out


class SimplifySplineTool(_SplinePick):
    """Refit a spline with fewer points."""

    name, label = "simplify_spline", "Simplify Spline"
    options = (
        Option("gap", "Tolerance", "length", tip="How far the curve may move."),
        Option("calculate", "Preview", "button"),
        Option("apply", "Apply", "button"),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.gap = DEFAULT_TOLERANCE
        self.spline: str | None = None
        self.result: Fit | None = None

    @property
    def prompt(self) -> str:  # type: ignore[override]
        """What to do next, or the preview's result."""
        if self.spline is None:
            return "Click the spline to simplify."
        if self.result is None:
            return "Type the tolerance, then press Preview."
        before = len(self.edit.sketch.entities[self.spline].points)  # type: ignore[union-attr]
        return (
            f"{len(self.result.points)} of {before} points left, within "
            f"{self.result.gap:.3g} mm. Press Apply."
        )

    def take_selection(self, ids: list[str]) -> None:
        """A spline selected before the tool started is the one to simplify."""
        sk = self.edit.sketch
        self.spline = next((i for i in ids if isinstance(sk.entities.get(i), Spline)), None)

    def click(self, snap: Snap) -> bool:
        """A click picks the spline."""
        self.hover(snap)
        if self.hot is not None:
            self.spline, self.result = self.hot, None
        return False

    def option_changed(self, key: str) -> bool:
        """Preview works out the result; Apply uses it. True when the sketch changed."""
        if self.spline is None or self.spline not in self.edit.sketch.entities:
            self.spline, self.result = None, None
            self.message = "Click a spline first."
            return False
        if key == "calculate" or (key == "apply" and self.result is None):
            if float(self.gap) <= 0:
                self.message = "The tolerance must be greater than zero. Enter a positive length."
                return False
            self.result = simplified(self.edit.sketch, self.spline, float(self.gap))
            if key == "calculate":
                return False
        if key == "apply" and self.result is not None:
            spline = self.edit.sketch.entities[self.spline]
            assert isinstance(spline, Spline)
            if len(self.result.points) >= len(spline.points):
                self.message = "No points can go within this tolerance. Enter a larger one."
                self.result = None
                return False
            self.edit.checkpoint()
            removed = simplify(self.edit.sketch, self.spline, self.result)
            self.result = None
            self.message = f"Removed {removed} spline points."
            return True
        if key == "gap":
            self.result = None
        return False

    def preview(self) -> Preview:
        """The simplified curve while a preview is shown."""
        out = Preview()
        if self.result is not None:
            pts = freeform_points(self.result)
            out.lines += list(itertools.pairwise(pts))
            out.points += list(self.result.points)
        return out


def freeform_points(result: Fit) -> list[tuple[float, float]]:
    """Points along a fitted spline, for previews."""
    from fdcad.core.sketch.conic import spline_points

    return spline_points(result.points, result.handles, 16)
