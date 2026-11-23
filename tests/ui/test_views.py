"""Standard views and normal to."""

from __future__ import annotations

import math

import pytest

from fdcad.ui.viewport.views import STANDARD_VIEWS, view_for_normal


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_standard_views_with_y_up() -> None:
    # Seven from Phase 1, plus Dimetric and Trimetric (TR14, D690).
    assert set(STANDARD_VIEWS) == {
        "front",
        "back",
        "left",
        "right",
        "top",
        "bottom",
        "iso",
        "dimetric",
        "trimetric",
    }
    for name, (eye, up) in STANDARD_VIEWS.items():
        n = math.sqrt(_dot(eye, eye))
        if name not in ("iso", "dimetric", "trimetric"):
            # The camera makes the up vector of the angled views square to the eye.
            assert abs(_dot(eye, up)) < 1e-9 * n
        assert up[1] >= 0 or name == "bottom"


@pytest.mark.parametrize(
    "normal",
    [(0, 0, 1), (0, 1, 0), (0, -1, 0), (1, 0, 0), (0.3, 0.4, 0.866), (0, 0, -1)],
)
def test_normal_to_looks_at_the_face(normal: tuple[float, float, float]) -> None:
    eye, up = view_for_normal(normal)
    n = math.sqrt(_dot(normal, normal))
    assert _dot(eye, normal) == pytest.approx(n)
    assert abs(_dot(eye, up)) < 1e-9
    assert _dot(up, up) == pytest.approx(1.0)


def test_top_face_matches_top_view() -> None:
    assert view_for_normal((0, 1, 0)) == STANDARD_VIEWS["top"]
    eye, up = view_for_normal((0, 0, 1))
    assert (eye, up) == STANDARD_VIEWS["front"]


def test_normal_to_snaps_up_to_a_model_axis() -> None:
    tilted_iso_up = (-0.41, 0.82, -0.41)
    _eye, up = view_for_normal((0, 0, 1), tilted_iso_up)
    assert up == pytest.approx((0.0, 1.0, 0.0))
    _eye, up = view_for_normal((1, 0, 0), (0.1, 0.2, 0.97))
    assert up == pytest.approx((0.0, 0.0, 1.0))
