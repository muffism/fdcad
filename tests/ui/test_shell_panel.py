"""Shell panel (PHASE2_SPEC P2.6): faces to remove, outward, multi thickness, body box,
Show preview and the diagnosis message."""

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.preview import PreviewGeometry
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.shell_form import ShellForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    ShellForm.show_preview = True
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def test_faces_outward_and_multi_thickness(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "shell", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, ShellForm)
    assert form.body_group.isHidden()  # one body
    report = session.report
    assert report is not None and report.body is not None
    b = report.body
    form.take_shapes(b, [b.face(f"{ext}/cap/end")])
    form.outward.setChecked(True)
    form.multi_group.set_checked(True)
    form.take_shapes(b, [b.face(f"{ext}/side/e5")])
    assert "thickness_1" in form.fields
    form.fields["thickness_1"].edit.setText("2.5")
    result = panel.current_feature()
    assert result is not None
    assert result.refs["faces"][0]["name"] == f"{ext}/cap/end"
    assert result.refs["thick_faces"][0]["name"] == f"{ext}/side/e5"
    assert result.params["thickness_1"] == Param("2.5", 2.5)
    assert result.params["outward"] is True
    form.multi_group.set_checked(False)
    result = panel.current_feature()
    assert result is not None and "thick_faces" not in result.refs
    assert "thickness_1" not in result.params


def test_closed_hollow_needs_no_faces_and_preview_can_be_off(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "shell", "boss"), is_new=True)
    result = panel.current_feature()
    assert result is not None and "faces" not in result.refs
    panel.form.preview.setChecked(False)
    assert panel.form.for_preview(result) is None


def test_body_box_shows_with_several_bodies(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate()
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})
    other = add_extrude(doc, sk, 10.0, merge=False)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "shell", "boss"), is_new=True)
    form = panel.form
    assert not form.body_group.isHidden()
    assert panel.current_feature() is None
    report = session.report
    assert report is not None and report.body is not None
    form.take_shapes(report.body, [report.body.face(f"{other}/cap/end")])
    result = panel.current_feature()
    assert result is not None and result.refs["body"][0]["name"] == f"{other}/cap/end"


def test_diagnosis_is_shown(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "shell", "boss"), is_new=True)
    text = "Shell 1 failed: face f6/side/e5 bends with a radius of 2 mm"
    panel.preview_checked(PreviewGeometry(None, error=text, failed=["f6/side/e5"]))
    assert not panel.form.check.isHidden()
    assert "radius of 2 mm" in panel.form.check.label.text()
