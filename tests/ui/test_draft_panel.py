"""Draft panel (PHASE2_SPEC P2.7): neutral plane from the list or a clicked flat face,
faces to draft, propagation and the changed faces preview option."""

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.draft_form import DraftForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import plate
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    DraftForm.show_changed = True
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def test_first_flat_face_is_the_neutral_plane_then_faces(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "draft", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, DraftForm)
    assert panel.current_feature() is None
    assert "neutral plane" in panel.message.text()
    report = session.report
    assert report is not None and report.body is not None
    b = report.body
    form.take_shapes(b, [b.face(f"{ext}/cap/end")])
    form.take_shapes(b, [b.face(f"{ext}/side/e5"), b.face(f"{ext}/side/e6")])
    form.reverse.setChecked(True)
    form.propagation.setCurrentIndex(form.propagation.findData("tangent"))
    result = panel.current_feature()
    assert result is not None
    assert result.refs["neutral"]["name"] == f"{ext}/cap/end"
    assert [r["name"] for r in result.refs["faces"]] == [f"{ext}/side/e5", f"{ext}/side/e6"]
    assert result.params["reverse"] is True
    assert result.params["propagation"] == "tangent"
    assert result.params["angle"].value == pytest.approx(math.radians(1))


def test_plane_from_the_list_and_all_faces(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "draft", "boss"), is_new=True)
    form = panel.form
    form.neutral.setCurrentIndex(form.neutral.findData({"feature": "f2"}))
    assert panel.current_feature() is None  # no faces and propagation None
    form.propagation.setCurrentIndex(form.propagation.findData("all"))
    result = panel.current_feature()
    assert result is not None and result.refs["neutral"] == {"feature": "f2"}
    assert result.refs["faces"] == []
    form.changed_only.setChecked(False)
    preview = form.for_preview(result)
    assert preview is not None and preview.params["preview_whole"] is True
    assert "preview_whole" not in result.params


def test_parting_line_type_shows_its_group_and_writes_its_keys(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    from fdcad.core.features.modify import edges_of

    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "draft", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, DraftForm)
    assert form.faces_group.isVisibleTo(panel) and not form.parting_group.isVisibleTo(panel)
    form.draft_type.setCurrentIndex(form.draft_type.findData("parting_line"))
    assert not form.faces_group.isVisibleTo(panel) and form.parting_group.isVisibleTo(panel)
    assert form.pick_neutral.text() == "Pick Direction Face"
    assert not form.angle2.isVisibleTo(panel)
    report = session.report
    assert report is not None and report.body is not None
    b = report.body
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    # The first flat face sets the direction; edges become parting lines; a face is refused.
    assert form.take_shapes(b, [top]) is None
    assert form.take_shapes(b, edges_of(top)) is None
    assert "edges" in (form.take_shapes(b, [b.face(f"{ext}/side/e5")]) or "")
    assert panel.current_feature() is not None
    form.other_side.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["draft_type"] == "parting_line"
    assert result.params["other_side"] is True
    assert result.refs["neutral"]["name"] == f"{ext}/cap/end"
    assert len(result.refs["parting_lines"]) == 4
    assert "faces" not in result.refs and "both_sides" not in result.params
    form.both_sides.setChecked(True)
    assert form.angle2.isVisibleTo(panel) and not form.other_side.isVisibleTo(panel)
    form.angle2.edit.setText("3")
    result = panel.current_feature()
    assert result is not None and result.params["both_sides"] is True
    assert "other_side" not in result.params
    assert result.params["angle2"].value == pytest.approx(math.radians(3))
    form.draft_type.setCurrentIndex(form.draft_type.findData("neutral_plane"))
    assert panel.current_feature() is None  # neutral plane method needs faces
    form.propagation.setCurrentIndex(form.propagation.findData("all"))
    result = panel.current_feature()
    assert result is not None
    for key in ("draft_type", "both_sides", "angle2"):
        assert key not in result.params
    assert "parting_lines" not in result.refs


def test_stored_step_draft_opens_with_its_values(qtbot: QtBot, panel: PropertyPanel) -> None:
    from fdcad.core.document.model import Param

    doc, _ext = plate()
    session = _session(qtbot, doc)
    feature = phase2_feature(doc, "draft", "boss")
    feature.params.update({"draft_type": "step", "both_sides": True, "angle2": Param("4", 0.07)})
    feature.refs.update({"neutral": {"feature": "f2"}, "parting_lines": []})
    panel.begin(session, feature, is_new=True)
    form = panel.form
    assert isinstance(form, DraftForm)
    assert form.draft_type.currentData() == "step"
    assert form.both_sides.isChecked() and form.angle2.edit.text() == "4"
    assert panel.current_feature() is None
    assert "parting line" in panel.message.text()


def test_draft_assistant_adds_the_faces_that_need_draft(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "draft", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, DraftForm)
    form.add_faces_needing_draft()
    assert "neutral plane" in form.assist_note.text()
    form.neutral.setCurrentIndex(form.neutral.findData({"feature": "f2"}))
    form.pick_neutral.setChecked(False)
    report = session.report
    assert report is not None and report.body is not None
    form.take_shapes(report.body, [report.body.face(f"{ext}/side/e5")])
    form.add_faces_needing_draft()
    qtbot.waitUntil(lambda: "Added 3 faces" in form.assist_note.text(), timeout=20000)
    names = sorted(r["name"] for r in form.faces.refs())
    assert names == [f"{ext}/side/e{k}" for k in (5, 6, 7, 8)]
    form.add_faces_needing_draft()
    qtbot.waitUntil(lambda: "No other face" in form.assist_note.text(), timeout=20000)
    result = panel.current_feature()
    assert result is not None and len(result.refs["faces"]) == 4
