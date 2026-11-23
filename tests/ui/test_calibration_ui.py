"""Fit Calibration and Keep Measured Fit (TR358, D2000)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.print_settings import active_profile
from fdcad.ui.print_tools import calibration_tool
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_make_the_plate_and_keep_the_fit(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def three(dialog: calibration_tool.CalibrationDialog) -> bool:
        dialog.count.setValue(3)
        return True

    monkeypatch.setattr(calibration_tool, "run", three)
    before = window.tabs.count()
    assert calibration_tool.make_calibration_part(window)
    assert window.tabs.count() == before + 1
    doc = window.current.session.document
    assert [v.name for v in doc.variables] == ["Pin", "Gap1", "Gap2", "Gap3"]
    assert calibration_tool.keep_measured_fit(window, 0.15)
    assert active_profile(window.settings).fit_tolerance == pytest.approx(0.15)
