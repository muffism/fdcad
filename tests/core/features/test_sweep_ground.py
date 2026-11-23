"""Ground flat ends of a swept spring (TR162 item 2, D2408)."""

from __future__ import annotations

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_curves import add
from tests.core.features.test_features import add_sketch, messages, volume


def _spring(**sweep: object) -> tuple[object, str]:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 10.0)
    sk = add_sketch(doc, s, {"feature": "f2"})
    hid = add(
        doc, "helix", {"sketch": {"feature": sk}},
        definition="pitch_turns", pitch=Param("6", 6.0), turns=Param("4", 4.0),
    )  # fmt: skip
    fid = add(
        doc, "sweep", {"path": {"feature": hid}},
        operation="boss", profile_type="circular", diameter=Param("2", 2.0), **sweep,
    )  # fmt: skip
    return doc, fid


def _zs(shape: object) -> tuple[float, float]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)  # type: ignore[arg-type]
    return box.CornerMin().Z(), box.CornerMax().Z()


def test_ground_ends_cut_the_spring_flat_at_both_ends() -> None:
    doc, fid = _spring()
    plain = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert plain.body is not None
    low, high = _zs(plain.body.shape)
    assert low == pytest.approx(-1.0, abs=0.01) and high == pytest.approx(25.0, abs=0.01)
    doc.feature(fid).params["ground_ends"] = True  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    low, high = _zs(res.body.shape)
    assert low == pytest.approx(0.0, abs=1e-6) and high == pytest.approx(24.0, abs=1e-6)
    assert volume(res.body.shape) < volume(plain.body.shape)
    names = {n for n, _f in res.body.faces}
    assert f"{fid}/ground/start" in names and f"{fid}/ground/end" in names
