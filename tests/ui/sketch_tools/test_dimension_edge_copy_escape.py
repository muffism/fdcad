"""Escape after Smart Dimension picks a part edge takes its copy away (D2648, bug hunt
O10a-6)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Line
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data

Vec = tuple[float, float]


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (20.0, 10.0)
    canvas.reference = [[(50.0, -20.0), (50.0, 40.0)]]  # a straight part edge
    yield canvas


def _click(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    p = canvas.to_screen(at)
    pos = QPoint(round(p.x()), round(p.y()))
    qtbot.mouseMove(canvas, pos)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=pos)


def _copies(canvas: SketchCanvas) -> list[str]:
    sk = canvas.edit.sketch
    return [e.id for e in sk.entities.values() if isinstance(e, Line) and e.construction]


def test_escape_takes_the_edge_copy_away(qtbot: QtBot, canvas: SketchCanvas) -> None:
    """The pick was dropped but its fixed construction line stayed in the sketch."""
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (50.0, 10.0))
    assert len(canvas.dim_picks) == 1 and len(_copies(canvas)) == 1
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.dim_picks == [] and _copies(canvas) == []
    assert canvas.dimension_mode  # the first Escape only drops the pick


def test_leaving_the_tool_takes_unused_copies_away(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (50.0, 10.0))
    assert len(_copies(canvas)) == 1
    canvas.set_tool("line")
    assert _copies(canvas) == []


def test_a_copy_a_dimension_uses_stays(qtbot: QtBot, canvas: SketchCanvas) -> None:
    lid = canvas.edit.sketch.add_line(0, -10, 0, 30)
    canvas.changed()
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (50.0, 10.0))
    _click(qtbot, canvas, (0.0, 10.0))
    assert lid in canvas.dim_picks
    _click(qtbot, canvas, (25.0, 35.0))  # place the distance
    if canvas.editor is not None:
        qtbot.keyClick(canvas.editor, Qt.Key.Key_Return)
    assert len(_copies(canvas)) == 1
    canvas.set_tool(None)
    assert len(_copies(canvas)) == 1
