"""WP7 snapping: arc midpoints, guides to part centres, direction snaps, Smart Dimension and
drag snapping, part centre copies and centre marks (TOOL_SPEC T1.2, T1.3.1, T2.5.4)."""

from __future__ import annotations

import math
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Circle, Line, Point, Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.inference import Snap, find_snap, line_relation

Vec = tuple[float, float]


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (20.0, 10.0)
    yield canvas


def _pos(canvas: SketchCanvas, at: Vec) -> QPoint:
    p = canvas.to_screen(at)
    return QPoint(round(p.x()), round(p.y()))


def _move(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    qtbot.mouseMove(canvas, _pos(canvas, at))


def _click(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    _move(qtbot, canvas, at)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_pos(canvas, at))


def _drag(qtbot: QtBot, canvas: SketchCanvas, a: Vec, b: Vec) -> None:
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_pos(canvas, a))
    steps = 6
    for i in range(1, steps + 1):
        t = i / steps
        _move(qtbot, canvas, (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_pos(canvas, b))


def _has(sk: Sketch, rtype: str, *ids: str) -> bool:
    return any(r.type == rtype and set(ids) <= set(r.entities) for r in sk.relations)


# Inference ------------------------------------------------------------------------------


def test_arc_midpoint_snaps_with_a_midpoint_relation() -> None:
    s = Sketch()
    aid = s.add_arc(0, 0, 10, 0, math.pi / 2)
    snap = find_snap(s, (7.3, 7.0), 0.5)
    assert snap.kind == "midpoint" and snap.target == aid
    assert snap.xy == pytest.approx((10 / math.sqrt(2), 10 / math.sqrt(2)))
    assert snap.relations == [("midpoint", [aid])]


def test_end_points_still_win_over_an_arc_midpoint() -> None:
    """T1.2.3: end points come before midpoints when both are in range."""
    s = Sketch()
    s.add_arc(0, 0, 1, 0, math.pi / 2)  # tiny arc: midpoint close to the ends
    p = s.add_point(0.75, 0.6)
    snap = find_snap(s, (0.74, 0.62), 0.5)
    assert snap.kind == "point" and snap.target == p


def test_alignment_guides_reach_extra_points() -> None:
    s = Sketch()
    snap = find_snap(s, (30.3, 80.0), 0.5, extra=[(30.0, 20.0)])
    assert snap.kind == "aligned" and snap.x == 30.0
    assert snap.guides == [((30.0, 20.0), (30.0, 80.0))]


def test_parallel_and_perpendicular_direction_snaps() -> None:
    s = Sketch()
    ref = s.add_line(0, 0, 10, 5)  # about 26.6 degrees
    angle = math.atan2(5, 10)
    # Nearly parallel, from another start: the free end turns onto the direction.
    near = angle + math.radians(2)
    end, rel = line_relation(
        s, (0, 20), Snap("free", 20 * math.cos(near), 20 + 20 * math.sin(near))
    )
    assert rel == ("parallel", [ref])
    assert end.kind == "parallel"
    assert math.atan2(end.y - 20, end.x) == pytest.approx(angle)
    # Nearly perpendicular.
    perp = angle + math.pi / 2 - math.radians(2)
    end, rel = line_relation(s, (5, 0), Snap("free", 5 + 8 * math.cos(perp), 8 * math.sin(perp)))
    assert rel == ("perpendicular", [ref])
    assert math.remainder(math.atan2(end.y, end.x - 5) - angle, math.pi) == pytest.approx(
        math.pi / 2, abs=1e-9
    ) or math.remainder(math.atan2(end.y, end.x - 5) - angle, math.pi) == pytest.approx(
        -math.pi / 2, abs=1e-9
    )
    # Far from both: nothing.
    assert line_relation(s, (0, 20), Snap("free", 10, 40))[1] is None
    # Horizontal wins over parallel to a near horizontal line.
    s.add_line(0, -10, 10, -9.8)
    assert line_relation(s, (0, 30), Snap("free", 10, 30.1))[1] == ("horizontal", [])
    # A snapped end keeps its place: the relation is added only when it already fits.
    assert line_relation(s, (0, 20), Snap("point", 10, 26, target="eX"))[1] is None


# Drawing --------------------------------------------------------------------------------


def test_line_tool_adds_parallel_and_perpendicular(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    ref = sk.add_line(0, 0, 20, 10)
    canvas.changed()
    canvas.set_tool("line")
    _click(qtbot, canvas, (0, 20))
    _click(qtbot, canvas, (20, 30.6))  # about 2 degrees off parallel
    sk = canvas.edit.sketch
    new = next(e for e in sk.entities.values() if isinstance(e, Line) and e.id != ref)
    assert _has(sk, "parallel", new.id, ref)
    (x1, y1), (x2, y2) = sk.xy(new.p1), sk.xy(new.p2)
    assert math.atan2(y2 - y1, x2 - x1) == pytest.approx(math.atan2(10, 20), abs=1e-6)
    # The chain continues from the end; go nearly perpendicular to the first line.
    _click(qtbot, canvas, (x2 + 3.35, y2 - 6.15))  # clear of alignment guides
    sk = canvas.edit.sketch
    third = [e for e in sk.entities.values() if isinstance(e, Line)][-1]
    assert _has(sk, "perpendicular", third.id) and not _has(sk, "parallel", third.id)


def test_circle_from_a_sketch_centre_is_concentric(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    first = sk.add_circle(30, 20, 5)
    canvas.changed()
    canvas.set_tool("circle")
    _click(qtbot, canvas, (30.2, 20.1))
    _click(qtbot, canvas, (38, 20))
    sk = canvas.edit.sketch
    second = next(e for e in sk.entities.values() if isinstance(e, Circle) and e.id != first)
    assert _has(sk, "concentric", second.id, first)


def test_part_centre_snap_ties_to_a_fixed_copy(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_reference([], [((30.0, 20.0), 8.0)])
    canvas.set_tool("point")
    _move(qtbot, canvas, (38.0, 20.0))  # over the part circle's edge: reveals the centre
    assert (30.0, 20.0) in canvas.revealed
    _click(qtbot, canvas, (30.3, 20.2))
    sk = canvas.edit.sketch
    copies = [
        e
        for e in sk.entities.values()
        if isinstance(e, Point) and e.construction and (e.x, e.y) == (30.0, 20.0)
    ]
    assert len(copies) == 1
    assert _has(sk, "fixed", copies[0].id)
    placed = next(e for e in sk.entities.values() if isinstance(e, Point) and not e.construction)
    assert _has(sk, "coincident", placed.id, copies[0].id)
    # A second snap there reuses the copy.
    _click(qtbot, canvas, (30.2, 20.3))
    assert len([e for e in canvas.edit.sketch.entities.values() if e.construction]) == 2


def test_guides_line_up_with_a_revealed_part_centre(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_reference([], [((30.0, 20.0), 8.0)])
    canvas.set_tool("line")
    _move(qtbot, canvas, (38.0, 20.0))
    snap = canvas._snap_at(canvas.to_screen((30.4, 45.0)))
    assert snap.kind == "aligned" and snap.x == pytest.approx(30.0)
    assert ((30.0, 20.0), (30.0, snap.y)) in snap.guides


# Smart Dimension --------------------------------------------------------------------------


def test_smart_dimension_shows_snaps_and_picks_end_points(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    sk = canvas.edit.sketch
    lid = sk.add_line(10, 0, 40, 0)
    line = sk.entities[lid]
    assert isinstance(line, Line)
    p = sk.add_point(10, 25)
    canvas.changed()
    canvas.set_tool("dimension")
    _move(qtbot, canvas, (40.6, 0.5))
    assert canvas.snap is not None and canvas.snap.kind == "point"
    assert canvas.snap.target == line.p2
    _click(qtbot, canvas, (40.6, 0.5))
    _click(qtbot, canvas, (10.3, 25.4))
    assert canvas.dim_picks == [line.p2, p]


def test_smart_dimension_picks_a_revealed_part_centre(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_reference([], [((30.0, 20.0), 8.0)])
    sk = canvas.edit.sketch
    p = sk.add_point(0, 20)
    canvas.changed()
    canvas.set_tool("dimension")
    _move(qtbot, canvas, (38.0, 20.0))  # reveal
    assert (30.0, 20.0) in canvas.revealed
    _click(qtbot, canvas, (30.3, 20.2))
    _click(qtbot, canvas, (0.2, 20.1))
    assert len(canvas.dim_picks) == 2
    copy = canvas.dim_picks[0]
    sk = canvas.edit.sketch
    ent = sk.entities[copy]
    assert isinstance(ent, Point) and ent.construction and _has(sk, "fixed", copy)
    _click(qtbot, canvas, (15, 26))
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.entities == [copy, p]
    assert dim.param.value == pytest.approx(30.0)


# Dragging ---------------------------------------------------------------------------------


def test_dragged_end_point_snaps_and_joins(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    lid = sk.add_line(0, 0, 20, 10)
    line = sk.entities[lid]
    assert isinstance(line, Line)
    target = sk.add_point(30, 25)
    canvas.changed()
    _drag(qtbot, canvas, (20, 10), (30.3, 25.4))
    sk = canvas.edit.sketch
    assert sk.xy(line.p2) == pytest.approx((30, 25), abs=1e-6)
    assert _has(sk, "coincident", line.p2, target)
    canvas.undo()
    assert not _has(canvas.edit.sketch, "coincident", line.p2, target)


def test_dragged_point_ignores_what_moves_with_it(qtbot: QtBot, canvas: SketchCanvas) -> None:
    """A corner never snaps to its own partner end point, which moves along."""
    sk = canvas.edit.sketch
    a = sk.add_line(0, 0, 20, 0)
    b = sk.add_line(20, 0, 20, 15)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    canvas.changed()
    exclude = canvas._drag_exclude(la.p2)
    assert {la.p2, lb.p1, a, b} <= set(exclude)
    _drag(qtbot, canvas, (20, 0), (26, 4))
    sk = canvas.edit.sketch
    assert sk.xy(la.p2) == pytest.approx((26, 4), abs=1e-6)
    assert len(sk.relations) == 2  # the origin fix and the corner, nothing new


def test_drop_that_would_over_define_adds_nothing(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    lid = sk.add_line(0, 10, 20, 10)
    line = sk.entities[lid]
    assert isinstance(line, Line)
    sk.relate("horizontal", lid)
    sk.relate("fixed", line.p1)
    target = sk.add_point(30, 20)
    sk.relate("fixed", target)
    canvas.changed()
    # The end can only slide along y = 10, so it cannot reach the fixed point at y = 20.
    _drag(qtbot, canvas, (20, 10), (30.2, 20.2))
    sk = canvas.edit.sketch
    assert not _has(sk, "coincident", line.p2, target)
    assert canvas.edit.status().state.value != "over"


# Centres shown (T2.5.4) ---------------------------------------------------------------------


def test_centres_show_on_hover_and_selection_in_every_mode(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    sk = canvas.edit.sketch
    aid = sk.add_arc(10, 10, 6, 0, math.pi)
    canvas.set_reference([], [((40.0, 20.0), 5.0)])
    canvas.changed()
    assert canvas.centre_marks() == []
    _move(qtbot, canvas, (10, 16))  # over the arc, no tool
    assert canvas.hover == aid
    assert (10.0, 10.0) in canvas.centre_marks()
    _move(qtbot, canvas, (45, 20))  # over the part circle: revealed in select mode too
    assert (40.0, 20.0) in canvas.centre_marks()
    canvas.selection = [aid]
    _move(qtbot, canvas, (60, 40))
    assert (10.0, 10.0) in canvas.centre_marks()
    canvas.repaint()  # the marks paint without a tool
