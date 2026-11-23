"""Cuts and joins made only where the tool is, on large bodies (D2601).

The face limit is lowered so small shapes take the local path; every result is compared
with the kernel's own boolean: material, faces, validity and the history of each face.
"""

from collections.abc import Iterator

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut as KernelCut
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse as KernelFuse
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Shape

from fdcad.core import local_boolean
from fdcad.core.naming.names import carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse


@pytest.fixture(autouse=True)
def _small_bodies(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(local_boolean, "MIN_FACES", 0)
    monkeypatch.setattr(local_boolean, "BIG_FACE_EDGES", 8)  # the plate's top is "big"
    monkeypatch.setattr(local_boolean, "MAX_NEAR_SHARE", 1.0)
    monkeypatch.delenv(local_boolean.CHECK_ENV, raising=False)
    local_boolean.forget()
    local_boolean.STATS.clear()
    yield
    local_boolean.forget()


def _volume(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-7)
    return float(props.Mass())


def _cyl(x: float, y: float, z: float, r: float, h: float) -> TopoDS_Shape:
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), r, h).Shape()


def _box(x: float, y: float, z: float, dx: float, dy: float, dz: float) -> TopoDS_Shape:
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def _plate() -> TopoDS_Shape:
    """A 100 x 60 x 10 plate with twelve holes in its top, so the top is a big face."""
    plate = _box(0, 0, 0, 100, 60, 10)
    for i in range(6):
        for j in range(2):
            plate = KernelCut(plate, _cyl(10 + 15 * i, 15 + 30 * j, -1, 2, 12)).Shape()
    return plate


def _same(kind: str, body: TopoDS_Shape, tool: TopoDS_Shape) -> TopoDS_Shape:
    """Make the boolean both ways; assert the local one ran and matches the kernel's."""
    local_op = (BRepAlgoAPI_Cut if kind == "cut" else BRepAlgoAPI_Fuse)(body, tool)
    assert "_local" in local_op.__dict__, local_boolean.STATS
    kernel_op = (KernelCut if kind == "cut" else KernelFuse)(body, tool)
    mine, theirs = local_op.Shape(), kernel_op.Shape()
    assert _volume(mine) == pytest.approx(_volume(theirs), rel=1e-9, abs=1e-9)
    assert len(faces_of(mine)) == len(faces_of(theirs))
    assert BRepCheck_Analyzer(mine).IsValid()
    # The history names the faces (D2601): every name lands on a face of the same size
    # in the same place. (Where the kernel keeps a tool face itself, the local splitter
    # may give an equal copy; the name follows it either way.)
    named = [(f"b{i}", f) for i, f in enumerate(faces_of(body))]
    named += [(f"t{i}", f) for i, f in enumerate(faces_of(tool))]
    assert _where(carry(named, local_op.History()), mine) == _where(
        carry(named, kernel_op.History()), theirs
    )
    return mine


def _where(
    named: list[tuple[str, TopoDS_Shape]], shape: TopoDS_Shape
) -> dict[str, tuple[float, ...]]:
    kept = restrict(named, shape, "left")
    out = {}
    for name, face in kept:
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        c = props.CentreOfMass()
        out[name] = tuple(round(v, 6) for v in (props.Mass(), c.X(), c.Y(), c.Z()))
    return out


CASES = [
    ("through hole", "cut", lambda: _cyl(50, 30, -5, 3, 20)),
    ("blind hole", "cut", lambda: _cyl(50, 30, 5, 3, 10)),
    ("pocket flush with the top", "cut", lambda: _box(45, 25, 5, 10, 8, 5)),
    ("hole that meets a hole", "cut", lambda: _cyl(13, 15, 4, 2.5, 10)),
    ("slot across the edge", "cut", lambda: _box(-5, 25, 5, 20, 10, 10)),
    ("notch at a corner", "cut", lambda: _box(95, 55, 5, 10, 10, 10)),
    ("boss on the top", "fuse", lambda: _cyl(50, 30, 10, 4, 6)),
    ("boss half sunk", "fuse", lambda: _cyl(50, 30, 6, 4, 8)),
    ("block on the side", "fuse", lambda: _box(100, 20, 0, 10, 20, 10)),
    ("rib across the top", "fuse", lambda: _box(20, 28, 10, 60, 4, 5)),
]


@pytest.mark.parametrize(("name", "kind", "tool"), CASES, ids=[c[0] for c in CASES])
def test_a_local_boolean_matches_the_kernel(name: str, kind: str, tool) -> None:  # type: ignore[no-untyped-def]
    _same(kind, _plate(), tool())


def test_cuts_in_a_row_reuse_the_face_index_and_stay_right() -> None:
    body = _plate()
    for x in (20, 35, 50, 65, 80):
        body = _same("cut", body, _cyl(x, 30, 3, 1.5, 10))
    assert local_boolean.STATS.get("cut") == 5


@pytest.mark.parametrize(
    ("name", "kind", "tool", "why"),
    [
        ("a hollow inside", "cut", lambda: _box(40, 20, 3, 10, 10, 4), "no tool face kept"),
        ("far away", "cut", lambda: _box(300, 0, 0, 5, 5, 5), "none near"),
        ("cut in two", "cut", lambda: _box(48, -5, -5, 4, 70, 20), "split in two"),
        ("a lump beside", "fuse", lambda: _box(120, 0, 0, 5, 5, 5), "none near"),
    ],
    ids=["hollow", "far", "in two", "lump"],
)
def test_what_it_cannot_do_goes_to_the_kernel(name: str, kind: str, tool, why: str) -> None:  # type: ignore[no-untyped-def]
    body = _plate()
    op = (BRepAlgoAPI_Cut if kind == "cut" else BRepAlgoAPI_Fuse)(body, tool())
    assert "_local" not in op.__dict__
    assert op.IsDone() and BRepCheck_Analyzer(op.Shape()).IsValid()
    kernel = (KernelCut if kind == "cut" else KernelFuse)(body, tool()).Shape()
    assert _volume(op.Shape()) == pytest.approx(_volume(kernel), rel=1e-9)


def test_small_bodies_and_lists_of_tools_go_to_the_kernel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_boolean, "MIN_FACES", 1000)
    op = BRepAlgoAPI_Cut(_plate(), _cyl(50, 30, -5, 3, 20))
    assert "_local" not in op.__dict__  # 41 faces: the kernel is quick on it


def test_it_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(local_boolean.DISABLE_ENV, "0")
    op = BRepAlgoAPI_Cut(_plate(), _cyl(50, 30, -5, 3, 20))
    assert "_local" not in op.__dict__


def test_check_mode_compares_with_the_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(local_boolean.CHECK_ENV, "1")
    op = BRepAlgoAPI_Cut(_plate(), _cyl(50, 30, -5, 3, 20))
    assert "_local" in op.__dict__  # and no LocalMismatchError was raised


def _perforated(holes: int) -> TopoDS_Shape:
    """A 210 x 110 x 20 plate with ``holes`` blind holes cut in one boolean: two faces a
    hole, all their rims on the top face."""
    from fdcad.core.features.solids import compound

    plate = _box(0, 0, 0, 210, 110, 20)
    tools = [_cyl(10 + 15 * (i % 14), 10 + 15 * (i // 14), 12, 3, 10) for i in range(holes)]
    return KernelCut(plate, compound(tools)).Shape()


def test_a_plate_of_some_hundred_faces_is_cut_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    """D2664: below 1000 faces a cut goes local only when every face near the tool is a
    big flat face stood in for by a patch; the kernel rebuilt all of that face's holes
    in each cut."""
    monkeypatch.setattr(local_boolean, "MIN_FACES", 1000)
    monkeypatch.setattr(local_boolean, "BIG_FACE_EDGES", 40)
    monkeypatch.setattr(local_boolean, "MAX_NEAR_SHARE", 0.3)
    plate = _perforated(56)
    assert len(faces_of(plate)) == 6 + 2 * 56
    _same("cut", plate, _cyl(100, 100, 12, 2, 10))  # a hole among the others: local
    assert local_boolean.STATS.get("cut") == 1
    op = BRepAlgoAPI_Cut(plate, _box(-5, 40, 5, 10, 10, 20))  # at the plate's outline
    assert "_local" not in op.__dict__
    assert local_boolean.STATS.get("not only big faces near") == 1
    small = _perforated(40)  # 86 faces: the kernel's
    op = BRepAlgoAPI_Cut(small, _cyl(100, 100, 12, 2, 10))
    assert "_local" not in op.__dict__
    assert local_boolean.STATS.get("cut") == 1
