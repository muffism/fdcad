"""Reapply Fillets on Draft (TR259, D1806)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.remove_fillets import find_rounds
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import messages
from tests.core.features.test_fillet import _plate_and_refs, add_fillet


def _drafted(reapply: bool) -> tuple[object, str]:
    doc, ext, _b, refs = _plate_and_refs(1)
    add_fillet(doc, 2.0, edges=refs)
    inner = str(refs[0]["name"])[len("edge(") : -1].split("|")
    side = next(n for n in inner if not n.endswith("cap/end"))
    fid = doc.new_feature_id()
    params: dict[str, object] = {"angle": Param("5 deg", math.radians(5))}
    if reapply:
        params["reapply_fillets"] = True
    doc.features.append(
        Feature(
            fid,
            "draft",
            "Draft 1",
            params=params,  # type: ignore[arg-type]
            refs={
                "neutral": {"kind": "face", "name": f"{ext}/cap/start"},
                "faces": [{"kind": "face", "name": side}],
            },
        )
    )
    return rebuild(doc)[fid], fid


def test_round_next_to_the_drafted_face_is_made_again() -> None:
    res, fid = _drafted(True)
    assert res.state is not FeatureState.ERROR, messages(res)  # type: ignore[attr-defined]
    rounded = res.body  # type: ignore[attr-defined]
    assert rounded is not None
    rounds = find_rounds(rounded)
    assert [r for _n, _f, r in rounds] == pytest.approx([2.0], rel=1e-3)
    assert any(n.startswith(f"{fid}/fillet/") for n, _f in rounded.faces)
