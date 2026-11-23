"""New parts get distinct names: Untitled, Untitled 2 and so on (bug hunt O10a-9, D2682)."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession, free_untitled
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _new(window: MainWindow) -> DocumentTab:
    return window.add_session(DocumentSession.new(UnitSystem.MM, window))


def test_free_untitled_takes_the_first_free_number() -> None:
    assert free_untitled(set()) == "Untitled"
    assert free_untitled({"untitled"}) == "Untitled 2"
    assert free_untitled({"untitled", "untitled 2", "untitled 4"}) == "Untitled 3"
    assert free_untitled({"untitled 2"}) == "Untitled"


def test_new_parts_have_distinct_names_in_tabs_and_the_close_prompt(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tabs = [_new(window) for _ in range(3)]
    titles = [window.tabs.tabText(window.tabs.indexOf(t)) for t in tabs]
    assert titles == ["Untitled", "Untitled 2", "Untitled 3"]
    asked: list[str] = []

    def question(_parent: Any, _title: str, text: str, *_rest: Any) -> Any:
        asked.append(text)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", question)
    for tab in tabs:
        tab.session.mark_recovered()  # unsaved, so closing asks
        window._ask_unsaved(window.tabs.indexOf(tab))
    assert [a.split("?")[0] for a in asked] == [
        "Save changes to Untitled before closing",
        "Save changes to Untitled 2 before closing",
        "Save changes to Untitled 3 before closing",
    ], asked
    assert window._default_name(tabs[1], ".fdprt") == "Untitled 2.fdprt"
    for tab in tabs:
        tab.session.wait()


def test_a_freed_name_is_used_again(qtbot: QtBot, window: MainWindow) -> None:
    first, second = _new(window), _new(window)
    assert second.session.title == "Untitled 2"
    assert window.close_tab(window.tabs.indexOf(first), ask=False)
    third = _new(window)
    assert third.session.title == "Untitled"  # the lowest name not in use
    for tab in (second, third):
        tab.session.wait()
