"""Change test (TR287, D774)."""

from __future__ import annotations

import copy

import pytest

from fdcad.core.change_test import run, values_of
from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from fdcad.samples.make import SAMPLE_DIR


def _plate():  # type: ignore[no-untyped-def]
    return fdef.load(SAMPLE_DIR / f"plate_with_holes{fdef.PART_SUFFIX}")


def test_values_are_the_plain_typed_ones() -> None:
    doc = _plate()
    labels = [v.label for v in values_of(doc)]
    assert labels and all("@" in label or "@" not in label for label in labels)
    assert not any(v.value <= 0 for v in values_of(doc))


def test_nothing_in_the_part_changes_and_a_safe_value_has_both_ranges() -> None:
    doc = _plate()
    before = fdef.dumps(doc)
    test = run(doc, percent=5, steps=1, values=values_of(doc)[:3])
    assert fdef.dumps(doc) == before
    assert len(test.results) == 3
    for r in test.results:
        if r.safe:
            assert r.down == 1 and r.up == 1


def test_a_value_that_breaks_the_part_is_found() -> None:
    """A fillet just under the largest it can be fails when the radius grows."""
    from fdcad.core.document.model import Feature, new_document
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 20, 20)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 4.0)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "fillet",
            "Fillet 1",
            params={"fillet_type": "constant", "radius": Param("3.9", 3.9)},
            refs={"faces": [{"kind": "face", "name": f"{ext}/cap/end"}]},
        )
    )
    values = [v for v in values_of(doc) if v.key == "radius"]
    test = run(doc, percent=10, steps=2, values=values)
    (result,) = test.results
    assert not result.safe and result.up == 0 and "up" in result.problem
    assert result.down >= 1


def test_stop_and_bad_step() -> None:
    doc = _plate()
    stopped = run(doc, percent=5, steps=1, cancelled=lambda: True)
    assert stopped.stopped and stopped.results == []
    with pytest.raises(ValueError, match="between 0 and 100"):
        run(copy.deepcopy(doc), percent=0)
