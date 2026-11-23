"""Enclosed cavities (TR284, D772)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.cavities import cavity_volume, enclosed_voids


def _box(x0, y0, z0, x1, y1, z1):  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), gp_Pnt(x1, y1, z1)).Shape()


def _hollow_cube():  # type: ignore[no-untyped-def]
    """A 20 mm cube with a closed 10 mm cube void in its middle."""
    return BRepAlgoAPI_Cut(_box(0, 0, 0, 20, 20, 20), _box(5, 5, 5, 15, 15, 15)).Shape()


def test_a_closed_void_is_found_with_its_volume() -> None:
    (void,) = enclosed_voids(_hollow_cube())
    assert void.body == 0
    assert void.volume == pytest.approx(1000.0)
    assert void.centre == pytest.approx((10.0, 10.0, 10.0))


def test_a_solid_or_an_open_pocket_has_no_void() -> None:
    assert enclosed_voids(_box(0, 0, 0, 10, 10, 10)) == []
    cup = BRepAlgoAPI_Cut(_box(0, 0, 0, 20, 20, 20), _box(5, 5, 5, 15, 15, 25)).Shape()
    assert enclosed_voids(cup) == []  # open at the top


def test_the_volume_a_cup_holds() -> None:
    cup = BRepAlgoAPI_Cut(_box(0, 0, 0, 20, 20, 20), _box(5, 5, 5, 15, 15, 25)).Shape()
    from fdcad.core.naming.names import faces_of

    faces = faces_of(cup)
    volume, shape = cavity_volume(cup, faces, (0.0, 0.0, 20.0), (0.0, 0.0, 1.0))
    assert volume == pytest.approx(10 * 10 * 15)
    assert shape is not None
    # The opening lower down holds less.
    lower, _s = cavity_volume(cup, faces, (0.0, 0.0, 12.0), (0.0, 0.0, 1.0))
    assert lower == pytest.approx(10 * 10 * 7)


def test_the_drain_hole_reaches_the_void(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from fdcad.core.cavities import drain_hole
    from fdcad.core.features.base import FeatureState
    from fdcad.core.features.import_step import part_from_step
    from fdcad.core.io.export import export_step
    from fdcad.core.rebuild.engine import RebuildEngine

    step = tmp_path / "hollow.step"
    export_step(_hollow_cube(), step)
    doc = part_from_step("hollow.step", step.read_bytes())
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    (void,) = enclosed_voids(report.body.shape)
    feature = drain_hole(doc, report.body, void)
    assert feature is not None and feature.type == "hole"
    assert feature.params["end_condition"] == "up_to_next"
    doc.features.append(feature)
    after = RebuildEngine().rebuild(doc)
    assert after.results[feature.id].state is not FeatureState.ERROR
    assert after.body is not None and enclosed_voids(after.body.shape) == []  # drained
