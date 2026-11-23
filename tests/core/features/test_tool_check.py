"""The check after a boss or cut sized to the tool, not to the part (D2619, IDEAS 50).

The volume check of D705 has a slack of 1 percent of the part and is off above 100
faces, so a small boss or cut that the kernel loses on a large part went unseen.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut as KernelCut
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse as KernelFuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

import fdcad.core.features.solids as solids_module
import fdcad.core.tool_check as tool_check
from fdcad.core.features.base import FeatureError
from fdcad.core.features.solids import combine, compound, solids, volume_of
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.tool_check import tools_kept


def _named(shape: Any, fid: str = "f1") -> NamedShape:
    return NamedShape(shape, restrict([], shape, fid))


def _box(x: float, y: float, z: float, dx: float, dy: float, dz: float) -> Any:
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def _plate() -> NamedShape:
    """A 200 by 200 by 10 plate: a 5 mm boss on it is 0.03 percent of its volume."""
    return _named(_box(0, 0, 0, 200, 200, 10))


def _holed_plate() -> NamedShape:
    """A plate with 40 holes: 126 faces, more than the volume check looks at."""
    body = _plate()
    pins = [
        BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(15 + 20 * i, 15 + 40 * j, -1), gp_Dir(0, 0, 1)), 3, 12
        ).Shape()
        for i in range(8)
        for j in range(5)
    ]
    return combine("f0", "Holes", body, _named(compound(pins), "f0"), "cut", pieces=True)


def _losing(kind: type) -> type:
    """A kernel boolean that reports success and gives the part back unchanged."""

    class Losing(kind):  # type: ignore[misc, valid-type]
        def Shape(self) -> Any:  # noqa: N802 (the kernel's name)
            return self.Arguments().First()

    return Losing


def test_a_lost_boss_on_a_large_part_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(solids_module, "BRepAlgoAPI_Fuse", _losing(KernelFuse))
    boss = _named(_box(50, 50, 10, 5, 5, 5), "f2")
    with pytest.raises(FeatureError, match="left out the material it adds"):
        combine("f2", "Boss", _plate(), boss, "boss")


def test_a_lost_cut_on_a_body_of_many_faces_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _holed_plate()
    monkeypatch.setattr(solids_module, "BRepAlgoAPI_Cut", _losing(KernelCut))
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(190, 190, -1), gp_Dir(0, 0, 1)), 2, 12)
    with pytest.raises(FeatureError, match="left material where it cuts"):
        combine("f2", "Cut", body, _named(hole.Shape(), "f2"), "cut")


def test_a_boss_the_kernel_loses_in_a_compound_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real fault of D1049, with the repair of the inside out solid taken away:
    the kernel fuses an inside out solid in a compound as the room around it."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    shape = _box(50, 50, 8, 5, 5, 5)
    shell = TopoDS.Shell(TopExp_Explorer(shape, TopAbs_SHELL).Current().Reversed())
    flagged = BRepBuilderAPI_MakeSolid(shell).Solid().Reversed()
    monkeypatch.setattr(solids_module, "right_side_out", lambda s: s)
    tool = _named(compound([flagged]), "f2")
    with pytest.raises(FeatureError, match="left out the material it adds"):
        combine("f2", "Badge", _plate(), tool, "boss")


@pytest.mark.parametrize(
    ("operation", "tool", "change"),
    [
        ("boss", (50, 50, 10, 5, 5, 5), 125.0),  # on the top face
        ("boss", (195, 50, 5, 10, 5, 10), 5 * 5 * 10 + 5 * 5 * 5),  # over the edge
        ("boss", (50, 50, 2, 5, 5, 5), 0.0),  # inside the plate: nothing to add
        ("cut", (50, 50, 5, 5, 5, 10), -125.0),  # a pocket from the top
        ("cut", (50, 50, 20, 5, 5, 5), 0.0),  # above the plate: nothing to remove
    ],
)
def test_right_booleans_pass(operation: str, tool: tuple[float, ...], change: float) -> None:
    body = _plate()
    result = combine("f2", "Feature", body, _named(_box(*tool), "f2"), operation)
    assert volume_of(result.shape) == pytest.approx(400000.0 + change, rel=1e-9)


def test_a_pattern_of_bosses_on_many_faces_passes() -> None:
    body = _holed_plate()
    pegs = compound([_box(5 + 20 * i, 180, 10, 4, 4, 6) for i in range(10)])
    result = combine("f2", "Pegs", body, _named(pegs, "f2"), "boss", pieces=True)
    assert len(solids(result.shape)) == 1


def test_the_check_costs_little_and_asks_the_kernel_nothing_when_right(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The happy path counts ray crossings on a few faces and never builds the kernel's
    classifier, which costs about 2 ms on a body of 200 faces (D2614)."""
    body = _holed_plate()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(190, 190, -1), gp_Dir(0, 0, 1)), 2, 12)
    tool = hole.Shape()
    op = KernelCut(body.shape, tool)
    result = op.Shape()
    asked: list[int] = []
    real = tool_check.BRepClass3d_SolidClassifier
    monkeypatch.setattr(
        tool_check, "BRepClass3d_SolidClassifier", lambda *a: asked.append(1) or real(*a)
    )
    assert tools_kept("cut", body.shape, [tool], result)  # first: every face is measured
    start = time.perf_counter()
    for _ in range(20):
        assert tools_kept("cut", body.shape, [tool], result)
    each = (time.perf_counter() - start) / 20
    assert asked == []
    assert each < 0.005  # about 0.5 ms on the owner's PC
