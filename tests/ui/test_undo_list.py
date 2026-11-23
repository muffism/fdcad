"""Edit, Undo To (TR208, D807)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.commands.document import RenameFeature
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_undo_back_to_a_step(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    session = tab.session
    window.fill_undo_menu()
    assert [a.text() for a in window.undo_menu.actions()] == ["Nothing to undo"]
    fid = ids["boss"]
    for name in ("One", "Two", "Three"):
        session.undo.push(RenameFeature(session, fid, name))
    window.fill_undo_menu()
    texts = [a.text() for a in window.undo_menu.actions()]
    assert len(texts) == 3 and texts[0] == "Rename Two"  # newest first
    window.undo_menu.actions()[1].trigger()  # back to before "Two"
    assert session.undo.index() == 1
    assert session.document.feature(fid).name == "One"
