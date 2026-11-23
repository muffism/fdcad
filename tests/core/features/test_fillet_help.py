"""Fillet failure help: other ways as fix buttons (TR346, D1405)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features import fillet as fillet_module
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fillet_help import ACTION, split_fillet
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, volume
from tests.core.features.test_fillet import _plate_and_refs, add_fillet


@pytest.fixture
def at_most_two(monkeypatch: pytest.MonkeyPatch) -> None:
    """The kernel 'fails' on more than two edges at once, so groups are needed."""
    real = fillet_module.round_edges

    def limited(fid: str, body: Any, items: list[Any], law_of: Any) -> Any:
        return None if len(items) > 2 else real(fid, body, items, law_of)

    monkeypatch.setattr(fillet_module, "round_edges", limited)


def test_ways_that_build_are_offered(at_most_two: None) -> None:
    doc, _ext, _b, refs = _plate_and_refs(4)
    fid = add_fillet(doc, 1.0, edges=refs)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    fixes = [f for i in res.issues for f in i.fixes if f.action == ACTION]
    labels = [f.label for f in fixes]
    assert "Fillet in 2 smaller groups" in labels
    assert "One fillet per edge (4 fillets)" in labels  # 4 steps of one edge build too
    groups = fixes[0].data["groups"]
    assert sorted(n for g in groups for n in g) == sorted(str(r["name"]) for r in refs)


def test_split_makes_new_fillets_that_rebuild() -> None:
    doc, _ext, _b, refs = _plate_and_refs(3)
    fid = add_fillet(doc, 1.0, edges=refs)
    f = doc.feature(fid)
    f.params["multiple_radius"] = True
    f.params["radius_3"] = Param("2", 2.0)
    whole = volume(body(rebuild(doc), fid).shape)
    names = [str(r["name"]) for r in refs]
    made = split_fillet(doc, fid, [[names[0], names[1]], [names[2]]])
    assert made[0].id == fid and made[1].id != fid and made[1].name != f.name
    assert made[1].params["radius_1"].value == 2.0 and "radius_3" not in made[0].params
    doc.features[-1] = made[0]
    doc.features.append(made[1])
    res = rebuild(doc)
    assert res[made[0].id].state is not FeatureState.ERROR
    # Rounded one after the other, the corner where they meet differs a little.
    assert volume(body(res, made[1].id).shape) == pytest.approx(whole, rel=1e-3)
