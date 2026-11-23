"""Diameter mode stays on in revolve sketches (TR361, D951)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data, sticky_diameter


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
    yield canvas


def _place(canvas: SketchCanvas, picks: list[str], at: tuple[float, float]) -> str:
    canvas.dim_picks = list(picks)
    canvas._dimension_click(canvas.to_screen(at))
    assert canvas.last_dimension is not None
    dim = canvas.edit.dimension(canvas.last_dimension)
    assert dim is not None
    return dim.type


def test_later_lines_stay_diameters_until_esc(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    axis = sk.add_line(0, -10, 0, 40, construction=True)
    first = sk.add_line(10, 0, 10, 5)
    second = sk.add_line(15, 8, 15, 14)
    third = sk.add_line(22, 20, 22, 26)
    slanted = sk.add_line(30, 0, 35, 9)
    canvas.changed()
    canvas.set_tool("dimension")
    assert _place(canvas, [first, axis], (-8.0, 2.0)) == "doubled_distance"  # past the axis
    assert canvas.diameter_axis == axis
    # One pick of a parallel line, text on its own side: still a diameter.
    assert _place(canvas, [second], (18.0, -8.0)) == "doubled_distance"
    dim = canvas.edit.dimension(canvas.last_dimension or "")
    assert dim is not None and dim.entities == [second, axis]
    assert abs(dim.param.value - 30.0) < 1e-6
    assert sticky_diameter(sk, [slanted], axis) is None  # not parallel: its length
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)  # Esc ends diameter mode with the tool
    canvas.set_tool("dimension")
    assert canvas.diameter_axis is None
    assert _place(canvas, [third], (30.0, 30.0)) == "distance"
