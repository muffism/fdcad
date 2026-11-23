"""Turn Off and Turn On for sketch relations and dimensions (TR109, D829)."""

from __future__ import annotations

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Dimension, Line, Sketch
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_toggle_off_and_on_again() -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 10, 3)
    s.relate("horizontal", lid)
    line = s.entities[lid]
    assert isinstance(line, Line)
    s.dimensions.append(Dimension("d1", "distance", [line.p1, line.p2], Param("20", 20.0)))
    edit = edit_of(s)
    assert edit.toggle_off(["r0", "d1"]) is True
    assert edit.sketch.relations[0].off and edit.sketch.dimensions[0].off
    assert edit.toggle_off(["r0", "d1"]) is False
    assert not edit.sketch.relations[0].off and not edit.sketch.dimensions[0].off
