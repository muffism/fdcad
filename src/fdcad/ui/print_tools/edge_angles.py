"""Edge Angle Analysis in the 3D view (TR420 item 1, D929).

Edges where the faces meet at the limit angle or more are drawn in the sharp colour,
and edges that are nearly but not quite smooth in the warning colour. Display only.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fdcad.ui import strings
from fdcad.ui.print_tools import overlay
from fdcad.ui.print_tools.toggle import ToggleOverlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab

SHARP_COLOR = DATA["edge_sharp"]
NEAR_COLOR = DATA["edge_nearly_smooth"]
#: The limit angle the analysis starts with, in degrees.
DEFAULT_LIMIT = 10.0


def ask_limit(window: Any, start: float) -> float | None:
    """Ask the limit angle in degrees; tests replace this. None when cancelled."""
    from PySide6.QtWidgets import QInputDialog

    value, ok = QInputDialog.getDouble(
        window, strings.EDGE_ANGLE_TITLE, strings.EDGE_ANGLE_ASK, start, 0.5, 179.0, 1
    )
    return value if ok else None


class EdgeAngleAnalysis(ToggleOverlay):
    """Colours sharp and nearly smooth edges while it is on."""

    limit = DEFAULT_LIMIT

    def set_on(self, on: bool) -> None:
        """Ask the limit when turned on, then work it out."""
        if on:
            chosen = ask_limit(self.window, self.limit)
            if chosen is None:
                action = self.window.commands.actions.get("evaluate.edge_angles")
                if action is not None:
                    action.setChecked(False)
                return
            self.limit = chosen
        super().set_on(on)

    def work_for(self, tab: DocumentTab) -> Callable[[], Any] | None:
        """Find the edge angles in the background."""
        from fdcad.core.edge_angles import edge_angles

        report = tab.session.report
        if report is None or report.body is None:
            self.window.status.setText(strings.EDGE_ANGLE_NOTHING)
            return None
        shape = report.body.shape
        limit = math.radians(self.limit)

        def work() -> tuple[list[Any], list[Any]]:
            sharp, near = [], []
            for found in edge_angles(shape):
                kind = found.kind(limit)
                if kind == "sharp":
                    sharp.append(found.edge)
                elif kind == "nearly_smooth":
                    near.append(found.edge)
            return sharp, near

        return work

    def show(self, tab: DocumentTab, result: tuple[list[Any], list[Any]]) -> None:
        """Draw the two edge sets and say how many there are."""
        sharp, near = result
        overlay.show_layer(tab.viewport, "edge_angle_sharp", sharp, SHARP_COLOR, 3.0)
        overlay.show_layer(tab.viewport, "edge_angle_near", near, NEAR_COLOR, 3.0)
        self.window.status.setText(
            strings.EDGE_ANGLE_FOUND.format(
                sharp=len(sharp), near=len(near), limit=f"{self.limit:g}"
            )
        )

    def hide(self, tab: DocumentTab) -> None:
        """Take the edge colours away."""
        overlay.show_layer(tab.viewport, "edge_angle_sharp", [], SHARP_COLOR)
        overlay.show_layer(tab.viewport, "edge_angle_near", [], NEAR_COLOR)

    def failed_text(self, message: str) -> str:
        """Status text for a failed analysis."""
        return strings.EDGE_ANGLE_FAILED.format(reason=message)
