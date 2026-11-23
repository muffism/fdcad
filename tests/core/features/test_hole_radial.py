"""Radial hole placement, holes on a point and along a slanted axis (TR397 item 1, D1915)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.names import centroid
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import on_top, p
from tests.core.features.test_hole_place import _placed


def _wall(made: Any, fid: str) -> Any:
    return next(f for n, f in made.faces if n.startswith(f"{fid}/hole/") and n.endswith("/wall"))


def test_a_hole_at_a_distance_and_angle_from_an_axis() -> None:
    doc, _ext, sk, top = on_top([(1, 1)])
    doc.features = [f for f in doc.features if f.id != sk]
    fid = _placed(
        doc,
        top,
        {"radial": [{"feature": "f1", "axis": "z"}]},
        radial_distance=p(20.0),
        radial_angle=Param("45", math.radians(45)),
    )
    res = rebuild(doc)
    made = body(res, fid)
    c = centroid(_wall(made, fid))
    s = 20 / math.sqrt(2)
    assert (abs(c[0]), abs(c[1])) == pytest.approx((s, s), abs=1e-6)


def test_a_hole_along_a_slanted_axis() -> None:
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch

    doc, _ext, sk, top = on_top([(1, 1)])
    doc.features = [f for f in doc.features if f.id != sk]
    s = Sketch()
    line = s.add_line(0, 0, -10, 10)  # Right plane: 45 degrees between +Z and +Y
    slant = add_sketch(doc, s, {"feature": "f4"})
    fid = _placed(
        doc,
        top,
        {"radial": [{"feature": "f1", "axis": "z"}]},
        radial_distance=p(math.hypot(25, 25)),
        radial_angle=Param("45", math.radians(45)),
    )
    doc.feature(fid).refs["hole_axis"] = [{"feature": slant, "sketch_entity": line}]
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    d = BRepAdaptor_Surface(_wall(body(res, fid), fid)).Cylinder().Axis().Direction()
    assert abs(d.Z()) == pytest.approx(math.sqrt(0.5), abs=1e-6)
    assert volume(body(res, fid).shape) < 25000
    doc.feature(fid).refs["hole_axis"] = [{"feature": "f1", "axis": "x"}]
    bad = rebuild(doc)[fid]
    assert bad.state is FeatureState.ERROR and "along the face" in messages(bad)
