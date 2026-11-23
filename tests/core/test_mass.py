"""Mass properties (TR79, D764)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.mass import mass_properties, report
from fdcad.core.measure import Frame

# A 20 x 10 x 4 mm block of steel (7.85 g/cm3) with a corner at the origin.
A, B, C = 20.0, 10.0, 4.0
STEEL = 7.85


def _block():  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), A, B, C).Shape()


def test_block_values_match_the_formulas() -> None:
    props = mass_properties([_block()], STEEL)
    volume = A * B * C
    mass = volume * STEEL / 1000
    assert props.volume == pytest.approx(volume)
    assert props.area == pytest.approx(2 * (A * B + B * C + A * C))
    assert props.mass == pytest.approx(mass)
    assert props.centre == pytest.approx((A / 2, B / 2, C / 2))
    ix = mass * (B**2 + C**2) / 12
    iy = mass * (A**2 + C**2) / 12
    iz = mass * (A**2 + B**2) / 12
    assert sorted(props.principal) == pytest.approx(sorted([ix, iy, iz]))
    assert props.inertia[0][0] == pytest.approx(ix)
    assert props.inertia[0][1] == pytest.approx(0.0, abs=1e-9)


def test_inertia_about_a_corner_frame() -> None:
    props = mass_properties([_block()], STEEL)
    mass = props.mass
    corner = props.inertia_in(Frame())
    assert corner[2][2] == pytest.approx(mass * (A**2 + B**2) / 3)  # about the z edge
    assert corner[0][1] == pytest.approx(-mass * A * B / 4)  # product of inertia
    # A turned frame: x along the model y, y along -x.
    turned = props.inertia_in(Frame((A / 2, B / 2, C / 2), (0, 1, 0), (-1, 0, 0), (0, 0, 1)))
    assert turned[0][0] == pytest.approx(props.inertia[1][1])


def test_two_bodies_and_a_cylinder() -> None:
    pin = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(50, 0, 0), gp_Dir(0, 0, 1)), 2.0, 10.0).Shape()
    both = mass_properties([_block(), pin], 1.0)
    assert both.bodies == 2
    assert both.volume == pytest.approx(A * B * C + math.pi * 4 * 10)
    assert A / 2 < both.centre[0] < 50


def test_bad_inputs() -> None:
    with pytest.raises(ValueError, match="no body"):
        mass_properties([], 1.0)
    with pytest.raises(ValueError, match="density"):
        mass_properties([_block()], 0.0)


def test_report_rows_in_both_units() -> None:
    props = mass_properties([_block()], STEEL)
    rows = dict(report(props, inch=False))
    assert rows["Mass"] == f"{props.mass:.6g} g"
    assert rows["Volume"] == "800 mm^3"
    assert rows["Centre of mass"] == "10, 5, 2 mm"
    inch = dict(report(props, inch=True, frame=Frame(), frame_name="Origin"))
    assert inch["Volume"].endswith("in^3") and inch["Mass"].endswith(" lb")
    assert any("about Origin" in label for label in inch)


def test_report_shows_rounding_noise_as_zero() -> None:
    """A value a thousand million times smaller than its neighbours is noise (D1034)."""
    from dataclasses import replace

    from fdcad.core.mass import MassProperties, report, tidy

    assert tidy([19.2455, 14.16, 4.22718e-16]) == [19.2455, 14.16, 0.0]
    assert tidy([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]
    assert tidy([1.0, 1e-3]) == [1.0, 1e-3]  # small but real values stay
    props = MassProperties(
        bodies=1,
        density=1.24,
        mass=39.35,
        volume=31735.2,
        area=10809.0,
        centre=(19.2455, 14.16, 4.22718e-16),
        inertia=(
            (13703.4, 6095.31, 4.7e-13),
            (6095.31, 18808.2, 3.9e-13),
            (4.7e-13, 3.9e-13, 21948.1),
        ),
        principal=(9647.66, 21948.1, 22864.0),
        axes=((-0.8325, 0.554, 4.3e-17), (0.0, -7.7e-17, 1.0), (-0.554, -0.8325, -6.4e-17)),
    )
    rows = dict(report(props, inch=False))
    assert rows["Centre of mass"] == "19.2455, 14.16, 0 mm"
    assert "e-" not in " ".join(rows.values())
    far = replace(props, centre=(5000.0, 0.02, 1e-14))
    assert dict(report(far, inch=False))["Centre of mass"] == "5000, 0.02, 0 mm"
