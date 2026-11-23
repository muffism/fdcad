"""Multi colour inlay (TR184, D867)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.solids import solids
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, plate, rect, volume


def test_pocket_and_separate_inlay_body() -> None:
    doc, ext = plate()  # 50 x 50 x 10
    top = body(rebuild(doc), ext)
    ref = reference_for(top, top.face(f"{ext}/cap/end"))
    s = Sketch()
    rect(s, 10, 10, 30, 20)  # 20 x 10
    sk = add_sketch(doc, s, ref)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "inlay",
            "Inlay 1",
            params={"depth": Param("1", 1.0)},
            refs={"sketch": {"feature": sk}},
        )
    )
    out = body(rebuild(doc), fid)
    pieces = solids(out.shape)
    assert len(pieces) == 2
    assert sorted(volume(p) for p in pieces) == pytest.approx([200.0, 25000.0 - 200.0])
    assert any(n.startswith(f"{fid}/inlay/") for n, _f in out.faces)
