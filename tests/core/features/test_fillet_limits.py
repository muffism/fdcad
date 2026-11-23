"""Fillet limits: edges to keep and a limiting plane (TR271, D1407)."""

from __future__ import annotations

from typing import Any

import pytest
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fillet_limits import largest_keeping
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, bounds, messages, volume
from tests.core.features.test_fillet_faces import PLATE, _plate_edge, add_fillet, strip
from tests.core.features.test_reference_geometry import _add

RIGHT = "f4"


def _limited(flip: bool, at: float = 30.0) -> tuple[Any, str, dict[str, Any]]:
    doc, _ext, edge = _plate_edge(0.0)
    plane = _add(doc, "ref_plane", {"first": {"feature": RIGHT}}, method="offset", distance=at)
    params: dict[str, Any] = {"fillet_type": "constant", "radius": Param("2", 2.0)}
    if flip:
        params["limit_flip"] = True
    fid = add_fillet(doc, params, edges=[edge], limit_plane={"feature": plane})
    return doc, fid, edge


@pytest.mark.parametrize(("flip", "span"), [(False, 30.0), (True, 20.0)])
def test_rounds_stop_at_the_plane(flip: bool, span: float) -> None:
    doc, fid, edge = _limited(flip)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(PLATE - strip(2) * span, rel=1e-6)
    made = res.body.face(f"{fid}/fillet/{edge['name']}")
    assert made is not None
    assert (bounds(made)[3] if not flip else bounds(made)[0]) == pytest.approx(30.0, abs=1e-6)


def test_an_edge_wholly_in_front_is_an_error() -> None:
    doc, fid, _edge = _limited(False, at=-5.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "in front of the limiting plane" in messages(res)


def test_a_swallowed_kept_edge_is_named() -> None:
    doc, _ext, edge = _plate_edge(0.0)
    fid = add_fillet(
        doc, {"fillet_type": "constant", "radius": Param("2", 2.0)}, edges=[edge], keep_edges=[edge]
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "swallows 1 edge to keep" in messages(res)


def test_a_kept_edge_that_stays_is_fine() -> None:
    doc, _ext, edge = _plate_edge(0.0)
    _doc2, _ext2, back = _plate_edge(50.0)
    fid = add_fillet(
        doc, {"fillet_type": "constant", "radius": Param("2", 2.0)}, edges=[edge], keep_edges=[back]
    )
    assert rebuild(doc)[fid].state is not FeatureState.ERROR


def test_largest_keeping_halves_towards_the_limit() -> None:
    from fdcad.core.features.fillet_tangent import middle
    from fdcad.core.features.modify import edges_of
    from fdcad.core.naming.names import NamedShape
    from tests.core.features.test_features import plate

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    point = middle(edges_of(b.shape)[0])

    def build(r: float) -> NamedShape | None:
        return b if r < 3.0 else None

    found = largest_keeping(build, [("e", point)], 8.0)
    assert found is not None and 2.9 < found < 3.0
    assert largest_keeping(build, [("e", gp_Pnt(1e3, 1e3, 1e3))], 8.0) is None
