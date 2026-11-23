"""Tests for the Phase 0 kernel smoke checks."""

import pytest
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.kernel_check import make_test_cube


def _volume(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def test_cube_is_valid_solid_with_expected_volume() -> None:
    cube = make_test_cube(10.0)
    assert BRepCheck_Analyzer(cube).IsValid()
    assert _volume(cube) == pytest.approx(1000.0, rel=1e-6)


@pytest.mark.parametrize("size", [0.0, -1.0])
def test_cube_rejects_non_positive_size(size: float) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        make_test_cube(size)
