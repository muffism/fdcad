"""Dome on a round face whose rim is a spline circle (IDEAS 54, DECISIONS D2621).

The round end of a scaled sweep or of a loft between circles is bounded by a spline
that is a circle in shape. The dome used to test the edge's kind, found no circle and
asked for Continuous dome; it now tests the edge's shape.
"""

import math

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Circle
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.dome import round_face
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_dome import add_dome, cap
from tests.core.features.test_features import add_sketch, body, plate, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_loft import _two_levels, add_loft
from tests.core.features.test_sweep import add_sweep, straight_path


def _rim_is_spline(face: TopoDS_Face) -> bool:
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    kinds = []
    while explorer.More():
        kinds.append(BRepAdaptor_Curve(TopoDS.Edge(explorer.Current())).GetType())
        explorer.Next()
    return bool(kinds) and GeomAbs_Circle not in kinds


def _scaled_sweep() -> tuple[Document, str]:
    """A round rod of radius 3 swept 20 up +Z, scaled to 2 at the end (radius 6)."""
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 3.0)
    fid = add_sweep(doc, add_sketch(doc, s, {"feature": "f2"}), straight_path(doc))
    doc.feature(fid).params.update({"scale_start": Param("1", 1.0), "scale_end": Param("2", 2.0)})
    return doc, fid


def test_scaled_sweep_end_is_round() -> None:
    doc, sweep = _scaled_sweep()
    end = body(rebuild(doc), sweep).face(f"{sweep}/cap/end")
    assert end is not None and _rim_is_spline(end)
    found = round_face(end)
    assert found is not None
    centre, radius = found
    assert radius == pytest.approx(6.0, rel=1e-6)
    assert centre == pytest.approx((0.0, 0.0, 20.0), abs=1e-6)


def test_dome_on_scaled_sweep_end() -> None:
    doc, sweep = _scaled_sweep()
    base = math.pi * 20 / 3 * (9 + 18 + 36)  # frustum from radius 3 to 6
    fid = add_dome(doc, [face_ref(doc, sweep, "cap/end")], 0.0)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    hemi = 2 / 3 * math.pi * 6**3
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base + hemi, rel=1e-4)
    doc.feature(fid).params["distance"] = Param("2", 2.0)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base + cap(6, 2), rel=1e-4)


def test_dome_on_loft_end() -> None:
    """A loft between two circles that leaves the first one square: spline rims."""
    doc = new_document()
    top = _two_levels(doc)
    a, b = Sketch(), Sketch()
    a.add_circle(0, 0, 5.0)
    b.add_circle(2, 1, 3.0)
    low, high = add_sketch(doc, a, {"feature": "f2"}), add_sketch(doc, b, top)
    loft = add_loft(doc, [low, high], start_constraint="normal", start_length=Param("10", 10.0))
    built = body(rebuild(doc), loft)
    end = built.face(f"{loft}/cap/end")
    assert end is not None and _rim_is_spline(end)
    before = volume(built.shape)
    fid = add_dome(doc, [face_ref(doc, loft, "cap/end")], 1.5)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume(body(rebuild(doc), fid).shape) - before == pytest.approx(cap(3, 1.5), rel=1e-4)


def test_square_face_is_still_not_round() -> None:
    doc, ext = plate()
    face = body(rebuild(doc), ext).face(f"{ext}/cap/end")
    assert face is not None and round_face(face) is None
