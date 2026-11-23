"""Convert Entities on a face: outer and inner loops (TR118, D1712)."""

from __future__ import annotations

from fdcad.core.sketch.model import Line
from fdcad.core.sketch.ops.convert import face_loops, loops_of
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import click, edit_of

Vec = tuple[float, float]


def _square(x: float, y: float, s: float) -> list[list[Vec]]:
    c = [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]
    return [[c[i], c[(i + 1) % 4]] for i in range(4)]


def _plate() -> list[list[Vec]]:
    """A 40 square plate with a 10 square hole and, apart, a 5 square boss."""
    return _square(0, 0, 40) + _square(10, 10, 10) + _square(60, 0, 5)


def test_face_loops_find_the_outer_and_inner_loop() -> None:
    polys = _plate()
    assert len(loops_of(polys)) == 3
    found = face_loops(polys, (30.0, 30.0))
    assert found is not None
    outer, inner = found
    assert sorted(outer) == [0, 1, 2, 3] and [sorted(i) for i in inner] == [[4, 5, 6, 7]]
    # Inside the hole, the hole is the face.
    hole = face_loops(polys, (15.0, 15.0))
    assert hole is not None and sorted(hole[0]) == [4, 5, 6, 7] and hole[1] == []
    assert face_loops(polys, (100.0, 100.0)) is None


def _lines(edit: object) -> int:
    return sum(isinstance(e, Line) for e in edit.sketch.entities.values())  # type: ignore[attr-defined]


def test_click_inside_a_face_converts_its_loops() -> None:
    edit = edit_of()
    tool = make_tool("convert", edit)
    tool.model_lines = _plate()  # type: ignore[attr-defined]
    assert click(edit, tool, 30, 30, snapped=False)
    assert _lines(edit) == 8


def test_inner_loops_off_and_ctrl_click_one_loop() -> None:
    edit = edit_of()
    tool = make_tool("convert", edit)
    tool.model_lines = _plate()  # type: ignore[attr-defined]
    tool.inner_loops = False  # type: ignore[attr-defined]
    assert click(edit, tool, 30, 30, snapped=False)
    assert _lines(edit) == 4
    tool.ctrl = True  # type: ignore[attr-defined]
    assert click(edit, tool, 15, 10, snapped=False)  # an edge of the hole: its loop
    assert _lines(edit) == 8
    assert not click(edit, tool, 30, 35, snapped=False)  # Ctrl in a face takes nothing
