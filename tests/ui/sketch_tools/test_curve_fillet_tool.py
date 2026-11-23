"""Sketch Fillet on a corner with an arc (TR48, D1317)."""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Arc
from fdcad.ui.sketch_tools.corner_tools import SketchFilletTool
from fdcad.ui.sketch_tools.inference import Snap
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_click_the_corner_of_a_line_and_an_arc() -> None:
    edit = edit_of()
    sk = edit.sketch
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    arc = sk.add_arc(15.0, 0.0, 5.0, math.pi / 2, math.pi)  # ends at (10, 0), going up
    a = sk.entities[arc]
    assert isinstance(a, Arc)
    sk.relate("coincident", sk.entities[line].p2, a.end)  # type: ignore[union-attr]
    edit.refresh()
    tool = SketchFilletTool(edit)
    tool.tolerance = 0.5
    tool.radius = 1.0
    assert tool.click(Snap("free", 10.0, 0.0))
    arcs = [e for e in sk.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 2
    edit.refresh()
    assert edit.result is not None and edit.result.solved


def _line_and_spline(edit: object) -> None:
    from fdcad.core.sketch.model import Spline

    sk = edit.sketch  # type: ignore[attr-defined]
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    ps = [sk.add_point(10.0, 0.0), sk.add_point(14.0, 8.0)]
    hs = [sk.add_point(10.0, 3.0, construction=True), sk.add_point(16.0, 10.0, construction=True)]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, ps, hs)
    sk.relate("coincident", sk.entities[line].p2, ps[0])
    edit.refresh()  # type: ignore[attr-defined]


def test_click_the_corner_of_a_line_and_a_spline() -> None:
    """TR48 (D1700): a spline corner is rounded from its point."""
    edit = edit_of()
    _line_and_spline(edit)
    tool = SketchFilletTool(edit)
    tool.tolerance = 0.5
    tool.radius = 1.0
    assert tool.click(Snap("free", 10.0, 0.0))
    arcs = [e for e in edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 1
    assert edit.sketch.radius(arcs[0].id) == 1.0 or abs(edit.sketch.radius(arcs[0].id) - 1) < 1e-6


def test_dragging_from_the_corner_sizes_the_fillet() -> None:
    """TR48 item 3 (D1702): press on the corner and drag; the radius follows."""
    edit = edit_of()
    sk = edit.sketch
    sk.add_line(0.0, 0.0, 10.0, 0.0)
    sk.add_line(10.0, 0.0, 10.0, 10.0)
    edit.refresh()
    tool = SketchFilletTool(edit)
    tool.tolerance = 0.5
    tool.radius = 1.0
    depth = edit.undo_depth
    assert tool.click(Snap("free", 10.0, 0.0))
    assert tool.busy
    tool.hover(Snap("free", 7.0, 0.0))  # 3 from the corner
    assert tool.release(Snap("free", 7.0, 0.0), True)
    assert not tool.busy
    arcs = [e for e in edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 1
    assert abs(edit.sketch.radius(arcs[0].id) - 3.0) < 1e-6
    assert tool.radius == 3.0
    radius_dims = [d for d in edit.sketch.dimensions if d.type == "radius"]
    assert len(radius_dims) == 1 and abs(radius_dims[0].param.value - 3.0) < 1e-9
    assert edit.undo_depth == depth + 1  # one undo step


def test_dragging_too_far_keeps_the_last_radius_that_fits() -> None:
    edit = edit_of()
    sk = edit.sketch
    sk.add_line(0.0, 0.0, 10.0, 0.0)
    sk.add_line(10.0, 0.0, 10.0, 10.0)
    edit.refresh()
    tool = SketchFilletTool(edit)
    tool.tolerance = 0.5
    tool.radius = 2.0
    assert tool.click(Snap("free", 10.0, 0.0))
    tool.hover(Snap("free", 10.0, 50.0))  # 50 does not fit
    arcs = [e for e in edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 1 and abs(edit.sketch.radius(arcs[0].id) - 2.0) < 1e-6
    assert "smaller radius" in tool.message


def test_chamfer_tool_on_a_line_and_an_arc() -> None:
    """TR48 (D1701): Sketch Chamfer cuts a corner with an arc."""
    from fdcad.core.sketch.model import Line
    from fdcad.ui.sketch_tools.corner_tools import SketchChamferTool

    edit = edit_of()
    sk = edit.sketch
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    arc = sk.add_arc(15.0, 0.0, 5.0, math.pi / 2, math.pi)
    a = sk.entities[arc]
    assert isinstance(a, Arc)
    sk.relate("coincident", sk.entities[line].p2, a.end)  # type: ignore[union-attr]
    edit.refresh()
    tool = SketchChamferTool(edit)
    tool.tolerance = 0.5
    tool.d1 = 2.0
    assert tool.click(Snap("free", 10.0, 0.0))
    lines = [e for e in edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 2
    edit.refresh()
    assert edit.result is not None and edit.result.solved
