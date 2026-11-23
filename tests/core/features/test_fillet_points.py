"""Variable fillet control point positions (TR133, D1403)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fillet import Item, point_positions, radius_law
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_fillet import _plate_and_refs, add_fillet


def _variable(fid: str = "f9", **params: object) -> Feature:
    values: dict[str, object] = {"fillet_type": "variable", "radius": Param("2", 2.0)}
    values.update(params)
    return Feature(fid, "fillet", "Fillet 1", params=values)  # type: ignore[arg-type]


def test_positions_default_to_even_spacing_and_follow_percent() -> None:
    assert point_positions(_variable(control_points=3)) == pytest.approx([0.25, 0.5, 0.75])
    placed = _variable(control_points=2, vp_1=Param("10", 10.0), vp_2=Param("80", 80.0))
    assert point_positions(placed) == pytest.approx([0.1, 0.8])


def test_law_is_sorted_by_position() -> None:
    f = _variable(
        control_points=2,
        vp_1=Param("70", 70.0),
        vp_2=Param("20", 20.0),
        vr_1_1=Param("4", 4.0),
        vr_1_2=Param("1", 1.0),
    )
    law = radius_law(f, Item("e", None, 1), 2.0)  # type: ignore[arg-type]
    assert law == pytest.approx([(0.0, 2.0), (0.2, 1.0), (0.7, 4.0), (1.0, 2.0)])


def test_moving_a_point_changes_the_round() -> None:
    volumes = []
    for percent in (25.0, 60.0):
        doc, _ext, _b, refs = _plate_and_refs()
        fid = add_fillet(doc, 1.0, edges=refs)
        f = doc.feature(fid)
        f.params.update(
            {
                "fillet_type": "variable",
                "vr_1_start": Param("1", 1.0),
                "vr_1_end": Param("2", 2.0),
                "control_points": 1,
                "vr_1_1": Param("1", 1.0),
                "vp_1": Param(f"{percent:g}", percent),
            }
        )
        volumes.append(volume(body(rebuild(doc), fid).shape))
    # Holding the small radius further along leaves more material.
    assert volumes[1] > volumes[0]


@pytest.mark.parametrize("bad", [0.0, 100.0, 50.0])
def test_bad_positions_are_errors(bad: float) -> None:
    doc, _ext, _b, refs = _plate_and_refs()
    fid = add_fillet(doc, 1.0, edges=refs)
    f = doc.feature(fid)
    f.params.update(
        {
            "fillet_type": "variable",
            "control_points": 2,
            "vp_1": Param("50", 50.0),
            "vp_2": Param(f"{bad:g}", bad),
        }
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "control point 2" in messages(res)
