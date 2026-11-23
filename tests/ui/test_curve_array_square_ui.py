"""Array Along Curve panel: Square to face (TR373, D1017)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.ui import strings
from tests.ui.test_property_panel import _session


def test_square_to_face_needs_a_face_and_writes_it(qtbot: QtBot) -> None:
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
    form.square_on.setChecked(True)
    feature = Feature("f99", "curve_array", "Array", params={})
    assert form.apply(feature) == strings.ARRAY_SQUARE_NEEDS_FACE
    face = {"kind": "face", "name": "face(a|b)"}
    form.square.set_refs([face])
    assert form.apply(feature) is None
    assert feature.refs["square_face"] == [face]
    assert not form.orient.isEnabled()
