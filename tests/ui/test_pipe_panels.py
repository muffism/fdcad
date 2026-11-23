"""Pipe, array along curve and contour panels, and the curvature graph overlay
(PHASE3_SPEC P3.7): the panels write their values, OK adds one undoable feature,
and the graph shows combs in a background job without changing the part."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.pipe_forms import ContourForm, CurveArrayForm, PipeForm
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from tests.core.features.test_curves import FRONT
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect
from tests.ui.test_phase2_flow import _folders, window
from tests.ui.test_property_panel import _session

__all__ = ["_folders", "window"]


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _line(doc: object, x1: float = 100.0) -> str:
    s = Sketch()
    s.add_line(0, 0, x1, 0)
    return add_sketch(doc, s, FRONT)  # type: ignore[arg-type]


def test_pipe_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    path = _line(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "pipe", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, PipeForm)
    assert panel.title.text() == "Pipe 1"
    assert panel.current_feature() is None  # no path yet
    form.path.setCurrentIndex(form.path.findData(path))
    form.fields["outer_diameter"].edit.setText("12")
    assert form.cap.isHidden()
    form.hollow.setChecked(True)
    assert not form.cap.isHidden()
    form.fields["inner_diameter"].edit.setText("8")
    form.cap.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.refs == {"path": {"feature": path}}
    assert result.params["outer_diameter"].value == pytest.approx(12.0)
    assert result.params["inner_diameter"].value == pytest.approx(8.0)
    assert result.params["cap_ends"] is True
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    report = session.report
    assert report is not None
    assert report.results[doc.features[-1].id].state is FeatureState.OK


def test_curve_array_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    s = Sketch()
    rect(s, -2, -2, 2, 2)
    block = add_extrude(doc, add_sketch(doc, s, FRONT), 4.0)
    path = _line(doc)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "curve_array", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, CurveArrayForm)
    form.path.setCurrentIndex(form.path.findData(path))
    assert panel.current_feature() is None  # nothing to copy yet
    form._add_choice(form.choice.findData(block))
    form.mode.setCurrentIndex(form.mode.findData("spacing"))
    form.fields["count"].edit.setText("3")
    form.fields["spacing"].edit.setText("20")
    form.orient.setChecked(False)
    form.skip.setText("2")
    result = panel.current_feature()
    assert result is not None
    assert result.refs["features"] == [{"feature": block}]
    assert result.params["mode"] == "spacing"
    assert result.params["count"].value == pytest.approx(3.0)
    assert result.params["orient"] is False
    assert result.params["skip"] == "2"
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert all(f.type != "curve_array" for f in doc.features)


def test_contour_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc, _ext = plate(10.0)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "contour", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, ContourForm)
    assert panel.current_feature() is None
    # the empty list's prompt is short, so it never widens the panel past its edge
    # measured in characters: the offscreen font on Windows is about twice as wide
    budget = form.direction.fontMetrics().horizontalAdvance("n" * 34) + 60
    assert form.direction.sizeHint().width() <= budget
    form.direction.setCurrentIndex(form.direction.findData({"feature": "f2"}))
    form.fields["spacing"].edit.setText("2.5")
    result = panel.current_feature()
    assert result is not None
    assert result.refs["direction"] == {"feature": "f2"}
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    report = session.report
    assert report is not None
    assert report.results[doc.features[-1].id].extras["levels"] == [2.5, 5.0, 7.5]


def test_curvature_graph_shows_combs_on_curves(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 10)
    sk = add_sketch(doc, s, FRONT)
    from tests.core.features.test_curves import P, add

    add(doc, "helix", {"sketch": {"feature": sk}}, definition="pitch_turns",
        pitch=P(5), turns=P(2))  # fmt: skip
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    assert isinstance(tab, DocumentTab)
    graph = window.curvature_graph
    action = window.commands.actions["evaluate.curvature_graph"]
    assert action.isCheckable()
    before = len(doc.features)
    action.trigger()
    assert graph.on and not graph.panel.isHidden()
    qtbot.waitUntil(lambda: "Curvature graph shown for 1 edge" in window.status.text())
    assert getattr(graph, "last_shape", None) is not None
    graph.density.setValue(80)
    qtbot.waitUntil(lambda: graph.last_shape is not None)
    action.trigger()
    assert not graph.on and graph.panel.isHidden()
    assert len(doc.features) == before and not session.undo.canUndo()


def test_new_commands_have_tooltips() -> None:
    from fdcad.ui import strings, strings_import

    del strings_import
    for cid in ("feature.pipe", "feature.curve_array", "feature.contour",
                "evaluate.curvature_graph"):  # fmt: skip
        assert strings.TOOLTIP_TEXT[cid]
