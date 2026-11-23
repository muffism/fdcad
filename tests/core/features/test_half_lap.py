"""Half lap joints between crossing plates (TR364, D882)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect


def _plates(dx: float = 0.0):  # type: ignore[no-untyped-def]
    doc = new_document()
    a = Sketch()
    rect(a, dx, 47, dx + 100, 50)  # 3 thick in Y
    add_extrude(doc, add_sketch(doc, a, {"feature": "f2"}), 40.0)
    b = Sketch()
    rect(b, dx + 48, 0, dx + 51, 100)  # 3 thick in X, crossing the first
    second = add_extrude(doc, add_sketch(doc, b, {"feature": "f2"}), 40.0, merge=False)
    part = body(rebuild(doc), second)
    refs = []
    for solid in solids(part.shape):
        from fdcad.core.naming.names import faces_of

        ref = reference_for(part, faces_of(solid)[0])
        assert ref is not None
        refs.append(ref)
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "half_lap", "Half Lap 1", refs={"bodies": refs}))
    return doc, fid, part


@pytest.mark.parametrize("dx", [0.0, 2000.0])
def test_each_plate_loses_half_the_crossing(dx: float) -> None:
    """D1087: far from the origin the notches came out empty and nothing was cut."""
    doc, fid, before = _plates(dx)
    doc.feature(fid).params["clearance"] = Param("0", 0.0)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    after = body(res, fid)
    assert len(solids(after.shape)) == 2
    lost = sorted(
        volume_of(x) - volume_of(y)
        for x, y in zip(solids(before.shape), solids(after.shape), strict=True)
    )
    assert lost == pytest.approx([180.0, 180.0], rel=1e-6)
    # Clearance widens each notch by 0.2 across the other plate.
    doc.feature(fid).params["clearance"] = Param("0.2", 0.2)
    after = body(rebuild(doc), fid)
    lost = [
        volume_of(x) - volume_of(y)
        for x, y in zip(solids(before.shape), solids(after.shape), strict=True)
    ]
    assert lost == pytest.approx([3.2 * 3 * 20, 3.2 * 3 * 20], rel=1e-3)


def _numbered(doc, fid, role, monkeypatch, backwards):  # type: ignore[no-untyped-def]
    """Where each numbered face of the feature lies, with the kernel listing the faces
    of every shape in its own order or backwards."""
    import fdcad.core.naming.names as names

    real = names.faces_of
    if backwards:
        monkeypatch.setattr(names, "faces_of", lambda shape: real(shape)[::-1])
    try:
        result = rebuild(doc)[fid]
    finally:
        monkeypatch.setattr(names, "faces_of", real)
    assert result.state is not FeatureState.ERROR, result.issues
    return {
        n: tuple(round(v, 6) for v in names.centroid(f))
        for n, f in result.body.faces
        if n.startswith(f"{fid}/{role}/") and "#" not in n
    }


def test_the_new_faces_are_numbered_by_position(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """D1068: found on a gearbox. The notch faces were numbered in the order the kernel
    listed them, which is not the same from one run to the next: the part as built and
    the same part opened from its file gave the numbers to different faces. Here the
    kernel's order is turned round, and the numbers must not move."""
    doc, fid, _before = _plates()
    as_listed = _numbered(doc, fid, "lap", monkeypatch, backwards=False)
    turned = _numbered(doc, fid, "lap", monkeypatch, backwards=True)
    assert len(as_listed) >= 3
    assert turned == as_listed
