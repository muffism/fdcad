"""Goal Seek and Sweep window (TR273, D1020)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.goal_seek import SWEEP, GoalSeekDialog, open_dialog
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.test_goal_seek import block
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _tab(qtbot: QtBot, window: MainWindow):  # type: ignore[no-untyped-def]
    session = DocumentSession(block(), None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["tools.goal_seek"].label == "Goal Seek and Sweep"
    assert BY_ID["tools.goal_seek"].keys == ()
    assert audit("tools.goal_seek") == []


def test_seek_then_use_value_in_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:
    tab = _tab(qtbot, window)
    dialog = GoalSeekDialog(window)
    qtbot.addWidget(dialog)
    assert dialog.variable.currentData() == "h"
    assert dialog.target.currentData() == "volume@Part"
    dialog.start.setValue(1)
    dialog.stop.setValue(30)
    dialog.goal.setValue(6000)
    assert dialog.run()
    qtbot.waitUntil(lambda: not dialog.running, timeout=60000)
    assert dialog.found is not None
    assert dialog.found.value == pytest.approx(15, rel=1e-5)
    assert tab.session.document.variables[0].value == 10  # unchanged until Use Value
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert dialog.use_value()
    assert tab.session.document.variables[0].value == pytest.approx(15, rel=1e-5)
    assert "Use Undo" in dialog.note.text()
    tab.session.undo.undo()
    assert tab.session.document.variables[0].value == 10


def test_sweep_lists_each_step(qtbot: QtBot, window: MainWindow) -> None:
    _tab(qtbot, window)
    dialog = GoalSeekDialog(window)
    qtbot.addWidget(dialog)
    dialog.mode.setCurrentIndex(dialog.mode.findData(SWEEP))
    dialog.start.setValue(5)
    dialog.stop.setValue(15)
    dialog.steps.setValue(3)
    assert dialog.run()
    qtbot.waitUntil(lambda: not dialog.running, timeout=60000)
    assert dialog.table.rowCount() == 3
    assert dialog.table.item(2, 1).text() == "6000"
    assert "3 of 3 steps" in dialog.note.text()
    dialog.table.selectRow(0)
    assert dialog.chosen_value() == pytest.approx(5)


def test_a_part_without_variables_says_what_to_do(qtbot: QtBot, window: MainWindow) -> None:
    tab = _tab(qtbot, window)
    tab.session.document.variables.clear()
    assert open_dialog(window) is None
    assert "Add one in the equations manager" in window.status.text()
