"""Add Loft Section from the tree menu (TR136 item 3, D2404)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QInputDialog
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.ui import strings
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_loft import _square, _two_levels, add_loft
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_add_loft_section_adds_plane_and_sketch_and_undoes(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 3)
    fid = add_loft(doc, [low, high])
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tree = window.tree
    assert tree is not None
    item = tree.item_for(fid)
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None and strings.ADD_LOFT_SECTION in [a.text() for a in menu.actions()]
    opened: list[str] = []
    monkeypatch.setattr(window, "edit_feature", opened.append)
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda *_a, **_k: (1.5, True)))
    count_before = len(session.document.features)
    assert tree.ask_loft_section(fid)
    features = session.document.features
    assert len(features) == count_before + 2
    profiles = session.document.feature(fid).refs["profiles"]
    assert len(profiles) == 3 and opened == [profiles[1]["feature"]]
    session.undo.undo()
    assert len(session.document.features) == count_before
    assert len(session.document.feature(fid).refs["profiles"]) == 2
    assert not tree.add_loft_section(fid, 5.0)  # off the profiles: a message, no change
