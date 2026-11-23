"""Fillet methods and profiles (TR62, D1402)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.modify import edges_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_fillet_faces import PLATE, _plate_edge, add_fillet, rib_part, strip


def _p(**values: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"fillet_type": "constant"}
    for key, value in values.items():
        out[key] = Param(f"{value:g}", float(value)) if isinstance(value, int | float) else value
    return out


@pytest.mark.parametrize(
    ("params", "removed"),
    [
        # A quarter ellipse with semi axes 2 and 4 on a square corner.
        (_p(radius=2, method="asymmetric", distance2=4, profile="elliptic"), 8 * (1 - math.pi / 4)),
        # Circular on asymmetric is the same ellipse.
        (_p(radius=2, method="asymmetric", distance2=4), 8 * (1 - math.pi / 4)),
        # A parabola (shape 0.5) from 2 mm to 2 mm: a third of the corner triangle stays cut.
        (_p(radius=2, profile="conic", rho=0.5), 2 / 3),
        # Chord 2 x sqrt 2 on a square corner is a 2 mm circle (kernel path).
        (_p(radius=2 * math.sqrt(2), method="chord"), strip(2)),
        # Circular through the conic route gives the circle exactly.
        (_p(radius=2, profile="conic", rho=math.sqrt(0.5) / (1 + math.sqrt(0.5))), strip(2)),
    ],
)
def test_profile_volumes(params: dict[str, Any], removed: float) -> None:
    doc, _ext, edge = _plate_edge(0.0)
    fid = add_fillet(doc, params, edges=[edge])
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(PLATE - removed * 50, rel=1e-5)
    assert res.body.face(f"{fid}/fillet/{edge['name']}") is not None


def test_reverse_swaps_the_two_distances() -> None:
    from tests.core.features.test_features import bounds

    tops = []
    for reverse in (False, True):
        doc, _ext, edge = _plate_edge(0.0)
        params = _p(radius=1, method="asymmetric", distance2=4)
        if reverse:
            params["reverse"] = True
        fid = add_fillet(doc, params, edges=[edge])
        made = body(rebuild(doc), fid).face(f"{fid}/fillet/{edge['name']}")
        assert made is not None
        tops.append(bounds(made)[4])  # how far the round reaches into the top face (y)
    assert sorted(tops) == pytest.approx([1.0, 4.0], abs=1e-6)


def test_curvature_continuous_lies_between_the_circle_and_the_corner() -> None:
    doc, _ext, edge = _plate_edge(0.0)
    fid = add_fillet(doc, _p(radius=2, profile="curvature"), edges=[edge])
    removed = (PLATE - volume(body(rebuild(doc), fid).shape)) / 50
    assert 0 < removed < 2.0  # inside the 2 x 2 corner triangle
    assert removed != pytest.approx(strip(2), rel=1e-3)


def test_concave_edge_gets_material_added() -> None:
    doc, ext, rib = rib_part()
    b = body(rebuild(doc), rib)
    side = next(f for n, f in b.faces if n.startswith(f"{rib}/side/") and _concave_count(b, f) > 0)
    from fdcad.core.features.fillet_faces import edges_by_convexity

    concave = edges_by_convexity(b, "concave", [side])
    assert concave
    ref = reference_for(b, concave[0][1])
    before = volume(b.shape)
    fid = add_fillet(doc, _p(radius=1, method="asymmetric", distance2=3), edges=[ref])
    after = volume(body(rebuild(doc), fid).shape)
    assert after - before == pytest.approx(3 * (1 - math.pi / 4) * 50, rel=1e-5)
    assert ext


def _concave_count(b: Any, face: Any) -> int:
    from fdcad.core.features.fillet_faces import edges_by_convexity

    return len(edges_by_convexity(b, "concave", [face]))


def test_curved_edge_is_named_in_the_error() -> None:
    from tests.core.features.test_fillet_tangent import rounded_plate

    doc, corner, b = rounded_plate()
    from fdcad.core.features.modify import edge_faces

    def on_round(e: Any) -> bool:
        names = [b.primary_name(f) or "" for f in edge_faces(b.shape, e)]
        return any(n.startswith(f"{corner}/fillet/") for n in names)

    arc = next(e for e in edges_of(b.shape) if on_round(e) and abs(_mid_z(e) - 10) < 1e-6)
    ref = reference_for(b, arc)
    fid = add_fillet(doc, _p(radius=1, profile="conic", rho=0.5), edges=[ref])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "edge 1 cannot take this profile" in messages(res)


def _mid_z(edge: Any) -> float:
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    c = BRepAdaptor_Curve(edge)
    return float(c.Value((c.FirstParameter() + c.LastParameter()) / 2).Z())


def test_elliptic_needs_asymmetric_and_rho_is_checked() -> None:
    doc, _ext, edge = _plate_edge(0.0)
    fid = add_fillet(doc, _p(radius=2, profile="elliptic"), edges=[edge])
    assert "Choose Asymmetric" in messages(rebuild(doc)[fid])
    doc, _ext, edge = _plate_edge(0.0)
    fid = add_fillet(doc, _p(radius=2, profile="conic", rho=1.2), edges=[edge])
    assert "between 0.05 and 0.95" in messages(rebuild(doc)[fid])


def test_a_shaped_fillet_cannot_change_to_a_chamfer() -> None:
    from fdcad.core.document.model import Feature
    from fdcad.core.fillet_chamfer import can_swap

    params = _p(radius=2, profile="conic", rho=0.5)
    feature = Feature("f9", "fillet", "Fillet 1", params=params, refs={"edges": [{"name": "e"}]})
    assert not can_swap(feature)
