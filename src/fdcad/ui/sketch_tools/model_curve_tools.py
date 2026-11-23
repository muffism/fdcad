"""Intersection Curves and Silhouette sketch tools (TUTORIAL_REVIEW_SPEC TR6, D759).

When a sketch opens, the part is cut with the sketch plane in a kernel job
(``core.sketch.model_curves``); its outline seen square to the plane is worked out
only when the Silhouette tool asks for it (D2609). The canvas hands the results to
these tools. Each tool previews its curves and
adds them with Add Curves as fixed curves, like Convert does for curve
features (D517). Pure Python, no Qt.
"""

from __future__ import annotations

import itertools

from fdcad.core.sketch.curve_convert import ProjectedCurve, add_curve
from fdcad.core.sketch.model_curves import INTERSECTION, SILHOUETTE
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool


class _ModelCurveTool(Tool):
    kind = ""
    what = ""
    options = (Option("add", "Add Curves", "button"),)

    def __init__(self, edit: object) -> None:
        super().__init__(edit)  # type: ignore[arg-type]
        #: The worked out curves by kind; the canvas fills it (None while still working).
        self.model_curves: dict[str, ProjectedCurve | None] = {}
        self.message = ""

    @property
    def curve(self) -> ProjectedCurve | None:
        """This tool's curves, or None while they are still being worked out."""
        return self.model_curves.get(self.kind)

    @property
    def prompt(self) -> str:
        """What the tool shows and what to press."""
        if self.curve is None:
            return f"Working out the {self.what}..."
        if not self.curve.pieces:
            if self.curve.problem:  # they could not be worked out: say why (D2635)
                return self.curve.problem
            return f"The part has no {self.what} on this sketch plane."
        return f"Press Add Curves to copy the {self.what} into the sketch."

    def option_changed(self, key: str) -> bool:
        """Add Curves: the curves as fixed curves, one undo step. True when added."""
        if key != "add":
            return False
        curve = self.curve
        if curve is None:
            self.message = f"The {self.what} are still being worked out. Press Add Curves again."
            return False
        if not curve.pieces:
            self.message = (
                curve.problem
                or f"No {self.what} to add. Move the sketch plane so it meets the part."
            )
            return False
        self.edit.checkpoint()
        made, already = add_curve(self.edit.sketch, curve, self.construction)
        if not made:
            self.edit.discard_checkpoint()
            self.message = f"The {self.what} are already in the sketch."
            return False
        self.drawn = made
        self.message = f"Added {len(made)} curves of the {self.what}." + (
            f" {already} were already in the sketch." if already else ""
        )
        return True

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """The curves that Add Curves would copy."""
        out = Preview()
        curve = self.curve
        if curve is not None:
            for line in curve.polylines:
                out.lines += list(itertools.pairwise(line))
        return out


class IntersectionCurvesTool(_ModelCurveTool):
    """Where the sketch plane cuts the part."""

    name, label = "intersection_curves", "Intersection Curves"
    kind, what = INTERSECTION, "intersection curves"
    needs = (INTERSECTION,)  # worked out when the tool is picked (D2683)


class SilhouetteTool(_ModelCurveTool):
    """The outline of the part seen square to the sketch plane."""

    name, label = "silhouette", "Silhouette"
    kind, what = SILHOUETTE, "silhouette curves"
    needs = (SILHOUETTE,)  # worked out when the tool is picked (D2609)


class TurnedOutlineTool(_ModelCurveTool):
    """The part spun about the sketch's X axis (TR319, D888)."""

    name, label = "turned_outline", "Turned Outline"
    kind, what = "turned", "turned outline"
