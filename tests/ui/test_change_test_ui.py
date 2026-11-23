"""Change Test window (TR287, D774)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["evaluate.change_test"].label == "Change Test"
    assert BY_ID["evaluate.change_test"].keys == () and audit("evaluate.change_test") == []


def test_run_lists_every_value_and_selects_its_feature(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    tool = window.change_test
    assert window.commands.trigger("evaluate.change_test")
    tool.percent.setValue(5.0)
    tool.steps.setValue(1)
    before = tab.session.document.features[-1].params.copy()
    assert tool.run()
    qtbot.waitUntil(lambda: tool.result is not None, timeout=60000)
    assert tool.found.count() == len(tool.rows) > 0
    assert "Tested" in tool.summary.text()
    tool.found.setCurrentRow(0)
    assert window.tree is not None and window.tree.selected_id() is not None
    assert tab.session.document.features[-1].params == before  # the part is unchanged
    assert not tab.session.is_dirty
