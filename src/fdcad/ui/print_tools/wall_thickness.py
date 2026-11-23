"""Wall thickness analysis in the 3D view (PLAN Phase 4, DECISIONS D414).

Faces on walls thinner than the active printer profile's minimum wall are
painted purple; faces that are thin only in part are painted pink. The work
runs in a kernel job. Display only: nothing in the part changes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_finish as finish_text
from fdcad.ui import strings_print as text
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools import jobs, overlay
from fdcad.ui.print_tools.toggle import ToggleOverlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab

FULL_COLOR = DATA["wall_full"]
PARTIAL_COLOR = DATA["wall_partial"]


def _faces(count: int) -> str:
    return f"{count} face" if count == 1 else f"{count} faces"


class WallThicknessAnalysis(ToggleOverlay):
    """Colours faces on thin walls while it is on."""

    min_wall = 0.0

    def work_for(self, tab: DocumentTab) -> Callable[[], list[Any]] | None:
        """Find the thin walls in the background."""
        from fdcad.core.printing.wall_thickness import thin_walls

        report = tab.session.report
        if report is None or report.body is None:
            self.window.status.setText(text.WALL_NOTHING)
            return None
        shape = report.body.shape
        min_wall = print_settings.active_profile(self.window.settings).min_wall
        target = print_settings.wall_target(self.window.settings)  # TR87 (D1808)
        if target > 0:
            min_wall = target
        self.min_wall = min_wall
        self._hover_on(tab)
        return lambda: thin_walls(shape, min_wall)

    def show(self, tab: DocumentTab, result: list[Any]) -> None:
        """Paint the faces and say how many there are and the thinnest wall."""
        colors = [(f.face, FULL_COLOR if f.full else PARTIAL_COLOR) for f in result]
        overlay.paint_faces(tab.viewport, colors)
        wall = f"{self.min_wall:g}"
        if not result:
            self.window.status.setText(text.WALL_NONE.format(wall=wall))
            return
        full = sum(1 for f in result if f.full)
        thinnest = min(f.thinnest for f in result)
        self.window.status.setText(
            text.WALL_FOUND.format(
                wall=wall,
                full=_faces(full),
                partial=_faces(len(result) - full),
                thinnest=f"{thinnest:.2f}",
            )
        )

    def hide(self, tab: DocumentTab) -> None:
        """Give the faces their own colours back."""
        overlay.paint_faces(tab.viewport, [])

    # Hover reading (TR87 item 2, D1808) ----------------------------------------------

    _hover_tabs: frozenset[int] = frozenset()
    _hover_busy = False

    def _hover_on(self, tab: DocumentTab) -> None:
        """Read the wall under the cursor while the analysis is on."""
        signal = getattr(tab.viewport, "cursor_point", None)
        if signal is None or id(tab) in self._hover_tabs:
            return
        self._hover_tabs = frozenset({*self._hover_tabs, id(tab)})
        signal.connect(lambda point, t=tab: self.hover(t, point))

    def hover(self, tab: DocumentTab, point: Any) -> None:
        """Measure the wall at ``point`` (a model point on the part, or None) in a kernel
        job and show it in the status bar; one reading at a time."""
        from fdcad.core.printing.wall_point import thickness_at

        report = tab.session.report
        if not self.on or point is None or report is None or report.body is None:
            return
        if self._hover_busy:
            return
        self._hover_busy = True
        shape = report.body.shape
        where = (float(point[0]), float(point[1]), float(point[2]))

        def done(value: float | None) -> None:
            self._hover_busy = False
            if self.on and value is not None:
                self.window.status.setText(
                    finish_text.WALL_HERE.format(value=f"{value:.2f}", wall=f"{self.min_wall:g}")
                )

        def failed(_message: str) -> None:
            self._hover_busy = False

        jobs.start(lambda: thickness_at(shape, where), done, failed)

    def failed_text(self, message: str) -> str:
        """Status text for a failed analysis."""
        return text.WALL_FAILED.format(reason=message)
