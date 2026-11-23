"""Click inside a closed sketch region to select its border (TR39, D849)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def _canvas(qtbot: QtBot, s: Sketch) -> SketchCanvas:
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)
    return canvas


def test_region_click(qtbot: QtBot) -> None:
    s = Sketch()
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    ids = [s.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    canvas = _canvas(qtbot, s)
    assert sorted(canvas.select_region_at((5, 5))) == sorted(ids)
    assert sorted(canvas.selection) == sorted(ids) and canvas.shaded_region is not None
    assert canvas.select_region_at((50, 50)) == []  # outside: nothing


def test_gap_means_no_region(qtbot: QtBot) -> None:
    s = Sketch()
    s.add_line(0, 0, 10, 0)
    s.add_line(10, 0, 10, 10)
    s.add_line(10, 10, 0, 10)
    s.add_line(0, 10, 0, 1)  # a gap at the corner
    canvas = _canvas(qtbot, s)
    assert canvas.select_region_at((5, 5)) == [] and canvas.shaded_region is None


def test_dragging_a_picked_region_moves_the_whole_shape(qtbot: QtBot) -> None:
    from PySide6.QtCore import QPoint, Qt

    from fdcad.core.sketch.model import Line

    s = Sketch()
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    ids = [s.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b = s.entities[ids[i]], s.entities[ids[(i + 1) % 4]]
        assert isinstance(a, Line) and isinstance(b, Line)
        s.relate("coincident", a.p2, b.p1)
    canvas = _canvas(qtbot, s)
    canvas.resize(600, 400)
    canvas.show()
    canvas.scale, canvas.center = 10.0, (5.0, 5.0)
    canvas.select_region_at((5, 5))
    start = canvas.to_screen((5.0, 0.0))
    p0 = QPoint(round(start.x()), round(start.y()))
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=p0)
    qtbot.mouseMove(canvas, p0 + QPoint(50, 0))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=p0 + QPoint(50, 0))
    left = canvas.edit.sketch.entities[ids[3]]
    assert isinstance(left, Line)
    assert canvas.edit.sketch.xy(left.p1)[0] > 2  # the far side moved too


def test_region_click_obeys_the_selection_filter(qtbot: QtBot) -> None:
    """A Points only filter picks no curves from a region (found in a full run)."""
    s = Sketch()
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    for i in range(4):
        s.add_line(*pts[i], *pts[(i + 1) % 4])
    canvas = _canvas(qtbot, s)
    canvas.select_filter = lambda _eid: False
    assert canvas.select_region_at((5, 5)) == [] and canvas.shaded_region is None
