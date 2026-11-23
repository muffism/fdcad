"""Shared helpers for the Phase 2 sketch tool tests (PHASE2_SPEC P2.8, P2.9)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Sketch, sketch_to_data
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.inference import Snap, find_snap
from fdcad.ui.sketch_tools.panel import SketchPanel
from fdcad.ui.sketch_tools.tools import Tool

Vec = tuple[float, float]
NONE = Qt.KeyboardModifier.NoModifier


def edit_of(sketch: Sketch | None = None) -> SketchEdit:
    """A sketch open for editing; ``sketch`` replaces the new sketch's content."""
    data = new_sketch_data() if sketch is None else sketch_to_data(sketch)
    feature = Feature("f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=data)
    return SketchEdit(feature)


def free(x: float, y: float) -> Snap:
    """The raw cursor at (x, y)."""
    return Snap("free", x, y)


def snap(edit: SketchEdit, x: float, y: float) -> Snap:
    """The snapped cursor at (x, y)."""
    return find_snap(edit.sketch, (x, y), 0.5)


def click(edit: SketchEdit, tool: Tool, x: float, y: float, snapped: bool = False) -> bool:
    """Hover and click the tool at (x, y), then solve."""
    s = snap(edit, x, y) if snapped else free(x, y)
    tool.hover(s)
    changed = tool.click(s)
    edit.refresh()
    return changed


def canvas_of(qtbot: QtBot, sketch: Sketch | None = None) -> tuple[SketchCanvas, SketchPanel]:
    """A shown canvas and its panel at 4 px per mm around (20, 10)."""
    canvas = SketchCanvas(edit_of(sketch), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (20.0, 10.0)
    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    panel.show()
    return canvas, panel


def pos(canvas: SketchCanvas, at: Vec) -> QPoint:
    """Widget pixel of a sketch point."""
    p = canvas.to_screen(at)
    return QPoint(round(p.x()), round(p.y()))


def ui_click(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    """Move to and click a sketch point."""
    qtbot.mouseMove(canvas, pos(canvas, at))
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, NONE, pos=pos(canvas, at))


def ui_drag(qtbot: QtBot, canvas: SketchCanvas, path: list[Vec]) -> None:
    """Press at the first point, move through the rest and release at the last."""
    qtbot.mouseMove(canvas, pos(canvas, path[0]))
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, NONE, pos=pos(canvas, path[0]))
    for p in path[1:]:
        qtbot.mouseMove(canvas, pos(canvas, p))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, NONE, pos=pos(canvas, path[-1]))
