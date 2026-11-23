"""Keep a measurement from the Measure box (TR190, TR191, D818)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.feature_dims import measurement_labels
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_keep_makes_a_measurement_with_a_label(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    tool = window.measure_tool
    tool.open()
    report = tab.session.report
    assert report is not None and report.body is not None
    tool.picks = [report.body.face(f"{ids['boss']}/cap/end")]
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert tool.keep()
    made = tab.session.document.features[-1]
    assert made.type == "measurement" and made.name == "Measurement 1"
    labels = measurement_labels(tab.session)
    assert labels and labels[0][1].startswith("Measurement 1:")
    tool.close()
