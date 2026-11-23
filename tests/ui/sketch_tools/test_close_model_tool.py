"""Close Sketch to Model tool (TR106, D1704)."""

from __future__ import annotations

from fdcad.core.sketch.curve_convert import CurvePiece, ProjectedCurve
from fdcad.core.sketch.model_curves import INTERSECTION
from fdcad.core.sketch.open_ends import open_end_points
from fdcad.ui.sketch_tools.close_model_tool import CloseToModelTool
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import edit_of


def _square() -> ProjectedCurve:
    c = [(0.0, 0.0), (40.0, 0.0), (40.0, 40.0), (0.0, 40.0)]
    pieces = [CurvePiece("line", (c[i], c[(i + 1) % 4])) for i in range(4)]
    return ProjectedCurve(INTERSECTION, "Intersection Curves", pieces)


def test_click_inside_the_side_to_keep() -> None:
    edit = edit_of()
    sk = edit.sketch
    a = sk.add_line(10.0, 0.0, 10.0, 20.0)
    b = sk.add_line(10.0, 20.0, 30.0, 0.0)
    sk.relate("coincident", sk.entities[a].p2, sk.entities[b].p1)  # type: ignore[union-attr]
    edit.refresh()
    tool = make_tool("close_to_model", edit)
    assert isinstance(tool, CloseToModelTool)
    assert "Working out" in tool.prompt
    tool.model_curves = {INTERSECTION: _square()}
    assert "Click inside" in tool.prompt
    tool.hover(Snap("free", 13.0, 5.0))
    assert tool.hot is not None and tool.preview().lines
    assert tool.click(Snap("free", 13.0, 5.0))
    assert open_end_points(edit.sketch) == []
    assert "Closed the profile with 1 part edge" in tool.take_message()
    assert tool.finished


def test_no_profile_on_the_edges_says_what_to_do() -> None:
    edit = edit_of()
    edit.sketch.add_line(10.0, 5.0, 10.0, 20.0)
    edit.refresh()
    tool = make_tool("close_to_model", edit)
    tool.model_curves = {INTERSECTION: _square()}  # type: ignore[attr-defined]
    assert "Move each end onto a part edge" in tool.prompt  # type: ignore[attr-defined]
    assert not tool.click(Snap("free", 13.0, 5.0))
