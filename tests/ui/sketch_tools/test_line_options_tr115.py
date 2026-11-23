"""Infinite construction line and flipped tangent arcs (TR115 items 1 and 2, D1710)."""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Arc, Line, Point
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.infinite_line import REACH
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import click, edit_of


def test_infinite_line_runs_far_beyond_both_clicks() -> None:
    edit = edit_of()
    tool = make_tool("infinite_line", edit)
    assert "passes through" in tool.prompt  # type: ignore[attr-defined]
    click(edit, tool, 0.0, 0.0, snapped=False)
    tool.hover(Snap("free", 10.0, 10.0))
    assert tool.preview().lines
    assert click(edit, tool, 10.0, 10.0, snapped=False)
    lines = [e for e in edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 1 and lines[0].construction
    a, b = edit.sketch.xy(lines[0].p1), edit.sketch.xy(lines[0].p2)
    assert abs(math.dist(a, b) - REACH * 2) < 1e-9
    on = [e for e in edit.sketch.entities.values() if isinstance(e, Point) and e.construction]
    assert len(on) >= 4  # two far ends and the two clicked points
    assert edit.result is not None and edit.result.solved


def test_flipped_tangent_arc_leaves_backward() -> None:
    edit = edit_of()
    sk = edit.sketch
    lid = sk.add_line(0.0, 0.0, 10.0, 0.0)
    edit.refresh()
    line = sk.entities[lid]
    assert isinstance(line, Line)
    tool = make_tool("tangent_arc", edit)
    tool.flip = True  # type: ignore[attr-defined]
    end = sk.xy(line.p2)
    tool.click(Snap("point", end[0], end[1], [("coincident", [line.p2])], target=line.p2))
    tool.hover(Snap("free", 8.0, 0.2))  # leave backward along the line: tangent
    # The arc turns back over the line: its centre is square above the line's end,
    # and it is the short way round (a quarter turn).
    assert click(edit, tool, 6.0, 4.0, snapped=False)
    arc = next(e for e in edit.sketch.entities.values() if isinstance(e, Arc))
    c = edit.sketch.xy(arc.center)
    assert abs(c[0] - 10.0) < 1e-6 and abs(c[1] - 4.0) < 1e-6
    s0, e0 = edit.sketch.xy(arc.start), edit.sketch.xy(arc.end)
    a0 = math.atan2(s0[1] - c[1], s0[0] - c[0])
    a1 = math.atan2(e0[1] - c[1], e0[0] - c[0])
    assert abs((a1 - a0) % (2 * math.pi) - math.pi / 2) < 1e-6
    assert edit.result is not None and edit.result.solved
