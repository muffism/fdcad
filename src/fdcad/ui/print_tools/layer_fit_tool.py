"""Evaluate, Layer Fit Check (TR187 item 1, DECISIONS D1209).

Runs the check on the part as it lies on the bed, with the active printer
profile's layer height and nozzle size as the line width, in the background,
then lists what does not fit in a message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMessageBox

from fdcad.ui import strings_print as text
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

#: The most lines shown; the rest are counted.
SHOWN = 25


def layer_fit(window: MainWindow) -> jobs.Job | None:
    """Check the active part and show the result."""
    from fdcad.core.printing.layer_fit import check, describe
    from fdcad.ui.preferences.print_settings import active_profile
    from fdcad.ui.print_tools.orientation import print_shape_work

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.LAYER_FIT_NOTHING)
        return None
    profile = active_profile(window.settings)
    printed = print_shape_work(tab, profile)
    layer, line = profile.layer_height, profile.nozzle

    def work() -> list[str]:
        shape, _note = printed()
        return [describe(m) for m in check(shape, layer, line)]

    def done(lines: Any) -> None:
        head = text.LAYER_FIT_HEAD.format(layer=f"{layer:g}", line=f"{line:g}")
        if not lines:
            message = text.LAYER_FIT_NONE.format(layer=f"{layer:g}", line=f"{line:g}")
            window.status.setText(message)
            return
        shown = list(lines[:SHOWN])
        if len(lines) > SHOWN:
            shown.append(text.LAYER_FIT_MORE.format(count=len(lines) - SHOWN))
        window.status.setText(text.LAYER_FIT_FOUND.format(count=len(lines)))
        QMessageBox.information(window, text.LAYER_FIT_TITLE, head + "\n\n" + "\n".join(shown))

    return jobs.start(
        work,
        done,
        lambda reason: window.status.setText(text.LAYER_FIT_FAILED.format(reason=reason)),
    )
