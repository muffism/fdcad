"""Omit attach edges when a whole feature is filleted (TR64 item 6, D997)."""

from __future__ import annotations

from fdcad.core.document.model import Param
from tests.core.features.phase3_parts import add_feature, block_with_hole_and_boss, ok_body, rebuild


def _rounded(omit: bool) -> int:
    doc, ids = block_with_hole_and_boss()
    params = {"fillet_type": "constant", "radius": Param("0.5", 0.5)}
    if omit:
        params["omit_attach"] = True
    fid = add_feature(doc, "fillet", params, {"features": [{"feature": ids["boss"]}]})
    body = ok_body(rebuild(doc), fid)
    return len([n for n, _f in body.faces if n.startswith(f"{fid}/fillet/")])


def test_attach_edges_stay_sharp() -> None:
    every = _rounded(False)
    own = _rounded(True)
    assert own == every - 4  # the four edges where the boss meets the plate stay sharp
