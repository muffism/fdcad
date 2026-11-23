"""Sketch, Pierce (TR101, D843)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, new_document
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools import pierce as pc
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_pierce_and_remove(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = new_document()
    doc.features.append(
        Feature("f9", "point_curve", "Curve 1", data={"points": [[0, 0, -1], [0, 0, 1]]})
    )
    s = Sketch()
    pid = s.add_point(1.0, 2.0)
    edit = edit_of(s)
    edit.feature.id = "f10"
    doc.features.append(edit.feature)
    canvas = SketchCanvas(edit, UnitSystem.MM)
    qtbot.addWidget(canvas)
    assert pc.curves_before(doc, "f10") == [("f9", "Curve 1")]
    monkeypatch.setattr(pc, "ask", lambda *_a: "Curve 1")
    assert pc.pierce(canvas, pid, doc)
    assert pc.pierced(canvas, pid)
    assert canvas.edit.to_feature().refs["pierce"] == [{"point": pid, "curve": {"feature": "f9"}}]
    assert any(r.type == "fixed" for r in canvas.edit.sketch.relations)
    pc.unpierce(canvas, pid)
    assert not pc.pierced(canvas, pid) and "pierce" not in canvas.edit.feature.refs
    assert not any(r.type == "fixed" for r in canvas.edit.sketch.relations)
