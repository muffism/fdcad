"""The command search box at the top left (owner request 2026-10-30)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_workflow import _folders, new_part, window  # noqa: F401


def test_box_sits_before_the_command_tabs(window: MainWindow) -> None:  # noqa: F811
    search = window.command_search
    assert window.command_tabs.cornerWidget(Qt.Corner.TopRightCorner) is search
    assert search.isVisible() and "Ctrl+K" in search.placeholderText()


def test_finds_by_name_and_by_search_word(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    new_part(qtbot, window)
    search = window.command_search
    search.setText("revol")
    names = [a.text().replace("&", "") for a in search.matches]
    assert names[:2] == ["Revolved Boss", "Revolved Cut"] or "Revolved Boss" in names
    search.setText("spin")  # a search word of Revolve
    assert any("Revolve" in a.text() for a in search.matches)
    search.setText("thread")
    assert search.matches
    search.setText("zzzz no such tool")
    # Empty state (U8.3): one line that says nothing matches, which does not run.
    assert not search.matches and search.popup.count() == 1
    assert "zzzz no such tool" in search.popup.item(0).text()
    assert search.run() is False
    search.setText("")
    assert not search.popup.isVisible()


def test_enter_runs_the_highlighted_command(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    new_part(qtbot, window)
    search = window.command_search
    ran: list[bool] = []
    action = window.commands.actions["view.fit"]
    action.triggered.connect(lambda: ran.append(True))
    search.setFocus()
    search.setText("zoom to fit")
    assert search.matches and search.matches[0] is action
    qtbot.keyClick(search, Qt.Key.Key_Return)
    assert ran == [True] and search.text() == ""
    search.setText("fit")
    qtbot.keyClick(search, Qt.Key.Key_Escape)
    assert search.text() == "" and not search.popup.isVisible()


def test_box_is_right_of_the_tabs(window: MainWindow) -> None:  # noqa: F811
    search, bar = window.command_search, window.command_tabs.tabBar()
    assert bar.geometry().right() <= search.geometry().left()
