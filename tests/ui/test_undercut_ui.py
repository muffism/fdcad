"""Undercut Analysis in the app (TR83, D864)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools.undercut import COLORS
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]


def test_plate_has_no_undercut_and_zoom(qtbot: QtBot, window: MainWindow) -> None:
    assert BY_ID["evaluate.undercut"].group == "Evaluate"
    tab, _ext = plate_tab(qtbot, window)
    analysis = window.undercut_analysis
    window.commands.actions["evaluate.undercut"].trigger()
    assert analysis.panel.isVisible()
    qtbot.waitUntil(lambda: "undercut faces" in window.status.text(), timeout=20000)
    assert window.status.text().startswith("0 undercut faces")
    painted = [c for _f, c in tab.viewport.painted_faces]  # type: ignore[attr-defined]
    assert len(painted) == 6 and COLORS["undercut"] not in painted
    side = analysis.legend["side"].text()
    assert side.endswith(": 4") or side.endswith(": 2")
    assert analysis.zoom_to("undercut") == []
    window.commands.actions["evaluate.undercut"].trigger()
    assert tab.viewport.painted_faces == []  # type: ignore[attr-defined]
