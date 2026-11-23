"""WP5 relations in the sketch editor: selection rules, tags, the panel and the Relations panel."""

from __future__ import annotations

import math
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Circle, Line
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import (
    SketchEdit,
    new_sketch_data,
    ordered_for,
    relations_for,
)
from fdcad.ui.sketch_tools.panel import SketchPanel
from fdcad.ui.sketch_tools.relations_panel import RelationsPanel, listed_relations


def _edit() -> SketchEdit:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    return SketchEdit(feature)


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    canvas = SketchCanvas(_edit(), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (0.0, 0.0)
    yield canvas


# T3.1 selection table -------------------------------------------------------------------


def test_relation_offers_follow_the_t31_table() -> None:
    edit = _edit()
    sk = edit.sketch
    l1, l2, l3 = sk.add_line(0, 0, 10, 0), sk.add_line(0, 5, 10, 6), sk.add_line(3, 3, 4, 9)
    axis = sk.add_line(-5, -5, -5, 5, construction=True)
    c1, c2 = sk.add_circle(0, 0, 3), sk.add_circle(1, 1, 4)
    a1, a2 = sk.add_arc(0, 0, 5, 0, 1), sk.add_arc(2, 0, 5, 1, 2)
    p1, p2, p3 = sk.add_point(1, 1), sk.add_point(2, 2), sk.add_point(3, 1)
    rows: list[tuple[list[str], set[str], set[str]]] = [
        # selection, must offer, must not offer
        ([p1, p2, p3], {"horizontal", "vertical"}, {"coincident"}),
        ([l1, l2, l3], {"collinear", "parallel", "equal", "horizontal"}, {"perpendicular"}),
        ([l1, l2], {"perpendicular", "collinear"}, set()),
        ([l1, c1], {"tangent"}, {"concentric"}),
        ([c1, c2, a1], {"concentric", "coradial", "equal"}, {"tangent"}),
        ([p1, c1], {"concentric", "coincident"}, {"coradial"}),
        ([p1, a1], {"midpoint", "coincident", "concentric"}, set()),
        ([p1, l1], {"midpoint", "coincident"}, set()),
        ([p1, p2, axis], {"symmetric"}, set()),
        ([l1, l3, axis], {"symmetric"}, set()),
        ([a1, a2, axis], {"symmetric"}, set()),
        ([c1, c2, axis], {"symmetric"}, set()),
        ([l1, l2, l3], set(), {"symmetric"}),  # no centerline among them
        ([p1, l1, l2], {"intersection"}, {"symmetric"}),
        ([c1], {"fixed"}, {"equal"}),
    ]
    for ids, want, never in rows:
        offered = set(relations_for(sk, ids))
        assert want <= offered, (ids, offered)
        assert not never & offered, (ids, offered)
    assert ordered_for(sk, "symmetric", [axis, l1, l3]) == [l1, l3, axis]
    assert ordered_for(sk, "intersection", [l1, p1, l2]) == [p1, l1, l2]


def test_every_offered_relation_solves() -> None:
    """Adding each offered relation to a matching selection gives a solvable sketch."""
    edit = _edit()
    sk = edit.sketch
    l1, l2 = sk.add_line(0, 0, 10, 1), sk.add_line(0, 5, 10, 7)
    axis = sk.add_line(-5, -5, -5, 5, construction=True)
    c1, a1 = sk.add_circle(0, 0, 3), sk.add_arc(2, 0, 5, 0.2, 1.4)
    p1, p2 = sk.add_point(1, 1), sk.add_point(2, 3)
    for ids in ([p1, p2], [l1, l2], [c1, a1], [p1, a1], [p1, p2, axis], [p1, l1, l2]):
        for rtype in relations_for(sk, ids):
            edit.checkpoint()
            edit.relate(rtype, ordered_for(sk, rtype, ids))
            edit.refresh()
            assert edit.result is not None, (rtype, ids, edit.error)
            edit.undo()
            sk = edit.sketch


# T1.3.2 tags select relations -----------------------------------------------------------


def _press(qtbot: QtBot, canvas: SketchCanvas, pos: QPoint, ctrl: bool = False) -> None:
    mods = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, mods, pos)


def test_clicking_a_tag_selects_the_relation_and_delete_removes_it(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    sk = canvas.edit.sketch
    lid = sk.add_line(0, 0, 20, 0)
    cid = sk.add_circle(30, 30, 5)
    sk.relate("horizontal", lid)
    sk.relate("fixed", cid)
    canvas.changed()
    canvas.repaint()
    assert len(canvas._tags) == 2
    rect, rtype, index = canvas._tags[0]
    assert rtype == "horizontal"
    _press(qtbot, canvas, rect.center().toPoint())
    assert canvas.selection == [f"r{index}"]
    assert canvas.selected_relations() == [index]
    assert lid in canvas._related()
    # Ctrl adds the second tag.
    canvas.repaint()
    _press(qtbot, canvas, canvas._tags[1][0].center().toPoint(), ctrl=True)
    assert len(canvas.selected_relations()) == 2
    _press(qtbot, canvas, canvas._tags[1][0].center().toPoint(), ctrl=True)
    assert canvas.selected_relations() == [index]
    key = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(canvas, key)
    assert [r.type for r in canvas.edit.sketch.relations] == ["fixed", "fixed"]
    assert lid in canvas.edit.sketch.entities  # only the relation went
    canvas.undo()
    assert any(r.type == "horizontal" for r in canvas.edit.sketch.relations)


# T3.2.4 existing relations with delete buttons and the selection state ------------------


def test_panel_lists_relations_with_a_delete_button_each(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    sk = canvas.edit.sketch
    lid = sk.add_line(0, 0, 20, 3)
    line = sk.entities[lid]
    assert isinstance(line, Line)
    sk.relate("horizontal", lid)
    sk.relate("coincident", line.p1, "e1")  # e1 is the origin point
    canvas.changed()
    canvas._update_defined()
    canvas.selection = [lid]
    canvas.selection_changed.emit()
    assert sorted(panel.delete_buttons) == [1]  # the horizontal relation of the line
    assert panel.selection_state.text() == "Selection: under defined"
    canvas.selection = [line.p1]
    canvas.selection_changed.emit()
    assert panel.selection_state.text() == "Selection: fully defined"
    canvas.selection = [lid]
    canvas.selection_changed.emit()
    panel.delete_buttons[1].click()
    assert [r.type for r in sk.relations if r.type == "horizontal"] == []
    assert canvas.edit.sketch.relations[-1].type == "coincident"


def test_panel_shows_over_defined_selection(qtbot: QtBot, canvas: SketchCanvas) -> None:
    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    sk = canvas.edit.sketch
    lid = sk.add_line(0, 0, 20, 0)
    sk.relate("fixed", lid)
    sk.relate("horizontal", lid)  # not needed: over defines
    canvas.changed()
    canvas.selection = [lid]
    canvas.selection_changed.emit()
    assert panel.selection_state.text() == "Selection: over defined"


# T3.3 Relations panel -------------------------------------------------------------------


def test_relations_panel_filters_highlights_and_deletes(qtbot: QtBot, canvas: SketchCanvas) -> None:
    edit = canvas.edit
    sk = edit.sketch
    lid = sk.add_line(0, 0, 20, 0)
    cid = sk.add_circle(40, 10, 5)
    circle = sk.entities[cid]
    assert isinstance(circle, Circle)
    ref = edit.reference_line((0, -10), (50, -10))  # a model edge copy (D113)
    sk.relate("fixed", lid)
    sk.relate("horizontal", lid)  # not needed: over defines
    point = sk.add_point(5, -10)
    sk.relate("coincident", point, ref)
    canvas.changed()
    rp = RelationsPanel(canvas)
    qtbot.addWidget(rp)
    # The origin's own fixed relation is never listed.
    assert 0 not in rp.listed()
    assert len(rp.listed()) == len(sk.relations) - 1
    rp.set_filter("problems")
    problems = {sk.relations[i].type for i in rp.listed()}
    assert problems and problems <= {"fixed", "horizontal"}
    assert all(sk.relations[i].entities == [lid] for i in rp.listed())
    rp.set_filter("model")
    assert {sk.relations[i].type for i in rp.listed()} == {"fixed", "coincident"}
    assert all(lid not in sk.relations[i].entities for i in rp.listed())
    assert listed_relations(edit, "model") == rp.listed()
    # Selecting a row selects the relation in the canvas, which highlights its items.
    horizontal = next(i for i, r in enumerate(sk.relations) if r.type == "horizontal")
    rp.set_filter("all")
    rp.select_rows([horizontal])
    assert canvas.selected_relations() == [horizontal]
    assert lid in canvas._related()
    rp.delete_selected()
    assert [r.type for r in canvas.edit.sketch.relations].count("horizontal") == 0
    rp.set_filter("problems")
    assert rp.listed() == []  # nothing over defines now
    rp.set_filter("all")
    count = len(sk.relations)
    rp.delete_listed()
    assert len(canvas.edit.sketch.relations) == 1  # only the origin fix stays
    canvas.undo()
    assert len(canvas.edit.sketch.relations) == count
    assert len(rp.listed()) == count - 1


def test_midpoint_on_an_arc_from_the_panel(qtbot: QtBot, canvas: SketchCanvas) -> None:
    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    sk = canvas.edit.sketch
    aid = sk.add_arc(0, 0, 10, 0, math.pi / 2)
    sk.relate("fixed", aid)
    pid = sk.add_point(6, 9)
    canvas.changed()
    canvas.selection = [pid, aid]
    canvas.selection_changed.emit()
    panel.relation_buttons["midpoint"].click()
    s = canvas.edit.sketch.xy(pid)
    assert s == pytest.approx((10 / math.sqrt(2), 10 / math.sqrt(2)), abs=1e-6)
