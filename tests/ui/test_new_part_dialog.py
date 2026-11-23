"""Tests for the New Part dialog."""

from pytestqt.qtbot import QtBot

from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.new_part_dialog import NewPartDialog


def test_default_is_millimetres(qtbot: QtBot) -> None:
    dialog = NewPartDialog()
    qtbot.addWidget(dialog)
    assert dialog.mm_button.isChecked() is True
    assert dialog.units() is UnitSystem.MM
    assert dialog.windowTitle() == "New Part"


def test_inch_default(qtbot: QtBot) -> None:
    dialog = NewPartDialog(UnitSystem.IN)
    qtbot.addWidget(dialog)
    assert dialog.units() is UnitSystem.IN


def test_choosing_inches(qtbot: QtBot) -> None:
    dialog = NewPartDialog()
    qtbot.addWidget(dialog)
    dialog.inch_button.setChecked(True)
    assert dialog.units() is UnitSystem.IN
