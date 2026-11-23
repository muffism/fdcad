"""Curve panels (PHASE3_SPEC P3.6): helix and spiral with variable pitch rows,
projected curve and composite curve; OK adds one undoable feature; curves show
in the sweep path list; the commands exist with icons."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.model import Sketch
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.curve_forms import (
    CompositeCurveForm,
    HelixForm,
    ProjectedCurveForm,
)
from fdcad.ui.property_panel.forms.pipe_forms import ContourForm
from fdcad.ui.property_panel.forms.sweep_form import SweepForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_curves import FRONT, RIGHT, P, add, circle_sketch
from tests.core.features.test_features import add_sketch, plate
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def test_helix_panel_writes_values_and_ok_adds_it(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    sk = circle_sketch(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "helix", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, HelixForm)
    assert panel.title.text() == "Helix 1"
    assert panel.current_feature() is None  # no sketch yet
    form.sketch.setCurrentIndex(form.sketch.findData(sk))
    form.fields["pitch"].edit.setText("4")
    form.fields["turns"].edit.setText("3")
    form.fields["start_angle"].edit.setText("30")
    form.clockwise.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.refs["sketch"] == {"feature": sk}
    assert result.params["definition"] == "pitch_turns"
    assert result.params["pitch"].value == pytest.approx(4.0)
    assert result.params["turns"].value == pytest.approx(3.0)
    assert result.params["start_angle"].value == pytest.approx(math.radians(30))
    assert result.params["clockwise"] is True
    assert "height" not in result.params
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    added = doc.features[-1]
    assert added.type == "helix"
    report = session.report
    assert report is not None and report.results[added.id].state is FeatureState.OK
    assert "curve" in report.results[added.id].extras
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert all(f.type != "helix" for f in doc.features)


def test_helix_definition_shows_the_right_fields(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    circle_sketch(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "helix", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, HelixForm)

    def shown(name: str) -> bool:
        return not form.fields[name].parentWidget().isHidden()

    form.definition.setCurrentIndex(form.definition.findData("height_turns"))
    assert shown("height") and shown("turns") and not shown("pitch")
    form.definition.setCurrentIndex(form.definition.findData("spiral"))
    assert shown("pitch") and shown("turns") and not shown("taper_angle")
    form.definition.setCurrentIndex(form.definition.findData("pitch_turns"))
    form.pitch_type.setCurrentIndex(form.pitch_type.findData("variable"))
    assert not shown("pitch") and not form.rows_widget.isHidden()
    assert form.heights() == ["height 0", "height 10"]
    form.add_row.click()
    assert "vp_turns_3" in form.fields
    form.fields["vp_turns_3"].edit.setText("6")
    form.fields["vp_pitch_3"].edit.setText("2")
    form.sketch.setCurrentIndex(0)
    result = panel.current_feature()
    assert result is not None
    assert result.params["pitch_type"] == "variable"
    assert result.params["vp_rows"] == 3
    assert result.params["vp_turns_3"].value == pytest.approx(6.0)
    assert "pitch" not in result.params
    form.remove_row.click()
    form.remove_row.click()  # never fewer than two rows
    assert form.row_count == 2


def test_projected_curve_panel_modes(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    a = Sketch()
    a.add_line(0, 0, 40, 0)
    sa = add_sketch(doc, a, FRONT)
    b = Sketch()
    b.add_line(0, 0, 0, 30)
    sb = add_sketch(doc, b, RIGHT)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "projected_curve", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, ProjectedCurveForm)
    form.sketch.setCurrentIndex(form.sketch.findData(sa))
    assert panel.current_feature() is None  # faces are needed
    form.mode.setCurrentIndex(form.mode.findData("sketches"))
    assert form.faces.isHidden() and not form.sketch2_row.isHidden()
    form.sketch2.setCurrentIndex(form.sketch2.findData(sb))
    result = panel.current_feature()
    assert result is not None
    assert result.params["mode"] == "sketches"
    assert result.refs == {"sketch": {"feature": sa}, "sketch2": {"feature": sb}}


def test_composite_curve_panel_and_sweep_path_list(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    s1 = Sketch()
    s1.add_line(0, 0, 20, 0)
    k1 = add_sketch(doc, s1, FRONT)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "composite_curve", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, CompositeCurveForm)
    assert panel.current_feature() is None
    form._add_choice(form.choice.findData(k1))
    result = panel.current_feature()
    assert result is not None and result.refs["items"] == [{"feature": k1}]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    curve_id = doc.features[-1].id
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    sweep = panel.form
    assert isinstance(sweep, SweepForm)
    assert sweep.path.findData(curve_id) >= 0
    panel.reject()


def test_curve_commands_exist() -> None:
    for cid in ("feature.helix", "feature.projected_curve", "feature.composite_curve"):
        assert cid in BY_ID


def test_direction_lists_offer_axes_and_only_earlier_planes(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    """Projected curve and contour directions list planes and axes above the feature."""
    doc, _ext = plate(10.0)
    axis = add(doc, "ref_axis", {"first": {"feature": "f3"}, "second": {"feature": "f4"}},
               method="two_planes")  # fmt: skip
    a = Sketch()
    a.add_line(0, 0, 40, 0)
    sa = add_sketch(doc, a, FRONT)
    contour = add(doc, "contour", {"direction": {"feature": axis}}, spacing=P(2.5))
    late = add(doc, "ref_plane", {"first": {"feature": "f2"}}, method="offset", distance=P(5))
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(contour), is_new=False)
    form = panel.form
    assert isinstance(form, ContourForm)
    choices = [form.direction.itemData(i) for i in range(form.direction.count())]
    assert {"feature": axis} in choices and {"feature": late} not in choices
    assert form.direction.currentData() == {"feature": axis}
    panel.reject()
    panel.begin(session, phase2_feature(doc, "projected_curve", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, ProjectedCurveForm)
    choices = [form.direction.itemData(i) for i in range(form.direction.count())]
    assert {"feature": axis} in choices and {"feature": late} in choices  # a new one is last
    form.sketch.setCurrentIndex(form.sketch.findData(sa))
    form.faces.add({"kind": "face", "name": "x"})
    form.use_direction.setChecked(True)
    form.direction.setCurrentIndex(form.direction.findData({"feature": axis}))
    result = panel.current_feature()
    assert result is not None and result.refs["direction"] == {"feature": axis}
    panel.reject()


def test_empty_lists_prompt_for_what_they_hold(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Only the helix asks for a sketch with one circle; other lists say what they take."""
    doc = new_document()
    session = _session(qtbot, doc)
    prompts = {}
    for ftype in ("helix", "projected_curve", "composite_curve", "curve_array"):
        panel.begin(session, phase2_feature(doc, ftype, "boss"), is_new=True)
        form = panel.form
        boxes = [getattr(form, n) for n in ("sketch", "choice", "path") if hasattr(form, n)]
        prompts[ftype] = [b.placeholderText() for b in boxes]
        panel.reject()
    assert prompts == {
        "helix": ["Choose a sketch with one circle"],
        "projected_curve": ["Choose a sketch."],
        "composite_curve": ["Add a sketch or curve"],
        "curve_array": ["Add a feature to copy", "Choose a sketch or curve"],
    }


def test_contour_curves_are_offered_as_paths_and_items(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate(10.0)
    contour = add(doc, "contour", {"direction": {"feature": "f2"}}, spacing=P(6))
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "composite_curve", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, CompositeCurveForm)
    assert form.choice.findData(contour) >= 0
    panel.reject()
    panel.begin(session, phase2_feature(doc, "sweep", "boss"), is_new=True)
    sweep = panel.form
    assert isinstance(sweep, SweepForm)
    assert sweep.path.findData(contour) >= 0
    panel.reject()
