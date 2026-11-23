"""Extrude panel additions (PHASE2_SPEC P2.1): end conditions with picks, Offset from
Face options, draft and the Thin Feature group."""

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.naming.select import reference_for
from fdcad.core.sketch.model import Sketch
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _second(qtbot: QtBot, operation: str = "cut") -> tuple[DocumentSession, str, str]:
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = add_extrude(doc, sk, 5.0, operation=operation)
    return _session(qtbot, doc), ext, fid


def test_old_extrude_gets_no_new_keys(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, fid = _second(qtbot)
    original = session.document.feature(fid)
    panel.begin(session, original, is_new=False)
    result = panel.current_feature()
    assert result is not None
    assert set(result.params) <= set(original.params) | {"merge", "reverse"}
    assert result.refs == original.refs


def test_end_conditions_are_listed_for_both_directions(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, fid = _second(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    for name in ("end_condition", "end_condition2"):
        box = panel.choices[name]
        items = [box.itemData(i) for i in range(box.count())]
        assert {"up_to_vertex", "up_to_face", "offset_from_face"} <= set(items)


def test_offset_from_face_with_a_picked_face(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext, fid = _second(qtbot)
    report = session.report
    assert report is not None and report.body is not None
    top = report.results[ext].body
    assert top is not None
    face = top.face(f"{ext}/cap/end")
    assert face is not None
    panel.begin(session, session.document.feature(fid), is_new=False)
    box = panel.choices["end_condition"]
    box.setCurrentIndex(box.findData("offset_from_face"))
    end = panel.ends[""]
    assert end.wants_pick()
    assert not end.pick_row.isHidden() and not end.options_row.isHidden()
    assert panel.values["depth"].parentWidget().isHidden()
    assert panel.current_feature() is None  # no pick yet
    assert panel.set_start_pick(reference_for(top, face)) is None
    panel.values["end_offset"].edit.setText("3")
    end.offset_reverse.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition"] == "offset_from_face"
    assert result.params["end_offset"] == Param("3", 3.0)
    assert result.params["end_offset_reverse"] is True
    assert result.refs["end"]["name"] == f"{ext}/cap/end"
    box.setCurrentIndex(box.findData("blind"))
    result = panel.current_feature()
    assert result is not None
    assert "end" not in result.refs and "end_offset" not in result.params


def test_up_to_face_lists_planes(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, fid = _second(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    box = panel.choices["end_condition"]
    box.setCurrentIndex(box.findData("up_to_face"))
    pick = panel.ends[""].pick
    pick.setCurrentIndex(pick.findData({"feature": "f3"}))
    result = panel.current_feature()
    assert result is not None and result.refs["end"] == {"feature": "f3"}


def test_draft_button_writes_angle_and_outward(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, fid = _second(qtbot, "boss")
    panel.begin(session, session.document.feature(fid), is_new=False)
    end = panel.ends[""]
    assert panel.values["draft_angle"].parentWidget().isHidden()
    end.draft.setChecked(True)
    assert not panel.values["draft_angle"].parentWidget().isHidden()
    panel.values["draft_angle"].edit.setText("3")
    end.outward.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["draft_angle"].value == pytest.approx(math.radians(3))
    assert result.params["draft_outward"] is True
    end.draft.setChecked(False)
    result = panel.current_feature()
    assert result is not None and "draft_angle" not in result.params


def test_thin_group_writes_its_values(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, fid = _second(qtbot, "boss")
    panel.begin(session, session.document.feature(fid), is_new=False)
    thin = panel.groups["thin"]
    assert not thin.isHidden()
    assert panel.thin is not None
    thin.set_checked(True)
    panel.thin.kind.setCurrentIndex(panel.thin.kind.findData("two_direction"))
    panel.values["thin_thickness"].edit.setText("2")
    panel.values["thin_thickness2"].edit.setText("1.5")
    panel.thin.cap.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["thin_type"] == "two_direction"
    assert result.params["thin_thickness"] == Param("2", 2.0)
    assert result.params["thin_thickness2"] == Param("1.5", 1.5)
    assert result.params["thin_cap"] is True
    assert result.params["thin_cap_thickness"] == Param("1", 1.0)
    thin.set_checked(False)
    result = panel.current_feature()
    assert result is not None
    assert not any(k.startswith("thin_") for k in result.params)


def test_hidden_direction_2_end_does_not_take_the_from_pick(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    # Bug hunt E3: Direction 2 set to Up to Face and then turned off still took
    # the next face picked in the view, so From never got it.
    session, ext, fid = _second(qtbot)
    panel.begin(session, session.document.feature(fid), is_new=False)
    panel.groups["direction2"].set_checked(True)
    box2 = panel.choices["end_condition2"]
    box2.setCurrentIndex(box2.findData("up_to_face"))
    panel.groups["direction2"].set_checked(False)
    assert not panel.end_wants_pick()
    start = panel.start
    assert start is not None
    start.condition.setCurrentIndex(start.condition.findData("surface"))
    report = session.report
    assert report is not None
    plate_body = report.results[ext].body
    assert plate_body is not None
    face = plate_body.face(f"{ext}/cap/end")
    assert face is not None
    ref = reference_for(plate_body, face)
    assert panel.set_start_pick(ref) is None
    result = panel.current_feature()
    assert result is not None and result.refs["start"] == ref


def test_inch_part_defaults_are_inch_sized(qtbot: QtBot, panel: PropertyPanel) -> None:
    # Bug hunt E5: in an inch part the From offset and end offset defaulted to
    # 10 in and the thin wall to 1 in.
    from fdcad.core.units import UnitSystem

    doc, _ext = plate()
    doc.units = UnitSystem.IN
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0, operation="cut")
    panel.begin(_session(qtbot, doc), doc.feature(fid), is_new=False)
    expected = {
        "start_offset": 12.7,
        "end_offset": 12.7,
        "end_offset2": 12.7,
        "thin_thickness": 1.27,
        "thin_thickness2": 1.27,
        "thin_cap_thickness": 1.27,
    }
    for name, mm in expected.items():
        param = panel.values[name].param()
        assert param is not None and param.value == pytest.approx(mm), name
    draft = panel.values["draft_angle"].param()
    assert draft is not None and draft.value == pytest.approx(math.radians(5))


def test_profile_offset_is_kept_only_when_set(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR344, D880."""
    session, _ext, fid = _second(qtbot, "boss")
    panel.begin(session, session.document.feature(fid), is_new=False)
    result = panel.current_feature()
    assert result is not None and "profile_offset" not in result.params
    panel.values["profile_offset"].edit.setText("-0.2")
    result = panel.current_feature()
    assert result is not None
    assert result.params["profile_offset"].value == pytest.approx(-0.2)
