"""A boss or cut whose tool the kernel made inside out (D1049).

Found on a bike frame (2026-11-12): a head badge wrapped on the head tube built with
no error and added nothing. The kernel had made the badge's solid inside out; the
wrap set the solid's reversed flag, which makes its volume read right, and passed it
on in a compound. The fuse took it for the room around the badge and gave the part
back unchanged.
"""

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED

from fdcad.core.features.solids import combine, compound, right_side_out, solids, volume_of
from fdcad.core.naming.names import NamedShape, restrict


def _box(x: float, size: float) -> NamedShape:
    shape = BRepPrimAPI_MakeBox(gp_Pnt(x, 0.0, 0.0), size, size, size).Shape()
    return NamedShape(shape, restrict([], shape, "f1"))


def _flagged(x: float, size: float):  # type: ignore[no-untyped-def]
    """A box as the old code handed over an inside out solid: shells facing in, the
    reversed flag set, so that its volume reads above zero."""
    shape = BRepPrimAPI_MakeBox(gp_Pnt(x, 0.0, 0.0), size, size, size).Shape()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    shell = TopoDS.Shell(TopExp_Explorer(shape, TopAbs_SHELL).Current().Reversed())
    inside_out = BRepBuilderAPI_MakeSolid(shell).Solid()
    assert volume_of(inside_out) == pytest.approx(-(size**3))
    flagged = inside_out.Reversed()
    assert flagged.Orientation() == TopAbs_REVERSED
    assert volume_of(flagged) == pytest.approx(size**3)
    return flagged


def test_an_inside_out_solid_is_made_again_facing_out() -> None:
    fixed = right_side_out(_flagged(0.0, 10.0))
    assert fixed.Orientation() == TopAbs_FORWARD
    assert volume_of(fixed) == pytest.approx(1000.0)
    whole = right_side_out(compound([_flagged(0.0, 10.0), _box(20.0, 5.0).shape]))
    parts = solids(whole)
    assert [p.Orientation() for p in parts] == [TopAbs_FORWARD, TopAbs_FORWARD]
    assert sorted(round(volume_of(p), 6) for p in parts) == [125.0, 1000.0]
    good = _box(0.0, 10.0).shape
    assert right_side_out(good).IsSame(good)  # a good solid is not touched


@pytest.mark.parametrize("wrapped", [False, True])
def test_a_boss_with_an_inside_out_tool_adds_its_material(wrapped: bool) -> None:
    body = _box(0.0, 10.0)
    solid = _flagged(8.0, 10.0)  # overlaps the body by 2 mm
    shape = compound([solid]) if wrapped else solid
    tool = NamedShape(shape, restrict([], shape, "f2"))
    result = combine("f2", "Boss", body, tool, "boss")
    assert volume_of(result.shape) == pytest.approx(1000.0 + 800.0, rel=1e-9)


@pytest.mark.parametrize("wrapped", [False, True])
def test_a_cut_with_an_inside_out_tool_removes_its_material(wrapped: bool) -> None:
    body = _box(0.0, 10.0)
    solid = _flagged(8.0, 10.0)
    shape = compound([solid]) if wrapped else solid
    tool = NamedShape(shape, restrict([], shape, "f2"))
    result = combine("f2", "Cut", body, tool, "cut")
    assert volume_of(result.shape) == pytest.approx(1000.0 - 200.0, rel=1e-9)
