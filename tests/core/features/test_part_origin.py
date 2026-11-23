"""Move the part origin (TR343, D2419)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, messages, plate, rect
from tests.core.features.test_stone_sprue import _box


def _move_origin(doc, **values: float) -> None:  # type: ignore[no-untyped-def]
    origin = next(f for f in doc.features if f.type == "origin")
    for key, v in values.items():  # angles are typed in degrees
        text = f"{math.degrees(v):g}" if key.startswith("r") else f"{v:g}"
        origin.params[key] = Param(text, v)


def test_the_main_planes_go_with_the_origin_and_other_geometry_stays() -> None:
    doc, ext = plate()  # the plate is sketched on the Front plane
    _move_origin(doc, ox=100.0, oy=0.0, oz=20.0)
    res = rebuild(doc)
    assert res[ext].state is FeatureState.OK, messages(res[ext])
    assert res["f2"].plane is not None and res["f2"].plane.origin == pytest.approx((100, 0, 20))
    assert _box(res[ext].body.shape)[:3] == pytest.approx([100, 0, 20], abs=1e-6)  # type: ignore[union-attr]
    assert res["f1"].datum is not None and res["f1"].datum.origin == pytest.approx((100, 0, 20))


def test_a_turned_origin_turns_the_planes_and_origin_axes() -> None:
    doc, _ext = plate()
    _move_origin(doc, rz=math.pi / 2)
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})
    block = add_extrude(doc, sk, 5.0, merge=False)
    res = rebuild(doc)
    assert res[block].state is not FeatureState.ERROR, messages(res[block])
    x = res["f2"].plane.x_dir  # type: ignore[union-attr]
    assert x == pytest.approx((0, 1, 0), abs=1e-9)  # the Front plane's X now runs along Y
    from fdcad.core.features.base import BuildContext
    from fdcad.core.features.geometry_refs import resolve_placement

    res = rebuild(doc)
    ctx = BuildContext(doc, None, res, {})
    line = resolve_placement(ctx, {"feature": "f1", "axis": "x"}, "t", "axis")
    assert line.direction == pytest.approx((0, 1, 0), abs=1e-9)
