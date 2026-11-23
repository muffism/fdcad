"""Infinite Construction Line (TUTORIAL_REVIEW_SPEC_2 TR115 item 1, D1710). No Qt.

Click a point the line passes through, then a second point for its direction. The
sketch has no endless curve, so the line is a construction line reaching a long way
(``REACH`` each way from the first click); trim it later to the length you need.
Both clicks become construction points on the line, so it keeps passing through
them, and a direction snap gives its relation as the Line tool does.
"""

from __future__ import annotations

from fdcad.ui.sketch_tools.geometry import Vec, dist
from fdcad.ui.sketch_tools.inference import Snap, line_relation
from fdcad.ui.sketch_tools.tools import Preview, Tool

#: How far the line reaches each way from the first click, in mm.
REACH = 1000.0
_MIN = 1e-6


def reach(a: Vec, b: Vec) -> tuple[Vec, Vec]:
    """The far ends of the line through ``a`` toward ``b``."""
    d = dist(a, b)
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    return (a[0] - ux * REACH, a[1] - uy * REACH), (a[0] + ux * REACH, a[1] + uy * REACH)


class InfiniteLineTool(Tool):
    """A construction line through two clicks that runs on far beyond both."""

    name, label = "infinite_line", "Infinite Construction Line"

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        self.direction: tuple[str, list[str]] | None = None

    @property
    def prompt(self) -> str:
        """What to click next."""
        if not self.clicks:
            return "Click a point the line passes through."
        return "Click a second point to set the direction."

    def hover(self, snap: Snap) -> Snap:
        """After the first click, the usual direction snaps."""
        self.cursor = snap
        self.direction = None
        if self.clicks and self.snapping:
            snap, self.direction = line_relation(self.edit.sketch, self.clicks[0].xy, snap)
            self.cursor = snap
        return snap

    def ready(self) -> bool:
        """Two clicks."""
        return len(self.clicks) == 2

    def commit(self) -> bool:
        """The long construction line and its two points on it."""
        a, b = self.clicks
        if dist(a.xy, b.xy) < _MIN:
            self.clicks.pop()
            return False
        sk = self.edit.sketch
        p, q = reach(a.xy, b.xy)
        lid = sk.add_line(*p, *q, True)
        for click in (a, b):
            pid = self.edit.place_point(click, construction=True)
            sk.relate("coincident", pid, lid)
        if self.direction is not None:
            rtype, others = self.direction
            sk.relate(rtype, lid, *others)
        self.drawn = [lid]
        return True

    def preview(self) -> Preview:
        """The line through the first click toward the cursor."""
        out = Preview()
        if self.clicks and self.cursor is not None and dist(self.clicks[0].xy, self.cursor.xy):
            out.lines.append(reach(self.clicks[0].xy, self.cursor.xy))
        return out
