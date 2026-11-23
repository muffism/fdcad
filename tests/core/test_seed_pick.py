"""Seed and boundary pick (TR328, D2108)."""

from __future__ import annotations

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.seed_pick import faces_between
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect


def _faces(shape):  # type: ignore[no-untyped-def]
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = explorer.Current()
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        c = props.CentreOfMass()
        out.append((face, (round(c.X(), 3), round(c.Y(), 3), round(c.Z(), 3))))
        explorer.Next()
    return out


def _pocket():  # type: ignore[no-untyped-def]
    doc, _ext = plate()
    s = Sketch()
    rect(s, 15, 15, 35, 35)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 4.0, operation="cut")
    return RebuildEngine().rebuild(doc).body.shape


def test_the_pocket_between_a_seed_and_a_boundary_face() -> None:
    shape = _pocket()
    faces = _faces(shape)
    ceiling = next(f for f, c in faces if c == (25.0, 25.0, 4.0))
    bottom = next(f for f, c in faces if c[2] == 0.0)
    found = faces_between(shape, ceiling, [bottom])
    assert len(found) == 5  # the pocket's ceiling and its four walls
    assert not any(f.IsSame(bottom) for f in found)


def test_edges_stop_the_fill_and_bad_picks_are_refused() -> None:
    shape = _pocket()
    faces = _faces(shape)
    ceiling = next(f for f, c in faces if c == (25.0, 25.0, 4.0))
    edges = []
    explorer = TopExp_Explorer(ceiling, TopAbs_EDGE)
    while explorer.More():
        edges.append(explorer.Current())
        explorer.Next()
    assert len(faces_between(shape, ceiling, edges)) == 1
    with pytest.raises(ValueError, match="no boundary"):
        faces_between(shape, ceiling, [])
    with pytest.raises(ValueError, match="seed is one of"):
        faces_between(shape, ceiling, [ceiling])
