"""Partial edge ends set by a picked vertex or plane (TR64 item 5, D1401)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_chamfer import add_chamfer
from tests.core.features.test_features import body, bounds, messages, volume
from tests.core.features.test_fillet_faces import PLATE, _plate_edge, add_fillet, strip
from tests.core.features.test_reference_geometry import _add

RIGHT = "f4"  # the built in plane square to X, through the origin


def _corner(doc: Any, ext: str, x: float) -> dict[str, Any]:
    """The top front vertex of the plate at ``x``."""
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    b = body(rebuild(doc), ext)
    explorer = TopExp_Explorer(b.shape, TopAbs_VERTEX)
    while explorer.More():
        v = TopoDS.Vertex(explorer.Current())
        p = BRep_Tool.Pnt_s(v)
        if abs(p.X() - x) < 1e-6 and abs(p.Y()) < 1e-6 and abs(p.Z() - 10) < 1e-6:
            ref = reference_for(b, v)
            assert ref is not None
            return ref
        explorer.Next()
    raise AssertionError("no vertex")


def test_fillet_from_a_vertex_to_a_plane() -> None:
    doc, ext, edge = _plate_edge(0.0)
    plane = _add(doc, "ref_plane", {"first": {"feature": RIGHT}}, method="offset", distance=30)
    fid = add_fillet(
        doc,
        {"fillet_type": "constant", "radius": Param("2", 2.0), "partial": "reference"},
        edges=[edge],
        partial_ends=[_corner(doc, ext, 0.0), {"feature": plane}],
    )
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(PLATE - strip(2) * 30, rel=1e-6)
    made = res.body.face(f"{fid}/fillet/{edge['name']}")
    assert made is not None
    assert bounds(made)[3] == pytest.approx(30.0, abs=1e-6)


def test_chamfer_between_two_planes() -> None:
    doc, _ext, edge = _plate_edge(0.0)
    a = _add(doc, "ref_plane", {"first": {"feature": RIGHT}}, method="offset", distance=10)
    b = _add(doc, "ref_plane", {"first": {"feature": RIGHT}}, method="offset", distance=35)
    params: dict[str, Any] = {
        "chamfer_type": "distance_distance",
        "method": "symmetric",
        "distance": Param("2", 2.0),
        "partial": "reference",
    }
    fid = add_chamfer(doc, params, edges=[edge], partial_ends=[{"feature": b}, {"feature": a}])
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - 2.0 * 25, rel=1e-6)


def test_one_end_only_is_an_error() -> None:
    doc, ext, edge = _plate_edge(0.0)
    fid = add_fillet(
        doc,
        {"fillet_type": "constant", "radius": Param("2", 2.0), "partial": "reference"},
        edges=[edge],
        partial_ends=[_corner(doc, ext, 0.0)],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "need two picks" in messages(res)


def test_a_plane_off_the_edge_is_an_error() -> None:
    doc, ext, edge = _plate_edge(0.0)
    plane = _add(doc, "ref_plane", {"first": {"feature": RIGHT}}, method="offset", distance=80)
    fid = add_fillet(
        doc,
        {"fillet_type": "constant", "radius": Param("2", 2.0), "partial": "reference"},
        edges=[edge],
        partial_ends=[_corner(doc, ext, 0.0), {"feature": plane}],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "does not cross edge" in messages(res)
