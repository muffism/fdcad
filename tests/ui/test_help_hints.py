"""First time hints, the panel help button and What's New (TR291, D2018)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from fdcad.ui.help import hints, newest_changes
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_hints_show_once_and_turn_off(tmp_path: Path) -> None:
    store = QSettings(str(tmp_path / "h.ini"), QSettings.Format.IniFormat)
    assert hints.should_show(store, "extrude")
    hints.mark_seen(store, "extrude")
    assert not hints.should_show(store, "extrude") and hints.should_show(store, "revolve")
    hints.turn_off(store)
    assert not hints.should_show(store, "revolve")
    hints.reset(store)
    assert hints.should_show(store, "extrude")
    assert "Show Me" in hints.hint_for("interlock") and hints.hint_for("no_such_type") == ""


def test_panel_hint_and_help_button(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.body_tools import flow

    _open(qtbot, window)
    window.settings.store.remove(hints.SEEN_KEY)
    window.settings.store.remove(hints.OFF_KEY)
    opened: list[bool] = []
    window.help.help_for_tool = lambda: opened.append(True)  # type: ignore[method-assign]
    assert flow.start(window, "feature.interlock")
    panel = window.panel
    assert not panel.hint.isHidden() and "Show Me" in panel.hint.text()
    panel.help_button.click()
    assert opened == [True]
    panel.reject()
    assert flow.start(window, "feature.interlock")
    assert panel.hint.isHidden()  # once per tool
    panel.reject()


def test_whats_new_reads_the_change_log(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = newest_changes(Path(__file__).parents[2] / "CHANGELOG.md")
    assert text.startswith("## [") and "### Added" in text
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    dialog = window.help.show_whats_new()
    assert dialog.objectName() == "whats_new"  # type: ignore[attr-defined]
