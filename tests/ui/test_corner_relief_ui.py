"""Corner Relief panel and command (TR244, D785)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_corner_relief import _pocket
from tests.ui.test_fastening_panels import panel
from tests.ui.test_property_panel import _session

__all__ = ["panel"]


def test_command_icon_and_tab() -> None:
    from fdcad.ui.command_tabs.tabs import FEATURE_GROUPS
    from fdcad.ui.icons.audit import audit

    assert BY_ID["feature.corner_relief"].label == "Corner Relief"
    assert BY_ID["feature.corner_relief"].keys == () and audit("feature.corner_relief") == []
    flat = repr(FEATURE_GROUPS)
    assert "feature.corner_relief" in flat


def test_relief_panel_on_all_corners_of_a_cut(qtbot: QtBot, panel: PropertyPanel) -> None:
    from fdcad.ui.property_panel.forms.shape_forms import CornerReliefForm

    doc, cut = _pocket()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "corner_relief", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, CornerReliefForm)
    assert not form.shown("flip")
    kind = form.choice_boxes["relief_type"]
    kind.setCurrentIndex(kind.findData("t_bone"))
    assert form.shown("flip")
    box = form.sketch_boxes["feature"]
    box.setCurrentIndex(box.findData(cut))
    feature = panel.current_feature()
    assert feature is not None
    assert feature.params["relief_type"] == "t_bone"
    assert feature.refs["feature"] == {"feature": cut}
    assert feature.params["tool_diameter"].value == pytest.approx(6.0)
