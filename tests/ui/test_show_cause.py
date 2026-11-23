"""Show the cause of an error in the app (TR288, D773)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.rebuild.causes import SHOW_CAUSE
from fdcad.ui.errors.panel import entries
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.rebuild.test_causes import _deleted_body_under_a_sketch
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_show_cause_selects_the_feature_and_errors_sort_by_cause(
    qtbot: QtBot, window: MainWindow
) -> None:
    doc, _ext, delete, user = _deleted_body_under_a_sketch()
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    rows = entries(session)
    assert rows[0].fid == user  # the error with a cause comes first
    fix = next(f for f in rows[0].issue.fixes if f.action == SHOW_CAUSE)
    window.apply_fix(user, fix)
    assert window.tree is not None and window.tree.selected_id() == delete
    assert "Delete Top" in window.status.text()
    assert not session.undo.canUndo()  # showing the cause changes nothing
