"""The bike frame opened in 51 s (D1090). These check that the three slow steps stay
fast and still give the same answers: finding a removed face again, working out what a
patched face group added, and keeping the pieces of a projected sketch on its face."""

from __future__ import annotations

import pytest
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.features import direct, wrap_project
from fdcad.core.features.booleans import boolean_shape
from fdcad.core.features.solids import precise_volume
from fdcad.core.naming import resolve
from fdcad.core.naming.names import faces_of
from tests.core.features.test_direct_editing import BASE, boss_faces, built


def _box(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float):  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), gp_Pnt(x1, y1, z1)).Shape()


def test_patch_measures_only_faces_near_the_removed_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every face of the part was measured once per removed face: 1.4 s on the frame.
    _doc, _ids, body = built()
    calls: list[object] = []
    real = resolve.face_snapshot
    monkeypatch.setattr(resolve, "face_snapshot", lambda f: (calls.append(f), real(f))[1])
    faces = boss_faces(body)
    patched = direct.patch(body, faces, "t", "Test", [str(i) for i in range(len(faces))])
    assert precise_volume(patched.shape) == pytest.approx(BASE - 600, rel=1e-9)
    every = len(faces) * len(faces_of(patched.shape))
    assert len(calls) < every / 2, (len(calls), every)


def test_a_boss_added_is_worked_out_near_it() -> None:
    # The two whole part cuts took 4.7 s on the frame; worked out in a box round the
    # boss they give the same 600 cubic mm.
    _doc, _ids, body = built()
    faces = boss_faces(body)
    patched = direct.patch(body, faces, "t", "Test", [str(i) for i in range(len(faces))])
    near = direct._near_difference(body.shape, patched.shape, faces)
    assert near is not None
    added, removed = near
    assert added is not None and precise_volume(added) == pytest.approx(600, rel=1e-9)
    assert removed is None or precise_volume(removed) < 1e-6
    whole = boolean_shape("cut", body.shape, patched.shape)
    assert whole is not None and precise_volume(whole) == pytest.approx(600, rel=1e-9)


def test_a_change_past_the_box_is_worked_out_on_the_whole_part() -> None:
    # A change that reaches a wall of the box may be cut short there, so the whole
    # part is used instead.
    from fdcad.core.naming.names import centroid

    before = _box(0, 0, 0, 100, 10, 10)
    after = _box(0, 0, 0, 40, 10, 10)  # 60 mm gone, from the end face at x = 100 back

    def end(x: float) -> list:  # type: ignore[type-arg]
        return [f for f in faces_of(before) if abs(centroid(f)[0] - x) < 1e-9]

    assert direct._near_difference(before, after, end(100)) is None  # runs past the box
    assert direct._near_difference(before, after, end(0)) is None  # all outside the box


def test_a_piece_on_the_face_is_found_without_the_slow_distance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The distance from a solid to a large face took 4.5 s for ten letters.
    block = _box(0, 0, 0, 50, 50, 10)
    top = next(f for f in faces_of(block) if abs(_z(f) - 10) < 1e-9)
    touching = _box(5, 5, 9, 10, 10, 10)
    near = _box(5, 5, 10.01, 10, 10, 11)
    far = _box(100, 100, 0, 110, 110, 10)
    for piece in (touching, near, far):
        full = BRepExtrema_DistShapeShape(piece, top)
        assert wrap_project._touches(piece, top) == (full.Value() <= 1e-4)
    solid_calls: list[object] = []
    from OCP import BRepExtrema  # _touches imports it when called

    original = BRepExtrema.BRepExtrema_DistShapeShape

    def counting(a, b, *rest):  # type: ignore[no-untyped-def]
        solid_calls.append(a)
        return original(a, b, *rest)

    monkeypatch.setattr(BRepExtrema, "BRepExtrema_DistShapeShape", counting)
    assert wrap_project._touches(touching, top)
    assert all(c is not touching for c in solid_calls)  # a corner answered it
    solid_calls.clear()
    assert not wrap_project._touches(far, top)
    assert solid_calls == []  # the boxes answered it


def _z(face) -> float:  # type: ignore[no-untyped-def]
    from fdcad.core.naming.names import centroid

    return centroid(face)[2]


def test_separate_sketch_regions_are_cut_in_one_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    sweeps = [_box(x, 0, -5, x + 5, 5, 20) for x in (0, 10, 20)]
    slab = _box(-10, -10, 9, 40, 20, 10)
    calls: list[object] = []
    real = wrap_project.BRepAlgoAPI_Common
    monkeypatch.setattr(
        wrap_project, "BRepAlgoAPI_Common", lambda a, b: (calls.append(a), real(a, b))[1]
    )
    pieces = wrap_project._cut_to_skin(sweeps, slab)
    assert len(calls) == 1
    assert len(pieces) == 3
    assert sum(precise_volume(p) for p in pieces) == pytest.approx(75, rel=1e-9)
    calls.clear()
    overlapping = [_box(0, 0, -5, 6, 5, 20), _box(5, 0, -5, 10, 5, 20)]
    wrap_project._cut_to_skin(overlapping, slab)
    assert len(calls) == 2  # sweeps that meet are cut one at a time, as before


def test_patching_one_body_leaves_the_other_bodies_as_they_are() -> None:
    # D1101: the kernel rebuilt every body of the part, and two gearbox plates whose
    # faces touch came back split another way: their faces were renamed by a Remove
    # Fillets on a block elsewhere, and a cached rebuild differed from a full one.
    from fdcad.core.features.solids import compound, solids
    from fdcad.core.naming.names import NamedShape, centroid
    from tests.core.features.test_boolean_named_bodies import _plate_and_locked_blocks

    _doc, _ids, body = built()
    locked = [s for s in solids(_plate_and_locked_blocks().shape) if centroid(s)[0] > 90]
    far, near = locked  # two blocks locked with teeth: their faces touch
    names = [*body.faces, *[(f"far/{i}", f) for i, f in enumerate(faces_of(far))]]
    names += [(f"near/{i}", f) for i, f in enumerate(faces_of(near))]
    part = NamedShape(compound([*solids(body.shape), far, near]), names)
    blocks = precise_volume(far) + precise_volume(near)
    faces = boss_faces(body)
    patched = direct.patch(part, faces, "t", "Test", [str(i) for i in range(len(faces))])
    kept = solids(patched.shape)
    assert len(kept) == 3
    assert any(s.IsSame(far) for s in kept) and any(s.IsSame(near) for s in kept)
    before = {n: f for n, f in names if n.startswith(("far/", "near/"))}
    after = {n: f for n, f in patched.faces if n.startswith(("far/", "near/"))}
    assert before.keys() == after.keys()
    assert all(after[n].IsSame(f) for n, f in before.items())
    assert precise_volume(patched.shape) == pytest.approx(BASE - 600 + blocks, rel=1e-9)


def test_patching_one_face_of_a_hole_in_two_says_it_changed_nothing() -> None:
    # D1104: a hole whose wall was in two faces (its top had been raised) was "filled" by
    # removing one of them; the other grew down into its place, the hole stayed, and the
    # feature said nothing.
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.gp import gp_Ax2, gp_Dir

    from fdcad.core.features.base import FeatureError
    from fdcad.core.naming.names import NamedShape

    block = _box(0, 0, 0, 40, 40, 20)
    lower = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 20, -1), gp_Dir(0, 0, 1)), 5, 11).Shape()
    upper = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 20, 10), gp_Dir(0, 0, 1)), 5, 11).Shape()
    shape = BRepAlgoAPI_Cut(BRepAlgoAPI_Cut(block, lower).Shape(), upper).Shape()
    part = NamedShape(shape, [(f"f/{i}", f) for i, f in enumerate(faces_of(shape))])
    walls = [f for f in faces_of(shape) if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder]
    assert len(walls) == 2
    with pytest.raises(FeatureError, match="changed nothing"):
        direct.patch(part, walls[:1], "t", "Fill", ["f/wall"])
    filled = direct.patch(part, walls, "t", "Fill", ["f/a", "f/b"])
    assert precise_volume(filled.shape) == pytest.approx(40 * 40 * 20, rel=1e-9)


def _plate_with_holes() -> tuple[object, object]:
    """A 200 x 200 x 10 plate with 25 x 25 small through holes: more than 600 faces."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir
    from OCP.TopoDS import TopoDS_Compound

    from fdcad.core.naming.names import NamedShape, centroid

    builder, holes = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(holes)
    for i in range(25):
        for j in range(25):
            axis = gp_Ax2(gp_Pnt(6 + i * 7.8, 6 + j * 7.8, -1), gp_Dir(0, 0, 1))
            builder.Add(holes, BRepPrimAPI_MakeCylinder(axis, 1.5, 12).Shape())
    plate = BRepAlgoAPI_Cut(_box(0, 0, 0, 200, 200, 10), holes).Shape()
    named = NamedShape(plate, [(f"f{k}", f) for k, f in enumerate(faces_of(plate))])
    top = next(f for f in faces_of(plate) if abs(centroid(f)[2] - 10) < 1e-6)
    return named, top


def test_moving_one_face_of_a_large_body_adds_a_slab(monkeypatch: pytest.MonkeyPatch) -> None:
    # The kernel's offset of the whole body took over three minutes on the machine bed
    # to lift one face 3 mm (D1105). On a large body whose neighbours meet the face
    # square, a slab is added on it instead, giving the same solid.
    body, top = _plate_with_holes()
    assert len(faces_of(body.shape)) > getattr(direct, "SLAB_FIRST_FACES", 600)  # type: ignore[attr-defined]

    def whole_body_offset(*_a: object) -> None:
        raise AssertionError("the whole body offset ran")

    monkeypatch.setattr(direct, "_carry_by_history", whole_body_offset)
    before = precise_volume(body.shape)  # type: ignore[attr-defined]
    moved = direct.offset_faces(body, [(top, 3.0)], "t", "Test", ["top"])  # type: ignore[arg-type, list-item]
    holes = 25 * 25 * 3.141592653589793 * 1.5**2
    assert precise_volume(moved.shape) == pytest.approx(before + 3 * (200 * 200 - holes), rel=1e-6)
    assert any(n == "top" or "f" in n for n, _f in moved.faces)
