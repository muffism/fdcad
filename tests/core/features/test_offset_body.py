"""Offset Body and Shell corners (TR129, D825)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, plate, volume

# plate(): a 50 x 50 x 10 block (25000 mm3).


def _offset(doc, params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "offset_body", "Offset Body 1", params=params))
    return fid


def test_grow_sharp_and_rounded_and_shrink() -> None:
    doc, ext = plate()
    fid = _offset(doc, {"distance": Param("1", 1.0)})
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    assert volume(body(res, fid).shape) == pytest.approx(52 * 52 * 12, rel=1e-6)
    names = [n for n, _ in body(res, fid).faces]
    assert f"{ext}/cap/end" in names  # faces keep their names
    doc.feature(fid).params["corners"] = "rounded"
    res = rebuild(doc)
    # Rounded: block + slabs on faces + quarter cylinders on edges + sphere corners.
    a, b, c, r = 50, 50, 10, 1
    rounded = a * b * c + 2 * r * (a * b + b * c + a * c) + math.pi * r * r * (a + b + c)
    rounded += 4 / 3 * math.pi * r**3
    assert volume(body(res, fid).shape) == pytest.approx(rounded, rel=1e-4)
    doc.feature(fid).params.pop("corners")
    doc.feature(fid).params["inward"] = True
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(48 * 48 * 8, rel=1e-6)
    doc.feature(fid).params["distance"] = Param("6", 6.0)
    assert rebuild(doc)[fid].state is FeatureState.ERROR


def test_shell_outward_corners_sharp_or_rounded() -> None:
    doc, _ext = plate()
    fid = doc.new_feature_id()
    params = {"thickness": Param("1", 1.0), "outward": True, "corners": "sharp"}
    doc.features.append(Feature(fid, "shell", "Shell 1", params=params))
    sharp = volume(body(rebuild(doc), fid).shape)
    assert sharp == pytest.approx(52 * 52 * 12 - 25000, rel=1e-6)
    doc.feature(fid).params["corners"] = "rounded"
    assert volume(body(rebuild(doc), fid).shape) < sharp - 1


def test_failure_names_the_tight_face_or_the_cause() -> None:
    """TR346 item 2 (D1405): never a bare failure."""
    from tests.core.features.test_features import messages
    from tests.core.features.test_fillet_tangent import rounded_plate

    doc, corner, _b = rounded_plate()
    fid = _offset(doc, {"distance": Param("6", 6.0), "inward": True})
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert f"face {corner}/fillet/" in messages(res)
    doc, _ext = plate()
    fid = _offset(doc, {"distance": Param("6", 6.0), "inward": True})
    assert "the wall may be too thin" in messages(rebuild(doc)[fid])
