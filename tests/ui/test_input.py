"""Shortcuts, gestures, shortcut bar and feature tree actions on the offscreen platform."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QSettings
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import _hole, plate


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


@pytest.fixture
def window(qtbot: QtBot, settings: Settings) -> Iterator[MainWindow]:
    win = MainWindow(settings)
    win.show()
    win.finish_setup()
    yield win
    if win.sketch_mode is not None and win.sketch_mode.is_open:
        win.sketch_mode._close()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _open_plate(qtbot: QtBot, win: MainWindow, hole: bool = True) -> DocumentTab:
    doc, ext = plate()
    if hole:
        _hole(doc, f"{ext}/cap/end")
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _keys(win: MainWindow, cid: str) -> list[str]:
    action = win.commands.actions[cid]
    return [k.toString(QKeySequence.SequenceFormat.PortableText) for k in action.shortcuts()]


def test_window_uses_shortcuts_md(window: MainWindow) -> None:
    assert _keys(window, "view.normal_to") == ["Ctrl+8", "N"]
    assert _keys(window, "sketch.line") == ["L"]
    assert _keys(window, "feature.extrude") == ["Shift+E"]
    # SHORTCUTS.md section 1: on a Mac, Redo is Cmd+Shift+Z first, and Cmd+Y too (D19).
    redo = ["Ctrl+Shift+Z", "Ctrl+Y"] if sys.platform == "darwin" else ["Ctrl+Y"]
    assert _keys(window, "edit.redo") == redo


def test_shortcut_editor_moves_a_key_and_saves(
    qtbot: QtBot, window: MainWindow, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = PreferencesDialog(settings, window)
    qtbot.addWidget(dialog)
    editor = dialog.shortcuts
    editor.select("view.wireframe")
    asked: list[str] = []

    def yes(*args: object) -> QMessageBox.StandardButton:
        asked.append(str(args[2]))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", yes)
    lost = editor.assign_current("L")
    assert asked and "Line" in asked[0]  # a key in use asks first (T14.7.3)
    assert lost == {"sketch.line": "L"}
    assert "Line" in editor.warning.text()
    dialog.accept()
    assert settings.shortcut_overrides["sketch.line"] == []
    window.commands.reload()
    assert "L" in _keys(window, "view.wireframe")
    assert _keys(window, "sketch.line") == []


def test_gestures_run_commands(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open_plate(qtbot, window, hole=False)
    assert window.commands.gesture("part", 0, -80) == "view.top"
    assert window.commands.gesture("part", 3, 2) is None  # too short
    front = next(f for f in tab.session.document.features if f.name == "Front Plane")
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=front.id)
    assert window.commands.gesture("sketch", -90, 0) == "sketch.line"
    canvas = window.sketch_mode.canvas
    assert canvas is not None and canvas.tool_name == "line"
    assert window.commands.gesture("sketch", 0, 90) == "sketch.corner_rectangle"
    assert canvas.tool_name == "corner_rectangle"


def test_shortcut_bar_lists_context_commands(qtbot: QtBot, window: MainWindow) -> None:
    menu = window.commands.shortcut_bar("part", QPoint(10, 10))
    texts = [a.text() for a in menu.actions()]
    assert "Extruded Boss" in texts and "Sketch" in texts
    menu.close()
    sketch_menu = window.commands.shortcut_bar("sketch", QPoint(10, 10))
    assert "Smart Dimension" in [a.text() for a in sketch_menu.actions()]
    sketch_menu.close()


def test_repeat_last_command(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open_plate(qtbot, window, hole=False)
    assert window.tree is not None and window.panel is not None
    sketch = next(f for f in tab.session.document.features if f.type == "sketch")
    window.tree.select(sketch.id)
    window.commands.trigger("feature.extrude")
    assert window.panel.is_editing
    window.panel.cancel()
    assert window.commands.last == "feature.extrude"
    assert window.commands.repeat()
    assert window.panel.is_editing
    window.panel.cancel()


def test_tree_move_rules_find_and_relatives(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open_plate(qtbot, window)
    tree = window.tree
    assert tree is not None
    doc = tab.session.document
    ids = [f.id for f in doc.features]
    cut, hole_sketch = ids[-1], ids[-2]
    assert not tree.move_feature(cut, ids.index(hole_sketch))
    assert "must stay below" in tree.message
    assert tab.session.undo.count() == 0
    assert tree.find_feature("plate") or tree.find_feature("Extrude")
    text = tree.relatives_text(hole_sketch)
    assert "Uses:" in text and doc.feature(cut).name in text


def test_confirmation_corner_follows_editing(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open_plate(qtbot, window, hole=False)
    assert not tab.corner_shown
    assert window.corner_at_cursor() is None
    assert window.tree is not None
    sketch = next(f for f in tab.session.document.features if f.type == "sketch")
    window.tree.select(sketch.id)
    window.insert_feature("extrude", "cut")
    assert tab.corner_shown and window.editing == "feature"
    popup = window.corner_at_cursor()
    assert popup is not None and [a.text() for a in popup.actions()] == ["OK", "Cancel"]
    popup.close()
    window.confirm_cancel()
    assert not tab.corner_shown and window.editing == ""
    front = next(f for f in tab.session.document.features if f.name == "Front Plane")
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=front.id)
    assert tab.corner_shown and window.editing == "sketch"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.confirm_ok()
    assert not tab.corner_shown
    assert tab.session.document.features[-1].type == "sketch"


def test_open_sample_as_untitled_copy(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.samples.location import sample_files

    path = next(p for p in sample_files() if p.stem == "bracket")
    window.open_sample(path)
    tab = window.current
    assert tab is not None and tab.session.path is None
    assert window.tabs.tabText(window.tabs.currentIndex()) == "Bracket"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        pass


def test_cut_on_a_face_sketch_goes_into_the_part(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open_plate(qtbot, window)  # its hole sketch is on the top face
    assert window.tree is not None and window.panel is not None
    hole_sketch = [f for f in tab.session.document.features if f.type == "sketch"][-1]
    window.tree.select(hole_sketch.id)
    window.insert_feature("extrude", "cut")
    assert window.panel.feature is not None
    assert window.panel.feature.params["reverse"] is True
    window.panel.cancel()


def test_shortcut_bar_says_when_matches_cannot_run(qtbot: QtBot) -> None:
    """Audit D11 item 11 (D745): disabled matches were left out without a word."""
    from PySide6.QtGui import QAction

    from fdcad.ui import strings
    from fdcad.ui.main_window.shortcut_bar import ShortcutBar

    on, off = QAction("Fillet"), QAction("Fill Pattern")
    off.setEnabled(False)
    bar = ShortcutBar([], [on, off])
    qtbot.addWidget(bar)
    bar.filter("fill")
    assert bar.listed == [on]
    assert bar.note is not None and bar.note.text() == strings.SEARCH_UNAVAILABLE.format(n=1)
    bar.filter("")
    assert bar.note is None
