"""Layer Preview in the 3D view (TR315, D993).

Lines on the part at every layer height of the active printer profile, across
the build direction of the print orientation, so small details can be judged
against the layers. Display only: nothing in the part changes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_print as text
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools import overlay
from fdcad.ui.print_tools.toggle import ToggleOverlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab

LAYER = "layer_preview"
COLOR = DATA["fits"]


class LayerPreview(ToggleOverlay):
    """Draws the layer lines while it is on."""

    def work_for(self, tab: DocumentTab) -> Callable[[], Any] | None:
        """Cut the part at every layer in the background."""
        from fdcad.core.printing import orientation
        from fdcad.core.printing.layer_lines import layer_lines

        report = tab.session.report
        if report is None or report.body is None:
            self.window.status.setText(text.LAYERS_NOTHING)
            return None
        body = report.body
        setup = dict(tab.session.document.print_setup or {})
        profile = print_settings.active_profile(self.window.settings)
        self.height = profile.layer_height

        def work() -> Any:
            try:
                face = orientation.down_face(body, setup)
            except orientation.OrientationError:
                face = None
            return layer_lines(body.shape, orientation.build_direction(face), profile.layer_height)

        return work

    def show(self, tab: DocumentTab, result: Any) -> None:
        """Draw the lines and say how many layers there are."""
        overlay.show_layer(tab.viewport, LAYER, result.edges, COLOR, 1.0)
        if result.problem:  # no lines could be worked out: say why (D2635)
            self.window.status.setText(result.problem)
            return
        msg = text.LAYERS_SHOWN.format(layers=result.layers, height=f"{self.height:g}")
        if result.step > 1:
            msg = f"{msg} {text.LAYERS_EVERY.format(step=result.step)}"
        self.window.status.setText(msg)

    def hide(self, tab: DocumentTab) -> None:
        """Take the lines away."""
        overlay.show_layer(tab.viewport, LAYER, [], COLOR)
