"""Message bars with Don't Show Again, and hidden messages in Preferences (TR203, D959)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.message_bars import MessageBars
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Settings
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


def test_bar_stays_until_closed_and_never_again(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    bars = MessageBars()
    qtbot.addWidget(bars)
    bars.settings = settings
    bar = bars.show_message("demo", "First text", "warning")
    assert bar is not None and bars.show_message("demo", "Second text") is bar  # one bar
    assert bar.label.text() == "Second text"
    bar.close_button.click()
    assert "demo" not in bars.bars
    bar = bars.show_message("demo", "Again")
    assert bar is not None
    bar.never_button.click()
    assert settings.hidden_messages == ["demo"]
    assert bars.show_message("demo", "Hidden now") is None


def test_preferences_show_hidden_messages_again(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.hide_message("rebuilds_paused")
    settings.hide_message("other")
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = PreferencesDialog(settings, parent)
    qtbot.addWidget(dialog)
    assert dialog.hidden_messages.count() == 2
    dialog.hidden_messages.item(0).setSelected(True)
    dialog.show_again.click()
    dialog.accept()
    assert settings.hidden_messages == ["other"]


def test_paused_rebuilds_show_a_bar(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ids = _open(qtbot, window)
    window.pause_action.trigger()
    assert "rebuilds_paused" in tab.message_bars.bars
    window.pause_action.trigger()
    assert "rebuilds_paused" not in tab.message_bars.bars
