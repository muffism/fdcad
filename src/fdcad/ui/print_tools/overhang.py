"""Overhang analysis in the 3D view (PLAN Phase 2, DECISIONS D354).

Faces steeper than the active profile's overhang angle, measured from the build
direction of the print orientation, are painted red; faces that overhang only in
part are painted orange. Display only: nothing in the part changes.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_print as text
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools import overlay
from fdcad.ui.print_tools.toggle import ToggleOverlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab

FULL_COLOR = DATA["overhang_full"]
PARTIAL_COLOR = DATA["overhang_partial"]


def _faces(count: int) -> str:
    return f"{count} face" if count == 1 else f"{count} faces"


class OverhangAnalysis(ToggleOverlay):
    """Colours overhanging faces while it is on."""

    def work_for(self, tab: DocumentTab) -> Callable[[], tuple[list[Any], str]] | None:
        """Find the overhanging faces in the background."""
        from fdcad.core.printing import orientation
        from fdcad.core.printing.overhang import overhangs

        report = tab.session.report
        if report is None or report.body is None:
            self.window.status.setText(text.OVERHANG_NOTHING)
            return None
        body = report.body
        doc = tab.session.document
        setup = dict(doc.print_setup or {})
        profile = print_settings.active_profile(self.window.settings)
        self.angle = profile.overhang_angle

        def work() -> tuple[list[Any], str]:
            note = ""
            try:
                face = orientation.down_face(body, setup)
            except orientation.OrientationError as exc:
                face, note = None, text.ORIENT_LOST.format(reason=exc)
            up = orientation.build_direction(face)
            found = overhangs(body.shape, up, profile.overhang_angle)
            from fdcad.core.printing.overhang_fix import rounded_overhangs

            rounded = rounded_overhangs(doc, body, [f.face for f in found])  # TR410
            if rounded:
                note = " ".join(t for t in (note, text.OVERHANG_ROUNDED.format(n=rounded)) if t)
            return found, note

        return work

    def show(self, tab: DocumentTab, result: tuple[list[Any], str]) -> None:
        """Paint the faces and say how many there are."""
        found, note = result
        colors = [(f.face, FULL_COLOR if f.full else PARTIAL_COLOR) for f in found]
        overlay.paint_faces(tab.viewport, colors)
        degrees = f"{math.degrees(self.angle):g}"
        if not found:
            msg = text.OVERHANG_NONE.format(angle=degrees)
        else:
            full = sum(1 for f in found if f.full)
            msg = text.OVERHANG_FOUND.format(
                full=_faces(full), partial=_faces(len(found) - full), angle=degrees
            )
        self.window.status.setText(f"{msg} {note}".strip())

    def hide(self, tab: DocumentTab) -> None:
        """Give the faces their own colours back."""
        overlay.paint_faces(tab.viewport, [])

    def failed_text(self, message: str) -> str:
        """Status text for a failed analysis."""
        return text.OVERHANG_FAILED.format(reason=message)
