"""Body folders in the feature tree (TR153 item 1, D2106)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core import body_folders as bf
from fdcad.core.body_visibility import hidden_names
from fdcad.ui.main_window import body_folders_ui
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.tree.feature_tree import BODY_FOLDER_ROLE
from tests.core.test_body_titles import _two_bodies
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _folder_row(win: MainWindow):  # type: ignore[no-untyped-def]
    tree = win.tree
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        for j in range(top.childCount()):
            child = top.child(j)
            if isinstance(child.data(0, BODY_FOLDER_ROLE), str):
                return child
    return None


def test_folder_hide_and_delete(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc, _named = _two_bodies()
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    monkeypatch.setattr(body_folders_ui, "ask_folder", lambda _p, _c: "Lids")
    window.tree.body_requested.emit("folder_move", 1)
    assert bf.members(session.document, session.report.body, "Lids") == [1]
    window.tree.refresh()  # type: ignore[attr-defined]
    row = _folder_row(window)
    assert row is not None and row.text(0) == "Lids" and row.childCount() == 1
    menu = window.tree._body_folder_menu("Lids")
    assert len(menu.actions()) == 6
    window.tree.body_requested.emit("folder:hide:Lids", -1)
    assert hidden_names(session.document)
    window.tree.body_requested.emit("folder:show:Lids", -1)
    assert not hidden_names(session.document)
    count = len(session.document.features)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.tree.body_requested.emit("folder:delete:Lids", -1)
    assert len(session.document.features) == count + 1
    assert session.document.features[-1].type == "delete_body"
    assert session.report.body_count == 1
    session.undo.undo()
    window.tree.body_requested.emit("folder:remove:Lids", -1)
    assert bf.stored(session.document) == {}
