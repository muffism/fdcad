"""Loft end constraints Tangent and Curvature to the faces next to a face profile
(TR136 item 2, D1924)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureState
from fdcad.core.features.loft import _adjacent_direction
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.phase3_parts import ok_body, volume_of
from tests.core.features.test_patterns import centred
from tests.core.features.test_sweep_sections import _profile_at


def _loft_from_top(kind: str) -> tuple[object, str, dict[str, object], str]:
    doc, plate, boss = centred()
    doc.features = [f for f in doc.features if f.id != boss]
    top = _profile_at(doc, 30.0, 10, 10)
    fid = doc.new_feature_id()
    params: dict[str, object] = {"operation": "boss", "start_constraint": kind}
    if kind != "default":
        params["start_length"] = Param("20", 20.0)
    doc.features.append(
        Feature(
            fid,
            "loft",
            "Loft 1",
            params=params,  # type: ignore[arg-type]
            refs={"profiles": [{"kind": "face", "name": f"{plate}/cap/end"}, {"feature": top}]},
        )
    )
    return doc, fid, rebuild(doc), plate  # type: ignore[return-value]


def test_the_sides_of_a_box_point_straight_up() -> None:
    doc, fid, results, plate = _loft_from_top("default")
    ctx = BuildContext(doc, ok_body(results, plate), results)  # type: ignore[arg-type]
    feature = doc.feature(fid)  # type: ignore[attr-defined]
    assert _adjacent_direction(feature, ctx, "start") == pytest.approx((0, 0, 1), abs=1e-9)


@pytest.mark.parametrize("kind", ["tangent", "curvature"])
def test_tangent_and_curvature_bulge_the_loft_out(kind: str) -> None:
    _doc, plain_id, plain, _p = _loft_from_top("default")
    _doc2, fid, results, _p2 = _loft_from_top(kind)
    assert results[fid].state is not FeatureState.ERROR, [i.message for i in results[fid].issues]
    assert volume_of(ok_body(results, fid).shape) > volume_of(ok_body(plain, plain_id).shape)


def test_a_sketch_end_cannot_be_tangent_to_faces() -> None:
    from fdcad.core.document.model import new_document
    from tests.core.features.test_loft import _square, _two_levels

    doc = new_document()
    up = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, up, 3)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "loft",
            "Loft 1",
            params={
                "operation": "boss",
                "start_constraint": "tangent",
                "start_length": Param("5", 5.0),
            },
            refs={"profiles": [{"feature": low}, {"feature": high}]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "need a face of the part" in res.issues[0].message
