"""An extra offset in a reference's own axes (TR149, D980)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.extra_placement import apply, has_extra, perpendicular


def _f(**params: object) -> Feature:
    return Feature("f9", "ref_plane", "Plane", params=dict(params))  # type: ignore[arg-type]


def test_nothing_set_changes_nothing() -> None:
    f = _f(method="offset")
    assert not has_extra(f)
    assert apply(f, (1.0, 2.0, 3.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)) == (
        (1.0, 2.0, 3.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
    )


def test_offsets_turns_and_flip() -> None:
    f = _f(
        extra_dx=Param("5", 5.0),
        extra_dz=Param("2", 2.0),
        extra_rx=Param("90deg", math.pi / 2),
        extra_flip=True,
    )
    origin, z, x = apply(f, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    assert origin == pytest.approx((5.0, 0.0, 2.0))
    assert x == pytest.approx((1.0, 0.0, 0.0))  # turning about X keeps X
    assert z == pytest.approx((0.0, 1.0, 0.0))  # Z turned to -Y, then flipped


def test_axis_gets_a_square_x() -> None:
    x = perpendicular((0.0, 0.0, 1.0))
    assert abs(x[2]) < 1e-12 and math.isclose(math.hypot(*x), 1.0)


def test_rebuilt_plane_axis_and_frame_take_the_extra() -> None:
    """The extra applies after each method, in a rebuild."""
    from tests.core.features.test_reference_geometry import (
        _add,
        _face,
        _ok,
        _plane_z,
        _plate,
        rebuild,
    )

    doc, ext, _ = _plate()
    plane = _add(
        doc, "ref_plane", {"first": _face(ext, "cap/end")}, method="offset", distance=5, extra_dz=3
    )
    axis = _add(
        doc,
        "ref_axis",
        {"first": {"feature": "f3"}, "second": {"feature": "f4"}},
        method="two_planes",
        extra_dx=2,
    )
    frame = _add(doc, "coord_system", {}, method="angles", x=1, y=2, z=3, extra_dz=4)
    r = rebuild(doc)
    assert _plane_z(_ok(r, plane))[0] == pytest.approx(18.0)
    datum = _ok(r, axis).datum
    assert datum is not None and math.dist(datum.origin, (0, 0, 0)) == pytest.approx(2.0)
    frame_datum = _ok(r, frame).datum
    assert frame_datum is not None and frame_datum.origin[2] == pytest.approx(7.0)
