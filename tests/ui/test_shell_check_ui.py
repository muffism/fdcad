"""Shell's Check Walls button (TR147 item 2, D998)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui import strings
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_check_walls_answers_in_the_panel(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    window.commands.actions["feature.shell"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "check_walls")
    assert form.check_walls()
    qtbot.waitUntil(
        lambda: form.check_result.text() not in ("", strings.SHELL_CHECK_WORKING), timeout=30000
    )
    assert "wall" in form.check_result.text()
    window.panel.reject()
