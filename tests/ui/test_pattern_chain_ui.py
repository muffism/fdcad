"""Pattern Chain from the command (TR141 item 1, D1901)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_shows_the_fields_of_the_listed_steps(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.pattern_chain")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == "pattern_chain"
    form = panel.body_form
    names = [f.name for f in form.shown_fields()]
    assert {"direction", "spacing", "axis", "turns", "instance_values"} <= set(names)
    assert "plane" not in names and "factor" not in names
    form.widgets["steps"].setText("scale, mirror")
    names = [f.name for f in form.shown_fields()]
    assert "factor" in names and "plane" in names and "spacing" not in names
    made = panel.current_feature()
    assert made is not None and made.params["steps"] == "scale, mirror"
    panel.reject()
