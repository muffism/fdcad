"""Parting Line (TR84, D1415)."""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.curves import edges_in
from fdcad.core.features.parting_line import free_ends, gaps
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import messages, plate

FRONT = "f2"  # normal along Z, the plate's thickness


def _parting(doc: Document, **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "parting_line",
            "Parting Line 1",
            params=params,
            refs={"direction": {"feature": FRONT}},
        )
    )
    return fid


def test_box_gives_one_closed_loop_round_the_walls() -> None:
    doc, _ext = plate()
    fid = _parting(doc)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, messages(res)
    curve = res.extras["curve"]
    assert len(edges_in(curve)) == 4
    assert res.extras["parting_closed"] is True


def test_reverse_moves_the_line_to_the_other_end() -> None:
    from tests.core.features.test_features import bounds

    doc, _ext = plate()
    fid = _parting(doc, reverse=True)
    res = rebuild(doc)[fid]
    assert bounds(res.extras["curve"])[2] == 10.0  # round the top of the walls now


def test_gaps_pair_nearest_ends() -> None:
    ends = [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (10.0, 0.0, 0.0), (10.0, 3.0, 0.0)]
    assert sorted(gaps(ends)) == [1.0, 3.0]
    assert free_ends([]) == []


def test_split_faces_cuts_a_straddle_cylinder_at_its_outline() -> None:
    """TR84 (D1811): a shaft pulled across its axis splits along its outline."""
    from tests.core.features.test_cosmetic_thread import shaft

    doc, ext, eid = shaft(5.0, 20.0)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "parting_line",
            "Parting Line 1",
            params={"split_faces": True},
            refs={"direction": {"feature": "f4"}},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    names = [n for n, _f in res.body.faces]
    assert f"{ext}/side/{eid}#1" in names and f"{ext}/side/{eid}#2" in names
    assert len(edges_in(res.extras["curve"])) >= 2
    # Without the tick the cylinder stays whole and no line is found across it.
    doc.feature(fid).params.pop("split_faces")
    plain = rebuild(doc)[fid]
    assert plain.body is None or f"{ext}/side/{eid}#1" not in [n for n, _f in plain.body.faces]
