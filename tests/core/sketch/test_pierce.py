"""Pierce: a sketch point kept where a curve crosses the plane (TR101, D843)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Point, Sketch, sketch_to_data


def _doc(points):  # type: ignore[no-untyped-def]
    doc = new_document()
    curve = doc.new_feature_id()
    doc.features.append(Feature(curve, "point_curve", "Curve 1", data={"points": points}))
    s = Sketch()
    pid = s.add_point(0.0, 0.0)
    sk = doc.new_feature_id()
    doc.features.append(
        Feature(
            sk,
            "sketch",
            "Sketch 1",
            refs={
                "plane": {"feature": "f2"},
                "pierce": [{"point": pid, "curve": {"feature": curve}}],
            },
            data=sketch_to_data(s),
        )
    )
    return doc, curve, sk, pid


def test_point_follows_the_crossing() -> None:
    doc, curve, sk, pid = _doc([[0, 0, -10], [0, 0, 10]])
    res = rebuild(doc)
    out = res[sk].sketch
    assert out is not None and res[sk].state is not FeatureState.ERROR
    plane = out.plane
    want = plane.to_2d(0.0, 0.0, 0.0)
    # Move the curve: through (a, b) wherever the front plane is, it crosses it once.
    a, b, c = plane.to_3d(7.0, 3.0).X(), plane.to_3d(7.0, 3.0).Y(), plane.to_3d(7.0, 3.0).Z()
    n = plane.normal
    doc.feature(curve).data["points"] = [
        [a - 5 * n[0], b - 5 * n[1], c - 5 * n[2]],
        [a + 5 * n[0], b + 5 * n[1], c + 5 * n[2]],
    ]
    res = rebuild(doc)
    point = res[sk].sketch.model.entities[pid]  # type: ignore[union-attr]
    assert isinstance(point, Point)
    assert (point.x, point.y) == pytest.approx((7.0, 3.0), abs=1e-6)
    del want


def test_a_curve_that_misses_warns() -> None:
    doc, curve, sk, _pid = _doc([[0, 0, 0], [0, 0, 0]])
    res = rebuild(doc)
    plane = res[sk].sketch.plane  # type: ignore[union-attr]
    n = plane.normal
    doc.feature(curve).data["points"] = [
        [n[0] * 5, n[1] * 5, n[2] * 5],
        [n[0] * 9 + 1, n[1] * 9 + 1, n[2] * 9 + 1],
    ]
    res = rebuild(doc)
    assert any(i.code == "pierce_lost" for i in res[sk].issues)


def test_behind_keeps_the_part_away_from_the_normal() -> None:
    """Cut Away while sketching (TR113, D844): display only, the part is not changed."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from fdcad.core.features.solids import volume_of
    from fdcad.core.sketch.reference import behind

    doc, _curve, sk, _pid = _doc([[0, 0, -10], [0, 0, 10]])
    plane = rebuild(doc)[sk].sketch.plane  # type: ignore[union-attr]
    n = plane.normal
    box = BRepPrimAPI_MakeBox(gp_Pnt(-5, -5, -5), 10.0, 10.0, 10.0).Shape()
    kept = behind(box, plane)
    assert volume_of(kept) == pytest.approx(500.0, rel=1e-6)  # half the cube
    assert volume_of(box) == pytest.approx(1000.0)
    del n
