"""A kept corner of a sketch fillet shows as a corner mark (TR105, D848)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Dimension, Line, Sketch
from fdcad.core.sketch.ops.corner import fillet
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_dimensioned_corner_is_kept_and_marked(qtbot: QtBot) -> None:
    s = Sketch()
    a = s.add_line(0, 0, 20, 0)
    b = s.add_line(20, 0, 20, 10)
    la, lb = s.entities[a], s.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    s.relate("coincident", la.p2, lb.p1)
    s.dimensions.append(Dimension("d1", "distance", [la.p1, la.p2], Param("20", 20.0)))
    s.next_dimension = 2
    made = fillet(s, a, (10, 0), b, (20, 5), 2.0)
    assert made.corner_point is not None
    assert s.dimensions[0].entities[1] == made.corner_point  # the dimension survives
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)
    assert canvas.point_marks()[made.corner_point] == "corner"
