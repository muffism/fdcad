"""Sweep panel (PHASE2_SPEC P2.2): profile and path choices, circular profile, path edges,
orientation, twist and Thin Feature."""

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.sweep_form import SweepForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_sweep import square_profile, straight_path
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def test_sketch_profile_path_and_twist(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    profile, path = square_profile(doc), straight_path(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SweepForm)
    assert panel.title.text() == "Sweep 1"
    assert panel.current_feature() is None  # no profile yet
    form.profile.setCurrentIndex(form.profile.findData(profile))
    form.path.setCurrentIndex(form.path.findData(path))
    form.twist.setCurrentIndex(form.twist.findData("angle"))
    assert not form.fields["twist_angle"].parentWidget().isHidden()
    form.fields["twist_angle"].edit.setText("45")
    result = panel.current_feature()
    assert result is not None
    assert result.refs["profile"] == {"feature": profile}
    assert result.refs["path"] == {"feature": path}
    assert result.params["twist"] == "angle"
    assert result.params["twist_angle"].value == pytest.approx(math.radians(45))
    assert "orientation" not in result.params


def test_circular_profile_and_thin(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    path = straight_path(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    form = panel.form
    form.profile_type.setCurrentIndex(form.profile_type.findData("circular"))
    assert form.profile_row.isHidden()
    form.path.setCurrentIndex(form.path.findData(path))
    form.fields["diameter"].edit.setText("3")
    form.orientation.setCurrentIndex(form.orientation.findData("keep_normal"))
    assert form.thin is not None
    assert form.thin.cap.isHidden()  # sweeps do not read Cap Ends (audit B item 13, D729)
    panel.groups["thin"].set_checked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["profile_type"] == "circular"
    assert result.params["diameter"] == Param("3", 3.0)
    assert result.params["orientation"] == "keep_normal"
    assert result.params["thin_type"] == "one_direction"
    assert "profile" not in result.refs


def test_swept_cut_has_no_thin_group(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "sweep", "cut"), is_new=True)
    assert panel.form.thin is None
    assert panel.title.text() == "Sweep Cut 1"


def test_second_path_orientation(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR396 item 2 (D1514)."""
    from fdcad.ui import strings

    doc = new_document()
    profile, path = square_profile(doc), straight_path(doc)
    other = straight_path(doc, 10.0)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SweepForm)
    form.profile.setCurrentIndex(form.profile.findData(profile))
    form.path.setCurrentIndex(form.path.findData(path))
    assert form.x_path_row.isHidden() and form.orient_face.isHidden()
    form.orientation.setCurrentIndex(form.orientation.findData("second_path"))
    assert not form.x_path_row.isHidden()
    feature = Feature("f99", "sweep", "Sweep", params={})
    assert form.apply(feature) == strings.SWEEP_NEEDS_X_PATH
    form.x_path.setCurrentIndex(form.x_path.findData(other))
    result = panel.current_feature()
    assert result is not None and result.params["orientation"] == "second_path"
    assert result.refs["x_path"] == {"feature": other}
    form.orientation.setCurrentIndex(form.orientation.findData("face"))
    assert not form.orient_face.isHidden()
    assert form.apply(feature) == strings.SWEEP_NEEDS_ORIENT_FACE
    form.orientation.setCurrentIndex(form.orientation.findData("follow_path"))
    form.corners.setCurrentIndex(form.corners.findData("round"))  # TR137 (D1515)
    result = panel.current_feature()
    assert result is not None and result.params["corners"] == "round"
    assert "start_tangency" not in result.params and "merge_faces" not in result.params
    form.tangency.setCurrentIndex(form.tangency.findData("path_tangent"))  # TR56 (D1905)
    form.merge_faces.setChecked(True)
    result = panel.current_feature()
    assert result is not None and result.params["start_tangency"] == "path_tangent"
    assert result.params["merge_faces"] is True
    assert form.fields["twist_angle2"].parentWidget().isHidden()  # TR137 (D1906)
    form.twist.setCurrentIndex(form.twist.findData("angle"))
    form.sweep_direction.setCurrentIndex(form.sweep_direction.findData("both"))
    assert not form.fields["twist_angle2"].parentWidget().isHidden()
    result = panel.current_feature()
    assert result is not None and result.params["sweep_direction"] == "both"
    assert "twist_angle2" in result.params
    form.section_chooser.setCurrentIndex(form.section_chooser.findData(other))  # TR137 (D1907)
    assert form.add_section()
    result = panel.current_feature()
    assert result is not None and result.refs["profiles"] == [{"feature": other}]
    form.section_values.setText("d1 = 4 + t")  # TR396 (D1910)
    result = panel.current_feature()
    assert result is not None and result.params["section_values"] == "d1 = 4 + t"


def test_face_profile_needs_a_face(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR138 item 1 (D1516)."""
    from fdcad.ui import strings

    doc = new_document()
    path = straight_path(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SweepForm)
    assert form.profile_face.isHidden()
    form.profile_type.setCurrentIndex(form.profile_type.findData("face"))
    assert not form.profile_face.isHidden() and form.profile_row.isHidden()
    form.path.setCurrentIndex(form.path.findData(path))
    feature = Feature("f99", "sweep", "Sweep", params={})
    assert form.apply(feature) == strings.SWEEP_NEEDS_PROFILE_FACE
    face = {"kind": "face", "name": "face(a|b)"}
    form.profile_face.set_refs([face])
    assert form.apply(feature) is None
    assert feature.params["profile_type"] == "face" and feature.refs["profile_face"] == [face]


def test_turns_and_follow_curvature(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR56 items 3 and 4 (D1504)."""
    doc = new_document()
    profile, path = square_profile(doc), straight_path(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SweepForm)
    form.profile.setCurrentIndex(form.profile.findData(profile))
    form.path.setCurrentIndex(form.path.findData(path))
    form.twist.setCurrentIndex(form.twist.findData("turns"))
    assert not form.fields["twist_turns"].parentWidget().isHidden()
    assert form.fields["twist_angle"].parentWidget().isHidden()
    form.fields["twist_turns"].edit.setText("2")
    form.orientation.setCurrentIndex(form.orientation.findData("curvature"))
    result = panel.current_feature()
    assert result is not None
    assert result.params["twist"] == "turns"
    assert result.params["twist_turns"].value == pytest.approx(2.0)
    assert result.params["orientation"] == "curvature"


def test_tool_body_is_offered_for_cuts_and_needs_a_body(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR138 item 3 (D2405)."""
    from fdcad.ui import strings

    doc = new_document()
    path = straight_path(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    assert panel.form.profile_type.findData("body") < 0  # a boss has no tool body
    panel.reject()
    panel.begin(session, phase2_feature(doc, "sweep", "cut"), is_new=True)
    form = panel.form
    assert isinstance(form, SweepForm)
    assert form.tool_body.isHidden()
    form.profile_type.setCurrentIndex(form.profile_type.findData("body"))
    assert not form.tool_body.isHidden() and form.profile_row.isHidden()
    form.path.setCurrentIndex(form.path.findData(path))
    feature = Feature("f99", "sweep", "Sweep", params={"operation": "cut"})
    assert form.apply(feature) == strings.SWEEP_NEEDS_TOOL_BODY
    face = {"kind": "face", "name": "face(a|b)"}
    form.tool_body.set_refs([face])
    assert form.apply(feature) is None
    assert feature.params["profile_type"] == "body" and feature.refs["tool_body"] == face


def test_ground_ends_tick(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR162 item 2 (D2408)."""
    doc = new_document()
    path = straight_path(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, SweepForm)
    form.profile_type.setCurrentIndex(form.profile_type.findData("circular"))
    form.path.setCurrentIndex(form.path.findData(path))
    feature = Feature("f99", "sweep", "Sweep", params={})
    form.fields["diameter"].edit.setText("2")
    assert form.apply(feature) is None and "ground_ends" not in feature.params
    form.ground_ends.setChecked(True)
    assert form.apply(feature) is None and feature.params["ground_ends"] is True
