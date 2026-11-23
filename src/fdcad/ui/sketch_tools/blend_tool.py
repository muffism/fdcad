"""Sketch, Blend Curve (TR318, D884): click near the ends of two curves to join them
with a smooth spline. Drag its handles to change each end's weight. Pure Python."""

from __future__ import annotations

from fdcad.core.sketch.model import Arc, Line, Spline
from fdcad.ui.sketch_tools import tool_text
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import Preview, Tool


class BlendCurveTool(Tool):
    """Two clicks on curves, near the ends to join."""

    name, label = "blend_curve", "Blend Curve"

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.message = ""

    def take_message(self) -> str:
        """The status note left by the last click, once."""
        msg, self.message = self.message, ""
        return msg

    def _curve(self, snap: Snap) -> str | None:
        eid = snap.target
        e = self.edit.sketch.entities.get(eid) if eid is not None else None
        if isinstance(e, (Line, Arc, Spline)):
            return eid
        # A click on an end point: the curve that ends there.
        for cid, c in self.edit.sketch.entities.items():
            ends = (
                (c.p1, c.p2)
                if isinstance(c, Line)
                else (c.start, c.end)
                if isinstance(c, Arc)
                else (c.points[0], c.points[-1])
                if isinstance(c, Spline)
                else ()
            )
            if eid in ends:
                return cid
        return None

    def click(self, snap: Snap) -> bool:
        """Only clicks on curves count."""
        snap = self.track(snap)
        if self._curve(snap) is None:
            self.message = tool_text.BLEND_PICK
            return False
        return super().click(snap)

    def ready(self) -> bool:
        """Both curves picked."""
        return len(self.clicks) == 2

    def commit(self) -> bool:
        """Add the blend spline."""
        from fdcad.core.sketch.blend import BlendError, add_blend

        a, b = (self._curve(s) for s in self.clicks)
        if a is None or b is None:
            return False
        try:
            sid = add_blend(
                self.edit.sketch,
                a,
                b,
                self.clicks[0].xy,
                self.clicks[1].xy,
                construction=self.construction,
            )
        except BlendError as exc:
            self.message = str(exc)
            return False
        self.drawn = [sid]
        return True

    def preview(self) -> Preview:
        """A line from the first pick to the cursor."""
        out = Preview()
        if self.clicks and self.cursor is not None:
            out.lines.append((self.clicks[0].xy, self.cursor.xy))
        return out


__all__ = ["BlendCurveTool"]
