"""Shortcut editor (TOOL_SPEC T14.7): search, categories, search words, conflicts, keys,
Remove Shortcut, Reset to Defaults and Copy List."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QSettings, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID, COMMANDS, DEFAULT_GESTURES, key_text, search_words
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.input_editors import KeyCapture, ShortcutEditor
from fdcad.ui.preferences.settings import Settings
from tests.ui.test_input import _folders, window  # noqa: F401  (fixtures)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


@pytest.fixture
def editor(qtbot: QtBot, settings: Settings) -> ShortcutEditor:
    widget = ShortcutEditor(settings)
    qtbot.addWidget(widget)
    return widget


def test_columns_search_and_categories(editor: ShortcutEditor) -> None:
    headers = [editor.table.horizontalHeaderItem(i).text() for i in range(4)]  # type: ignore[union-attr]
    assert headers == ["Category", "Command", "Shortcut", "Search Words"]
    assert len(editor.visible_ids()) == len(COMMANDS)
    editor.search.setText("zoom")
    shown = editor.visible_ids()
    assert "view.fit" in shown and "sketch.line" not in shown
    editor.search.setText("whole")  # a search word of Zoom to Fit
    assert editor.visible_ids() == ["view.fit"]
    editor.search.setText("")
    categories = [editor.category.itemText(i) for i in range(editor.category.count())]
    assert categories[0] == "All" and "Sketch" in categories and "Other" in categories
    editor.category.setCurrentIndex(categories.index("Sketch"))
    assert {BY_ID[c].group for c in editor.visible_ids()} == {"Sketch"}
    editor.search.setText("arc")
    assert set(editor.visible_ids()) <= {c.id for c in COMMANDS if c.group == "Sketch"}
    assert "sketch.center_arc" in editor.visible_ids()


def test_search_words_are_editable_and_reach_the_shortcut_bar(
    qtbot: QtBot,
    window,  # noqa: F811
    settings: Settings,
) -> None:
    dialog = PreferencesDialog(settings, window)
    qtbot.addWidget(dialog)
    editor = dialog.shortcuts
    editor.select("sketch.point")
    row = editor.table.currentRow()
    cell = editor.table.item(row, 3)
    assert cell is not None and cell.flags() & Qt.ItemFlag.ItemIsEditable
    assert not editor.table.item(row, 2).flags() & Qt.ItemFlag.ItemIsEditable  # type: ignore[union-attr]
    cell.setText("dot  marker")
    assert editor.words["sketch.point"] == "dot marker"
    dialog.accept()
    assert settings.search_words == {"sketch.point": "dot marker"}
    bar = window.commands.shortcut_bar("part", QPoint(10, 10))
    bar.search.setText("marker")
    assert [a.text() for a in bar.listed] == ["Point"]
    bar.close()
    assert search_words("feature.extrude") and search_words("x", {"x": "y"}) == "y"


def test_key_in_use_asks_and_moves(editor: ShortcutEditor, monkeypatch: pytest.MonkeyPatch) -> None:
    editor.select("view.wireframe")
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.No)
    assert editor.assign_current("L") == {}
    assert editor.map.keys("sketch.line") == ["L"]
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    assert editor.assign_current("L") == {"sketch.line": "L"}
    assert editor.map.keys("sketch.line") == [] and "L" in editor.map.keys("view.wireframe")
    # A free key is assigned without a question.
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: pytest.fail("asked"))
    editor.select("view.redraw")
    assert editor.assign_current("ctrl+k") == {}
    row = editor.table.currentRow()
    assert _native("Ctrl+K") in editor.table.item(row, 2).text()  # type: ignore[union-attr]


def _native(portable: str) -> str:
    """How the editor shows a key on this platform (native text, upper case letters)."""
    native = QKeySequence(portable).toString(QKeySequence.SequenceFormat.NativeText)
    return key_text(native)


def _press(widget: KeyCapture, key: Qt.Key, mods: Qt.KeyboardModifier, text: str) -> None:
    QApplication.sendEvent(widget, QKeyEvent(QEvent.Type.KeyPress, key, mods, text))


def test_keys_use_upper_case_and_caps_lock_is_not_shift(qtbot: QtBot) -> None:
    box = KeyCapture()
    qtbot.addWidget(box)
    none = Qt.KeyboardModifier.NoModifier
    _press(box, Qt.Key.Key_L, none, "l")
    assert box.text() == "L"
    _press(box, Qt.Key.Key_L, none, "L")  # Caps Lock on: upper case text, no Shift
    assert box.text() == "L"
    assert box.keySequence().toString() == "L"
    _press(box, Qt.Key.Key_CapsLock, none, "")
    _press(box, Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier, "")
    assert box.text() == "L"  # Caps Lock and modifier keys alone change nothing
    _press(box, Qt.Key.Key_L, Qt.KeyboardModifier.ShiftModifier, "L")
    assert box.text() == _native("Shift+L")  # shown the platform's way (Mac symbols)
    _press(box, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier, "\x05")
    assert box.keySequence().toString() == "Ctrl+E"
    assert key_text("ctrl+shift+e") == "Ctrl+Shift+E"


def test_remove_reset_and_copy(
    qtbot: QtBot,
    window,  # noqa: F811
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog = PreferencesDialog(settings, window)
    qtbot.addWidget(dialog)
    editor = dialog.shortcuts
    editor.select("sketch.line")
    editor.clear_current()  # Remove Shortcut
    assert editor.map.keys("sketch.line") == []
    editor.set_words("sketch.line", "segment")
    dialog.gestures.boxes[("part", "up")].setCurrentIndex(0)  # no command
    editor.reset_to_defaults("shortcuts")
    assert editor.map.keys("sketch.line") == ["L"] and editor.words == {"sketch.line": "segment"}
    editor.reset_to_defaults("everything")
    assert editor.words == {}
    dialog.accept()
    assert settings.gestures == {k: dict(v) for k, v in DEFAULT_GESTURES.items()}
    text = editor.copy_list()
    assert "View\tZoom to Fit\tF\n" in text
    assert QGuiApplication.clipboard().text() == text
    assert text.count("\n") == len(COMMANDS)
    # The Reset to Defaults button asks which reset; Cancel does nothing.
    monkeypatch.setattr(QMessageBox, "exec", lambda _self: 0)
    assert editor.ask_reset() is None
