"""Mould Cavity (TR85 item 1, D2111)."""

from __future__ import annotations

import pytest
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect

BLOCK = 50 * 50 * 10


def _doc():  # type: ignore[no-untyped-def]
    """A 50 x 50 x 10 block and a 10 x 10 x 4 part inside it, kept separate."""
    doc, _ext = plate()
    s = Sketch()
    rect(s, 20, 20, 30, 30)
    sk = add_sketch(doc, s, {"feature": "f2"})
    part = add_extrude(doc, sk, 4.0, merge=False)
    report = RebuildEngine().rebuild(doc)
    pieces = solids(report.body.shape)
    big = max(range(len(pieces)), key=lambda i: volume_of(pieces[i]))
    refs = [reference_for(report.body, TopExp_Explorer(p, TopAbs_FACE).Current()) for p in pieces]
    return doc, refs[big], refs[1 - big], part


def _cavity(doc, block, part, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "mould_cavity", "Mould Cavity 1", params=params,
                refs={"main": block, "part": part})
    )  # fmt: skip
    report = RebuildEngine().rebuild(doc)
    return report, report.results[fid]


def test_cavity_is_cut_with_shrinkage_and_the_part_kept() -> None:
    doc, block, part, _p = _doc()
    report, result = _cavity(doc, block, part, factor=Param("1.1", 1.1))
    assert result.state is not FeatureState.ERROR
    pieces = sorted(volume_of(s) for s in solids(report.body.shape))
    scaled = 11 * 11 * 4.2  # the part grows below the block bottom, so 4.2 of 4.4 is inside
    assert pieces[1] == pytest.approx(BLOCK - scaled, rel=1e-6)
    assert pieces[0] == pytest.approx(400)


def test_per_axis_scale_and_part_removed() -> None:
    doc, block, part, _p = _doc()
    params = {"uniform": False, "keep_part": False}
    params.update({k: Param(v, float(v)) for k, v in (("fx", "1"), ("fy", "1"), ("fz", "1.5"))})
    report, _result = _cavity(doc, block, part, **params)
    pieces = solids(report.body.shape)
    assert len(pieces) == 1
    assert volume_of(pieces[0]) == pytest.approx(BLOCK - 500, rel=1e-6)


def test_bad_picks_and_scales_are_refused() -> None:
    doc, block, part, _p = _doc()
    _report, result = _cavity(doc, block, block)
    assert result.state is FeatureState.ERROR and "one body" in result.issues[0].message
    doc.features.pop()
    _report, result = _cavity(doc, block, part, factor=Param("5", 5.0))
    assert result.state is FeatureState.ERROR and "out of range" in result.issues[0].message
