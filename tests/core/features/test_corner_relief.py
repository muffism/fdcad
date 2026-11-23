"""Corner Relief (TR244, D785)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.corner_relief import feature_corners
from fdcad.core.naming.select import reference_for
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    plate,
    rebuild,
    rect,
    volume,
)

DEPTH, TOOL = 5.0, 3.0
R = TOOL / 2


def _pocket() -> tuple[Document, str]:
    """A 50 by 50 by 10 plate with a 20 by 10 pocket 5 deep cut in from the bottom."""
    doc, _ext = plate()
    s = Sketch()
    rect(s, 15, 20, 35, 30)
    cut = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), DEPTH, operation="cut")
    assert volume(body(rebuild(doc), cut).shape) == pytest.approx(25000 - 20 * 10 * DEPTH)
    return doc, cut


def _relief(doc: Document, refs: dict, kind: str, **extra: object) -> tuple[float, object]:
    fid = doc.new_feature_id()
    params = {"relief_type": kind, "tool_diameter": Param(str(TOOL), TOOL), **extra}
    doc.features.append(Feature(fid, "corner_relief", "Corner Relief 1", params=params, refs=refs))
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    doc.features.pop()
    return volume(body({fid: res}, fid).shape), res


def _dogbone_area(r: float) -> float:
    """The part of a disc of radius r, centred r along the diagonal into the pocket, that
    lies in the material round the corner (x < 0 or y < 0)."""
    n = 2001
    xs = np.linspace(-r, 2 * r, n)
    gx, gy = np.meshgrid(xs, xs)
    c = r / math.sqrt(2)
    disc = (gx - c) ** 2 + (gy - c) ** 2 <= r * r
    cell = (xs[1] - xs[0]) ** 2
    return float(np.sum(disc & ((gx < 0) | (gy < 0))) * cell)


def test_the_four_inside_corners_of_a_pocket() -> None:
    doc, cut = _pocket()
    b = body(rebuild(doc), cut)
    assert len(feature_corners(b, cut)) == 4


def test_t_bone_dogbone_and_fillet_volumes() -> None:
    doc, cut = _pocket()
    pocketed = 25000 - 20 * 10 * DEPTH
    refs = {"feature": {"feature": cut}}
    t_bone, res = _relief(doc, refs, "t_bone")
    assert pocketed - t_bone == pytest.approx(4 * math.pi * R * R / 2 * DEPTH, rel=1e-6)
    made = {
        n.split("/relief/")[1].split("#")[0].split("/")[0]
        for n, _f in res.body.faces
        if "/relief/" in n
    }
    assert made == {"1", "2", "3", "4"}
    dogbone, _r = _relief(doc, refs, "dogbone")
    assert pocketed - dogbone == pytest.approx(4 * _dogbone_area(R) * DEPTH, rel=1e-2)
    rounded, _r = _relief(doc, refs, "fillet")
    assert rounded - pocketed == pytest.approx(4 * (1 - math.pi / 4) * R * R * DEPTH, rel=1e-4)
    bigger, _r = _relief(doc, refs, "t_bone", clearance=Param("0.5", 0.5))
    assert bigger < t_bone


def test_a_pocket_in_a_body_that_sits_on_another() -> None:
    """D1082: the corner test asked the kernel about a point in the whole part, and for
    two bodies that share a face the kernel says a point in the upper one is outside.
    The pocket's corners were then not corners, and no relief was cut."""
    doc, lower = plate()
    s = Sketch()
    rect(s, 0, 0, 50, 50)
    upper = add_extrude(
        doc, add_sketch(doc, s, {"kind": "face", "name": f"{lower}/cap/end"}), 10.0, merge=False
    )
    s = Sketch()
    rect(s, 15, 20, 35, 30)
    cut = add_extrude(
        doc,
        add_sketch(doc, s, {"kind": "face", "name": f"{upper}/cap/end"}),
        DEPTH,
        operation="cut",
        reverse=True,  # down into the upper body
    )
    pocketed = volume(body(rebuild(doc), cut).shape)
    assert pocketed == pytest.approx(2 * 25000 - 20 * 10 * DEPTH)
    dogbone, _r = _relief(doc, {"feature": {"feature": cut}}, "dogbone")
    assert pocketed - dogbone == pytest.approx(4 * _dogbone_area(R) * DEPTH, rel=1e-2)


def test_picked_edges_and_a_wrong_pick() -> None:
    doc, cut = _pocket()
    b = body(rebuild(doc), cut)
    corner = feature_corners(b, cut)[0]
    ref = reference_for(b, corner)
    assert ref is not None
    one, _r = _relief(doc, {"edges": [ref]}, "t_bone")
    assert 25000 - 20 * 10 * DEPTH - one == pytest.approx(math.pi * R * R / 2 * DEPTH, rel=1e-6)
    fid = doc.new_feature_id()
    plate_edge = next(
        e for e in _all_edges(b) if reference_for(b, e) and e not in feature_corners(b, cut)
    )
    doc.features.append(
        Feature(
            fid,
            "corner_relief",
            "Corner Relief 1",
            params={"relief_type": "dogbone", "tool_diameter": Param("3", 3.0)},
            refs={"edges": [reference_for(b, plate_edge)]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "not a straight inside corner" in res.issues[0].message


def _all_edges(b):  # type: ignore[no-untyped-def]
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    out = []
    ex = TopExp_Explorer(b.shape, TopAbs_EDGE)
    while ex.More():
        out.append(TopoDS.Edge(ex.Current()))
        ex.Next()
    # An outside edge of the plate: first one on a plate side face.
    from fdcad.core.features.corner_relief import inside_corner

    return [e for e in out if inside_corner(b, e) is None]
