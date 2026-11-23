"""3D Sketch panel (TR7, D1719)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, new_document
from fdcad.core.sketch.model import Sketch, sketch_to_data
from tests.ui.test_property_panel import _session


def test_parts_and_lines_from_the_panel(qtbot: QtBot) -> None:
    from fdcad.ui.main_window.new_feature import phase2_feature
    from fdcad.ui.property_panel.forms.sketch3d_form import Sketch3DForm
    from fdcad.ui.property_panel.panel import PropertyPanel

    doc = new_document()
    front = next(f.id for f in doc.features if f.name == "Front Plane")
    s = Sketch()
    s.add_line(0.0, 0.0, 10.0, 0.0)
    doc.features.append(
        Feature(
            doc.new_feature_id(),
            "sketch",
            "Sketch 1",
            refs={"plane": {"feature": front}},
            data=sketch_to_data(s),
        )
    )
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    feature = phase2_feature(doc, "sketch3d", "boss")
    assert feature.name == "3D Sketch 1"
    panel.begin(session, feature, is_new=True)
    form = panel.form
    assert isinstance(form, Sketch3DForm)
    assert panel.current_feature() is None  # nothing in it yet
    assert form.add_part()
    form.points.setPlainText("10 0 0\n10 10 0\n10 10 10")
    form.kind.setCurrentIndex(form.kind.findData("spline"))
    assert form.add_line()
    assert form.line_list.count() == 1 and form.part_list.count() == 1
    made = panel.current_feature()
    assert made is not None
    assert made.data["parts"][0]["plane"] == {"feature": front}
    assert made.data["lines"][0]["kind"] == "spline"
    assert len(made.data["lines"][0]["points"]) == 3
    form.points.setPlainText("1 2 3")
    assert not form.add_line()


def test_relations_from_the_panel(qtbot: QtBot) -> None:
    """TR7 (D2206): Along Z and a 3D Length between line points."""
    from fdcad.ui.main_window.new_feature import phase2_feature
    from fdcad.ui.property_panel.forms.sketch3d_form import Sketch3DForm, _without_line
    from fdcad.ui.property_panel.panel import PropertyPanel

    doc = new_document()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, phase2_feature(doc, "sketch3d", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, Sketch3DForm)
    form.points.setPlainText("0 0 0\n1 1 9")
    assert form.add_line()
    assert form.rel_first.findData("1.2") >= 0
    form.rel_type.setCurrentIndex(form.rel_type.findData("along_z"))
    form.rel_first.setCurrentIndex(form.rel_first.findData("1.1"))
    form.rel_second.setCurrentIndex(form.rel_second.findData("1.2"))
    assert form.add_relation()
    form.rel_type.setCurrentIndex(form.rel_type.findData("length"))
    form.rel_value.setValue(12.0)
    assert form.add_relation()
    form.rel_type.setCurrentIndex(form.rel_type.findData("fixed"))
    assert not form.rel_second.isEnabled()
    assert form.add_relation()
    assert form.relation_list.count() == 3
    made = panel.current_feature()
    assert made is not None
    assert made.data["relations"][1] == {"type": "length", "points": ["1.1", "1.2"], "value": 12.0}
    assert made.data["relations"][2]["at"] == [0.0, 0.0, 0.0]
    form.rel_second.setCurrentIndex(form.rel_second.findData("1.1"))
    form.rel_type.setCurrentIndex(form.rel_type.findData("coincident"))
    assert not form.add_relation()  # the same point twice
    rels = [
        {"type": "along_x", "points": ["1.1", "1.2"]},
        {"type": "along_y", "points": ["2.1", "P1:e2"]},
    ]
    assert _without_line(rels, 1) == [{"type": "along_y", "points": ["1.1", "P1:e2"]}]
