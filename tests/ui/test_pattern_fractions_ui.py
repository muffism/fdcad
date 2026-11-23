"""Linear Pattern Fractions field (TR366, D1018)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_fractions_show_for_their_law_and_are_written(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.linear_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    law = form.widgets["law1"]
    law.setCurrentIndex(law.findData("fractions"))
    line = form.widgets["fractions1"]
    line.setText("0.2, 1")
    names = [f.name for f in form.shown_fields()]
    assert "fractions1" in names
    made = panel.current_feature()
    assert made is not None and made.params["law1"] == "fractions"
    assert made.params["fractions1"] == "0.2, 1"
    law.setCurrentIndex(law.findData("even"))
    assert "fractions1" not in [f.name for f in form.shown_fields()]
    panel.reject()
