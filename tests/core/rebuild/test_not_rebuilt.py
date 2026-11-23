"""Features after a failure are marked not rebuilt (TR352, D881)."""

from __future__ import annotations

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.engine import NOT_REBUILT, RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def test_later_solid_features_are_marked_and_the_report_names_the_failure() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    first = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    bad = add_extrude(doc, add_sketch(doc, Sketch(), {"feature": "f2"}), 5.0)  # empty sketch
    t = Sketch()
    rect(t, 20, 0, 30, 10)
    later = add_extrude(doc, add_sketch(doc, t, {"feature": "f2"}), 5.0)
    report = RebuildEngine().rebuild(doc)
    assert report.results[bad].state is FeatureState.ERROR
    assert report.failed_at == bad
    assert report.results[first].state is FeatureState.OK
    later_result = report.results[later]
    assert later_result.state is FeatureState.WARNING
    assert any(i.code == NOT_REBUILT for i in later_result.issues)
    # Fixed: nothing is marked any more.
    doc.feature(bad).params["depth"] = Param("5", 5.0)
    doc.features = [f for f in doc.features if f.id != bad]
    report = RebuildEngine().rebuild(doc)
    assert report.failed_at is None
    assert not any(i.code == NOT_REBUILT for i in report.results[later].issues)
