"""Fastening feature panels (PHASE4_SPEC P4.4): every panel opens with defaults and the
Favourites box; boss and hook take a click as position; vent roles and areas."""

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.features.preview import PreviewGeometry
from fdcad.core.rebuild.runner import rebuild
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.preferences import phase4_settings as prefs
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.fastening_forms import (
    LipGrooveForm,
    MountingBossForm,
    SnapHookForm,
    VentForm,
)
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import body, plate
from tests.core.features.test_vent import vent_doc
from tests.ui.test_property_panel import _session


@pytest.fixture(autouse=True)
def temp_prefs(tmp_path: Path) -> Any:
    prefs.OVERRIDE = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    yield
    prefs.OVERRIDE = None


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


@pytest.mark.parametrize(
    "ftype", ["mounting_boss", "snap_hook", "snap_groove", "lip_groove", "vent"]
)
def test_every_panel_opens_with_favourites(qtbot: QtBot, panel: PropertyPanel, ftype: str) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, ftype, "boss"), is_new=True)
    form = panel.form
    assert form is not None and "favourites" in panel.groups
    assert form.favourites_box.buttons["save"].text()


@pytest.mark.parametrize("cls", [MountingBossForm, SnapHookForm])
def test_click_sets_face_and_position(qtbot: QtBot, panel: PropertyPanel, cls: Any) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    ftype = "mounting_boss" if cls is MountingBossForm else "snap_hook"
    panel.begin(session, phase2_feature(doc, ftype, "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, cls)
    report = session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ext}/cap/end")
    assert form.take_point(report.body, [top], (20.0, 30.0, 10.0))
    feature = panel.current_feature()
    assert feature is not None
    assert feature.refs["face"][0]["name"] == f"{ext}/cap/end"
    assert feature.params["pos_y"].value == pytest.approx(30.0)  # type: ignore[union-attr]
    count = len(doc.features)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    assert len(doc.features) == count + 1
    body(rebuild(doc), doc.features[-1].id)


def test_boss_fields_follow_the_type(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "mounting_boss", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, MountingBossForm)
    assert form.shown("hole_diameter") and not form.shown("head_diameter")
    box = form.choice_boxes["boss_type"]
    box.setCurrentIndex(box.findData("screw_head"))
    assert form.shown("head_diameter")
    box.setCurrentIndex(box.findData("pin"))
    assert form.shown("pin_diameter") and not form.shown("hole_diameter")
    form.fields["fin_count"].edit.setText("0")
    assert not form.shown("fin_length")
    # TR146 (D1517): mating sizes, with their gaps once something is picked.
    assert form.shown("height_face") and not form.shown("height_clearance")
    assert form.shown("pin_edge") and not form.shown("pin_clearance")
    form.picks["height_face"].set_refs([{"kind": "face", "name": "face(a|b)"}])
    assert form.shown("height_clearance")
    form.picks["pin_edge"].set_refs([{"kind": "edge", "name": "edge(a|b)"}])
    assert form.shown("pin_clearance")
    assert form.shown("step_height") and not form.shown("step_diameter")  # TR146 (D1916)
    form.fields["step_height"].edit.setText("2")
    assert form.shown("step_diameter")


def test_lip_groove_link(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "lip_groove", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, LipGrooveForm)
    assert form.shown("spacing") and not form.shown("groove_width")
    form.checks["link"].setChecked(False)
    assert form.shown("groove_width") and not form.shown("spacing")
    assert form.shown("jump_gaps") and form.shown("follow_wall")  # TR146 item 2 (D2407)
    assert "lip_edges" in form.picks and "groove_edges" in form.picks


def test_vent_roles_and_area(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext, _top, sk, ids = vent_doc()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "vent", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, VentForm)
    box = form.sketch_boxes["sketch"]
    box.setCurrentIndex(box.findData(sk))
    assert form.table.rowCount() == 10
    assert panel.current_feature() is None  # no boundary yet
    for eid in ids["boundary"]:
        form.set_role(eid, "boundary")
    form.set_role(ids["ribs"][0], "ribs")
    report = session.report
    assert report is not None and report.body is not None
    form.take_shapes(report.body, [report.body.face(f"{ext}/cap/end")])
    feature = panel.current_feature()
    assert feature is not None
    assert len(feature.refs["boundary"]) == 4 and len(feature.refs["ribs"]) == 1
    form.preview_checked(PreviewGeometry(None, info={"total_area": 600.0, "open_area": 560.0}))
    assert "93.3 percent" in form.area.text()
    assert form.shown("rib_draft") and form.shown("fill_fillet")  # TR146 item 3 (D2406)
    assert feature.params["rib_draft"].value == 0.0


def test_rib_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    from fdcad.ui.property_panel.forms.shape_forms import RibForm
    from tests.core.features.test_rib import add_rib, hollow_box

    doc = hollow_box()
    fid = add_rib(doc, [(-10, -5), (10, -5)])
    sketch_id = doc.feature(fid).refs["sketch"]["feature"]
    doc.features.pop()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "rib", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, RibForm)
    box = form.sketch_boxes["sketch"]
    box.setCurrentIndex(box.findData(sketch_id))
    assert not form.shown("use_draft")
    direction = form.choice_boxes["direction"]
    direction.setCurrentIndex(direction.findData("normal"))
    form.checks["use_draft"].setChecked(True)
    assert form.shown("draft_angle")
    feature = panel.current_feature()
    assert feature is not None and "use_draft" not in feature.params
    assert feature.params["direction"] == "normal" and "draft_angle" in feature.params
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    body(rebuild(doc), doc.features[-1].id)


def test_dome_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    from fdcad.ui.property_panel.forms.shape_forms import DomeForm

    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "dome", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, DomeForm)
    report = session.report
    assert report is not None and report.body is not None
    form.take_shapes(report.body, [report.body.face(f"{ext}/cap/end")])
    form.checks["continuous"].setChecked(True)
    feature = panel.current_feature()
    assert feature is not None and feature.params["continuous"] is True
    assert feature.refs["faces"][0]["name"] == f"{ext}/cap/end"
    # TR147 (D2301): the profile sketch is optional and empty by default.
    box = form.sketch_boxes["profile_sketch"]
    assert box.currentData() is None and "profile_sketch" not in feature.refs
    box.setCurrentIndex(box.findData(doc.features[-2].id))
    feature = panel.current_feature()
    assert feature is not None
    assert feature.refs["profile_sketch"] == {"feature": doc.features[-2].id}


def test_wrap_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    from fdcad.ui.property_panel.forms.shape_forms import WrapForm

    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "wrap", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, WrapForm)
    kind = form.choice_boxes["wrap_type"]
    kind.setCurrentIndex(kind.findData("scribe"))
    assert not form.shown("thickness")


def test_wrap_panel_method(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Method Spline Surface is written as ``method``; Analytical is not written (D528)."""
    from fdcad.ui.property_panel.forms.shape_forms import WrapForm

    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "wrap", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, WrapForm)
    sketches = form.sketch_boxes["sketch"]
    sketches.setCurrentIndex(sketches.findData(doc.features[-2].id))
    report = session.report
    assert report is not None and report.body is not None
    form.take_shapes(report.body, [report.body.face(f"{ext}/cap/end")])
    method = form.choice_boxes["method"]
    assert method.currentData() == "analytical"
    assert form.shown("reverse")
    feature = panel.current_feature()
    assert feature is not None and "method" not in feature.params
    method.setCurrentIndex(method.findData("spline"))
    assert not form.shown("reverse")  # reverse is for the cylinder of the analytical method
    feature = panel.current_feature()
    assert feature is not None and feature.params["method"] == "spline"
    panel.reject()
    stored = phase2_feature(doc, "wrap", "boss")
    stored.params["method"] = "spline"
    panel.begin(session, stored, is_new=True)
    form = panel.form
    assert isinstance(form, WrapForm)
    assert form.choice_boxes["method"].currentData() == "spline"


def test_spec_form_choices_and_row_labels(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Regression (D482): building a choice row once reused the number value and row
    label variables for the choice items. Each box lists its choices as data and
    label, and each row label is the field label."""
    from PySide6.QtWidgets import QLabel

    from fdcad.ui.property_panel.forms.shape_forms import WrapForm

    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "wrap", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, WrapForm)
    assert form.choice_boxes
    for name, box in form.choice_boxes.items():
        f = form.defs[name]
        items = tuple((box.itemData(i), box.itemText(i)) for i in range(box.count()))
        assert items == f.choices
        layout, widget = form.rows[name]
        label = layout.labelForField(widget)
        assert isinstance(label, QLabel) and label.text() == f.label
