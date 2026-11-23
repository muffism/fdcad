"""Sketch canvas snapping fixes: segment reveal, model centre retention, origin label."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.inference import Snap


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    edit = SketchEdit(feature)
    canvas = SketchCanvas(edit, UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (0.0, 0.0)
    yield canvas


def _move(qtbot: QtBot, canvas: SketchCanvas, x: float, y: float) -> None:
    p = canvas.to_screen((x, y))
    qtbot.mouseMove(canvas, QPoint(round(p.x()), round(p.y())))


def _click(qtbot: QtBot, canvas: SketchCanvas, x: float, y: float) -> None:
    p = canvas.to_screen((x, y))
    pos = QPoint(round(p.x()), round(p.y()))
    qtbot.mouseMove(canvas, pos)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=pos)


def test_sampled_mouse_path_reveals_centre(qtbot: QtBot, canvas: SketchCanvas) -> None:
    """A 30 px path that skips over the edge still reveals the model centre."""
    canvas.set_reference([], [((10.0, 10.0), 10.0)])
    canvas.set_tool("circle")
    # At scale 4, 30 px is 7.5 mm. The edge band is 8 to 12 mm from the centre,
    # so none of these steps lands on the edge; the crossing must reveal it.
    for x in (40.0, 32.5, 25.0, 17.5, 10.0):
        _move(qtbot, canvas, x, 10.0)
    assert (10.0, 10.0) in canvas.revealed
    _click(qtbot, canvas, 10.0, 10.0)
    _click(qtbot, canvas, 14.0, 10.0)
    circle = next(iter(canvas.edit.sketch.curves()))
    assert canvas.edit.sketch.xy(circle.center) == pytest.approx((10.0, 10.0))


def test_sketch_circles_do_not_push_out_model_centre(qtbot: QtBot, canvas: SketchCanvas) -> None:
    """Sketch circle centres snap through find_snap, not through the reveal list."""
    canvas.set_reference([], [((10.0, 10.0), 8.0)])
    canvas.set_tool("circle")
    _move(qtbot, canvas, 18.0, 10.0)  # on the model circle edge
    assert canvas.revealed == [(10.0, 10.0)]
    for x in (40.0, 60.0, 80.0):
        canvas.edit.sketch.add_circle(x, 0.0, 5.0)
    for x in (45.0, 65.0, 85.0):
        _move(qtbot, canvas, x, 0.0)  # near each sketch circle's edge
    assert canvas.revealed == [(10.0, 10.0)]
    snap = canvas._snap_at(canvas.to_screen((10.4, 10.3)))
    assert snap.kind == "center" and snap.xy == (10.0, 10.0)


def test_origin_snap_label_is_origin(canvas: SketchCanvas) -> None:
    """The sketch origin snap reads Origin, not Endpoint."""
    snap = canvas._snap_at(canvas.to_screen((0.1, 0.1)))
    assert snap.kind == "point"
    assert canvas._snap_label(snap) == "Origin"
    assert canvas._snap_label(Snap("point", 5.0, 5.0)) == "Endpoint"
