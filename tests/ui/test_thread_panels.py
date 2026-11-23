"""Cosmetic thread panel (PHASE4_SPEC P4.2) and the thread display pattern."""

from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.main_window.phase4_features import thread_notes
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.thread_forms import CosmeticThreadForm
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import add_sketch_edges
from tests.core.features.test_cosmetic_thread import add_thread, end_edge_ref, shaft
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def test_cosmetic_thread_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, ext, eid = shaft()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "cosmetic_thread", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, CosmeticThreadForm)
    assert panel.current_feature() is None  # no edge yet
    report = session.report
    assert report is not None and report.body is not None
    edge = report.body.edge(f"edge({ext}/cap/end|{ext}/side/{eid})")
    form.take_shapes(report.body, [edge])
    box = form.choice_boxes["size"]
    box.setCurrentIndex(box.findData("M10"))
    assert form.fields["diameter"].param().value == pytest.approx(10.0)  # type: ignore[union-attr]
    assert form.fields["pitch"].param().value == pytest.approx(1.5)  # type: ignore[union-attr]
    end = form.choice_boxes["end_condition"]
    end.setCurrentIndex(end.findData("full"))
    assert not form.shown("length")
    feature = panel.current_feature()
    assert feature is not None and "length" not in feature.params
    assert feature.refs["edge"][0]["name"].startswith("edge(")


def test_thread_pattern_and_notes_from_a_report() -> None:
    doc, ext, eid = shaft()
    add_thread(doc, end_edge_ref(doc, ext, eid))
    report = RebuildEngine().rebuild(doc)
    add_sketch_edges(report)
    assert report.thread_edges is not None
    assert thread_notes(doc, report)[0].startswith("Cosmetic thread M10x1.5")


def test_modeled_thread_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    from fdcad.ui.property_panel.forms.thread_forms import ModeledThreadForm

    doc, ext, eid = shaft()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "modeled_thread", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, ModeledThreadForm)
    assert "nominal" in form.nominal_note.text()
    report = session.report
    assert report is not None and report.body is not None
    form.take_shapes(report.body, [report.body.edge(f"edge({ext}/cap/end|{ext}/side/{eid})")])
    end = form.choice_boxes["end_condition"]
    end.setCurrentIndex(end.findData("revolutions"))
    assert form.shown("revolutions") and not form.shown("length")
    form.fields["revolutions"].edit.setText("4")
    hand = form.choice_boxes["hand"]
    hand.setCurrentIndex(hand.findData("left"))
    feature = panel.current_feature()
    assert feature is not None
    assert feature.params["hand"] == "left" and feature.params["revolutions"].value == 4.0  # type: ignore[union-attr]
    assert feature.params["keep_length"] is True
    grade = form.choice_boxes["thread_class"]  # TR393 (D1507)
    assert grade.currentData() == "none" and grade.findData("6g") >= 0
    grade.setCurrentIndex(grade.findData("6g"))
    feature = panel.current_feature()
    assert feature is not None and feature.params["thread_class"] == "6g"
    profile = form.choice_boxes["form"]  # TR254 (D1510)
    profile.setCurrentIndex(profile.findData("acme"))
    feature = panel.current_feature()
    assert feature is not None and feature.params["form"] == "acme"
    finish = form.choice_boxes["end_finish"]  # TR254 (D1918)
    finish.setCurrentIndex(finish.findData("fade"))
    assert not form.shown("profile_sketch")
    profile.setCurrentIndex(profile.findData("sketch"))
    assert form.shown("profile_sketch")
    profile.setCurrentIndex(profile.findData("acme"))
    form.fields["taper_angle"].edit.setText("1.79")  # TR145 (D1917)
    feature = panel.current_feature()
    assert feature is not None
    assert feature.params["taper_angle"].value == pytest.approx(0.031241, abs=1e-5)  # type: ignore[union-attr]
    assert feature.params["end_finish"] == "fade"


def test_a_picked_round_edge_picks_the_size_that_fits(qtbot: QtBot, panel: PropertyPanel) -> None:
    """D589: a 6 mm shaft gets M6, so a new thread builds without changing the size."""
    from fdcad.core.features.preview import build_preview

    doc, ext, eid = shaft(radius=3.0)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "modeled_thread", "boss"), is_new=True)
    form = panel.form
    report = session.report
    assert report is not None and report.body is not None
    form.take_shapes(report.body, [report.body.edge(f"edge({ext}/cap/end|{ext}/side/{eid})")])
    assert form.choice_boxes["size"].currentData() == "M6"
    assert form.fields["diameter"].edit.text() == "6"
    feature = panel.current_feature()
    assert feature is not None
    assert build_preview(doc, feature, report.results).error is None


def test_user_thread_sizes_fill_diameter_pitch_and_class(
    qtbot: QtBot, panel: PropertyPanel, tmp_path: Any
) -> None:
    """TR327 (D1920): the user size file is the thread table too."""
    from fdcad.core.features import hole_data
    from fdcad.ui.property_panel.forms.thread_forms import ModeledThreadForm

    doc, _ext, _eid = shaft()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "modeled_thread", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, ModeledThreadForm)
    table = tmp_path / "threads.csv"
    table.write_text("name,diameter,pitch,class\nM7 fine,7,0.75,6g\n", encoding="utf-8")
    assert form.load_user_sizes(str(table)).startswith("1 user hole sizes")
    box = form.choice_boxes["size"]
    box.setCurrentIndex(box.findData("M7 fine"))
    assert form.fields["pitch"].param().value == pytest.approx(0.75)  # type: ignore[union-attr]
    assert form.choice_boxes["thread_class"].currentData() == "6g"
    hole_data.USER_SIZES[:] = []
    from fdcad.ui.preferences import phase4_settings as prefs

    prefs.set_user_hole_text("")
