"""Spacing law fields on Array Along Curve and Circular Pattern (TR366, D1500)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_property_panel import _session
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_curve_array_law_fields_show_and_are_written(qtbot: QtBot) -> None:
    from fdcad.core.document.model import new_document
    from fdcad.ui.main_window.new_feature import phase2_feature
    from fdcad.ui.property_panel.forms.pipe_forms import CurveArrayForm
    from fdcad.ui.property_panel.panel import PropertyPanel

    doc = new_document()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, phase2_feature(doc, "curve_array", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, CurveArrayForm)
    form.features.add({"feature": "f1"})
    form.path_edges.add({"kind": "edge", "name": "edge(a|b)"})
    form.law.setCurrentIndex(form.law.findData("fractions"))
    assert not form.fractions.isHidden()
    form.fractions.setText("0.2, 0.5, 1")
    feature = Feature("f99", "curve_array", "Array", params={})
    assert form.apply(feature) is None
    assert feature.params["law"] == "fractions"
    assert feature.params["fractions"] == "0.2, 0.5, 1"
    form.law.setCurrentIndex(form.law.findData("growing"))
    assert form.fractions.isHidden()
    assert form.apply(feature) is None
    assert "ratio" in feature.params and "fractions" not in feature.params
    form.law.setCurrentIndex(form.law.findData("even"))
    assert form.apply(feature) is None
    assert "law" not in feature.params and "ratio" not in feature.params


def test_circular_per_copy_angles_field(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.circular_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    law = form.widgets["law1"]
    law.setCurrentIndex(law.findData("angles"))
    form.widgets["angles1"].setText("30, 75, 160")
    assert "angles1" in [f.name for f in form.shown_fields()]
    made = panel.current_feature()
    assert made is not None and made.params["law1"] == "angles"
    assert made.params["angles1"] == "30, 75, 160"
    law.setCurrentIndex(law.findData("even"))
    assert "angles1" not in [f.name for f in form.shown_fields()]
    panel.reject()


def test_linear_seed_cell_and_rotate_fields(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.linear_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    names = [f.name for f in form.shown_fields()]
    assert "seed_cell1" in names and "rotate" not in names
    assert "check" in names  # TR399 (D1519)
    form.widgets["seed_cell1"].edit.setText("2")
    made = panel.current_feature()
    assert made is not None and made.params["seed_cell1"].value == 2.0
    form.widgets["symmetric1"].setChecked(True)
    assert "seed_cell1" not in [f.name for f in form.shown_fields()]
    panel.reject()


def test_linear_fit_fill_shows_size_not_count(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.linear_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    fill = form.widgets["fill1"]
    fill.setCurrentIndex(fill.findData("fit"))
    names = [f.name for f in form.shown_fields()]
    assert "spacing1" in names and "total1" in names and "count1" not in names
    panel.reject()


def test_increment_law_and_vary_values_are_written(qtbot: QtBot, window: MainWindow) -> None:
    """TR59 item 1 (D1513)."""
    _open(qtbot, window)
    assert flow.start(window, "feature.linear_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    law = form.widgets["law1"]
    law.setCurrentIndex(law.findData("increment"))
    assert "increment1" in [f.name for f in form.shown_fields()]
    form.widgets["increment1"].edit.setText("2")
    form.widgets["vary"].setText("depth 1")
    made = panel.current_feature()
    assert made is not None and made.params["law1"] == "increment"
    assert made.params["increment1"].value == 2.0 and made.params["vary"] == "depth 1"
    panel.reject()


def test_suppress_region_mode_shows_once_a_region_is_picked(
    qtbot: QtBot, window: MainWindow
) -> None:
    _open(qtbot, window)
    assert flow.start(window, "feature.linear_pattern")
    panel = window.panel
    assert panel is not None and panel.body_form is not None
    form = panel.body_form
    assert "region_mode" not in [f.name for f in form.shown_fields()]
    form.widgets["region"].add({"feature": "f2"}, "Sketch")
    assert "region_mode" in [f.name for f in form.shown_fields()]
    made = panel.current_feature()
    assert made is not None and made.refs["region"] == [{"feature": "f2"}]
    assert made.params["region_mode"] == "inside"
    panel.reject()
