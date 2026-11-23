"""Real faces where a section cuts the part, for Measure (TR213, D2502)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.GProp import GProp_GProps

from fdcad.core.section import PlaneSetting, Reference, SectionState
from fdcad.core.section_faces import cut_faces

FRONT = Reference((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
RIGHT = Reference((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0))


def _area(faces: list) -> float:
    total = 0.0
    for f in faces:
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, props)
        total += props.Mass()
    return total


def _box(x: float, y: float, z: float, dx: float, dy: float, dz: float):  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def test_one_plane_cuts_a_box() -> None:
    box = _box(0, 0, 0, 20, 10, 6)
    faces = cut_faces(box, SectionState([PlaneSetting(FRONT, offset=3.0)]))
    assert len(faces) == 1 and _area(faces) == pytest.approx(200.0)


def test_corner_cut_gives_two_faces() -> None:
    box = _box(-10, -5, -10, 20, 10, 20)
    state = SectionState([PlaneSetting(FRONT), PlaneSetting(RIGHT, "right")])
    faces = cut_faces(box, state)
    # The corner x > 0, z > 0 goes: each plane shows a 10 by 10 face.
    assert len(faces) == 2 and _area(faces) == pytest.approx(200.0)


def test_body_kept_whole_has_no_cut_face() -> None:
    two = BRepAlgoAPI_Fuse(_box(0, 0, 0, 10, 10, 10), _box(30, 0, 0, 10, 10, 10)).Shape()
    state = SectionState([PlaneSetting(FRONT, offset=5.0)])
    assert _area(cut_faces(two, state)) == pytest.approx(200.0)
    state.whole = [1]
    assert _area(cut_faces(two, state)) == pytest.approx(100.0)


def test_opposite_zones_and_misses() -> None:
    box = _box(-10, -5, -10, 20, 10, 20)
    state = SectionState(
        [PlaneSetting(FRONT), PlaneSetting(RIGHT, "right")], zones=[(True, True), (False, False)]
    )
    assert _area(cut_faces(box, state)) == pytest.approx(400.0)
    assert cut_faces(None, state) == []
    away = SectionState([PlaneSetting(FRONT, offset=50.0)])
    assert cut_faces(box, away) == []


def test_measure_reads_a_cut_face() -> None:
    from fdcad.core.measure import measure

    box = _box(0, 0, 0, 20, 10, 6)
    faces = cut_faces(box, SectionState([PlaneSetting(FRONT, offset=3.0)]))
    values = {v.key: v.value for v in measure(faces).values}
    assert values["area"] == pytest.approx(200.0)
