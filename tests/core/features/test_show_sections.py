"""Show Sections for sweeps and lofts (TR139 item 2, D1909)."""

from __future__ import annotations

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import messages
from tests.core.features.test_sweep import add_sweep, square_profile, straight_path


def _z_range(shape: object) -> tuple[float, float]:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)  # type: ignore[arg-type]
    return box.CornerMin().Z(), box.CornerMax().Z()


@pytest.mark.parametrize(("k", "z"), [(1, 0.0), (6, 10.0), (11, 20.0)])
def test_a_sweep_shows_the_section_by_number(k: int, z: float) -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), straight_path(doc), show_section=Param(str(k), k))
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    low, high = _z_range(res.extras["reference"])
    assert low == pytest.approx(z, abs=1e-6) and high == pytest.approx(z, abs=1e-6)
    assert res.extras["report"][0].startswith(f"Section {k} of 11")


def test_the_section_shows_when_the_sweep_fails() -> None:
    doc = new_document()
    fid = add_sweep(
        doc,
        square_profile(doc),
        straight_path(doc),
        show_section=Param("3", 3.0),
        orientation="keep_normal",
        twist="angle",
        twist_angle=Param("90", 1.5708),
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "reference" in res.extras


def test_a_section_number_out_of_range_is_refused() -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), straight_path(doc), show_section=Param("12", 12.0))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "from 0 to 11" in messages(res)


def test_a_loft_shows_a_slice() -> None:
    from fdcad.core.document.model import Feature
    from tests.core.features.test_loft import _square, _two_levels

    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 3)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "loft",
            "Loft 1",
            params={"operation": "boss", "show_section": Param("6", 6.0)},
            refs={"profiles": [{"feature": low}, {"feature": high}]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    low_z, high_z = _z_range(res.extras["reference"])
    assert low_z == pytest.approx(high_z, abs=1e-4) and low_z > 0
