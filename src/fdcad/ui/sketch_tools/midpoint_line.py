"""Midpoint Line (TUTORIAL_REVIEW_SPEC TR4, D688). Pure Python, no Qt.

The first click is the middle of the line, the second one end; the other end
mirrors it. The middle point is a construction point with a Midpoint relation
to the line, so the line stays centred on it when its length changes.
"""

from __future__ import annotations

from fdcad.ui.sketch_tools.geometry import Vec, dist
from fdcad.ui.sketch_tools.inference import Snap, line_relation
from fdcad.ui.sketch_tools.tools import Preview, Tool

#: Shorter than this (mm) counts as no line.
_MIN = 1e-6


def _mirror(mid: Vec, end: Vec) -> Vec:
    return 2 * mid[0] - end[0], 2 * mid[1] - end[1]


class MidpointLineTool(Tool):
    """Click the middle, then one end."""

    name, label = "midpoint_line", "Midpoint Line"

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        #: Horizontal or vertical (or parallel, perpendicular) from a direction snap.
        self.direction: tuple[str, list[str]] | None = None

    @property
    def prompt(self) -> str:
        """What to click next."""
        if not self.clicks:
            return "Click the middle of the line."
        return "Click one end. The other end mirrors it."

    def hover(self, snap: Snap) -> Snap:
        """After the middle, the end gets the usual direction snaps."""
        self.cursor = snap
        self.direction = None
        if self.clicks and self.snapping:
            snap, self.direction = line_relation(self.edit.sketch, self.clicks[0].xy, snap)
            self.cursor = snap
        return snap

    def ready(self) -> bool:
        """Two clicks: the middle and an end."""
        return len(self.clicks) == 2

    def commit(self) -> bool:
        """The line with both ends, and its middle point with a Midpoint relation."""
        mid, end = self.clicks
        if dist(mid.xy, end.xy) < _MIN:
            self.clicks.pop()
            return False
        sk = self.edit.sketch
        other = _mirror(mid.xy, end.xy)
        lid = sk.add_line(*other, *end.xy, self.construction)
        line = self.edit.line(lid)
        self.edit.attach(line.p2, end)
        centre = self.edit.place_point(mid, construction=True)
        sk.relate("midpoint", centre, lid)
        if self.direction is not None:
            rtype, others = self.direction
            sk.relate(rtype, lid, *others)
        self.drawn = [lid]
        return True

    def preview(self) -> Preview:
        """The line through the middle to the cursor and its mirror."""
        out = Preview()
        if self.clicks and self.cursor is not None:
            mid, end = self.clicks[0].xy, self.cursor.xy
            out.lines.append((_mirror(mid, end), end))
            out.points.append(mid)
        return out
