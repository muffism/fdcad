"""Hole Tool panel slots (PHASE4_SPEC P4.1 item 2, DECISIONS D524)."""

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.features.preview import build_preview
from fdcad.core.rebuild.runner import rebuild
from fdcad.ui.property_panel.forms.hole_form import HoleForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import body, volume
from tests.ui.test_hole_panel import _open, panel, temp_prefs  # noqa: F401


def _type(form: HoleForm, kind: str) -> None:
    box = form.choice_boxes["hole_type"]
    box.setCurrentIndex(box.findData(kind))


def _place(session: object, ext: str, form: HoleForm) -> None:
    report = session.report  # type: ignore[attr-defined]
    assert report is not None and report.body is not None
    form.tabs.setCurrentIndex(1)
    assert form.take_point(report.body, [report.body.face(f"{ext}/cap/end")], (25.0, 25.0, 10.0))
    form.tabs.setCurrentIndex(0)


def test_slot_fields_show_for_the_slot_types_only(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    _s, _ext, form = _open(qtbot, panel)
    assert form.shown("slot") and not form.shown("slot_span")
    form.checks["slot"].setChecked(True)
    assert form.shown("slot_span") and form.shown("slot_span_mode") and form.shown("slot_angle")
    for kind in ("counterbore", "countersink"):
        _type(form, kind)
        assert form.shown("slot") and form.shown("slot_span")
    for kind in ("tapped", "heat_set_insert", "nut_trap", "nut_slot"):
        _type(form, kind)
        assert not form.shown("slot") and not form.shown("slot_span")
    assert form.shown("slot_length")  # the nut slot's own length
    _type(form, "simple")
    assert form.shown("slot_span") and not form.shown("slot_length")


def test_slot_values_reach_the_feature(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    session, ext, form = _open(qtbot, panel)
    _place(session, ext, form)
    feature = panel.current_feature()
    assert feature is not None and "slot" not in feature.params
    form.checks["slot"].setChecked(True)
    form.fields["slot_span"].edit.setText("12")
    feature = panel.current_feature()
    assert feature is not None and feature.params["slot"] is True
    assert feature.params["slot_span"].value == pytest.approx(12.0)
    # Defaults stay out of the file.
    assert "slot_span_mode" not in feature.params and "slot_angle" not in feature.params
    box = form.choice_boxes["slot_span_mode"]
    box.setCurrentIndex(box.findData("overall"))
    form.fields["slot_angle"].edit.setText("45")
    feature = panel.current_feature()
    assert feature is not None and feature.params["slot_span_mode"] == "overall"
    assert feature.params["slot_angle"].value == pytest.approx(math.pi / 4)
    doc = session.document
    geometry = build_preview(doc, feature, session.report.results)  # type: ignore[union-attr]
    assert geometry.error is None and geometry.shape is not None
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    hole = doc.features[-1]
    d = hole.params["diameter"].value
    removed = 25000 - volume(body(rebuild(doc), hole.id).shape)
    r, centres = d / 2, 12.0 - d
    assert removed == pytest.approx((math.pi * r * r + 2 * r * centres) * 10.0, rel=1e-6)


def test_switching_to_tapped_drops_the_slot(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    session, ext, form = _open(qtbot, panel)
    _place(session, ext, form)
    form.checks["slot"].setChecked(True)
    _type(form, "tapped")
    feature = panel.current_feature()
    assert feature is not None
    assert not any(k.startswith("slot") for k in feature.params)
