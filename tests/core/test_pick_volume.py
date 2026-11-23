"""Pick inside, outside or touching a box, cylinder or sphere (TR329, D2208)."""

from __future__ import annotations

import numpy as np
import pytest

from fdcad.core.pick_volume import PickVolume, PickVolumeError, pick_in_volume
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.test_goal_seek import block


def _shape():  # type: ignore[no-untyped-def]
    report = RebuildEngine().rebuild(block(10.0))  # 20 x 20 x 10 from the origin
    assert report.body is not None
    return report.body.shape


def test_contains_for_each_shape() -> None:
    pts = np.array([[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 0.0, 6.0]])
    assert PickVolume("sphere", (0, 0, 0), radius=5.0).contains(pts).tolist() == [
        True,
        True,
        False,
    ]
    box = PickVolume("box", (0, 0, 0), size=(10.0, 10.0, 10.0))
    assert box.contains(pts).tolist() == [True, True, False]
    cyl = PickVolume("cylinder", (0, 0, 0), size=(0, 0, 14.0), radius=3.0, axis=(0, 0, 1))
    assert cyl.contains(pts).tolist() == [True, False, True]
    with pytest.raises(PickVolumeError, match="above zero"):
        PickVolume("box", (0, 0, 0), size=(0.0, 1.0, 1.0)).check()


def test_faces_and_vertices_inside_outside_and_touching() -> None:
    shape = _shape()
    near = PickVolume("box", (0.0, 0.0, 5.0), size=(2.0, 2.0, 12.0))  # round the Z edge at 0, 0
    assert len(pick_in_volume(shape, near, "inside", "vertex")) == 2
    assert len(pick_in_volume(shape, near, "inside", "edge")) == 1
    assert len(pick_in_volume(shape, near, "outside", "vertex")) == 6
    touching = pick_in_volume(shape, near, "touching", "face")
    assert len(touching) == 4  # the two sides at the edge, the top and the bottom
    everything = PickVolume("sphere", (10.0, 10.0, 5.0), radius=50.0)
    assert len(pick_in_volume(shape, everything, "inside", "face")) == 6
