"""Offset tool: the Outside corners option (TR391, D945)."""

from __future__ import annotations

from fdcad.core.sketch.model import Arc, Line
from fdcad.ui.sketch_tools.offset_tool import OffsetTool
from tests.ui.sketch_tools.p2_helpers import edit_of, free


def test_round_corners_from_the_tool() -> None:
    edit = edit_of()
    sk = edit.sketch
    pts = [(0, 0), (20, 0), (20, 20), (0, 20)]
    lines = [sk.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b = sk.entities[lines[i]], sk.entities[lines[(i + 1) % 4]]
        assert isinstance(a, Line) and isinstance(b, Line)
        sk.relate("coincident", a.p2, b.p1)
    tool = OffsetTool(edit)
    assert "corners" in [o.key for o in tool.options] and tool.corners == "sharp"
    tool.corners = "round"
    tool.picks = list(lines)
    tool.distance, tool.locked = 2.0, True
    tool.hover(free(40, 40))
    preview = tool.preview()
    assert len(preview.arcs) >= 4
    assert tool._place((40, 40))
    assert sum(isinstance(sk.entities[c], Arc) for c in tool.drawn) == 4
