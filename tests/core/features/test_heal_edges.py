"""Heal Edges, the Geometry Check fix for gaps and loose edges (TR262, D1807)."""

from __future__ import annotations

import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.heal_edges import largest_gap
from fdcad.core.geometry_check import check
from fdcad.core.naming.names import NamedShape, restrict
from tests.core.features.phase3_parts import run
from tests.core.features.test_features import volume


def _loose_box() -> NamedShape:
    """A box whose edges claim a 0.05 mm gap (as a loose import does)."""
    shape = BRepPrimAPI_MakeBox(20, 10, 5).Shape()
    builder = BRep_Builder()
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        builder.UpdateEdge(TopoDS.Edge(explorer.Current()), 0.05)
        explorer.Next()
    return NamedShape(shape, restrict([], shape, "imp"))


def test_heal_closes_the_gaps_and_keeps_names() -> None:
    body = _loose_box()
    assert any(i.kind == "gap" for i in check(body.shape)[0])
    res = run("heal_edges", body, {"tolerance": Param("0.1", 0.1)}, {})
    assert res.state is FeatureState.OK
    assert res.body is not None
    assert largest_gap(res.body.shape) < 0.01
    assert not any(i.kind == "gap" for i in check(res.body.shape)[0])
    assert volume(res.body.shape) == pytest.approx(1000, rel=1e-9)
    assert sorted(n for n, _f in res.body.faces) == sorted(n for n, _f in body.faces)


def test_bad_tolerance_is_an_error() -> None:
    res = run("heal_edges", _loose_box(), {"tolerance": Param("0", 0.0)}, {})
    assert res.state is FeatureState.ERROR


def test_healing_does_not_change_the_body_it_was_given() -> None:
    """D1066: found on a gearbox of 318 features. The heal worked on the body where it
    was. A body shares its edges with the results of the features before it, so those
    results were changed too, and some were left not valid."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.TopAbs import TopAbs_VERTEX

    body = _loose_box()
    # Loose corners too: the fixer then finds nothing to replace and hands the same
    # body on, and the tolerance updates after it wrote into the body itself.
    builder = BRep_Builder()
    explorer = TopExp_Explorer(body.shape, TopAbs_VERTEX)
    while explorer.More():
        builder.UpdateVertex(TopoDS.Vertex(explorer.Current()), 0.05)
        explorer.Next()
    res = run("heal_edges", body, {"tolerance": Param("0.1", 0.1)}, {})
    assert res.state is FeatureState.OK and res.body is not None
    assert largest_gap(res.body.shape) < 0.01
    assert largest_gap(body.shape) == pytest.approx(0.05)  # as it was handed in
    assert not res.body.shape.IsSame(body.shape)
    assert BRepCheck_Analyzer(body.shape).IsValid()
    # Every face went to its healed copy, under its own name.
    before = {n: f for n, f in body.faces}
    for name, face in res.body.faces:
        assert not face.IsSame(before[name])


def test_a_body_that_healing_would_break_stays_as_it_was(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """D1066: a body fitted loosely by a deform was valid, and not after the heal.
    Such a body is kept as it was, with a warning. Here the kernel's answer is stood
    in for by a broken one: a box with a face taken out."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepTools import BRepTools_ReShape
    from OCP.TopAbs import TopAbs_FACE

    import fdcad.core.features.heal_edges as module

    real = module.heal

    def breaking(shape, tolerance):  # type: ignore[no-untyped-def]
        fixed, step = real(shape, tolerance)
        edit = BRepTools_ReShape()
        edit.Remove(TopExp_Explorer(fixed, TopAbs_FACE).Current())
        return edit.Apply(fixed), step

    monkeypatch.setattr(module, "heal", breaking)
    body = _loose_box()
    res = run("heal_edges", body, {"tolerance": Param("0.1", 0.1)}, {})
    assert res.state is FeatureState.WARNING
    assert "would be worse after healing" in res.issues[0].message
    assert res.body is not None and res.body.shape.IsSame(body.shape)
    assert BRepCheck_Analyzer(res.body.shape).IsValid()
    assert sorted(n for n, _f in res.body.faces) == sorted(n for n, _f in body.faces)


def test_a_body_that_healing_would_loosen_stays_as_it_was(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """D1066: the old heal left a shaft with an edge 36 mm loose that went in exact.
    A body whose loosest edge would come out looser is kept as it was."""
    import fdcad.core.features.heal_edges as module

    real = module.heal

    def loosening(shape, tolerance):  # type: ignore[no-untyped-def]
        fixed, step = real(shape, tolerance)
        BRep_Builder().UpdateEdge(TopoDS.Edge(TopExp_Explorer(fixed, TopAbs_EDGE).Current()), 3.0)
        return fixed, step

    monkeypatch.setattr(module, "heal", loosening)
    body = _loose_box()
    res = run("heal_edges", body, {"tolerance": Param("0.1", 0.1)}, {})
    assert res.state is FeatureState.WARNING
    assert "would be worse after healing" in res.issues[0].message
    assert res.body is not None and res.body.shape.IsSame(body.shape)
    assert largest_gap(res.body.shape) == pytest.approx(0.05)
