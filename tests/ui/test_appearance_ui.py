"""Appearance panel, copy and paste, tree row and undo (PHASE2_SPEC P2.11, D254)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, new_document
from fdcad.core.sketch.model import Sketch
from fdcad.ui.appearance.tool import part_display, selected_faces
from fdcad.ui.appearance.tree_rows import APPEARANCE_ROLE
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, rect


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1200, 800)
    win.show()
    win.finish_setup()
    yield win
    win.appearance_tool.close()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _plate() -> Document:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 10.0)
    return doc


def _open(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    session = DocumentSession(_plate(), None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _faces(tab: DocumentTab) -> list[object]:
    report = tab.session.report
    assert report is not None and report.body is not None
    out = []
    exp = TopExp_Explorer(report.body.shape, TopAbs_FACE)
    while exp.More():
        out.append(exp.Current())
        exp.Next()
    return out


def test_commands_exist() -> None:
    for cid in ("edit.appearance", "edit.copy_appearance", "edit.paste_appearance"):
        assert cid in BY_ID


def test_panel_colours_the_part_and_faces_with_undo(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    face = _faces(tab)[0]
    tab.selection = [face]
    names = selected_faces(tab)
    assert len(names) == 1
    window.commands.trigger("edit.appearance")
    panel = window.appearance_tool.panel
    assert panel is not None
    assert panel.target.currentText() == "Selected faces (1)"
    panel.apply("#3A6EA5")
    assert session.document.appearance["faces"] == {names[0]: "#3A6EA5"}
    _color, faces = part_display(tab)
    assert len(faces) == 1 and faces[0][1] == "#3A6EA5"
    # No rebuild for a colour: it is a display change, but undoable.
    assert session.undo.canUndo()
    panel.select_kind("part")
    panel.swatches[4].click()
    assert session.document.appearance["part_color"] == "#C8553D"
    session.undo.undo()
    assert session.document.appearance["part_color"] == "#B4BCC4"
    session.undo.undo()
    assert session.document.appearance["faces"] == {}
    panel.select_kind("face")
    panel.apply("#6BA368")
    assert panel.remove.isEnabled()
    panel.remove.click()
    assert session.document.appearance["faces"] == {}
    assert panel.in_use.count() >= 1
    panel.close_button.click()
    assert window.appearance_tool.panel is None


def test_feature_colour_from_the_tree_and_copy_paste(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    tree = window.tree
    assert tree is not None
    tree.select("f6")
    tool = window.appearance_tool
    tool.open()
    assert tool.panel is not None and tool.panel.target.currentText() == "Extrude f6"
    tool.panel.apply("#E59A2F")
    assert session.document.appearance["features"] == {"f6": "#E59A2F"}
    tool.copy()
    assert tool.copied == "#E59A2F"
    tree.select("f5")  # a sketch: not a target, so paste goes to the selected face
    face = _faces(tab)[2]
    tab.selection = [face]
    tool.paste()
    name = selected_faces(tab)[0]
    assert session.document.appearance["faces"] == {name: "#E59A2F"}
    tab.selection = []
    tool.paste()  # nothing selected: the part
    assert session.document.appearance["part_color"] == "#E59A2F"


def test_paste_without_copy_says_so(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    window.appearance_tool.paste()
    assert "Copy an appearance first" in window.status.text()


def test_tree_row_lists_colours_and_opens_the_panel(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window)
    tree = window.tree
    assert tree is not None
    row = next(
        tree.topLevelItem(i)
        for i in range(tree.topLevelItemCount())
        if tree.topLevelItem(i).data(0, APPEARANCE_ROLE) == "appearances"  # type: ignore[union-attr]
    )
    assert row is not None and row.text(0) == "Appearances (1)" and row.childCount() == 1
    tree.itemDoubleClicked.emit(row, 0)
    assert window.appearance_tool.panel is not None
    window.appearance_tool.panel.apply("#123456")  # the tree follows at once
    row = next(
        tree.topLevelItem(i)
        for i in range(tree.topLevelItemCount())
        if tree.topLevelItem(i).data(0, APPEARANCE_ROLE) == "appearances"  # type: ignore[union-attr]
    )
    assert row is not None and "#123456" in row.child(0).text(0)
    assert tab.session.document.appearance["part_color"] == "#123456"


def test_copy_appearance_of_a_face_takes_its_body_colour(qtbot: QtBot, window: MainWindow) -> None:
    """Round 10c: a face drawn in its body's colour copied the part colour instead."""
    from fdcad.core.appearance import Target
    from fdcad.core.body_visibility import body_of
    from fdcad.core.io import fdef
    from fdcad.ui.appearance.commands import SetAppearance

    sample = Path(__file__).parents[2] / "samples" / "multibody_split_part.fdprt"
    session = DocumentSession(fdef.load(sample), None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        tab = window.add_session(session)
    session.undo.push(SetAppearance(session, [Target("body", "2")], "#3A6EA5", "Color Body 2"))
    report = session.report
    assert report is not None and report.body is not None
    face = next(f for f in _faces(tab) if body_of(report.body.shape, f) == 1)  # type: ignore[arg-type]
    tab.selection = [face]
    window.appearance_tool.copy()
    assert window.appearance_tool.copied == "#3A6EA5"


def _colour_rows(window: MainWindow) -> list[object]:
    tree = window.tree
    assert tree is not None
    row = next(
        tree.topLevelItem(i)
        for i in range(tree.topLevelItemCount())
        if tree.topLevelItem(i).data(0, APPEARANCE_ROLE) == "appearances"  # type: ignore[union-attr]
    )
    assert row is not None
    return [row.child(i) for i in range(row.childCount())]


def test_colour_rows_remove_with_delete_and_menu(qtbot: QtBot, window: MainWindow) -> None:
    """D584: colours in use can be removed with Delete or a right click, in panel and tree."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    from fdcad.core.appearance import Target
    from fdcad.ui import strings
    from fdcad.ui.appearance.commands import SetAppearance

    tab = _open(qtbot, window)
    session = tab.session
    session.undo.push(SetAppearance(session, [Target("feature", "f6")], "#6BA368", "x"))
    tree = window.tree
    assert tree is not None
    # Tree: one row per item; the feature row is selectable and Delete removes its colour.
    rows = _colour_rows(window)
    assert [r.text(0) for r in rows] == ["#B4BCC4: Part", "#6BA368: Extrude f6"]  # type: ignore[attr-defined]
    feature_row = rows[1]
    assert feature_row.flags() & Qt.ItemFlag.ItemIsSelectable  # type: ignore[attr-defined]
    tree.setCurrentItem(feature_row)
    menu = tree._context_menu(session, feature_row)  # type: ignore[arg-type]
    assert menu is not None
    texts = [a.text() for a in menu.actions()]
    assert texts == [strings.APPEARANCE_CHANGE, strings.APPEARANCE_REMOVE]
    assert menu.actions()[1].isEnabled()
    tree.delete_selected()
    assert session.document.appearance.get("features", {}) == {}
    assert len(tab.session.document.features) >= 3  # no feature was deleted
    session.undo.undo()
    assert session.document.appearance["features"] == {"f6": "#6BA368"}
    # Panel: select the row and press Delete.
    window.appearance_tool.open()
    panel = window.appearance_tool.panel
    assert panel is not None
    assert panel.in_use.count() == 2
    panel.in_use.setCurrentRow(1)
    qtbot.keyClick(panel.in_use, Qt.Key.Key_Delete)
    assert session.document.appearance.get("features", {}) == {}
    # The part row: Remove puts the default back, and is off while it is the default.
    menu = panel.row_menu(panel.in_use.item(0))
    assert menu is not None and not menu.actions()[1].isEnabled()
    # Change Color from the menu, with the colour dialog answered.
    import fdcad.ui.appearance.entries as entries

    original = entries.QColorDialog.getColor
    entries.QColorDialog.getColor = staticmethod(lambda *_a, **_k: QColor("#3A6EA5"))  # type: ignore[method-assign]
    try:
        panel.row_menu(panel.in_use.item(0)).actions()[0].trigger()  # type: ignore[union-attr]
    finally:
        entries.QColorDialog.getColor = original  # type: ignore[method-assign]
    assert session.document.appearance["part_color"] == "#3A6EA5"
    assert panel.row_menu(panel.in_use.item(0)).actions()[1].isEnabled()  # type: ignore[union-attr]
