"""Curve through points (TR61, D817)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.point_curve import read_points
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, volume


def _curve(doc, points=None, **kw):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    data = {"points": points} if points is not None else {}
    doc.features.append(
        Feature(
            fid,
            "point_curve",
            "Curve 1",
            params=kw.pop("params", {}),
            refs=kw.pop("refs", {}),
            data=data,
        )
    )
    return fid


def test_a_curve_through_typed_points_is_a_sweep_path() -> None:
    from tests.core.features.test_sweep import add_sweep, square_profile

    doc = new_document()
    profile = square_profile(doc)  # 2 by 4 on the Front plane
    curve = _curve(doc, [[0, 0, 0], [0, 0, 10], [0, 0, 20]])
    fid = add_sweep(doc, profile, curve)
    results = rebuild(doc)
    assert results[curve].state is FeatureState.OK, results[curve].issues
    assert results[curve].extras["curve"] is not None
    assert volume(body(results, fid).shape) == pytest.approx(8 * 20, rel=1e-6)


def test_closed_and_errors() -> None:
    doc = new_document()
    ring = _curve(doc, [[0, 0, 0], [10, 0, 0], [10, 10, 5], [0, 10, 0]], params={"closed": True})
    lonely = _curve(doc, [[0, 0, 0]])
    twice = _curve(doc, [[0, 0, 0], [0, 0, 0], [1, 1, 1]])
    results = rebuild(doc)
    assert results[ring].state is FeatureState.OK
    assert "at least two points" in results[lonely].issues[0].message
    assert "same place" in results[twice].issues[0].message


def test_read_points_skips_headers_and_takes_any_separator() -> None:
    text = "x,y,z\n0,0,0\n1;2;3\n 4 5 6 \nnot,a,point\n7\t8\t9\n"
    assert read_points(text) == [[0, 0, 0], [1, 2, 3], [4, 5, 6], [7, 8, 9]]


def test_picked_vertices() -> None:
    from fdcad.core.naming.select import reference_for
    from tests.core.features.test_features import plate

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    corners = []
    ex = TopExp_Explorer(b.shape, TopAbs_VERTEX)
    while ex.More() and len(corners) < 3:
        ref = reference_for(b, ex.Current())
        if ref is not None and ref not in corners:
            corners.append(ref)
        ex.Next()
    fid = _curve(doc, refs={"points": corners})
    assert rebuild(doc)[fid].state is FeatureState.OK
    assert Param  # keep the import for readers
