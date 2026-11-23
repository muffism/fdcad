"""Linked Body Copy: the command and Break Link (TR154, D2417)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui import strings
from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_linked_copy import _cut_hole, _linked
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_opens_with_defaults(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.linked_copy")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == "linked_copy"
    panel.reject()


def test_break_link_from_the_tree_and_undo(qtbot: QtBot, window: MainWindow) -> None:
    doc, ext, fid = _linked()
    hole = _cut_hole(doc, ext)
    session = DocumentSession(doc, None, window)  # type: ignore[arg-type]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tree = window.tree
    assert tree is not None
    item = tree.item_for(fid)
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None and strings.BREAK_BODY_LINK in [a.text() for a in menu.actions()]
    before = [f.id for f in session.document.features]
    assert before.index(hole) > before.index(fid)
    assert tree.break_body_link(fid)
    after = [f.id for f in session.document.features]
    assert after[-1] == fid and session.document.feature(fid).data["link"] is False
    session.undo.undo()
    assert [f.id for f in session.document.features] == before
    assert "link" not in session.document.feature(fid).data
