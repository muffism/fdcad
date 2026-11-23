"""Edges that round on their own but not together are named as such (D2604).

Found by the edit storm on the gearbox: at a draft of 3.03 degrees (3 as built) the
kernel could not round the four boss roots in one call, though each rounded alone.
The fillet named the fourth edge and said the radius was too large for it, which
was not so: it rounds alone. The edges of each wall meet at a corner, so rounding
them in passes would change that corner; the fix buttons (D1405) offer it instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features import fillet
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate
from tests.core.features.test_fillet import add_fillet, top_edges


@pytest.fixture
def one_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """The kernel, as on the gearbox: two edges in one call on the first body fail."""
    real = fillet.round_edges
    first: list[NamedShape] = []

    def flaky(fid: str, b: NamedShape, items: list[Any], *rest: Any) -> NamedShape | None:
        if not first:
            first.append(b)
        if b is first[0] and len(items) > 1:
            return None
        return real(fid, b, items, *rest)

    monkeypatch.setattr(fillet, "round_edges", flaky)


@pytest.mark.usefixtures("one_at_a_time")
def test_an_edge_that_rounds_alone_is_not_blamed_on_its_radius() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in top_edges(b, ext)[:2]]
    fid = add_fillet(doc, 2.0, edges=refs)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    assert "failed on 1 of 2 edges: edge 2 (rounds on its own)" in text
    assert "cannot round them together" in text
    assert "radius is larger" not in text


def test_a_radius_too_large_still_says_so() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in top_edges(b, ext)[:2]]
    fid = add_fillet(doc, 12.0, edges=refs)  # more than the 10 mm plate allows
    text = messages(rebuild(doc)[fid])
    assert "radius is larger" in text and "rounds on its own" not in text


def _corner_edges(b: NamedShape) -> list[Any]:
    """The four upright edges of the 50 by 50 plate, in order round the plate."""
    from fdcad.core.features.fillet_tangent import middle
    from fdcad.core.features.modify import edges_of

    out: list[Any] = []
    for _n, face in b.faces:
        for edge in edges_of(face):
            if abs(middle(edge).Z() - 5) < 1e-6 and not any(edge.IsSame(o) for o in out):
                out.append(edge)
    return out


@pytest.mark.parametrize("radius", [25.0, 30.0])
def test_four_equal_edges_whose_rounds_meet_report_evenly(radius: float) -> None:
    """Audit E item 8 (D2680): at 25 mm the rounds of the plate's four corners meet.
    Only the second and fourth were named, "rounds on its own", with no largest
    radius and no Reduce fix; now all four are named alike with the radius."""
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in _corner_edges(b)]
    fid = add_fillet(doc, radius, edges=refs)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    assert "failed on 4 of 4 edges" in text, text
    words = [f"edge {k} (largest radius 24.4 mm)" for k in range(1, 5)]
    assert all(w in text for w in words), text
    assert "run into each other" in text and "rounds on its own" not in text
    labels = [f.label for i in res.issues for f in i.fixes]
    assert "Reduce the radius to 24.4 mm" in labels, labels
    assert "Fillet the rest (skip 2 edges)" in labels  # two corners still round together
    fixed = add_fillet(doc, 24.4, edges=refs)
    doc.features = [f for f in doc.features if f.id != fid]
    assert rebuild(doc)[fixed].state is FeatureState.OK  # the offered radius builds


@pytest.mark.slow
def test_the_gearbox_boss_roots_at_a_slightly_larger_draft() -> None:
    doc = fdef.load(Path(__file__).parents[3] / "samples" / "gearbox.fdprt")
    doc.solid = {}
    boss = next(f for f in doc.features if f.name == "Output Bearing Boss")
    boss.params["draft_angle"] = Param("3.03", boss.params["draft_angle"].value * 1.01)
    roots = next(f for f in doc.features if f.name == "Boss Roots")
    result = RebuildEngine().rebuild(doc).results[roots.id]
    issue = next(i for i in result.issues if i.state is FeatureState.ERROR)
    # Edges 3 and 4, the roots of the two mirrored bosses, fail as a pair from about
    # 1.86 mm up at this draft, so both are named with that radius (D2680); the fix that
    # keeps the radius is still offered.
    assert "edge 3 (largest radius 1.82 mm), edge 4 (largest radius 1.82 mm)" in issue.message
    labels = [f.label for f in issue.fixes]
    assert "Fillet each chain as its own feature (2 fillets)" in labels, labels
    assert "Reduce the radius to 1.82 mm" in labels
