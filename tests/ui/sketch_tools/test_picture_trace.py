"""Trace a sketch picture from the Sketch Picture tool (TR116 item 2, D1711)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line
from fdcad.core.sketch.open_ends import open_end_points
from fdcad.ui.sketch_tools.picture_tool import PictureTool
from tests.ui.sketch_tools.p2_helpers import canvas_of, free


def _png(tmp_path: Path) -> bytes:
    """A white 40 x 20 image with a black 10 x 10 square at columns 5 to 14, rows 5 to 14."""
    image = QImage(40, 20, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    painter.fillRect(QRect(5, 5, 10, 10), QColor("#000000"))
    painter.end()
    path = tmp_path / "logo.png"
    assert image.save(str(path))
    return path.read_bytes()


def _picture_tool(qtbot: QtBot, tmp_path: Path) -> tuple[object, PictureTool]:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("picture")
    tool = canvas.tool
    assert isinstance(tool, PictureTool)
    assert tool.insert(_png(tmp_path), "logo.png", "png", 40, 20)
    return canvas, tool


def test_trace_colour_region(qtbot: QtBot, tmp_path: Path) -> None:
    canvas, tool = _picture_tool(qtbot, tmp_path)
    tool.option_changed("trace_colour")
    assert "colour region" in tool.prompt
    # The picture is 40 x 20 mm at the origin; pixel (row 10, column 10) is at (10, 10).
    assert tool.click(free(10.0, 10.0))
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]  # type: ignore[attr-defined]
    assert len(lines) == 4
    xs = sorted({round(canvas.edit.sketch.xy(ln.p1)[0], 6) for ln in lines})  # type: ignore[attr-defined]
    assert xs == [5.0, 15.0]
    assert open_end_points(canvas.edit.sketch) == []  # type: ignore[attr-defined]
    assert "Traced 4 lines" in tool.take_message()
    assert tool.trace_mode is None


def test_trace_box_and_escape(qtbot: QtBot, tmp_path: Path) -> None:
    canvas, tool = _picture_tool(qtbot, tmp_path)
    tool.option_changed("trace_box")
    assert not tool.click(free(1.0, 19.0))
    assert "other corner" in tool.prompt
    assert tool.click(free(20.0, 1.0))
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]  # type: ignore[attr-defined]
    assert len(lines) == 4
    tool.option_changed("trace_box")
    assert not tool.cancel()  # Escape drops the trace first
    assert tool.trace_mode is None


def test_click_off_the_picture_while_tracing(qtbot: QtBot, tmp_path: Path) -> None:
    _canvas, tool = _picture_tool(qtbot, tmp_path)
    tool.option_changed("trace_colour")
    assert not tool.click(free(100.0, 100.0))
    assert "Click on the picture" in tool.take_message()
