"""Recently Edited and naming new features as they are made (TR221, D963)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui import strings
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _submenu(menu, title):  # type: ignore[no-untyped-def]
    for action in menu.actions():
        if action.menu() is not None and action.text() == title:
            return action.menu()
    return None


def test_recently_edited_lists_applied_features(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    before = window.tree.empty_menu()
    assert before is None or _submenu(before, strings.RECENTLY_EDITED) is None
    window.panel.applied.emit(ids["boss"], False)
    window.panel.applied.emit(ids["plate"], False)
    assert tab.session.recent_edits[:2] == [ids["plate"], ids["boss"]]
    menu = window.tree.empty_menu()
    assert menu is not None
    sub = _submenu(menu, strings.RECENTLY_EDITED)
    assert sub is not None
    names = [a.text() for a in sub.actions()]
    doc = tab.session.document
    assert names[:2] == [doc.feature(ids["plate"]).name, doc.feature(ids["boss"]).name]
    seen: list[str] = []
    window.tree.edit_requested.disconnect()
    window.tree.edit_requested.connect(seen.append)
    sub.actions()[1].trigger()
    assert seen == [ids["boss"]]


def test_new_feature_name_opens_for_typing(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    window.settings.name_new_features = True
    renamed: list[str] = []
    window.tree.rename = renamed.append  # type: ignore[method-assign]
    window.panel.applied.emit(ids["boss"], True)
    tab.session.request_rebuild(force=True)
    qtbot.waitUntil(lambda: renamed == [ids["boss"]], timeout=20000)
