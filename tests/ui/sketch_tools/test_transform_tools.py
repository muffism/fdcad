"""Move, Copy, Rotate, Scale and Stretch Entities tools (TR1, D684)."""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Circle, Line, Sketch
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.tools import make_tool
from fdcad.ui.sketch_tools.transform_tools import TRANSFORM_TOOLS
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, free, ui_click


def _square() -> Sketch:
    sk = Sketch()
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    lines = [sk.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b = sk.entities[lines[i]], sk.entities[lines[(i + 1) % 4]]
        assert isinstance(a, Line) and isinstance(b, Line)
        sk.relate("coincident", a.p2, b.p1)
    sk.relate("horizontal", lines[0])
    sk.relate("vertical", lines[1])
    sk.dimension("distance", [lines[0]], Param("10mm", 10))
    return sk


def _circle() -> Sketch:
    sk = Sketch()
    sk.add_circle(0, 0, 2)  # e1 centre, e2 circle
    return sk


def _circles(sk: Sketch) -> list[Circle]:
    return [e for e in sk.entities.values() if isinstance(e, Circle)]


def test_five_commands_with_icons_and_tips() -> None:
    from fdcad.ui.icons.audit import audit
    from fdcad.ui.strings import TOOLTIP_TEXT as TOOLTIPS

    for name in TRANSFORM_TOOLS:
        cid = f"sketch.{name}"
        assert cid in BY_ID
        assert audit(cid) == []
        assert TOOLTIPS.get(cid)
        assert make_tool(name, edit_of()).label == BY_ID[cid].label


def test_move_from_base_to_target_is_one_undo_step() -> None:
    edit = edit_of(_circle())
    tool = make_tool("move_entities", edit)
    click(edit, tool, 2, 0)  # pick the circle
    assert tool.picks == ["e2"]  # type: ignore[attr-defined]
    click(edit, tool, 0, 0, snapped=True)  # base point: the centre
    assert tool.base == (0, 0)  # type: ignore[attr-defined]
    target = free(7, 4)
    tool.hover(target)
    assert (tool.dx, tool.dy) == pytest.approx((7, 4))  # type: ignore[attr-defined]
    assert tool.preview().circles
    depth = edit.undo_depth
    assert tool.click(target)
    edit.refresh()
    assert edit.undo_depth == depth + 1
    assert edit.sketch.xy("e1") == pytest.approx((7, 4))
    edit.undo()
    assert edit.sketch.xy("e1") == pytest.approx((0, 0))


def test_copy_by_typed_delta_and_enter() -> None:
    edit = edit_of(_circle())
    tool = make_tool("copy_entities", edit)
    tool.take_selection(["e2"])  # type: ignore[attr-defined]
    tool.count, tool.dx = 3, 15.0  # type: ignore[attr-defined]
    tool.option_changed("count")  # type: ignore[attr-defined]
    tool.option_changed("dx")  # type: ignore[attr-defined]
    assert len(tool.preview().circles) >= 4
    assert tool.enter() is True  # type: ignore[attr-defined]
    edit.refresh()
    xs = sorted(edit.sketch.xy(c.center)[0] for c in _circles(edit.sketch))
    assert xs == pytest.approx([0, 15, 30, 45])
    assert tool.picks == ["e2"]  # the tool keeps going  # type: ignore[attr-defined]


def test_rotate_about_clicked_centre_by_typed_angle() -> None:
    edit = edit_of(_square())
    tool = make_tool("rotate_entities", edit)
    tool.take_selection(["e3", "e6", "e9", "e12"])  # type: ignore[attr-defined]
    click(edit, tool, 0, 0, snapped=True)  # centre at a corner
    tool.angle = math.radians(30)  # type: ignore[attr-defined]
    tool.option_changed("angle")  # type: ignore[attr-defined]
    assert tool.enter() is True  # type: ignore[attr-defined]
    edit.refresh()
    line = edit.sketch.entities["e3"]
    assert isinstance(line, Line)
    p2 = edit.sketch.xy(line.p2)
    assert p2 == pytest.approx((10 * math.cos(math.radians(30)), 10 * math.sin(math.radians(30))))
    assert "Horizontal" in tool.take_message()  # type: ignore[attr-defined]


def test_scale_with_copy() -> None:
    edit = edit_of(_circle())
    tool = make_tool("scale_entities", edit)
    click(edit, tool, 2, 0)
    click(edit, tool, 0, 0, snapped=True)
    tool.factor, tool.make_copy = 3.0, True  # type: ignore[attr-defined]
    assert tool.enter() is True  # type: ignore[attr-defined]
    radii = sorted(c.radius for c in _circles(edit.sketch))
    assert radii == pytest.approx([2, 6])


def test_stretch_by_dragged_box() -> None:
    edit = edit_of(_square())
    tool = make_tool("stretch_entities", edit)
    click(edit, tool, 8, -2)  # first corner
    tool.release(free(12, 12), True)  # type: ignore[attr-defined]
    assert tool.box is not None  # type: ignore[attr-defined]
    click(edit, tool, 10, 0, snapped=True)  # base
    click(edit, tool, 15, 0)  # target: 5 to the right
    line = edit.sketch.entities["e3"]
    assert isinstance(line, Line)
    assert edit.sketch.xy(line.p2) == pytest.approx((15, 0))
    assert edit.sketch.xy(line.p1) == pytest.approx((0, 0))
    assert "dimension" in tool.take_message()  # type: ignore[attr-defined]


def test_escape_steps_back() -> None:
    edit = edit_of(_circle())
    tool = make_tool("move_entities", edit)
    click(edit, tool, 2, 0)
    click(edit, tool, 0, 0, snapped=True)
    assert tool.cancel() is False and tool.base is None  # type: ignore[attr-defined]
    assert tool.cancel() is False and not tool.picks  # type: ignore[attr-defined]
    assert tool.cancel() is True


def test_canvas_takes_selection_shows_labels_and_enter_applies(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot, _circle())
    canvas.selection = ["e2"]
    canvas.set_tool("move_entities")
    assert canvas.tool is not None and canvas.tool.picks == ["e2"]  # type: ignore[attr-defined]
    ui_click(qtbot, canvas, (0, 0))  # base at the centre
    keys = [k for k, _r, _t in canvas.values.labels()]
    assert keys == ["dx", "dy"]
    canvas.set_tool_option("dx", 6.0)
    canvas.setFocus()
    qtbot.keyClick(canvas, Qt.Key.Key_Return)
    assert canvas.edit.sketch.xy("e1")[0] == pytest.approx(6)
