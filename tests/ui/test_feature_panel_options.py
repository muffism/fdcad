"""Feature panel completion (WP10): From list, Through All for bosses, Direction 2 end
conditions, Cut Outside and value stepping (TOOL_SPEC T5.1.2 to T5.1.5, T6.1.4)."""

import copy
import math

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.naming.select import reference_for
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.property_panel.stepping import step_text
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect, shaft
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _second_feature(qtbot: QtBot, operation: str = "boss") -> tuple[DocumentSession, str]:
    """A plate, then a small extrude on the Front plane (so a body exists before it)."""
    doc, _ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = add_extrude(doc, sk, 5.0, operation=operation)
    return _session(qtbot, doc), fid


# From ---------------------------------------------------------------------------------


def test_old_feature_keeps_its_params_exactly(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot)
    original = session.document.feature(fid)
    panel.begin(session, original, is_new=False)
    result = panel.current_feature()
    assert result is not None
    new_keys = {"start_condition", "start_offset", "start_reverse", "end_condition2", "cut_outside"}
    assert not new_keys & set(result.params)
    assert {k: v for k, v in result.params.items() if k not in ("merge", "reverse")} == {
        k: v for k, v in original.params.items() if k not in ("merge", "reverse")
    }
    assert result.refs == original.refs


def test_from_list_has_four_choices(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    assert panel.start is not None
    box = panel.start.condition
    assert [box.itemData(i) for i in range(box.count())] == [
        "sketch_plane", "surface", "vertex", "offset",
    ]  # fmt: skip
    assert panel.start.pick_row.isHidden() and panel.start.offset_row.isHidden()


def test_offset_start_writes_offset_and_reverse(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    assert panel.start is not None
    panel.start.condition.setCurrentIndex(panel.start.condition.findData("offset"))
    assert not panel.start.offset_row.isHidden()
    panel.values["start_offset"].edit.setText("7")
    panel.start.reverse.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["start_condition"] == "offset"
    assert result.params["start_offset"] == Param("7", 7.0)
    assert result.params["start_reverse"] is True
    panel.start.condition.setCurrentIndex(panel.start.condition.findData("sketch_plane"))
    result = panel.current_feature()
    assert result is not None
    assert not {"start_condition", "start_offset", "start_reverse"} & set(result.params)


def test_surface_start_lists_planes_and_takes_picked_faces(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    session, fid = _second_feature(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    assert panel.start is not None
    panel.start.condition.setCurrentIndex(panel.start.condition.findData("surface"))
    assert panel.current_feature() is None  # nothing picked yet
    assert "Pick a face" in panel.message.text()
    pick = panel.start.pick
    names = [pick.itemText(i) for i in range(pick.count())]
    assert names == ["Front Plane", "Top Plane", "Right Plane"]
    pick.setCurrentIndex(0)
    result = panel.current_feature()
    assert result is not None and result.refs["start"] == {"feature": "f2"}
    report = session.report
    assert report is not None and report.body is not None
    plate_id = session.document.features[5].id
    top = report.body.face(f"{plate_id}/cap/end")
    assert top is not None
    ref = reference_for(report.body, top)
    assert ref is not None
    assert panel.set_start_pick(ref) is None
    result = panel.current_feature()
    assert result is not None and result.refs["start"]["name"] == f"{plate_id}/cap/end"
    assert pick.currentText().startswith("Face of")


def test_pick_from_a_later_feature_is_refused(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot)
    plate_id = session.document.features[5].id
    panel.begin(session, session.document.feature(plate_id), is_new=False)
    assert panel.start is not None
    panel.start.condition.setCurrentIndex(panel.start.condition.findData("surface"))
    ref = {"kind": "face", "name": f"{fid}/cap/end"}
    problem = panel.set_start_pick(ref)
    assert problem is not None and "later feature" in problem
    vertex = {"kind": "vertex", "name": f"vertex({plate_id}/a|b|c)"}
    assert panel.set_start_pick(vertex) == "Pick a face of the part or a plane for From."


def test_vertex_start_lists_points_of_other_sketches(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate()
    s = Sketch()
    point = s.add_point(0, 30)
    other = add_sketch(doc, s, {"feature": "f4"})
    s2 = Sketch()
    rect(s2, 0, 0, 5, 5)
    sk = add_sketch(doc, s2, {"feature": "f3"})
    fid = add_extrude(doc, sk, 5.0)
    session = _session(qtbot, doc)
    panel.begin(session, session.document.feature(fid), is_new=False)
    assert panel.start is not None
    panel.start.condition.setCurrentIndex(panel.start.condition.findData("vertex"))
    pick = panel.start.pick
    datas = [pick.itemData(i) for i in range(pick.count())]
    assert {"feature": other, "sketch_entity": point} in datas
    assert all(d.get("feature") != sk for d in datas)  # not the feature's own sketch
    pick.setCurrentIndex(datas.index({"feature": other, "sketch_entity": point}))
    result = panel.current_feature()
    assert result is not None
    assert result.params["start_condition"] == "vertex"
    assert result.refs["start"] == {"feature": other, "sketch_entity": point}


def test_stored_start_reopens(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot)
    feature = copy.deepcopy(session.document.feature(fid))
    feature.params["start_condition"] = "surface"
    feature.refs["start"] = {"feature": "f3"}
    panel.begin(session, feature, is_new=False)
    assert panel.start is not None
    assert panel.start.current == "surface"
    assert panel.start.pick.currentData() == {"feature": "f3"}
    result = panel.current_feature()
    assert result is not None and result.refs["start"] == {"feature": "f3"}


# Direction 1 and 2 ------------------------------------------------------------------------


def test_boss_offers_through_all_once_a_body_exists(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    end = panel.choices["end_condition"]
    items = [end.itemData(i) for i in range(end.count())]
    assert items == [  # TOOL_SPEC T16 item 1 order
        "blind",
        "through_all",
        "through_all_both",
        "up_to_next",
        "up_to_vertex",
        "up_to_face",
        "offset_from_face",
        "up_to_body",
        "mid_plane",
    ]


def test_direction2_end_conditions(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot, "cut")
    panel.begin(session, session.document.feature(fid), is_new=False)
    panel.groups["direction2"].set_checked(True)
    box2 = panel.choices["end_condition2"]
    assert [box2.itemData(i) for i in range(box2.count())][:2] == ["blind", "through_all"]
    panel.values["depth2"].edit.setText("3")
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition"] == "two_directions"
    assert "end_condition2" not in result.params
    assert result.params["depth2"] == Param("3", 3.0)
    box2.setCurrentIndex(box2.findData("through_all"))
    assert panel.values["depth2"].parentWidget().isHidden()
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition2"] == "through_all"
    assert "depth2" not in result.params
    end = panel.choices["end_condition"]
    end.setCurrentIndex(end.findData("through_all"))
    box2.setCurrentIndex(box2.findData("blind"))
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition"] == "through_all"
    assert result.params["end_condition2"] == "blind"


def test_direction2_off_with_mid_plane_writes_nothing(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    panel.groups["direction2"].set_checked(True)
    end = panel.choices["end_condition"]
    end.setCurrentIndex(end.findData("mid_plane"))
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition"] == "mid_plane"
    assert "end_condition2" not in result.params and "depth2" not in result.params


# Cut Outside ----------------------------------------------------------------------------


def test_cut_outside_tick_for_cuts_only(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot, "cut")
    panel.begin(session, session.document.feature(fid), is_new=False)
    outside = panel.flags["cut_outside"]
    assert not outside.isChecked()
    result = panel.current_feature()
    assert result is not None and "cut_outside" not in result.params
    outside.setChecked(True)
    result = panel.current_feature()
    assert result is not None and result.params["cut_outside"] is True
    panel.reject()
    session2, boss = _second_feature(qtbot)
    panel.begin(session2, session2.document.feature(boss), is_new=False)
    assert "cut_outside" not in panel.flags


def test_revolve_cut_has_cut_outside(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, rev = shaft(360, operation="cut")
    session = DocumentSession(doc)
    panel.begin(session, doc.feature(rev), is_new=False)
    panel.flags["cut_outside"].setChecked(True)
    result = panel.current_feature()
    assert result is not None and result.params["cut_outside"] is True
    assert panel.start is None  # From choices are for Extrude only


def test_ok_is_one_undoable_command(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot, "cut")
    before = copy.deepcopy(session.document.feature(fid).params)
    panel.begin(session, session.document.feature(fid), is_new=False)
    panel.flags["cut_outside"].setChecked(True)
    panel.accept()
    assert session.document.feature(fid).params["cut_outside"] is True
    session.undo.undo()
    assert session.document.feature(fid).params == before


# Stepping -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind", "units", "steps", "factor", "expected"),
    [
        ("10", Kind.LENGTH, UnitSystem.MM, 1, 1.0, "11"),
        ("10", Kind.LENGTH, UnitSystem.MM, -1, 10.0, "10"),  # would reach 0: not taken
        ("10", Kind.LENGTH, UnitSystem.MM, 2, 0.1, "10.2"),
        ("2 cm", Kind.LENGTH, UnitSystem.MM, 1, 1.0, "2.1 cm"),
        ("1", Kind.LENGTH, UnitSystem.IN, 1, 1.0, "1.1"),
        ("90", Kind.ANGLE, UnitSystem.MM, -1, 10.0, "80"),
        ("=Width/2", Kind.LENGTH, UnitSystem.MM, 1, 1.0, "=Width/2"),
        ("Width", Kind.LENGTH, UnitSystem.MM, 1, 1.0, "Width"),
        ("5 parsecs", Kind.LENGTH, UnitSystem.MM, 1, 1.0, "5 parsecs"),
    ],
)
def test_step_text(
    text: str, kind: Kind, units: UnitSystem, steps: int, factor: float, expected: str
) -> None:
    assert step_text(text, kind, units, steps, factor) == expected


def test_step_in_radians_is_one_degree() -> None:
    assert float(step_text("1 rad", Kind.ANGLE, UnitSystem.MM, 1).split()[0]) == pytest.approx(
        1 + math.pi / 180, abs=1e-6
    )


def test_wheel_and_arrows_step_panel_fields(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, fid = _second_feature(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    edit = panel.values["depth"].edit
    edit.setText("5")
    wheel = QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )  # fmt: skip
    QApplication.sendEvent(edit, wheel)
    assert edit.text() == "6"
    QApplication.sendEvent(
        edit, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.ControlModifier)
    )
    assert edit.text() == "16"
    QApplication.sendEvent(
        edit, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    )
    assert edit.text() == "15.9"
    result = panel.current_feature()
    assert result is not None and result.params["depth"] == Param("15.9", 15.9)
    assert panel.start is not None
    assert panel.values["start_offset"].stepper is not None


def test_cut_print_top_is_saved_only_when_chosen(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR175 (D784): Extruded Cut's Print Top."""
    session, fid = _second_feature(qtbot, "cut")
    panel.begin(session, session.document.feature(fid), is_new=False)
    top = panel.choices["print_top"]
    assert top.currentData() == "none"
    assert "print_top" not in panel.current_feature().params
    top.setCurrentIndex(top.findData("teardrop"))
    assert panel.current_feature().params["print_top"] == "teardrop"
    boss, bid = _second_feature(qtbot)
    panel.begin(boss, boss.document.feature(bid), is_new=False)
    assert "print_top" not in panel.choices
