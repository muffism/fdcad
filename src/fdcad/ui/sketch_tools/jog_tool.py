"""Sketch, Jog Line (TR52, D902): click a line where the step goes, then click to one
side to set how far the rest of the line steps over. Pure Python, no Qt."""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Line
from fdcad.ui.sketch_tools import tool_text
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import Preview, Tool


class JogLineTool(Tool):
    """Two clicks: the line (and where), then the side and depth."""

    name, label = "jog_line", "Jog Line"

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.message = ""

    def take_message(self) -> str:
        """The status note left by the last click, once."""
        msg, self.message = self.message, ""
        return msg

    def click(self, snap: Snap) -> bool:
        """The first click must be on a line."""
        snap = self.track(snap)
        if not self.clicks:
            target = self.edit.sketch.entities.get(snap.target or "")
            if not isinstance(target, Line):
                self.message = tool_text.JOG_PICK_LINE
                return False
        return super().click(snap)

    def ready(self) -> bool:
        """The line and the depth are both clicked."""
        return len(self.clicks) == 2

    def _depth(self) -> float:
        sk = self.edit.sketch
        line = sk.entities[self.clicks[0].target or ""]
        assert isinstance(line, Line)
        (x1, y1), (x2, y2) = sk.xy(line.p1), sk.xy(line.p2)
        length = math.hypot(x2 - x1, y2 - y1)
        px, py = self.clicks[1].xy
        return ((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)) / length if length else 0.0

    def commit(self) -> bool:
        """Jog the line."""
        from fdcad.core.sketch.ops.jog import JogError, jog

        try:
            made = jog(
                self.edit.sketch, str(self.clicks[0].target), self.clicks[0].xy, self._depth()
            )
        except JogError as exc:
            self.message = str(exc)
            return False
        self.drawn = made
        return True

    def preview(self) -> Preview:
        """The spot on the line and a guide to the cursor."""
        out = Preview()
        if self.clicks and self.cursor is not None:
            out.lines.append((self.clicks[0].xy, self.cursor.xy))
            out.points.append(self.clicks[0].xy)
        return out


__all__ = ["JogLineTool"]
