"""Normal cut in sheet metal parts (TR12.2, D700)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.model import SheetResult
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch, sketch_to_data
from fdcad.samples.make import SAMPLE_DIR, measure


def _bracket() -> Document:
    return fdef.loads((SAMPLE_DIR / "sheet_metal_bracket.fdprt").read_text(encoding="utf-8"))


def _volume(doc: Document) -> float:
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    return float(measure(report.body.shape)["volume"])


def _side_cut(doc: Document, normal: bool | None) -> str:
    """A round cut from the Right Plane, along X, through the base flange's edge on its
    side: plain, its faces lean to the sheet; square, they stand straight."""
    sk = Sketch()
    sk.add_circle(-1, 20, 3)  # world y = 20, z = 1: across the 2 mm base sheet
    sketch = Feature(
        doc.new_feature_id(),
        "sketch",
        "Side Sketch",
        refs={"plane": {"feature": "f4"}},
        data=sketch_to_data(sk),
    )
    params: dict[str, object] = {
        "operation": "cut",
        "end_condition": "through_all_both",
        "depth": Param("1", 1.0),
        "reverse": False,
    }
    if normal is not None:
        params["normal_cut"] = normal
    cut = Feature(
        doc.new_feature_id(),
        "extrude",
        "Cut 1",
        params=params,
        refs={"sketch": {"feature": sketch.id}},  # type: ignore[arg-type]
    )
    doc.features[-1:-1] = [sketch, cut]
    return cut.id


def test_square_cut_differs_from_the_plain_cut_and_keeps_the_sheet_model() -> None:
    base = _volume(_bracket())
    square, plain = _bracket(), _bracket()
    fid = _side_cut(square, None)  # on by default in sheet metal
    _side_cut(plain, False)
    report = RebuildEngine().rebuild(square)
    result = report.results[fid]
    assert result.state is not FeatureState.ERROR, [i.message for i in result.issues]
    assert isinstance(result, SheetResult) and result.sheet is not None
    removed_square = base - _volume(square)
    removed_plain = base - _volume(plain)
    assert removed_square > 1.0 and removed_plain > 1.0
    assert removed_square != pytest.approx(removed_plain, rel=1e-3)


def test_square_cut_shows_in_the_flat_pattern() -> None:
    def flat(doc: Document) -> float:
        doc.features[-1].params["flattened"] = True
        return _volume(doc)

    plain_flat = flat(_bracket())
    square = _bracket()
    _side_cut(square, None)
    assert flat(square) < plain_flat - 1.0
    assert math.isfinite(plain_flat)


def test_cuts_outside_sheet_metal_are_unchanged() -> None:
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    before = _volume(doc)
    doc.feature("f8").params["normal_cut"] = True
    assert _volume(doc) == pytest.approx(before)
