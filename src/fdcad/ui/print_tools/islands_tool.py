"""Evaluate, Suction Cups and Islands (TR409, DECISIONS D1213).

Looks at the part as it lies on the bed in the background, marks each suction
cup and floating island in the view, and offers the fixes: Drain Holes for cups
and Suggest Orientation to tilt the part another way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMessageBox

from fdcad.ui import strings_print as text
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

LAYER = "cups_islands"


def ask(window: MainWindow, message: str, cups: int) -> str:
    """The fix the user picks: "drain", "orient" or "" (a seam for tests)."""
    box = QMessageBox(QMessageBox.Icon.Information, text.CUPS_TITLE, message, parent=window)
    drain = box.addButton(text.CUPS_DRAIN, QMessageBox.ButtonRole.ActionRole) if cups else None
    orient = box.addButton(text.CUPS_ORIENT, QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Close)
    box.exec()
    clicked = box.clickedButton()
    return (
        "drain" if drain is not None and clicked is drain else "orient" if clicked is orient else ""
    )


def cups_and_islands(window: MainWindow) -> jobs.Job | None:
    """Find and mark cups and islands, then offer the fixes."""
    from fdcad.core.printing import orientation
    from fdcad.core.printing.islands import find
    from fdcad.ui.preferences.print_settings import active_profile
    from fdcad.ui.print_tools.fit_tool import tab_fit
    from fdcad.ui.print_tools.overlay import show_layer

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.CUPS_NOTHING)
        return None
    body = report.body
    setup = dict(tab.session.document.print_setup or {})
    profile = active_profile(window.settings)
    fit = tab_fit(tab)

    def work() -> Any:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
        from OCP.gp import gp_Pnt

        try:
            face = orientation.down_face(body, setup)
        except orientation.OrientationError:
            face = None
        trsf = orientation.placement(body.shape, face, profile, fit)
        found = find(orientation.moved(body.shape, trsf))
        back = trsf.Inverted()
        marks = [
            BRepBuilderAPI_MakeVertex(gp_Pnt(*p).Transformed(back)).Vertex()
            for p in [*found.cup_points, *found.islands]
        ]
        return found, marks

    def done(result: Any) -> None:
        found, marks = result
        if window.current is not tab:
            return
        from fdcad.ui.themes.theme import DATA

        show_layer(tab.viewport, LAYER, marks, DATA["overhang_full"], width=6.0)
        if not found.cups and not found.islands:
            window.status.setText(text.CUPS_NONE)
            return
        message = text.CUPS_FOUND.format(
            cups=found.cups, deepest=f"{found.deepest:.1f}", islands=len(found.islands)
        )
        window.status.setText(message)
        choice = ask(window, message, found.cups)
        if choice == "drain":
            from fdcad.ui.body_tools import flow

            flow.start(window, "feature.drain_holes")
        elif choice == "orient":
            from fdcad.ui.print_tools.arrange_tool import suggest_orientation

            suggest_orientation(window)

    return jobs.start(
        work, done, lambda reason: window.status.setText(text.CUPS_FAILED.format(reason=reason))
    )
