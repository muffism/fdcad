"""Result line after each command (TR290, D878)."""

from __future__ import annotations

import pytest

from fdcad.core.rebuild.change_line import describe
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def test_the_new_feature_is_described() -> None:
    from fdcad.core.document.model import new_document

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    engine = RebuildEngine()
    first = engine.rebuild(doc)
    assert describe(doc, first) is None  # a full build says nothing
    b = Sketch()
    rect(b, 2, 2, 4, 4)
    add_extrude(doc, add_sketch(doc, b, {"feature": "f2"}), 5.0)
    second = engine.rebuild(doc)
    change = describe(doc, second)
    assert change is not None
    assert change.added == pytest.approx(0.0, abs=1e-6)  # inside: no new material
    c = Sketch()
    rect(c, 20, 0, 30, 10)
    fid = add_extrude(doc, add_sketch(doc, c, {"feature": "f2"}), 2.0)
    change = describe(doc, engine.rebuild(doc))
    assert change is not None and change.name == doc.feature(fid).name
    assert change.added == pytest.approx(200.0) and change.faces == 6


def test_a_failed_feature_is_marked_failed() -> None:
    """D1041: a feature that fails keeps the body before it; that is not "no change"."""
    from fdcad.core.features.base import FeatureState
    from fdcad.core.naming.select import reference_for
    from tests.core.features.test_features import body, plate
    from tests.core.features.test_fillet import add_fillet, top_edges

    doc, ext = plate()
    engine = RebuildEngine()
    b = body(engine.rebuild(doc).results, ext)
    fid = add_fillet(doc, 60.0, edges=[reference_for(b, top_edges(b, ext)[0])])  # far too large
    report = engine.rebuild(doc)
    assert report.results[fid].state is FeatureState.ERROR
    change = describe(doc, report)
    assert change is not None and change.failed and change.name == doc.feature(fid).name
    doc.feature(fid).params["radius"].value = 2.0
    doc.feature(fid).params["radius"].expr = "2"
    change = describe(doc, engine.rebuild(doc))
    assert change is not None and not change.failed and change.removed > 0
