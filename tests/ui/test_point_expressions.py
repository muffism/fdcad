"""Fill Points from x(t), y(t), z(t) in Curve Through Points (TR374, D1011)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from tests.ui.test_property_panel import _session


def test_fill_points_from_expressions(qtbot: QtBot) -> None:
    from fdcad.core.document.model import new_document
    from fdcad.ui.main_window.new_feature import phase2_feature
    from fdcad.ui.property_panel.forms.point_curve_form import PointCurveForm
    from fdcad.ui.property_panel.panel import PropertyPanel

    doc = new_document()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, phase2_feature(doc, "point_curve", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, PointCurveForm)
    form.t_to.setText(str(math.pi))
    form.t_count.setValue(3)
    assert form.fill_from_expressions() and form.table.rowCount() == 3
    made = panel.current_feature()
    assert made is not None
    assert made.data["points"][1] == pytest.approx([0.0, 10.0, math.pi])
    assert made.data["equation"]["x"] == "10*cos(t)" and made.data["equation"]["count"] == 3
    form.t_from.setText("nope")
    assert not form.fill_from_expressions()
    assert form.table.rowCount() == 3  # the table is kept
