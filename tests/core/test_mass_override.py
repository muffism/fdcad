"""Centre of mass point and mass overrides (TR80, D1021)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.io import fdef
from fdcad.core.mass import (
    MassOverride,
    apply_override,
    check_override,
    mass_properties,
    override_from_data,
)
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_multibody import two_blocks


def _com_point(doc):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "ref_point", "Point 1", params={"method": "centre_of_mass"}))
    return fid


def test_point_follows_the_model() -> None:
    doc, _a, _b, _body = two_blocks(gap=10.0)  # blocks at x 0..20 and 30..50
    fid = _com_point(doc)
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.OK
    assert result.datum is not None
    assert result.datum.origin == pytest.approx((25, 10, 5))
    doc.mass_override = MassOverride(100.0, centre=(1.0, 2.0, 3.0)).to_data()
    assert rebuild(doc)[fid].datum.origin == pytest.approx((1, 2, 3))


def test_point_above_any_body_says_what_to_do() -> None:
    from fdcad.core.document.model import new_document

    doc = new_document()
    fid = _com_point(doc)
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "Move the point below" in result.issues[0].message


def test_override_replaces_mass_centre_and_scales_inertia() -> None:
    _doc, _a, _b, body = two_blocks(gap=10.0)
    measured = mass_properties(solids(body.shape), 1.0)
    over = apply_override(measured, MassOverride(2 * measured.mass))
    assert over.mass == pytest.approx(2 * measured.mass)
    assert over.centre == pytest.approx(measured.centre)
    assert over.inertia[0][0] == pytest.approx(2 * measured.inertia[0][0])
    assert over.density == pytest.approx(2.0)
    typed = ((10.0, 0.0, 0.0), (0.0, 20.0, 0.0), (0.0, 0.0, 25.0))
    over = apply_override(measured, MassOverride(5.0, (0.0, 0.0, 0.0), typed))
    assert over.principal == pytest.approx((10, 20, 25))
    assert over.centre == (0.0, 0.0, 0.0)


def test_checks_and_saving() -> None:
    assert check_override(MassOverride(0.0)) is not None
    bad = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 5.0))  # 5 > 1 + 1
    assert "real body" in (check_override(MassOverride(1.0, None, bad)) or "")
    assert check_override(MassOverride(1.0, (0, 0, 0), ((2, 0, 0), (0, 2, 0), (0, 0, 3)))) is None
    doc, *_ = two_blocks()
    doc.mass_override = MassOverride(12.5, (1.0, 2.0, 3.0)).to_data()
    again = fdef.loads(fdef.dumps(doc))
    assert override_from_data(again.mass_override) == MassOverride(12.5, (1.0, 2.0, 3.0))
    raw = fdef.dumps(doc).replace('"mass": 12.5', '"mass": -1')
    assert fdef.loads(raw).mass_override == {}  # damaged: dropped, the part still opens
    doc.mass_override = {}
    assert "mass_override" not in fdef.dumps(doc)
