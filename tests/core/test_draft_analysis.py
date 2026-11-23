"""Draft analysis maths and the draft assistant (PHASE2_SPEC P2.7 item 4, DECISIONS D522)."""

import math

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeSphere

from fdcad.core.draft_analysis import (
    NEEDS,
    NEGATIVE,
    POSITIVE,
    STRADDLE,
    draft_faces,
    faces_needing_draft,
)
from fdcad.core.features.draft import plane_of
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_draft import add_draft
from tests.core.features.test_features import body, plate

UP = (0.0, 0.0, 1.0)


def _normal(face: object) -> tuple[float, float, float]:
    found = plane_of(face)  # type: ignore[arg-type]
    assert found is not None
    return tuple(round(v, 6) for v in found[1])  # type: ignore[return-value]


def test_box_faces_by_group() -> None:
    box = BRepPrimAPI_MakeBox(10, 20, 30).Shape()
    groups = {_normal(f.face): f.group for f in draft_faces(box, UP, math.radians(1))}
    assert groups[(0, 0, 1)] == POSITIVE
    assert groups[(0, 0, -1)] == NEGATIVE
    sides = [g for n, g in groups.items() if n[2] == 0]
    assert sides == [NEEDS] * 4


def test_reversed_pull_swaps_positive_and_negative() -> None:
    box = BRepPrimAPI_MakeBox(10, 20, 30).Shape()
    groups = {_normal(f.face): f.group for f in draft_faces(box, (0, 0, -1), math.radians(1))}
    assert groups[(0, 0, 1)] == NEGATIVE
    assert groups[(0, 0, -1)] == POSITIVE


def test_sphere_straddles() -> None:
    sphere = BRepPrimAPI_MakeSphere(10).Shape()
    found = draft_faces(sphere, UP, math.radians(1))
    assert [f.group for f in found] == [STRADDLE]
    f = found[0]
    assert f.positive + f.negative + f.needs == pytest.approx(1.0)


def test_drafted_sides_have_positive_draft_below_the_angle_only() -> None:
    doc, _ext = plate()
    fid = add_draft(doc, [], propagation="all")  # 5 degrees
    shape = body(rebuild(doc), fid).shape
    small = [f.group for f in draft_faces(shape, UP, math.radians(3))]
    assert small.count(POSITIVE) == 5 and small.count(NEEDS) == 0
    large = [f.group for f in draft_faces(shape, UP, math.radians(10))]
    assert large.count(NEEDS) == 4


def test_assistant_finds_the_vertical_sides() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    found = faces_needing_draft(b.shape, UP, math.radians(1))
    names = sorted(b.primary_name(f) or "" for f in found)
    assert names == [f"{ext}/side/e5", f"{ext}/side/e6", f"{ext}/side/e7", f"{ext}/side/e8"]
