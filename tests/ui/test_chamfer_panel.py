"""Chamfer panel (PHASE2_SPEC P2.5): types, picks, parameters and lost picks first."""

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.modify import edges_of
from fdcad.core.features.preview import PreviewGeometry
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.chamfer_form import ChamferForm
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _open(qtbot: QtBot, panel: PropertyPanel) -> tuple[DocumentSession, str]:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "chamfer", "boss"), is_new=True)
    return session, ext


def _body(session: DocumentSession):  # type: ignore[no-untyped-def]
    report = session.report
    assert report is not None and report.body is not None
    return report.body


def test_distance_distance_with_edges(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    assert isinstance(panel.form, ChamferForm)
    b = _body(session)
    panel.form.take_shapes(b, edges_of(b.face(f"{ext}/cap/end"))[:2])
    panel.form.method.setCurrentIndex(panel.form.method.findData("asymmetric"))
    panel.form.fields["distance2"].edit.setText("2")
    panel.form.flip.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["chamfer_type"] == "distance_distance"
    assert result.params["method"] == "asymmetric"
    assert result.params["distance"] == Param("1", 1.0)
    assert result.params["distance2"] == Param("2", 2.0)
    assert result.params["flip"] is True
    assert len(result.refs["edges"]) == 2


def test_angle_distance_shows_the_angle(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    form = panel.form
    form.kind.setCurrentIndex(form.kind.findData("angle_distance"))
    assert not form.fields["angle"].parentWidget().isHidden()
    assert form.fields["distance2"].parentWidget().isHidden()
    b = _body(session)
    form.take_shapes(b, [b.face(f"{ext}/cap/end")])
    result = panel.current_feature()
    assert result is not None
    assert result.params["angle"].value == pytest.approx(math.radians(45))
    assert "faces" in result.refs and "method" not in result.params


def test_vertex_type_takes_vertices(qtbot: QtBot, panel: PropertyPanel) -> None:
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    session, ext = _open(qtbot, panel)
    form = panel.form
    form.kind.setCurrentIndex(form.kind.findData("vertex"))
    b = _body(session)
    edge = edges_of(b.face(f"{ext}/cap/end"))[0]
    assert form.take_shapes(b, [edge]) is not None  # an edge is refused
    explorer = TopExp_Explorer(b.shape, TopAbs_VERTEX)
    assert form.take_shapes(b, [explorer.Current()]) is None
    form.equal.setChecked(False)
    result = panel.current_feature()
    assert result is not None
    assert result.params["chamfer_type"] == "vertex"
    assert {"distance", "distance2", "distance3"} <= set(result.params)
    assert len(result.refs["vertices"]) == 1 and "edges" not in result.refs


def test_lost_picks_are_listed_first(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    b = _body(session)
    form = panel.form
    form.take_shapes(b, edges_of(b.face(f"{ext}/cap/end"))[:2])
    second = form.items.names()[1]
    panel.preview_checked(
        PreviewGeometry(None, error="Chamfer 1: 1 picked item(s) were lost", failed=[second])
    )
    assert form.items.names()[0] == second
    assert form.items.list.item(0).text().startswith("Lost:")
