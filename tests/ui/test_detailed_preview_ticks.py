"""Detailed preview ticks on the Extrude and Rib panels (TR164, D1809)."""

from __future__ import annotations

from typing import Any

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_extrude_tick_marks_only_the_preview_copy(qtbot: QtBot, window: MainWindow) -> None:
    _tab, ids = _open(qtbot, window)
    window.edit_feature(ids["boss"])
    panel = window.panel
    assert hasattr(panel, "detailed_box")
    sent: list[Any] = []
    panel.values_changed.connect(sent.append)
    try:
        panel.detailed_box.setChecked(True)
        assert sent and sent[-1] is not None and sent[-1].data.get("preview_detailed") is True
        made = panel.current_feature()
        assert made is not None and "preview_detailed" not in made.data
    finally:
        panel.detailed_box.setChecked(False)
    panel.reject()


def test_rib_tick_marks_only_the_preview_copy(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    window.commands.actions["feature.rib"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "detailed")
    form.detailed.setChecked(True)
    try:
        feature = window.panel.feature
        assert feature is not None
        assert form.for_preview(feature).data.get("preview_detailed") is True
        assert "preview_detailed" not in feature.data
    finally:
        form.detailed.setChecked(False)
    window.panel.reject()
