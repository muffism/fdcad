"""Temporary guide lines (TUTORIAL_REVIEW_SPEC_2 TR232, D1714). Pure Python, no Qt.

While a drawing tool is active, resting the cursor on a sketch point for a moment
marks it as the start of a guide; resting on a second point draws a dashed guide
between the two. A guide's ends, middle, thirds and quarters are snap points
(free points: they add no relations). Guides are display only and vanish when
the tool ends.
"""

from __future__ import annotations

import math

Vec = tuple[float, float]
#: How long the cursor rests on a point before it counts (milliseconds).
DWELL_MS = 600
#: Fractions along a guide that snap.
FRACTIONS = (0.0, 0.25, 1 / 3, 0.5, 2 / 3, 0.75, 1.0)


class Guides:
    """The open sketch's temporary guides and a started one."""

    def __init__(self) -> None:
        self.lines: list[tuple[Vec, Vec]] = []
        #: The first point of a guide being made.
        self.anchor: Vec | None = None

    def clear(self) -> None:
        """Drop every guide (the tool ended)."""
        self.lines = []
        self.anchor = None

    def rest_on(self, p: Vec) -> str:
        """The cursor rested on point ``p``: start a guide there, or finish one. Returns
        "started", "made" or "" (resting on the start again)."""
        if self.anchor is None:
            self.anchor = p
            return "started"
        if math.dist(self.anchor, p) < 1e-9:
            return ""
        self.lines.append((self.anchor, p))
        self.anchor = None
        return "made"

    def points(self) -> list[Vec]:
        """Every snap point of the guides."""
        out: list[Vec] = []
        for a, b in self.lines:
            for t in FRACTIONS:
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        return out

    def snap(self, at: Vec, tolerance: float) -> Vec | None:
        """The nearest guide snap point within ``tolerance`` of ``at``, or None."""
        best: tuple[float, Vec] | None = None
        for p in self.points():
            d = math.dist(p, at)
            if d <= tolerance and (best is None or d < best[0]):
                best = (d, p)
        return best[1] if best else None
