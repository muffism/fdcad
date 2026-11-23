"""Cut away the part in front of the sketch plane (TR113, D844)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_sketch_mode import _folders, _front_sketch, _new_part, window

__all__ = ["_folders", "window"]


def test_toggle_is_kept_in_the_sketch(qtbot: QtBot, window: MainWindow) -> None:
    win = window
    _new_part(qtbot, win)
    canvas = _front_sketch(qtbot, win)
    mode = win.sketch_mode
    assert mode is not None
    assert not mode.cut_away_action.isChecked()
    assert mode.toggle_cut_away() is True
    assert canvas.edit.feature.data.get("cut_away") is True
    assert "hidden" in win.status.text()
    assert mode.toggle_cut_away() is False
    assert "cut_away" not in canvas.edit.feature.data
    mode.toggle_cut_away()
    feature = canvas.edit.to_feature()
    assert feature.data.get("cut_away") is True  # saved with the sketch
    mode.cancel()
