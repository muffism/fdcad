"""Link to thickness on bosses in sheet metal parts (TR165, D1100)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Sketch
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.sheetmetal.parts import plate, sheet_doc
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.ui.test_property_panel import _session


@pytest.mark.parametrize("operation", ["boss", "cut"])
def test_link_to_thickness_is_offered_for_bosses_and_cuts(qtbot: QtBot, operation: str) -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"feature": "f1"})
    fid = add_extrude(doc, sk, 5.0, operation=operation)
    doc.feature(fid).params["link_thickness"] = True
    doc.feature(fid).params["depth"] = Param("5", 5.0)
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, session.document.feature(fid), is_new=False)
    link = panel.flags["link_thickness"]
    assert link.isChecked()
    link.setChecked(False)
    result = panel.current_feature()
    assert result is not None and "link_thickness" not in result.params


def test_edge_flange_panel_keeps_the_profile_sketch(qtbot: QtBot) -> None:
    """TR166 item 1 (D1101): the profile sketch pick is stored under its own ref."""
    from tests.core.features.sheetmetal.test_flange_profile import _flange, _rect

    doc, fid = _flange(_rect(20, 0, 60, 30))
    want = doc.feature(fid).refs["profile_sketch"]
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, session.document.feature(fid), is_new=False)
    result = panel.current_feature()
    assert result is not None and result.refs["profile_sketch"] == want
    assert "sketch" not in result.refs
