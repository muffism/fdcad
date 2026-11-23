"""Build volume check (PLAN Phase 2, DECISIONS D353): the printer bed and build
volume drawn in the 3D view under the part as it would print, with a warning
when the part does not fit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_print as text
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools import overlay
from fdcad.ui.print_tools.toggle import ToggleOverlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.core.printing.orientation import FitResult
    from fdcad.ui.main_window.window import DocumentTab

LAYER = "build_volume"
FIT_COLOR = DATA["fits"]
TOO_BIG_COLOR = DATA["too_big"]


@dataclass
class VolumeResult:
    """What the background check found."""

    fit: FitResult
    bed: Any
    box: Any
    note: str


def _size(values: tuple[float, float, float], units: str) -> str:
    scale = 25.4 if units == "in" else 1.0
    digits = 3 if units == "in" else 1
    return " x ".join(f"{v / scale:.{digits}f}" for v in values) + f" {units}"


class BuildVolume(ToggleOverlay):
    """Shows the bed and build volume of the active printer profile."""

    def work_for(self, tab: DocumentTab) -> Callable[[], VolumeResult] | None:
        """Lay the part on the bed and compare it with the build volume (background)."""
        from fdcad.core.printing import orientation

        report = tab.session.report
        if report is None or report.body is None:
            self.window.status.setText(text.VOLUME_NOTHING)
            return None
        body = report.body
        setup = dict(tab.session.document.print_setup or {})
        profile = print_settings.active_profile(self.window.settings)
        from fdcad.ui.print_tools.fit_tool import tab_fit

        fit = tab_fit(tab)  # Scale to Fit Printer (TR185)

        def work() -> VolumeResult:
            note = ""
            try:
                face = orientation.down_face(body, setup)
            except orientation.OrientationError as exc:
                face, note = None, text.ORIENT_LOST.format(reason=exc)
            found = orientation.check_fit(body.shape, face, profile, fit)
            bed, box = orientation.volume_shapes(body.shape, face, profile, fit)
            return VolumeResult(found, bed, box, note)

        self.printer = profile.name
        return work

    def message(self, result: VolumeResult, units: str) -> str:
        """The status bar text for ``result``."""
        fit = result.fit
        values = {
            "printer": self.printer,
            "size": _size(fit.size, units),
            "volume": _size(fit.volume, units),
            "axes": ", ".join(fit.too_large),
            "bodies": fit.bodies,
            "too_big": fit.too_big,
        }
        if fit.bodies > 1:
            msg = text.VOLUME_BODIES_FIT if fit.fits else text.VOLUME_BODIES_TOO_BIG
        else:
            msg = text.VOLUME_FITS if fit.fits else text.VOLUME_TOO_BIG
        msg = msg.format(**values)
        if fit.in_zones:  # TR413 (D992)
            msg = f"{msg} {text.VOLUME_IN_ZONES.format(count=fit.in_zones)}"
        if fit.too_tall:
            msg = f"{msg} {text.VOLUME_TOO_TALL.format(count=fit.too_tall)}"
        return f"{msg} {result.note}".strip()

    def show(self, tab: DocumentTab, result: VolumeResult) -> None:
        """Draw the bed and the volume edges, green when the part fits, red when not."""
        color = FIT_COLOR if result.fit.fits else TOO_BIG_COLOR
        overlay.show_layer(tab.viewport, LAYER + "_bed", [result.bed], color, shaded=True)
        overlay.show_layer(tab.viewport, LAYER, [result.box], color, width=1.5)
        self.window.status.setText(self.message(result, tab.session.document.units.value))

    def hide(self, tab: DocumentTab) -> None:
        """Take the bed and volume away."""
        overlay.show_layer(tab.viewport, LAYER + "_bed", [], FIT_COLOR)
        overlay.show_layer(tab.viewport, LAYER, [], FIT_COLOR)

    def failed_text(self, message: str) -> str:
        """Status text for a failed check."""
        return text.VOLUME_FAILED.format(reason=message)
