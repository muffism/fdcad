"""Two point and tangent circles (TR317, D877)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Circle, Sketch
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import click, edit_of


def _circles(sk: Sketch) -> list[Circle]:
    return [e for e in sk.entities.values() if isinstance(e, Circle)]


def _on(eid: str, x: float, y: float) -> Snap:
    return Snap("on_curve", x, y, target=eid)


def test_two_point_circle() -> None:
    edit = edit_of()
    tool = make_tool("two_point_circle", edit)
    click(edit, tool, 0, 0)
    assert click(edit, tool, 20, 0)
    (c,) = _circles(edit.sketch)
    assert edit.sketch.xy(c.center) == pytest.approx((10, 0), abs=1e-9)
    assert edit.sketch.radius(c.id) == pytest.approx(10.0)


def _triangle() -> tuple[Sketch, list[str]]:
    s = Sketch()
    a = s.add_line(0, 0, 30, 0)
    b = s.add_line(30, 0, 0, 40)
    c = s.add_line(0, 40, 0, 0)
    for line in (a, b, c):
        s.relate("fixed", line)
    return s, [a, b, c]


def test_tangent_to_three_lines_is_the_incircle() -> None:
    sketch, (a, b, c) = _triangle()
    edit = edit_of(sketch)
    tool = make_tool("tangent_circle", edit)
    for snap in (_on(a, 10, 0), _on(b, 15, 20), _on(c, 0, 10)):
        tool.hover(snap)
        tool.click(snap)
    edit.refresh()
    (circle,) = _circles(edit.sketch)
    # A 30, 40, 50 right triangle has an incircle of radius 10 at (10, 10).
    assert edit.sketch.radius(circle.id) == pytest.approx(10.0, abs=1e-6)
    assert edit.sketch.xy(circle.center) == pytest.approx((10, 10), abs=1e-6)
    assert [r.type for r in edit.sketch.relations].count("tangent") == 3


def test_tangent_to_two_with_a_radius_and_refuses_empty_first_clicks() -> None:
    sketch, (a, _b, c) = _triangle()
    edit = edit_of(sketch)
    tool = make_tool("tangent_circle", edit)
    assert not tool.click(Snap("free", 5, 5))
    assert tool.take_message()
    for snap in (_on(a, 10, 0), _on(c, 0, 10), Snap("free", 4, 4)):
        tool.hover(snap)
        tool.click(snap)
    edit.refresh()
    (circle,) = _circles(edit.sketch)
    r = edit.sketch.radius(circle.id)
    assert edit.sketch.xy(circle.center) == pytest.approx((r, r), abs=1e-6)
    assert any(d.type == "radius" for d in edit.sketch.dimensions)
    assert math.isfinite(r) and r > 0


def test_blend_curve_tool_joins_two_lines() -> None:
    """TR318, D884."""
    from fdcad.core.sketch.model import Spline

    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(20, 10, 20, 20)
    edit = edit_of(s)
    tool = make_tool("blend_curve", edit)
    assert not tool.click(Snap("free", 50, 50))
    assert tool.take_message()
    for snap in (_on(a, 9, 0), _on(b, 20, 11)):
        tool.hover(snap)
        tool.click(snap)
    edit.refresh()
    splines = [e for e in edit.sketch.entities.values() if isinstance(e, Spline)]
    assert len(splines) == 1 and len(splines[0].points) == 2


def test_jog_line_tool() -> None:
    """TR52, D902."""
    s = Sketch()
    lid = s.add_line(0, 0, 40, 0)
    edit = edit_of(s)
    tool = make_tool("jog_line", edit)
    assert not tool.click(Snap("free", 5, 5))
    assert tool.take_message()
    for snap in (Snap("on_curve", 20, 0, target=lid), Snap("free", 20, 6)):
        tool.hover(snap)
        tool.click(snap)
    edit.refresh()
    from fdcad.core.sketch.model import Line

    lines = [e for e in edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 3
    assert max(edit.sketch.xy(ln.p2)[1] for ln in lines) == pytest.approx(6.0, abs=1e-6)


def test_parabola_tool() -> None:
    """TR52, D902."""
    from fdcad.core.sketch.model import Spline

    edit = edit_of()
    tool = make_tool("parabola", edit)
    for x, y in ((0, 2), (0, 0), (-8, 0), (8, 0)):
        click(edit, tool, x, y)
    assert any(isinstance(e, Spline) for e in edit.sketch.entities.values())
