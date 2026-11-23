"""Loft panel (PHASE2_SPEC P2.3): ordered profiles, connection points, constraints,
Close loft and Thin Feature."""

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, new_document
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.loft_form import LoftForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_loft import _square, _two_levels
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def test_profiles_order_connection_and_constraints(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 3)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "loft", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, LoftForm)
    for sid in (high, low):
        form.sketch.setCurrentIndex(form.sketch.findData(sid))
        form.add_sketch()
    assert panel.current_feature() is not None
    form.profiles.list.setCurrentRow(1)
    form.profiles.move_item(-1)  # low first now
    form.profiles.list.setCurrentRow(1)
    form.connect_point.setValue(2)
    start = form.kinds["start"]
    start.setCurrentIndex(start.findData("normal"))
    assert not form.fields["start_length"].parentWidget().isHidden()
    form.fields["start_length"].edit.setText("8")
    result = panel.current_feature()
    assert result is not None
    assert result.refs["profiles"] == [{"feature": low}, {"feature": high}]
    assert result.params["connect_2"] == 2
    assert result.params["start_constraint"] == "normal"
    assert result.params["start_length"] == Param("8", 8.0)
    assert "end_constraint" not in result.params


def test_close_loft_turns_constraints_off_and_thin(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    a, b = _square(doc, {"feature": "f2"}, 5), _square(doc, {"feature": "f4"}, 5)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "loft", "boss"), is_new=True)
    form = panel.form
    form.profiles.add({"feature": a})
    form.profiles.add({"feature": b})
    form.close.setChecked(True)
    assert not form.kinds["start"].isEnabled()
    panel.groups["thin"].set_checked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["close_loft"] is True
    assert result.params["thin_type"] == "one_direction"


def test_one_profile_is_not_enough(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    a = _square(doc, {"feature": "f2"}, 5)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "loft", "cut"), is_new=True)
    panel.form.profiles.add({"feature": a})
    assert panel.current_feature() is None
    assert "two profiles" in panel.message.text()
    assert panel.form.thin is None


def test_pick_list_keeps_widget_move(qtbot: QtBot) -> None:
    """Regression (D485): PickList.move(step) once hid QWidget.move, so Qt style
    calls such as move(QPoint) failed. The reorder step is move_item now."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QListWidgetItem

    from fdcad.ui.property_panel.forms.base import PickList

    picks = PickList(new_document(), "tip", ordered=True)
    qtbot.addWidget(picks)
    picks.move(QPoint(3, 4))
    assert picks.pos() == QPoint(3, 4)
    for name in ("a", "b"):
        picks.list.addItem(QListWidgetItem(name))
    picks.list.setCurrentRow(1)
    picks.up.click()
    assert [picks.list.item(i).text() for i in range(2)] == ["b", "a"]


def test_guides_centerline_and_sections(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Guide Curves, Centerline and Number of Sections (TR55, D804)."""
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 3)
    guide = _square(doc, {"feature": "f4"}, 1)  # any sketch will do for the list
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "loft", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, LoftForm)
    form.profiles.add({"feature": low})
    form.profiles.add({"feature": high})
    form.guides.chooser.setCurrentIndex(form.guides.chooser.findData(guide))
    assert form.guides.add_chosen()
    assert not form.guides.add_chosen()  # already listed
    form.centerline.setCurrentIndex(form.centerline.findData(guide))
    form.fields["sections"].edit.setText("6")
    result = panel.current_feature()
    assert result is not None
    assert result.refs["guides"] == [{"feature": guide}]
    assert result.refs["centerline"] == {"feature": guide}
    assert result.params["sections"] == Param("6", 6.0)
    assert form.guides.take({"kind": "edge", "name": "e"}) is False  # tick off: not a guide
    form.guides.pick_edges.setChecked(True)
    assert form.guides.take({"kind": "edge", "name": "e"})


def test_edges_picked_together_make_one_loop_profile(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR138 item 1 (D1908): a loop of model edges is a loft profile."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.core.rebuild.runner import rebuild
    from tests.core.features.test_patterns import centred

    doc, plate, boss = centred()
    doc.features = [f for f in doc.features if f.id != boss]
    body = rebuild(doc)[plate].body
    assert body is not None
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "loft", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, LoftForm)
    edges = []
    ex = TopExp_Explorer(body.face(f"{plate}/cap/end"), TopAbs_EDGE)
    while ex.More():
        edges.append(ex.Current())
        ex.Next()
    assert form.take_shapes(body, edges) is None
    refs = form.profiles.refs()
    assert len(refs) == 1 and refs[0]["kind"] == "loop" and len(refs[0]["edges"]) == 4
    assert form.profiles.list.item(0).text().startswith("Edge loop of")


def test_show_section_is_written_only_when_set(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR139 item 2 (D1909)."""
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 3)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "loft", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, LoftForm)
    for sid in (low, high):
        form.sketch.setCurrentIndex(form.sketch.findData(sid))
        form.add_sketch()
    result = panel.current_feature()
    assert result is not None and "show_section" not in result.params
    form.fields["show_section"].edit.setText("4")
    result = panel.current_feature()
    assert result is not None and result.params["show_section"].value == 4.0


def test_connectors_per_profile_and_reset(qtbot: QtBot, panel: PropertyPanel) -> None:
    """TR136 item 1 (D2403): more connectors typed per profile, and Reset."""
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 5)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "loft", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, LoftForm)
    form.profiles.add({"feature": low})
    form.profiles.add({"feature": high})
    form.profiles.list.setCurrentRow(0)
    form.match_points.setText("2")
    form.match_points.textEdited.emit("2")
    form.profiles.list.setCurrentRow(1)
    assert form.match_points.text() == ""
    form.match_points.setText("3")
    form.match_points.textEdited.emit("3")
    form.connect_point.setValue(1)
    result = panel.current_feature()
    assert result is not None
    assert (result.params["match_1"], result.params["match_2"]) == ("2", "3")
    form.profiles.list.setCurrentRow(0)
    assert form.match_points.text() == "2"
    form.reset()
    result = panel.current_feature()
    assert result is not None
    assert not [k for k in result.params if k.startswith(("match_", "connect_"))]
