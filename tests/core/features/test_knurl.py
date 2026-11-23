"""Knurl (TR163 item 1, D2015)."""

from __future__ import annotations

import math
import time
from typing import Any

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch


def _knurl(**params: Any) -> Any:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.select import reference_for

    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 8)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0)
    body = RebuildEngine().rebuild(doc).body
    side = next(f for f in faces_of(body.shape)
                if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder)  # fmt: skip
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "knurl", "Knurl 1", params=params,
                                refs={"round_face": reference_for(body, side)}))  # fmt: skip
    return rebuild(doc)[fid]


FULL = math.pi * 64 * 20


def test_straight_knurl_cuts_grooves_all_round() -> None:
    res = _knurl(
        knurl_pattern="straight", knurl_pitch=Param("1.5", 1.5), knurl_depth=Param("0.5", 0.5)
    )
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 1
    removed = FULL - volume_of(res.body.shape)
    assert 0.3 * 2 * math.pi * 8 * 0.5 * 20 < removed < 2 * math.pi * 8 * 0.5 * 20


def test_diamond_knurl_is_reasonably_quick() -> None:
    start = time.perf_counter()
    res = _knurl(
        knurl_pattern="diamond", knurl_pitch=Param("2", 2.0), knurl_depth=Param("0.4", 0.4)
    )
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume_of(res.body.shape) < FULL
    assert any("/knurl#" in name for name, _f in res.body.faces)
    assert time.perf_counter() - start < 60


def test_pitch_limits() -> None:
    res = _knurl(knurl_pitch=Param("0.1", 0.1), knurl_depth=Param("0.05", 0.05))
    assert res.state is FeatureState.ERROR and "Enter a pitch" in res.issues[0].message


def test_a_knurl_on_a_stem_stops_at_the_shoulder() -> None:
    """D1060: found on a gearbox knob. The grooves ran 0.2 mm past both ends of the
    face. Where the stem stands on a wider body they notched it, and the notches met
    each other along edges only: 220 edges with more than two faces, and no warning.
    Here: a 16 mm stem, 15 long, on a 40 mm disc."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.GeomAbs import GeomAbs_Cylinder

    from fdcad.core.features.solids import zero_thickness
    from fdcad.core.naming.select import reference_for
    from tests.core.features.test_hole import face_ref

    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 20)
    disc = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    s = Sketch()
    s.add_circle(0, 0, 8)
    add_extrude(doc, add_sketch(doc, s, face_ref(doc, disc, "cap/end")), 15.0)
    body = RebuildEngine().rebuild(doc).body
    before = volume_of(body.shape)
    stem = next(
        f for _n, f in body.faces
        if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder
        and abs(BRepAdaptor_Surface(f).Cylinder().Radius() - 8.0) < 1e-9
    )  # fmt: skip
    fid = doc.new_feature_id()
    params = {"knurl_pattern": "straight", "knurl_pitch": Param("2.5", 2.5),
              "knurl_depth": Param("0.5", 0.5)}  # fmt: skip
    doc.features.append(Feature(fid, "knurl", "Knurl 1", params=params,
                                refs={"round_face": reference_for(body, stem)}))  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert zero_thickness(res.body.shape) == []
    assert BRepCheck_Analyzer(res.body.shape, True, True).IsValid()
    removed = before - volume_of(res.body.shape)
    # Twenty V grooves, 0.5 deep and 2.5 wide at the surface, 15 long (and 0.2 more at
    # the free end): nothing is taken from the disc.
    assert removed < 20 * 0.5 * 2.6 * 0.5 * 15.3
