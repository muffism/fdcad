"""The fit calibration plate (TR358, D2000)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.printing.calibration import calibration_part, gaps
from fdcad.core.rebuild.engine import RebuildEngine


def test_gaps_step_and_limits() -> None:
    assert gaps(0.1, 0.05, 4) == [0.1, 0.15, 0.2, 0.25]
    for bad in ((0.1, 0.0, 3), (-0.1, 0.05, 3), (0.1, 0.05, 11)):
        with pytest.raises(ValueError):
            gaps(*bad)


def test_the_plate_builds_with_labels_and_variables() -> None:
    doc = calibration_part(0.1, 0.05, 4)
    report = RebuildEngine().rebuild(doc)
    assert all(r.state is not FeatureState.ERROR for r in report.results.values())
    assert [v.name for v in doc.variables] == ["Pin", "Gap1", "Gap2", "Gap3", "Gap4"]
    labels = next(f for f in doc.features if f.name == "Label Sketch")
    assert [t["text"] for t in labels.data["texts"]] == ["0.1", "0.15", "0.2", "0.25"]
