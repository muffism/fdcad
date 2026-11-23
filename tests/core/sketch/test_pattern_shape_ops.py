"""Sketch patterns, slots and polygons on small sketches of our own (P2.8 items 8, 9,
11 and 12)."""

from __future__ import annotations

import itertools
import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.core.sketch.ops.geom import geo
from fdcad.core.sketch.ops.pattern import PatternError, circular, linear
from fdcad.core.sketch.ops.shapes import ShapeError, arc_slot, polygon, straight_slot
from fdcad.core.sketch.profiles import BASIS_PLANES, build_profile
from fdcad.core.sketch.solver import SketchStatus, solve
from fdcad.core.sketch.topology import check


def _origin(sk: Sketch) -> str:
    o = sk.add_point(0, 0, construction=True)
    sk.relate("fixed", o)
    return o


def _circles(sk: Sketch) -> list[Circle]:
    return [e for e in sk.entities.values() if isinstance(e, Circle)]


def test_linear_grid_follows_the_original_and_skips() -> None:
    sk = Sketch()
    _origin(sk)
    c = sk.add_circle(10, 0, 2)
    dof = solve(sk).dof
    res = linear(
        sk, [c], 4, 10, 0, 2, 8, math.pi / 2, skip={(2, 1)}, add_dimensions=True, fix_direction=True
    )
    assert len(res.copies) == 6
    centres = sorted(sk.xy(e.center) for e in _circles(sk))
    places = [(round(x, 9), round(y, 9)) for x, y in centres]
    assert (20.0, 8.0) in places  # place (1, 1)
    assert (30.0, 8.0) not in places  # place (2, 1) is skipped
    out = solve(sk)
    assert out.solved and out.status is not SketchStatus.OVER and out.dof == dof
    # Sizes and spacing follow: a new radius and spacing reach every copy.
    sk.dimension("radius", [c], Param("3", 3))
    sk.dimensions[0].param = Param("12", 12.0)
    assert solve(sk).solved
    assert all(e.radius == pytest.approx(3) for e in _circles(sk))
    xs = sorted({round(sk.xy(e.center)[0], 6) for e in _circles(sk)})
    assert [b - a for a, b in itertools.pairwise(xs)] == pytest.approx([12, 12, 12])


def test_linear_needs_two_instances_and_a_spacing() -> None:
    sk = Sketch()
    c = sk.add_circle(0, 0, 1)
    with pytest.raises(PatternError):
        linear(sk, [c], 1, 5, 0)
    with pytest.raises(PatternError):
        linear(sk, [c], 3, 0, 0)


def test_circular_pattern_around_the_origin() -> None:
    sk = Sketch()
    o = _origin(sk)
    lid = sk.add_line(10, 0, 15, 0)
    res = circular(sk, [lid], (0, 0), 6, add_dimensions=True, centre_point=o, skip={2})
    assert len(res.copies) == 4
    ends = [geo(sk, i).a for i in res.copies]
    angles = sorted(round(math.degrees(math.atan2(y, x))) % 360 for x, y in ends)
    assert angles == [60, 180, 240, 300]
    out = solve(sk)
    assert out.solved and out.status is not SketchStatus.OVER


def test_circular_partial_angle_unequal_spacing() -> None:
    sk = Sketch()
    c = sk.add_circle(10, 0, 1)
    circular(sk, [c], (0, 0), 3, total=math.radians(30), equal_spacing=False)
    angles = sorted(
        round(math.degrees(math.atan2(*reversed(sk.xy(e.center))))) for e in _circles(sk)
    )
    assert angles == [0, 30, 60]


def test_straight_slot_shape_and_profile() -> None:
    sk = Sketch()
    res = straight_slot(sk, (0, 0), (20, 0), 6, add_dimensions=True)
    assert [type(sk.entities[i]).__name__ for i in res.curves] == ["Line", "Arc", "Line", "Arc"]
    out = solve(sk)
    assert out.solved and out.status is not SketchStatus.OVER and out.dof == 3
    assert not check(sk)
    profile = build_profile(sk, BASIS_PLANES["xy"])
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(profile.faces[0], props)
    assert props.Mass() == pytest.approx(20 * 6 + math.pi * 9, rel=1e-6)


def test_slot_width_dimension_drives_the_caps() -> None:
    sk = Sketch()
    straight_slot(sk, (0, 0), (20, 0), 6, add_dimensions=True, length_mode="overall")
    overall = sk.dimensions[1]
    assert overall.measure_to and overall.param.value == pytest.approx(26)
    sk.dimensions[0].param = Param("8", 8.0)
    assert solve(sk).solved
    arcs = [e for e in sk.entities.values() if isinstance(e, Arc) and not e.construction]
    assert all(sk.radius(a.id) == pytest.approx(4) for a in arcs)


def test_centre_slot_has_a_midpoint() -> None:
    sk = Sketch()
    res = straight_slot(sk, (-10, 0), (10, 0), 4, centre=(0, 0))
    assert res.centre is not None
    assert any(r.type == "midpoint" and r.entities[0] == res.centre for r in sk.relations)


def test_arc_slot() -> None:
    sk = Sketch()
    res = arc_slot(sk, (0, 0), (20, 0), (0, 20), True, 4, add_dimensions=True)
    outer, _cap_end, inner, _cap_start = res.curves
    assert geo(sk, outer).r == pytest.approx(22) and geo(sk, inner).r == pytest.approx(18)
    out = solve(sk)
    assert out.solved and out.status is not SketchStatus.OVER and out.dof == 4
    assert not check(sk)
    with pytest.raises(ShapeError):
        arc_slot(Sketch(), (0, 0), (2, 0), (0, 2), True, 5)


@pytest.mark.parametrize("inscribed", [True, False])
def test_polygon(inscribed: bool) -> None:
    sk = Sketch()
    res = polygon(sk, (0, 0), (10, 0), 6, inscribed)
    assert len(res.curves) == 6
    lengths = {round(geo(sk, i).length, 9) for i in res.curves}
    side = 10.0 if inscribed else 20 / math.sqrt(3)
    assert lengths == {round(side, 9)}
    out = solve(sk)
    assert out.solved and out.dof == 4 and out.status is SketchStatus.UNDER
    assert all(isinstance(sk.entities[i], Line) for i in res.curves)
    with pytest.raises(ShapeError):
        polygon(Sketch(), (0, 0), (1, 0), 41)
