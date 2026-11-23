"""Rebuild overhead fixes from the Phase 6 performance pass (docs/PERFORMANCE_REPORT.md, D432).

1. A rebuild solves the part's equations once, not twice.
2. A feature's cache key is made from that feature only, with the same canonical
   data as the saved file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import fdcad.core.equations.engine as equations
import fdcad.core.io.fdef as fdef_module
from fdcad.core.document.model import Document
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine, to_json_data_feature
from fdcad.samples.graphs import SAMPLE_DIR as GRAPH_SAMPLE_DIR
from fdcad.samples.make import SAMPLE_DIR

SAMPLES = sorted([*SAMPLE_DIR.glob("*.fdprt"), *GRAPH_SAMPLE_DIR.glob("*.fdprt")])


def test_rebuild_solves_equations_once(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = fdef.load(SAMPLE_DIR / "configured_bolt_family.fdprt")
    calls = []
    real = equations.solve

    def counting(d: Document) -> equations.Solution:
        calls.append(1)
        return real(d)

    monkeypatch.setattr(equations, "solve", counting)
    RebuildEngine().rebuild(doc)
    assert len(calls) == 1


def test_bad_variable_is_still_reported_once_solved() -> None:
    doc = fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt")
    doc.variables[0].expr = "=Nope + 1"
    report = RebuildEngine().rebuild(doc)
    assert report.variable_error is not None
    assert "Nope" in report.variable_error


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_feature_key_data_matches_the_file(path: Path) -> None:
    doc = fdef.load(path)
    for feature in doc.features:
        whole = fdef.to_json_data(Document(features=[feature]))["features"][0]
        assert to_json_data_feature(feature) == whole


def test_feature_key_does_not_build_a_document(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt")
    calls = []
    real = fdef_module.to_json_data
    monkeypatch.setattr(fdef_module, "to_json_data", lambda d: calls.append(1) or real(d))
    import fdcad.core.rebuild.engine as engine_module

    monkeypatch.setattr(
        engine_module, "to_json_data", lambda d: calls.append(1) or real(d), raising=False
    )
    RebuildEngine().rebuild(doc)
    assert calls == []
