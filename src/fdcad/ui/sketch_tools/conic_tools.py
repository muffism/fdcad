"""Conic and Equation Curve sketch tools (TUTORIAL_REVIEW_SPEC TR28, D757). Pure Python.

Both add an ordinary sketch spline (``core.sketch.conic``), so the curve can be
dimensioned, related, trimmed and used in profiles like any spline.

- Conic: click the start, the end, then the top point where the end tangents
  meet. The Shape value (rho, 0.01 to 0.99) sets how full the curve is: 0.5 is a
  parabola, less is flatter (part of an ellipse), more is fuller.
- Equation Curve: type x(t) and y(t), the range of t and the number of points,
  then press Add Curve. Plain numbers are in the part's unit.
"""

from __future__ import annotations

import itertools

from fdcad.core.sketch.conic import (
    POINTS_DEFAULT,
    POINTS_MAX,
    POINTS_MIN,
    CurveError,
    conic_spline,
    equation_spline,
    spline_points,
)
from fdcad.core.sketch.model import Spline
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.geometry import Vec
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool


def _add_spline(tool: Tool, points: list[Vec], handles: list[Vec], ends: list[object]) -> str:
    """Add the spline; ``ends`` are the snaps of the first and last points (or None)."""
    sk = tool.edit.sketch
    ids = []
    for i, p in enumerate(points):
        snap = ends[0] if i == 0 else ends[1] if i == len(points) - 1 else None
        if snap is not None:
            ids.append(tool.edit.place_point(snap, tool.construction))  # type: ignore[arg-type]
        else:
            ids.append(sk.add_point(p[0], p[1], tool.construction))
    hids = [sk.add_point(h[0], h[1], construction=True) for h in handles]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, ids, hids, tool.construction)
    tool.drawn = [sid]
    return sid


class ConicTool(Tool):
    """Start, end, then the top point; the Shape value sets the curve."""

    name, label = "conic", "Conic"
    options = (
        Option(
            "rho",
            "Shape (rho)",
            "number",
            tip="0.5 is a parabola; less is flatter, more is fuller. Between 0.01 and 0.99.",
        ),
    )

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        self.rho = 0.5
        self.message = ""

    @property
    def prompt(self) -> str:
        """What to click next."""
        return (
            "Click the start of the conic.",
            "Click the end of the conic.",
            "Click the top point, where the end tangents meet.",
        )[min(len(self.clicks), 2)]

    def ready(self) -> bool:
        """Start, end and top point."""
        return len(self.clicks) == 3

    def _shape(self, top: Vec) -> tuple[list[Vec], list[Vec]]:
        s, e = self.clicks[0].xy, self.clicks[1].xy
        return conic_spline(s, top, e, float(self.rho))

    def commit(self) -> bool:
        """The conic as a spline, its ends tied to what they snapped to."""
        try:
            points, handles = self._shape(self.clicks[2].xy)
        except CurveError as exc:
            self.message = f"Conic not drawn: {exc}"
            self.clicks.pop()
            self._keep = True  # the ends stay; only the top point is picked again
            return False
        _add_spline(self, points, handles, [self.clicks[0], self.clicks[1]])
        return True

    def after_commit(self) -> None:
        """Start the next conic, or keep the ends after a top point that made none."""
        if getattr(self, "_keep", False):
            self._keep = False
            return
        self.clicks.clear()

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """The chord after two clicks, then the curve to the cursor."""
        out = Preview()
        if self.cursor is None or not self.clicks:
            return out
        if len(self.clicks) == 1:
            out.lines.append((self.clicks[0].xy, self.cursor.xy))
            return out
        top = self.cursor.xy
        out.lines.append((self.clicks[0].xy, top))
        out.lines.append((top, self.clicks[1].xy))
        try:
            points, handles = self._shape(top)
        except CurveError:
            return out
        out.lines += list(itertools.pairwise(spline_points(points, handles, 16)))
        out.points.append(top)
        return out


class EquationCurveTool(Tool):
    """x(t) and y(t) typed in the panel; Add Curve puts the spline in the sketch."""

    name, label = "equation_curve", "Equation Curve"
    options = (
        Option(
            "x_expr",
            "x(t)",
            "text",
            tip="For example 20*cos(t). Plain numbers use the part's unit.",
        ),
        Option("y_expr", "y(t)", "text", tip="For example 10*sin(t)."),
        Option("t_start", "t from", "number"),
        Option("t_end", "t to", "number"),
        Option("count", "Points", "int", low=POINTS_MIN, high=POINTS_MAX),
        Option("add", "Add Curve", "button"),
    )
    prompt = "Type x(t) and y(t) and the range of t, then press Add Curve."

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        self.x_expr = "20*cos(t)"
        self.y_expr = "10*sin(t)"
        self.t_start = 0.0
        self.t_end = 3.141592653589793
        self.count = POINTS_DEFAULT
        self.message = ""
        #: The part's unit for plain numbers; the canvas sets it when the tool starts.
        self.units = UnitSystem.MM

    def _curve(self) -> tuple[list[Vec], list[Vec]]:
        return equation_spline(
            self.x_expr,
            self.y_expr,
            float(self.t_start),
            float(self.t_end),
            int(self.count),
            self.units,
        )

    def option_changed(self, key: str) -> bool:
        """Add Curve adds the spline as one undo step. True when the sketch changed."""
        if key != "add":
            return False
        try:
            points, handles = self._curve()
        except CurveError as exc:
            self.message = f"Equation curve not added: {exc}"
            return False
        self.edit.checkpoint()
        _add_spline(self, points, handles, [None, None])
        self.message = f"Added an equation curve through {len(points)} points."
        return True

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """The curve as it would be added."""
        out = Preview()
        try:
            points, handles = self._curve()
        except CurveError:
            return out
        out.lines += list(itertools.pairwise(spline_points(points, handles, 8)))
        return out


class ParabolaTool(Tool):
    """Focus, apex, then the two ends (TR52, D902): an exact parabola as a spline."""

    name, label = "parabola", "Parabola"

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        self.message = ""

    @property
    def prompt(self) -> str:
        """What to click next."""
        return (
            "Click the focus of the parabola.",
            "Click its apex (the tip of the curve).",
            "Click where the curve starts.",
            "Click where the curve ends.",
        )[min(len(self.clicks), 3)]

    def take_message(self) -> str:
        """The status note left by the last click, once."""
        msg, self.message = self.message, ""
        return msg

    def ready(self) -> bool:
        """Focus, apex and both ends."""
        return len(self.clicks) == 4

    def commit(self) -> bool:
        """The parabola, ends on the curve nearest the clicks."""
        from fdcad.core.sketch.conic import parabola_top

        focus, apex, s, e = (c.xy for c in self.clicks)
        try:
            start, top, end = parabola_top(focus, apex, s, e)
            points, handles = conic_spline(start, top, end, 0.5)
        except CurveError as exc:
            self.message = f"Parabola not drawn: {exc}"
            return False
        _add_spline(self, points, handles, [None, None])
        return True

    def preview(self) -> Preview:
        """The clicks so far, and the curve once both ends are known."""
        from fdcad.core.sketch.conic import parabola_top

        out = Preview()
        out.points += [c.xy for c in self.clicks]
        if len(self.clicks) == 3 and self.cursor is not None:
            try:
                start, top, end = parabola_top(
                    self.clicks[0].xy, self.clicks[1].xy, self.clicks[2].xy, self.cursor.xy
                )
                points, handles = conic_spline(start, top, end, 0.5)
            except CurveError:
                return out
            line = spline_points(points, handles, 48)
            out.lines += list(itertools.pairwise(line))
        return out


class HyperbolaTool(Tool):
    """Centre, vertex, then one end (TR374, D985): a partial hyperbola branch, exact,
    as a spline, symmetric about its axis."""

    name, label = "hyperbola", "Partial Hyperbola"

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        self.message = ""

    @property
    def prompt(self) -> str:
        """What to click next."""
        return (
            "Click the centre of the hyperbola.",
            "Click its vertex (the tip of the branch).",
            "Click one end of the branch; the other end mirrors it across the axis.",
        )[min(len(self.clicks), 2)]

    def take_message(self) -> str:
        """The status note left by the last click, once."""
        msg, self.message = self.message, ""
        return msg

    def ready(self) -> bool:
        """Centre, vertex and one end."""
        return len(self.clicks) == 3

    def commit(self) -> bool:
        """The branch through the vertex, between the end and its mirror."""
        from fdcad.core.sketch.conic import hyperbola_top

        centre, vertex, end = (c.xy for c in self.clicks)
        try:
            start, top, finish, rho = hyperbola_top(centre, vertex, end)
            points, handles = conic_spline(start, top, finish, rho)
        except CurveError as exc:
            self.message = f"Hyperbola not drawn: {exc}"
            return False
        _add_spline(self, points, handles, [None, None])
        return True

    def preview(self) -> Preview:
        """The clicks so far, and the branch once the vertex is known."""
        from fdcad.core.sketch.conic import hyperbola_top

        out = Preview()
        out.points += [c.xy for c in self.clicks]
        if len(self.clicks) == 2 and self.cursor is not None:
            try:
                start, top, finish, rho = hyperbola_top(
                    self.clicks[0].xy, self.clicks[1].xy, self.cursor.xy
                )
                points, handles = conic_spline(start, top, finish, rho)
            except CurveError:
                return out
            line = spline_points(points, handles, 48)
            out.lines += list(itertools.pairwise(line))
        return out
