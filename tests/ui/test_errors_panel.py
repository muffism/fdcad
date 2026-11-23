"""Errors panel, one click fixes and the bodies folder (PLAN 5A items 3, 6 and 7)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QTreeWidgetItem
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, Param
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.show()
    win.finish_setup()
    yield win
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _open(qtbot: QtBot, win: MainWindow, doc: Document) -> DocumentTab:
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _touching() -> tuple[Document, str]:
    doc, _ = plate()
    s = Sketch()
    rect(s, 50, 50, 60, 60)  # touches the plate only along one edge
    touch = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    return doc, touch


def _separate() -> Document:
    doc, _ = plate()
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    return doc


def test_zero_thickness_entry_and_fix(qtbot: QtBot, window: MainWindow) -> None:
    doc, touch = _touching()
    tab = _open(qtbot, window, doc)
    panel = window.errors
    assert panel is not None
    codes = [e.issue.code for e in panel.items]
    assert sorted(codes) == ["separate_body", "zero_thickness"]
    assert all(e.fid == touch for e in panel.items)
    assert window.left is not None
    assert "Errors (2)" in [window.left.tabToolTip(i) for i in range(window.left.count())]
    panel.select(codes.index("zero_thickness"))
    assert [b.text() for b in panel.fix_buttons] == ["Add 0.01 mm"]
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.fix_buttons[0].click()
    depth = tab.session.document.feature(touch).params["depth"]
    assert isinstance(depth, Param) and depth.value == pytest.approx(10.01)
    assert depth.expr == "10.01"
    assert tab.session.undo.count() == 1


def test_separate_body_keep_and_bodies_folder(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window, _separate())
    assert window.tree is not None
    folder = window.tree.topLevelItem(1)  # under the part name row
    assert folder is not None and folder.text(0) == "Solid Bodies (2)"
    assert folder.childCount() == 2
    assert window.bodies.text() == "2 bodies"
    panel = window.errors
    assert panel is not None and len(panel.items) == 1
    panel.select(0)
    (keep,) = panel.fix_buttons
    fid = panel.items[0].fid
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        keep.click()
    assert panel.items == []
    # Saved in the part with one undoable step (D527); the geometry is unchanged.
    assert tab.session.undo.count() == 1
    assert tab.session.document.feature(fid).data["keep_separate_body"] is True
    report = tab.session.report
    assert report is not None and report.results[fid].issues == []
    assert report.rebuilt == []  # the key is left out of the rebuild key
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert "keep_separate_body" not in tab.session.document.feature(fid).data
    assert len(panel.items) == 1


def test_warn_about_separate_bodies_menu(qtbot: QtBot, window: MainWindow) -> None:
    doc = _separate()
    fid = doc.features[-1].id
    doc.feature(fid).data["keep_separate_body"] = True
    tab = _open(qtbot, window, doc)
    panel = window.errors
    tree = window.tree
    assert panel is not None and tree is not None and panel.items == []

    def row() -> QTreeWidgetItem:
        found = tree.findItems("*", Qt.MatchFlag.MatchWildcard | Qt.MatchFlag.MatchRecursive)
        return next(i for i in found if i.data(0, Qt.ItemDataRole.UserRole) == fid)

    menu = tree._context_menu(tab.session, row())
    assert menu is not None
    actions = {a.text(): a for a in menu.actions()}
    assert "Warn About Separate Bodies" in actions
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        actions["Warn About Separate Bodies"].trigger()
    assert "keep_separate_body" not in tab.session.document.feature(fid).data
    assert len(panel.items) == 1
    menu = tree._context_menu(tab.session, row())
    assert menu is not None
    assert "Warn About Separate Bodies" not in [a.text() for a in menu.actions()]
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert tab.session.document.feature(fid).data["keep_separate_body"] is True
