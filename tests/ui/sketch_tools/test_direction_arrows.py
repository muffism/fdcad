"""Direction arrows on offsets and patterns (TR341 item 2, D1705)."""

from __future__ import annotations

import math

from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_offset_preview_points_to_the_side() -> None:
    edit = edit_of()
    line = edit.sketch.add_line(0.0, 0.0, 20.0, 0.0)
    edit.refresh()
    tool = make_tool("offset", edit)
    tool.tolerance = 0.5
    tool.click(Snap("free", 10.0, 0.0))
    tool.distance = 3.0  # type: ignore[attr-defined]
    tool.locked = True  # type: ignore[attr-defined]
    tool.hover(Snap("free", 10.0, 5.0))
    arrows = tool.preview().arrows
    assert len(arrows) == 1
    (tx, ty), (dx, dy) = arrows[0]
    assert abs(ty) < 1e-9 and 0 <= tx <= 20
    assert dy > 0 and abs(dx) < 1e-9  # toward the cursor side
    tool.hover(Snap("free", 10.0, -5.0))
    assert tool.preview().arrows[0][1][1] < 0
    assert line in edit.sketch.entities


def test_linear_and_circular_patterns_show_their_directions() -> None:
    edit = edit_of()
    edit.sketch.add_line(0.0, 0.0, 5.0, 0.0)
    edit.refresh()
    tool = make_tool("linear_pattern", edit)
    tool.tolerance = 0.5
    tool.click(Snap("free", 2.5, 0.0))
    arrows = tool.preview().arrows
    assert len(arrows) == 1  # one row: Direction 1 only
    assert arrows[0][1][0] > 0
    tool.reverse1 = True  # type: ignore[attr-defined]
    assert tool.preview().arrows[0][1][0] < 0
    tool.count2 = 2  # type: ignore[attr-defined]
    assert len(tool.preview().arrows) == 2
    edit = edit_of()
    edit.sketch.add_line(10.0, 0.0, 15.0, 0.0)
    edit.refresh()
    circ = make_tool("circular_pattern", edit)
    circ.tolerance = 0.5
    circ.click(Snap("free", 12.5, 0.0))
    (tail, d) = circ.preview().arrows[0]
    # Counter clockwise about the origin from the seed's anchor.
    cross = tail[0] * d[1] - tail[1] * d[0]
    assert cross > 0
    circ.reverse = True  # type: ignore[attr-defined]
    (tail, d) = circ.preview().arrows[0]
    assert tail[0] * d[1] - tail[1] * d[0] < 0
    assert not math.isnan(d[0])


def test_canvas_draws_an_arrow_at_a_fixed_screen_size(qtbot: object) -> None:
    from tests.ui.sketch_tools.p2_helpers import canvas_of

    canvas, _panel = canvas_of(qtbot)  # type: ignore[arg-type]
    segs = canvas.arrow_segments([((20.0, 10.0), (0.0, 5.0))])
    assert len(segs) == 3  # the shaft and both sides of the head
    a, b = segs[0]
    assert abs(a.x() - b.x()) < 1e-9 and a.y() - b.y() == canvas.ARROW_PX  # up on screen
    canvas.scale = 40.0
    a2, b2 = canvas.arrow_segments([((20.0, 10.0), (0.0, 5.0))])[0]
    assert a2.y() - b2.y() == canvas.ARROW_PX
    canvas.grab()  # paints without error
