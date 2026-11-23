"""Close Sketch to Model tool (TUTORIAL_REVIEW_SPEC_2 TR106, D1704). Pure Python, no Qt.

The canvas hands the part's intersection curves to the tool (D759). Moving the
cursor inside one of the two possible closed shapes previews it; a click closes
the profile that way, one undo step.
"""

from __future__ import annotations

import itertools

from fdcad.core.sketch.close_to_model import CloseError, Closing, close, closings
from fdcad.core.sketch.curve_convert import ProjectedCurve
from fdcad.core.sketch.model_curves import INTERSECTION, SILHOUETTE
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import Preview, Tool

WORKING = "Working out the part edges in the sketch plane..."
PICK_SIDE = "Click inside the shape to keep: the profile is closed by the part edges there."
CLOSED = "Closed the profile with {count} part {edges}."


class CloseToModelTool(Tool):
    """Close an open profile whose ends sit on part edges, by those edges."""

    name, label = "close_to_model", "Close Sketch to Model"
    needs = (INTERSECTION, SILHOUETTE)  # worked out on demand (D2609, D2683)

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        #: The part curves by kind; the canvas fills it (None while still working).
        self.model_curves: dict[str, ProjectedCurve | None] = {}
        self.message = ""
        #: The closing under the cursor.
        self.hot: Closing | None = None

    def _ways(self) -> tuple[str, str, list[Closing]] | None:
        """The open ends and the two closings, or None (the reason in ``message``)."""
        pieces = []
        for kind in (INTERSECTION, SILHOUETTE):
            curve = self.model_curves.get(kind)
            if curve is not None and curve.pieces:
                pieces = list(curve.pieces)
                try:
                    return closings(self.edit.sketch, pieces)
                except CloseError as exc:
                    self.message = str(exc)
        if not pieces:
            self.message = (
                WORKING
                if any(kind not in self.model_curves for kind in (INTERSECTION, SILHOUETTE))
                else "The part has no edges in this sketch plane. "
                "Use a sketch plane that meets the part."
            )
        return None

    @property
    def prompt(self) -> str:
        """What to click."""
        if not self.model_curves:
            return WORKING
        found = self._ways()
        return PICK_SIDE if found is not None else self.message

    def hover(self, snap: Snap) -> Snap:
        """Find the closing whose shape holds the cursor."""
        snap = super().hover(snap)
        found = self._ways()
        self.hot = None
        if found is not None:
            inside = [w for w in found[2] if w.contains(snap.xy)]
            self.hot = min(inside, key=lambda w: w.area) if inside else None
        return snap

    def click(self, snap: Snap) -> bool:
        """Close the profile with the side under the cursor."""
        found = self._ways()
        if found is None:
            return False
        a, b, ways = found
        inside = [w for w in ways if w.contains(snap.xy)]
        if not inside:
            self.message = PICK_SIDE
            return False
        way = min(inside, key=lambda w: w.area)
        self.edit.checkpoint()
        made = close(self.edit.sketch, a, b, way)
        self.drawn = made
        self.message = CLOSED.format(count=len(made), edges="edge" if len(made) == 1 else "edges")
        self.hot = None
        self.finished = True
        return True

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """The closing under the cursor."""
        out = Preview()
        if self.hot is not None:
            for piece in self.hot.pieces:
                out.lines += list(itertools.pairwise(piece.polyline()))
        return out
