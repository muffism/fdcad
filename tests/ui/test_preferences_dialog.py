"""Preferences dialog."""

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.units import UnitSystem
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Navigation, Settings, Theme


def _settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


def test_shows_current_values(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.theme = Theme.DARK
    settings.autosave_minutes = 7
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    assert dialog.theme_box.currentData() is Theme.DARK
    assert dialog.autosave_box.value() == 7
    assert dialog.units_box.currentData() is UnitSystem.MM
    assert dialog.windowTitle() == "Preferences"


def test_ok_saves_values(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    dialog.units_box.setCurrentIndex(dialog.units_box.findData(UnitSystem.IN))
    dialog.navigation_box.setCurrentIndex(dialog.navigation_box.findData(Navigation.TRACKPAD))
    dialog.autosave_box.setValue(12)
    dialog.accept()
    assert settings.default_units is UnitSystem.IN
    assert settings.navigation is Navigation.TRACKPAD
    assert settings.autosave_minutes == 12


def test_preferences_leave_no_dialog_behind(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Round 10a (D599): every open left a hidden dialog of about 300 widgets, so each
    # later theme change restyled more of them (Preferences OK took 80 s in the sweep).
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QDialog

    from fdcad.ui.main_window.window import MainWindow

    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    win = MainWindow(_settings(tmp_path))
    qtbot.addWidget(win)
    for _ in range(3):
        win.preferences()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not win.findChildren(PreferencesDialog)


def test_pick_distance_is_saved_and_scales_picking(qtbot: QtBot, tmp_path: Path) -> None:
    """TR313 (D917)."""
    from fdcad.ui.input import pick_size

    settings = _settings(tmp_path)
    assert settings.pick_size == "normal"
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    assert dialog.pick_size_box.currentData() == "normal"
    dialog.pick_size_box.setCurrentIndex(dialog.pick_size_box.findData("large"))
    dialog.accept()
    assert settings.pick_size == "large"
    settings.store.setValue("selection/pick_size", "huge")  # unknown: Normal
    assert settings.pick_size == "normal"
    try:
        pick_size.set_size("large")
        assert pick_size.scale() == 1.5
        from fdcad.ui.sketch_tools.canvas import PICK_PX, SketchCanvas

        class _Fake:
            scale = 2.0

        assert SketchCanvas.tolerance.fget(_Fake()) == PICK_PX * 1.5 / 2.0  # type: ignore[attr-defined]
    finally:
        pick_size.set_size("normal")
