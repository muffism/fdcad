"""A value the part file cannot keep fails its feature, not the rebuild (D2671).

A nan or an infinite number in a feature that builds made ``rebuild()`` raise
"Cannot save the value nan" from the feature's cache key, so nothing was shown and
the app had no feature to point at (CLAUDE.md section 5 item 7). The feature now
fails with a message that names the value, and the features below carry on as they
do after any failed feature.
"""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.engine import NOT_REBUILT, RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, messages, rect


def _part() -> tuple[Document, str, str, str]:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 5)
    sketch = add_sketch(doc, s, {"feature": "f2"})
    first = add_extrude(doc, sketch, 4.0)
    s2 = Sketch()
    rect(s2, 2, 2, 3, 3)
    second = add_extrude(doc, add_sketch(doc, s2, {"feature": "f2"}), 8.0)
    s3 = Sketch()
    rect(s3, 6, 1, 3, 3)
    third = add_extrude(doc, add_sketch(doc, s3, {"feature": "f2"}), 6.0)
    return doc, first, second, third


@pytest.mark.parametrize(
    ("where", "value", "said"),
    [
        ("data", math.nan, "not a number"),
        ("data", math.inf, "too large"),
        ("list", math.nan, "not a number"),
    ],
)
def test_the_feature_fails_and_the_rest_of_the_part_builds(
    where: str, value: float, said: str
) -> None:
    doc, first, second, third = _part()
    if where == "data":
        doc.feature(second).data["kept"] = value
    else:
        doc.feature(second).params["width"] = [value, 2.0]
    report = RebuildEngine().rebuild(doc)
    failed = report.results[second]
    assert failed.state is FeatureState.ERROR
    text = messages(failed)
    name = doc.feature(second).name
    assert text.startswith(f"{name} failed:") and said in text, text
    assert ("kept" if where == "data" else "width") in text, text
    assert body(report.results, first).shape is not None
    # The feature below builds on the part from before the failed one, as after any
    # failed feature (TR352).
    below = report.results[third]
    assert below.state is FeatureState.WARNING and below.body is not None
    assert any(i.code == NOT_REBUILT for i in below.issues)
    assert report.failed_at == second


@pytest.mark.parametrize("value", [math.nan, math.inf])
def test_a_measured_value_that_is_not_a_finite_number_is_not_kept(value: float) -> None:
    """A Sensor or a Bounding Box that measures nan or inf must not hand it to the
    formulas that read it: min(3, nan) is 3 but min(nan, 3) is nan."""
    from fdcad.core.features.base import FeatureResult
    from fdcad.core.rebuild.engine import _store_measured

    doc = new_document()
    sensor = doc.features[-1]
    sensor.type = "sensor"
    assert _store_measured(doc, sensor, FeatureResult(body=None, extras={"value": 2.0}))
    assert not _store_measured(doc, sensor, FeatureResult(body=None, extras={"value": value}))
    assert doc.measured[sensor.id] == {"value": 2.0}


def test_the_feature_builds_again_once_the_value_is_fixed() -> None:
    doc, _first, second, third = _part()
    engine = RebuildEngine()
    doc.feature(second).data["kept"] = math.nan
    engine.rebuild(doc)
    del doc.feature(second).data["kept"]
    report = engine.rebuild(doc)
    assert report.results[second].state is FeatureState.OK
    assert report.results[third].state is FeatureState.OK
