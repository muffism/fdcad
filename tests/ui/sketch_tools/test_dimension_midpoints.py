"""Smart Dimension to midpoints, and switches for end, middle and centre picks
(TR418, D953)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Point
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data


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


def test_distance_to_a_line_midpoint(canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    line = sk.add_line(0, 0, 20, 0)
    top = sk.add_point(10, 15)
    canvas.changed()
    canvas.set_options(dataclasses.replace(canvas.options, dimension_middles=True))
    canvas.set_tool("dimension")
    canvas._dimension_click(canvas.to_screen((10.0, 0.0)))
    assert len(canvas.dim_picks) == 1
    middle = sk.entities[canvas.dim_picks[0]]
    assert isinstance(middle, Point) and middle.construction
    assert any(r.type == "midpoint" and r.entities == [middle.id, line] for r in sk.relations)
    canvas.dim_picks.append(top)
    canvas._dimension_click(canvas.to_screen((30.0, 8.0)))
    dim = canvas.edit.dimension(canvas.last_dimension or "")
    assert dim is not None and abs(dim.param.value - 15.0) < 1e-6
    # The same midpoint again shares the point instead of adding one more.
    count = len(sk.entities)
    canvas._dimension_click(canvas.to_screen((10.0, 0.0)))
    assert canvas.dim_picks == [middle.id] and len(sk.entities) == count


def test_switch_off_picks_the_curve(canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    line = sk.add_line(0, 0, 20, 0)
    canvas.changed()
    assert not canvas.options.dimension_middles  # off by default
    canvas.set_tool("dimension")
    count = len(sk.entities)
    canvas._dimension_click(canvas.to_screen((10.0, 0.0)))
    assert canvas.dim_picks == [line] and len(sk.entities) == count


def test_end_switch_off_picks_the_curve(canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    line = sk.add_line(0, 0, 20, 0)
    canvas.changed()
    canvas.set_options(dataclasses.replace(canvas.options, dimension_ends=False))
    canvas.set_tool("dimension")
    canvas._dimension_click(canvas.to_screen((20.0, 0.0)))
    assert canvas.dim_picks == [line]
