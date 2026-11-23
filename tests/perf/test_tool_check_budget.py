"""The point check of each boolean's tool stays cheap on a long tree (D2619).

generated_200 makes 98 cuts on a plate of about 200 faces. The kernel's own point
classifier takes about 2.7 ms just to load on such a body, so the check counts ray
crossings on the few faces a ray can reach instead, and never builds a classifier
when the cut is right. Measured: about 1 ms a cut, 0.1 s over the rebuild.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

import fdcad.core.features.solids as solids_module
import fdcad.core.tool_check as tool_check
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR

MARGIN = 1.5


def test_the_tool_check_on_200_features(monkeypatch: pytest.MonkeyPatch) -> None:
    spent: list[float] = []
    real = tool_check.tools_kept

    def timed(*args: Any) -> bool:
        start = time.perf_counter()
        kept = real(*args)
        spent.append(time.perf_counter() - start)
        assert kept
        return kept

    asked: list[int] = []
    classifier = tool_check.BRepClass3d_SolidClassifier
    monkeypatch.setattr(solids_module, "tools_kept", timed)
    monkeypatch.setattr(
        tool_check, "BRepClass3d_SolidClassifier", lambda *a: asked.append(1) or classifier(*a)
    )
    report = RebuildEngine().rebuild(fdef.load(SAMPLE_DIR / "generated_200.fdprt"))
    assert report.body is not None
    assert len(spent) >= 98
    assert asked == []
    assert sum(spent) < 0.2 * MARGIN
