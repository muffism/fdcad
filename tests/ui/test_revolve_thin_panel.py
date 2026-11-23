"""Thin Feature group on the Revolve panel (TOOL_SPEC T6.1 item 5, DECISIONS D523)."""

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.preview import build_preview
from fdcad.core.rebuild.runner import rebuild
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import body, shaft, volume
from tests.core.features.test_revolve_thin import add_revolve, lines
from tests.ui.test_property_panel import _new_from_last, _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def test_thin_group_shows_for_revolve_and_writes_its_values(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    doc, rev = shaft(360)
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(rev), is_new=False)
    thin = panel.groups["thin"]
    assert not thin.isHidden() and not thin.is_checked()
    assert panel.thin is not None
    result = panel.current_feature()
    assert result is not None and not any(k.startswith("thin_") for k in result.params)
    thin.set_checked(True)
    panel.values["thin_thickness"].edit.setText("1")
    assert panel.values["thin_thickness2"].parentWidget().isHidden()
    panel.thin.cap.setChecked(True)
    assert not panel.values["thin_cap_thickness"].parentWidget().isHidden()
    result = panel.current_feature()
    assert result is not None
    assert result.params["thin_type"] == "one_direction"
    assert result.params["thin_thickness"] == Param("1", 1.0)
    assert result.params["thin_cap"] is True
    thin.set_checked(False)
    result = panel.current_feature()
    assert result is not None and not any(k.startswith("thin_") for k in result.params)


def test_open_profile_revolve_from_the_panel(qtbot: QtBot, panel: PropertyPanel) -> None:
    doc = new_document()
    s, axis = lines([(0, 0), (10, 0), (10, 20)])
    add_revolve(doc, s, axis)  # without Thin Feature the open profile fails
    session = _session(qtbot, doc)
    feature = _new_from_last(session)
    panel.begin(session, feature, is_new=True)
    assert panel.axis_box.currentData() == axis
    panel.groups["thin"].set_checked(True)
    assert panel.thin is not None
    panel.thin.kind.setCurrentIndex(panel.thin.kind.findData("mid_plane"))
    panel.values["thin_thickness"].edit.setText("2")
    result = panel.current_feature()
    assert result is not None and result.params["thin_type"] == "mid_plane"
    report = session.report
    assert report is not None
    geometry = build_preview(session.document, result, report.results)
    assert geometry.error is None and geometry.shape is not None
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    done = session.document.features[-1]
    # Mid plane: a 2 mm wall centred on the L (sharp outer corner), ending on the axis.
    expected = math.pi * (11**2 * 2 + (11**2 - 9**2) * 19)
    v = volume(body(rebuild(session.document), done.id).shape)
    assert v == pytest.approx(expected, rel=1e-6)
