"""Spline, ellipse and partial ellipse tools (PHASE2_SPEC P2.8 items 10 and 13)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.freeform import axes, sample
from fdcad.core.sketch.model import Ellipse, EllipseArc, Spline
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.geometry import distance_to
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, free, pos, ui_click


def test_commands() -> None:
    for cid in ("sketch.spline", "sketch.ellipse", "sketch.partial_ellipse"):
        assert cid in BY_ID


def test_ellipse_tool_and_swapped_axes() -> None:
    edit = edit_of()
    tool = make_tool("ellipse", edit)
    click(edit, tool, 0, 0, snapped=True)  # the origin
    click(edit, tool, 4, 0)
    tool.hover(free(1, 3))
    assert tool.preview().lines
    assert click(edit, tool, 1, 10)  # the second axis is the longer one
    (e,) = [x for x in edit.sketch.entities.values() if isinstance(x, Ellipse)]
    _c, a, b, phi = axes(edit.sketch, e)
    assert (a, b) == pytest.approx((10, 4))
    assert phi == pytest.approx(math.pi / 2)
    assert any(r.type == "coincident" and e.center in r.entities for r in edit.sketch.relations)
    assert edit.result is not None and edit.result.solved


def test_partial_ellipse_sweep() -> None:
    edit = edit_of()
    tool = make_tool("partial_ellipse", edit)
    click(edit, tool, 0, 0)
    click(edit, tool, 10, 0)
    click(edit, tool, 0, 4)  # the second axis; the sweep starts here (top)
    for k in range(1, 11):  # turn counter clockwise to the left end
        t = math.pi / 2 + k / 10 * math.pi / 2
        tool.hover(free(10 * math.cos(t), 4 * math.sin(t)))
    assert click(edit, tool, -10, 0)
    (arc,) = [x for x in edit.sketch.entities.values() if isinstance(x, EllipseArc)]
    assert edit.sketch.xy(arc.start) == pytest.approx((0, 4), abs=1e-9)
    assert edit.sketch.xy(arc.end) == pytest.approx((-10, 0), abs=1e-9)


def test_spline_tool_finishes_on_cancel() -> None:
    edit = edit_of()
    tool = make_tool("spline", edit)
    for x, y in [(0, 0), (10, 5), (20, 0)]:
        assert not click(edit, tool, x, y)
    assert tool.preview().lines
    depth = edit.undo_depth
    assert tool.cancel() is False  # finishes, the tool stays
    assert tool.take_changed()  # type: ignore[attr-defined]
    assert edit.undo_depth == depth + 1
    (s,) = [x for x in edit.sketch.entities.values() if isinstance(x, Spline)]
    assert len(s.points) == 3 and len(s.handles) == 3
    assert tool.cancel() is True  # nothing in progress: the tool ends


def test_spline_drag_sets_a_tangent_handle(qtbot: QtBot) -> None:
    from PySide6.QtCore import Qt

    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("spline")
    ui_click(qtbot, canvas, (0, 0))
    # Press at (10, 5) and drag to (14, 9): that point's handle.
    qtbot.mouseMove(canvas, pos(canvas, (10, 5)))
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=pos(canvas, (10, 5)))
    qtbot.mouseMove(canvas, pos(canvas, (12, 7)))
    qtbot.mouseMove(canvas, pos(canvas, (14, 9)))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=pos(canvas, (14, 9)))
    ui_click(qtbot, canvas, (20, 0))
    qtbot.mouseDClick(canvas, Qt.MouseButton.LeftButton, pos=pos(canvas, (20, 0)))
    splines = [x for x in canvas.edit.sketch.entities.values() if isinstance(x, Spline)]
    assert len(splines) == 1
    s = splines[0]
    assert len(s.points) == 3
    assert canvas.edit.sketch.xy(s.handles[1]) == pytest.approx((14, 9), abs=0.3)
    # It draws and can be picked.
    canvas.repaint()
    on = sample(canvas.edit.sketch, s)[16]
    assert distance_to(canvas.edit.sketch, s.id, on) < 1e-9
    assert canvas.pick(pos(canvas, on).toPointF()) is not None


@pytest.mark.parametrize("tool_name", ["ellipse", "slot"])
def test_new_shapes_extrude(tool_name: str) -> None:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.document.model import Feature, Param, new_document
    from fdcad.core.rebuild.engine import RebuildEngine

    edit = edit_of()
    tool = make_tool(tool_name, edit)
    if tool_name == "ellipse":
        for x, y in [(30, 30), (40, 30), (30, 34)]:
            click(edit, tool, x, y)
        expected = math.pi * 10 * 4 * 5
    else:
        for x, y in [(30, 30), (50, 30), (40, 33)]:
            click(edit, tool, x, y)
        expected = (20 * 6 + math.pi * 9) * 5
    doc = new_document()
    sketch = edit.to_feature()
    doc.features.append(sketch)
    doc.next_id = max(doc.next_id, int(sketch.id[1:]) + 1)  # ids are unique (fdef)
    fid = doc.new_feature_id()
    params = {"operation": "boss", "end_condition": "blind", "depth": Param("5", 5.0)}
    doc.features.append(
        Feature(fid, "extrude", "Extrude", params=params, refs={"sketch": {"feature": sketch.id}})
    )
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None, report.results[fid].error
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(report.body.shape, props)
    assert props.Mass() == pytest.approx(expected, rel=1e-6)


def test_ellipse_gets_construction_axes() -> None:
    """TR114 (D967): both axes as construction lines, tied to the ellipse."""
    from fdcad.core.sketch.model import Line
    from fdcad.core.sketch.solver import solve

    def drawn(axes: bool):  # type: ignore[no-untyped-def]
        edit = edit_of()
        tool = make_tool("ellipse", edit)
        tool.axes = axes  # type: ignore[attr-defined]
        for x, y in [(30, 30), (40, 30), (30, 34)]:
            click(edit, tool, x, y)
        return edit.sketch

    sk = drawn(True)
    lines = [e for e in sk.entities.values() if isinstance(e, Line) and e.construction]
    lengths = sorted(round(math.dist(sk.xy(x.p1), sk.xy(x.p2)), 6) for x in lines)
    assert lengths == [8.0, 20.0]
    bare = drawn(False)
    assert not [e for e in bare.entities.values() if isinstance(e, Line)]
    assert solve(sk).dof == solve(bare).dof  # the axes add no freedom


def test_dragging_a_picked_circle_moves_its_group(qtbot) -> None:  # type: ignore[no-untyped-def]
    """TR53 (D973): a circle or point of a picked group moves the whole group."""
    from PySide6.QtCore import QPointF

    from fdcad.core.document.model import Feature
    from fdcad.core.sketch.model import Circle
    from fdcad.core.units import UnitSystem
    from fdcad.ui.sketch_tools.canvas import SketchCanvas
    from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data

    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (20.0, 10.0)
    sk = canvas.edit.sketch
    cid = sk.add_circle(10, 10, 3)
    pid = sk.add_point(30, 10)
    canvas.changed()
    canvas.selection = [cid, pid]
    circle = sk.entities[cid]
    assert isinstance(circle, Circle)
    start = canvas.to_screen((13.0, 10.0))  # on the circle's edge
    canvas._press = start
    canvas._drag = {"id": cid, "start": canvas.to_sketch(start), "moved": False}
    canvas._drag_move(start + QPointF(20, 0))  # 5 mm to the right at scale 4
    assert sk.xy(circle.center)[0] == pytest.approx(15.0, abs=1e-6)
    assert sk.xy(pid)[0] == pytest.approx(35.0, abs=1e-6)
    assert circle.radius == pytest.approx(3.0)  # moved, not resized
