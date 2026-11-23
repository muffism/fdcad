"""Hole Tool: click a point of an existing sketch to skip it (TR143 item 2, D1520)."""

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.features.hole import position_points
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.hole_form import HoleForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import add_sketch, plate
from tests.core.features.test_hole import face_ref
from tests.ui.test_hole_panel import panel, temp_prefs  # noqa: F401
from tests.ui.test_property_panel import _session


def test_skipped_points_get_no_hole() -> None:
    s = Sketch()
    a, b = s.add_point(10, 10), s.add_point(40, 10)
    f = Feature("f9", "hole", "Hole", refs={"sketch": {"feature": "f5"}})
    assert len(position_points(f, s)) == 2
    f.data["skip_points"] = [a]
    assert [p[0] for p in position_points(f, s)] == [b]


def test_a_click_near_a_point_skips_it_and_again_brings_it_back(
    qtbot: QtBot,
    panel: PropertyPanel,  # noqa: F811
) -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    s = Sketch()
    a = s.add_point(10, 10)
    s.add_point(40, 10)
    sk = add_sketch(doc, s, top)
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, "hole", "boss"), is_new=True)
    form = panel.form
    assert isinstance(form, HoleForm)
    form.tabs.setCurrentIndex(1)
    box = form.sketch_boxes["sketch"]
    box.setCurrentIndex(box.findData(sk))
    assert form.count.text().startswith("2")
    report = session.report
    assert report is not None and report.body is not None
    plane = report.results[sk].sketch.plane
    near = plane.to_3d(10.5, 10.0)
    where = (near.X(), near.Y(), near.Z())
    assert form.take_point(report.body, [], where)
    assert form.skip_points == [a] and form.count.text().startswith("1")
    feature = panel.current_feature()
    assert feature is not None and feature.data["skip_points"] == [a]
    assert form.take_point(report.body, [], where)
    assert form.skip_points == [] and form.count.text().startswith("2")
