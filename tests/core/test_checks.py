"""Expected value checks (TR359, D889)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.checks import evaluate
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body
from tests.core.features.test_hole import add_hole, on_top


def test_checks_pass_and_fail() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    hole = add_hole(doc, sk, "simple", top, diameter=5.0, end_condition="through_all")
    shape = body(rebuild(doc), hole).shape
    volume = 25000 - math.pi * 6.25 * 10
    doc.extra["checks"] = [
        {"kind": "volume", "value": volume, "tolerance": 0.01},
        {"kind": "size_x", "value": 50.0, "tolerance": 0.001},
        {"kind": "size_z", "value": 12.0, "tolerance": 0.5},  # wrong on purpose
        {"kind": "holes", "value": 1, "tolerance": 0},
        {"kind": "faces", "value": 7, "tolerance": 0},
        {"kind": "measurement", "value": 1.0, "feature": "f99", "key": "distance"},
        {"kind": "nonsense", "value": 1.0},  # skipped
    ]
    results = evaluate(doc, shape)
    assert [r.kind for r in results] == [
        "volume",
        "size_x",
        "size_z",
        "holes",
        "faces",
        "measurement",
    ]
    assert [r.passed for r in results] == [True, True, False, True, True, False]
    assert results[2].actual == pytest.approx(10.0, abs=1e-6)
    assert results[5].actual is None
