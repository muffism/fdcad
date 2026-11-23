"""The freeze bar in the tree and the edit guard (TR98, D2507)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document import freeze
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.tree import freeze_bar
from fdcad.ui.tree.feature_tree import FID_ROLE
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def _menu_texts(window: MainWindow, fid: str) -> list[str]:
    tree = window.tree
    assert tree is not None and tree.session is not None
    item = tree.item_for(fid)
    assert item is not None
    menu = tree._context_menu(tree.session, item)
    assert menu is not None
    return [a.text() for a in menu.actions()]


def test_freeze_unfreeze_and_edit_guard(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = _open_plate(qtbot, window)
    session = tab.session
    tree = window.tree
    assert tree is not None
    assert freeze_bar.FREEZE_HERE in _menu_texts(window, ext)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert freeze_bar.move(session, ext)
    assert freeze.place(session.document) == ext
    tree.refresh()
    marks = [i.data(0, FID_ROLE) for i in tree.all_items()]
    assert freeze_bar.MARK in marks
    assert marks.index(freeze_bar.MARK) > marks.index(ext)  # below it (and its sketch)
    assert freeze_bar.MOVE_ABOVE in _menu_texts(window, ext)
    window.edit_feature(ext)
    assert "above the freeze bar" in window.status.text()
    bar = next(i for i in tree.all_items() if i.data(0, FID_ROLE) == freeze_bar.MARK)
    menu = tree._context_menu(session, bar)
    assert menu is not None
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        next(a for a in menu.actions() if a.text() == freeze_bar.UNFREEZE_ALL).trigger()
    assert freeze.place(session.document) is None
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert freeze.place(session.document) == ext
