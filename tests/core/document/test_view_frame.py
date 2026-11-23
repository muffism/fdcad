"""The part's own view directions (TR333, D955)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document import view_frame as vf

FRONT = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
TOP = ((0.0, 1.0, 0.0), (0.0, 0.0, -1.0))


def _close(a: vf.Vec3, b: vf.Vec3) -> bool:
    return all(abs(x - y) < 1e-9 for x, y in zip(a, b, strict=True))


def test_front_set_to_the_right_side() -> None:
    eye, up = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)  # looking from the right
    frame = vf.frame_for(FRONT, eye, up)
    assert _close(vf.turn(frame, FRONT[0]), eye) and _close(vf.turn(frame, FRONT[1]), up)
    # Top turns with it and stays square to the new front.
    top_eye, _top_up = (vf.turn(frame, v) for v in TOP)
    assert abs(vf._dot(top_eye, eye)) < 1e-9
    assert _close(top_eye, (0.0, 1.0, 0.0))


def test_tilted_camera_is_made_square() -> None:
    eye = (0.3, 0.2, 1.0)
    frame = vf.frame_for(FRONT, eye, (0.1, 1.0, 0.0))
    for row in frame:  # a rotation: unit rows
        assert math.isclose(sum(x * x for x in row), 1.0, abs_tol=1e-9)
    turned = vf.turn(frame, FRONT[0])
    n = math.sqrt(sum(c * c for c in eye))
    assert _close(turned, tuple(c / n for c in eye))


def test_store_and_reset() -> None:
    extra: dict = {}
    frame = vf.frame_for(FRONT, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    extra[vf.KEY] = vf.with_frame(extra, frame)
    extra[vf.KEY] = vf.with_home(extra, ((0.0, 0.0, 2.0), (0.0, 1.0, 0.0)))
    assert vf.frame_of(extra) == tuple(tuple(r) for r in frame)
    assert vf.home_of(extra) == ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
    extra[vf.KEY] = vf.with_frame(extra, None)
    assert vf.frame_of(extra) == vf.IDENTITY and vf.home_of(extra) is not None
    assert vf.with_home(extra, None) is None  # nothing left: the key goes


def test_damaged_values_fall_back() -> None:
    assert vf.frame_of({vf.KEY: {"frame": [[1, 2], "x"]}}) == vf.IDENTITY
    assert vf.home_of({vf.KEY: {"home": {"eye": [1, 2, 3]}}}) is None
    with pytest.raises(vf.ViewFrameError, match="Turn the view"):
        vf.frame_for(FRONT, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
