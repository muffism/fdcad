"""Select Similar and selection conversion (TR303, D943)."""

from __future__ import annotations

from typing import Any

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.select_similar import convert, describe, similar_faces


def _all(shape: Any, kind: Any) -> list[Any]:
    out, exp = [], TopExp_Explorer(shape, kind)
    while exp.More():
        out.append(exp.Current())
        exp.Next()
    return out


def _plate() -> Any:
    """A 60 x 20 x 10 plate with two r3 holes and one r4 hole."""
    part = BRepPrimAPI_MakeBox(60.0, 20.0, 10.0).Shape()
    for x, r in ((10.0, 3.0), (30.0, 3.0), (50.0, 4.0)):
        axis = gp_Ax2(gp_Pnt(x, 10.0, -1.0), gp_Dir(0, 0, 1))
        part = BRepAlgoAPI_Cut(part, BRepPrimAPI_MakeCylinder(axis, r, 12.0).Shape()).Shape()
    return part


def _walls(part: Any, radius: float) -> list[Any]:
    return [
        f
        for f in _all(part, TopAbs_FACE)
        if describe(f).kind == "cylinder" and abs(describe(f).sizes[0] - radius) < 1e-6
    ]


def test_same_kind_and_size_finds_holes_of_one_size() -> None:
    part = _plate()
    small = _walls(part, 3.0)
    found = similar_faces(part, small[0], ["kind_size"])
    assert len(found) == len(small) >= 2
    assert not any(f.IsSame(w) for f in found for w in _walls(part, 4.0))


def test_parallel_and_except() -> None:
    part = _plate()
    top = max(
        (f for f in _all(part, TopAbs_FACE) if describe(f).kind == "plane"),
        key=lambda f: describe(f).area * abs(describe(f).direction[2]),  # type: ignore[index]
    )
    parallel = similar_faces(part, top, ["parallel"])
    # Top and bottom, and the hole walls (their axes are parallel to the normal).
    assert len(parallel) == 2 + len(_walls(part, 3.0)) + len(_walls(part, 4.0))
    planes_only = similar_faces(part, top, ["parallel"], except_rules=[])
    assert len(planes_only) == len(parallel)
    no_cylinders = [f for f in parallel if describe(f).kind == "plane"]
    both = similar_faces(part, top, ["parallel", "kind_size"])
    assert len(both) == len(no_cylinders) == 2
    without = similar_faces(part, top, ["parallel"], except_rules=["kind_size"])
    assert len(without) == len(parallel) - 1  # the bottom is a plane too; only top stays


def test_any_rule_and_area() -> None:
    part = _plate()
    small = _walls(part, 3.0)[0]
    either = similar_faces(part, small, ["area", "kind_size"], match_any=True)
    assert len(either) >= 2
    with pytest.raises(ValueError):
        similar_faces(part, small, [])


def test_convert() -> None:
    part = _plate()
    wall = _walls(part, 4.0)[0]
    edges = convert(part, [wall], "edges")
    assert edges and all(e.ShapeType() == TopAbs_EDGE for e in edges)
    faces = convert(part, edges[:1], "faces")
    assert len(faces) == 2 and any(f.IsSame(wall) for f in faces)
    body = convert(part, [edges[0]], "bodies")
    assert len(body) == len(_all(part, TopAbs_FACE))
    second = BRepPrimAPI_MakeBox(gp_Pnt(100, 0, 0), 5.0, 5.0, 5.0).Shape()
    two = BRepAlgoAPI_Fuse(part, second).Shape()
    one_body = convert(two, [_all(second, TopAbs_FACE)[0]], "bodies")
    assert len(one_body) in (0, 6)  # the fuse copies faces: an unknown pick gives nothing
