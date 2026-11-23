"""Scale to Fit Printer (TR185, D828)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools.fit_tool import tab_fit
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_fit_is_kept_on_the_tab_and_saved_as_a_scale(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ids = _open(qtbot, window)
    tool = window.print_fit
    job = tool.scale_to_fit()
    assert job is not None
    qtbot.waitUntil(lambda: tool.job is None, timeout=20000)
    assert tab_fit(tab) is None  # the small test part fits already
    tool.set_fit(tab, (0.5, 30.0))
    assert tab_fit(tab) == (0.5, 30.0)
    count = len(tab.session.document.features)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert tool.save_as_feature()
    made = tab.session.document.features[count]
    assert made.type == "scale" and made.params["factor"].value == 0.5
    assert tab_fit(tab) == (1.0, 30.0)  # the turn stays a print setting
    tool.clear()
    assert tab_fit(tab) is None
    assert not tool.save_as_feature()
