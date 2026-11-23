"""Sketch Colour from the tree (TR233, D928)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.appearance import sketch_color
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    new_part,
    rectangle_sketch,
    window,
)


def test_sketch_colour_is_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    session = tab.session
    tree = window.tree
    assert tree is not None
    item = tree.item_for(sid)
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None and "Sketch Colour" in [a.text() for a in menu.actions()]
    assert tree.pick_sketch_color(sid, "#FF8800")
    assert sketch_color(session.document.appearance, sid) == "#FF8800"
    tab.refresh_sketches()  # draws with the colour; no rebuild needed
    menu = tree._context_menu(session, tree.item_for(sid))  # type: ignore[arg-type]
    assert menu is not None
    clear = next(a for a in menu.actions() if a.text() == "Usual Sketch Colour")
    clear.trigger()
    assert sketch_color(session.document.appearance, sid) is None
    session.undo.undo()
    session.undo.undo()
    assert sketch_color(session.document.appearance, sid) is None
