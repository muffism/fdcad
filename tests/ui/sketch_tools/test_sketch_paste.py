"""Ctrl+C and Ctrl+V inside a sketch (TR3.1, D685)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QGuiApplication
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Sketch
from fdcad.ui.sketch_tools.paste_tool import CLIPBOARD_FORMAT, PasteTool
from tests.ui.sketch_tools.p2_helpers import canvas_of, pos, ui_click

CTRL = Qt.KeyboardModifier.ControlModifier


def _corner() -> Sketch:
    sk = Sketch()
    o = sk.add_point(0, 0, construction=True)  # e1
    sk.relate("fixed", o)
    a = sk.add_line(0, 0, 10, 0)  # e4
    b = sk.add_line(10, 0, 10, 5)  # e7
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    sk.relate("coincident", la.p1, o)
    sk.dimension("distance", [a], Param("10mm", 10))
    return sk


def _lines(sk: Sketch) -> list[Line]:
    return [e for e in sk.entities.values() if isinstance(e, Line)]


def test_copy_then_paste_follows_cursor_and_click_places(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot, _corner())
    canvas.selection = ["e4", "e7"]
    canvas.setFocus()
    qtbot.keyClick(canvas, Qt.Key.Key_C, CTRL)
    mime = QGuiApplication.clipboard().mimeData()
    assert mime is not None and mime.hasFormat(CLIPBOARD_FORMAT)
    qtbot.keyClick(canvas, Qt.Key.Key_V, CTRL)
    assert isinstance(canvas.tool, PasteTool)
    qtbot.mouseMove(canvas, pos(canvas, (30, 12.5)))
    shown = canvas.tool.preview()
    assert len(shown.lines) == 2
    depth = canvas.edit.undo_depth
    ui_click(qtbot, canvas, (30, 12.5))
    assert canvas.tool is None
    assert canvas.edit.undo_depth == depth + 1
    lines = _lines(canvas.edit.sketch)
    assert len(lines) == 4
    new = [ln for ln in lines if ln.id not in ("e4", "e7")]
    assert sorted(canvas.selection) == sorted(ln.id for ln in new)
    # The copy keeps its corner and its dimension, but not the tie to the origin.
    assert len(canvas.edit.sketch.dimensions) == 2
    xs = sorted(canvas.edit.sketch.xy(p)[0] for ln in new for p in (ln.p1, ln.p2))
    assert xs[0] == pytest.approx(25, abs=0.5)


def test_escape_cancels_the_paste(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot, _corner())
    canvas.selection = ["e4"]
    assert canvas.copy_selection() == 1
    assert canvas.start_paste()
    canvas.setFocus()
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.tool is None
    assert len(_lines(canvas.edit.sketch)) == 2


def test_paste_with_foreign_clipboard_says_so(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot, _corner())
    messages: list[str] = []
    canvas.status_message.connect(messages.append)
    QGuiApplication.clipboard().setText("hello")
    assert not canvas.start_paste()
    mime = QMimeData()
    mime.setData(CLIPBOARD_FORMAT, b"{not json")
    from fdcad.ui import clipboard

    clipboard.put(mime)  # D2617: cleared before exit
    assert not canvas.start_paste()
    assert len(messages) == 2
    canvas.selection = []
    assert canvas.copy_selection() == 0
