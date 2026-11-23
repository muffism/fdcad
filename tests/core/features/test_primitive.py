"""Primitive solids (TR127, D813)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import volume_of
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import plate


def p(v: float) -> Param:
    return Param(f"{v:g}", float(v))


def _make(doc: Any, kind: str, **sizes: Any) -> Any:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {"kind": kind}
    refs = sizes.pop("refs", {})
    for key, value in sizes.items():
        params[key] = p(value) if isinstance(value, (int, float)) and key != "centred" else value
    doc.features.append(Feature(fid, "primitive", f"Primitive {fid}", params=params, refs=refs))
    return rebuild(doc)[fid]


@pytest.mark.parametrize(
    ("kind", "sizes", "expected"),
    [
        ("box", {"length": 10, "width": 20, "height": 30}, 6000.0),
        ("cylinder", {"diameter": 10, "height": 20}, math.pi * 25 * 20),
        ("sphere", {"diameter": 10}, 4 / 3 * math.pi * 125),
        ("cone", {"diameter": 10, "diameter2": 0, "height": 30}, math.pi * 25 * 30 / 3),
        ("torus", {"ring": 40, "tube": 10}, 2 * math.pi**2 * 20 * 25),
        ("wedge", {"length": 10, "width": 4, "height": 6, "top": 2}, 10 * 4 * (6 + 2) / 2),
        (
            "prism",
            {"diameter": 20, "height": 5, "sides": 6},
            6 * 0.5 * 100 * math.sin(math.pi / 3) * 5,
        ),
        ("tube", {"diameter": 10, "inner": 6, "height": 10}, math.pi * (25 - 9) * 10),
    ],
)
def test_each_shape_has_its_volume(kind: str, sizes: dict[str, float], expected: float) -> None:
    doc = new_document()
    res = _make(doc, kind, **sizes)
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume_of(res.body.shape) == pytest.approx(expected, rel=1e-6)


def test_cut_a_centred_cylinder_from_a_plate_on_its_top_face() -> None:
    doc, ext = plate()  # 50 by 50 by 10
    res = _make(
        doc, "cylinder", diameter=10, height=4, centred=True, operation="cut",
        refs={"frame": {"kind": "face", "name": f"{ext}/cap/end"}},
    )  # fmt: skip
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume_of(res.body.shape) == pytest.approx(25000 - math.pi * 25 * 2, rel=1e-6)


def test_bad_sizes_say_what_to_do() -> None:
    doc = new_document()
    res = _make(doc, "tube", diameter=6, inner=8, height=5)
    assert res.state is FeatureState.ERROR and "inside diameter" in res.issues[0].message
    res = _make(doc, "prism", diameter=6, height=5, sides=2)
    assert "3 to 64 sides" in res.issues[0].message


def test_a_primitive_kept_apart_on_purpose_does_not_warn() -> None:
    """D1061: with Merge result off the separate body is what was asked for. A box
    beside the plate warned "created a separate body"; an extrude with Merge result
    off does not."""
    doc, _ext = plate()
    fid = doc.new_feature_id()
    params = {"kind": "sphere", "operation": "boss", "diameter": p(10), "merge": False}
    doc.features.append(Feature(fid, "primitive", "Ball", params=params))
    res = rebuild(doc)[fid]  # at the origin: it overlaps the plate's corner
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    doc.feature(fid).params["merge"] = True
    doc.feature(fid).params["kind"] = "sphere"
    assert rebuild(doc)[fid].state is FeatureState.OK  # joined: one body, no warning
