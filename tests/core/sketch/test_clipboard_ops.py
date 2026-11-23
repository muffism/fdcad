"""Copy and paste of sketch entities, and sketches moved to another plane (TR3, TR9, D685)."""

from __future__ import annotations

import json

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Circle, Line, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.ops.clipboard import (
    ClipError,
    clip_from_data,
    clip_to_data,
    extract,
    insert,
    unlink_model,
)
from fdcad.core.sketch.solver import solve


def _slot_like() -> tuple[Sketch, list[str], str]:
    """Two joined lines with a length dimension, and an origin they are tied to."""
    sk = Sketch()
    o = sk.add_point(0, 0, construction=True)
    sk.relate("fixed", o)
    a = sk.add_line(0, 0, 10, 0)
    b = sk.add_line(10, 0, 10, 5)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    sk.relate("coincident", la.p1, o)
    sk.relate("horizontal", a)
    sk.dimension("distance", [a], Param("10mm", 10))
    return sk, [a, b], o


def test_extract_keeps_inner_relations_and_counts_the_rest() -> None:
    sk, picks, _o = _slot_like()
    clip = extract(sk, picks)
    copied = sketch_from_data(clip.data)
    assert len([e for e in copied.entities.values() if isinstance(e, Line)]) == 2
    assert sorted(r.type for r in copied.relations) == ["coincident", "horizontal"]
    assert len(copied.dimensions) == 1
    assert clip.left_behind == 1  # the tie to the origin
    assert clip.anchor == pytest.approx((5, 2.5))


def test_insert_with_new_ids_at_an_offset_and_it_solves() -> None:
    sk, picks, _o = _slot_like()
    clip = extract(sk, picks)
    before = set(sk.entities)
    made = insert(sk, clip, (20, 0))
    assert len(made) == 2 and not set(made) & before
    line = sk.entities[made[0]]
    assert isinstance(line, Line)
    assert sk.xy(line.p1) == pytest.approx((20, 0))
    assert len(sk.dimensions) == 2 and sk.dimensions[1].id != sk.dimensions[0].id
    assert solve(sk).solved


def test_clip_goes_through_json() -> None:
    sk, picks, _o = _slot_like()
    text = json.dumps(clip_to_data(extract(sk, picks)))
    clip = clip_from_data(json.loads(text))
    made = insert(sk, clip, (0, 10))
    assert len(made) == 2
    with pytest.raises(ClipError):
        clip_from_data({"nothing": 1})
    with pytest.raises(ClipError):
        extract(sk, [])


def test_circle_radius_and_origin_left_out() -> None:
    sk, _picks, o = _slot_like()
    c = sk.add_circle(3, 3, 1.5)
    clip = extract(sk, [c, o])
    made = insert(sk, clip, (1, 1))
    assert len(made) == 1
    circle = sk.entities[made[0]]
    assert isinstance(circle, Circle) and circle.radius == 1.5


def _linked() -> Sketch:
    sk = Sketch()
    o = sk.add_point(0, 0, construction=True)
    sk.relate("fixed", o)
    helper = sk.add_point(5, 5, construction=True)
    p = sk.entities[helper]
    p.source = {"kind": "vertex", "name": "vertex(f6/a|f6/b|f6/c)"}  # type: ignore[union-attr]
    sk.relate("fixed", helper)
    line = sk.add_line(5, 5, 15, 5)
    ln = sk.entities[line]
    assert isinstance(ln, Line)
    sk.relate("coincident", ln.p1, helper)
    return sk


def test_unlink_removes_part_links_and_their_relations() -> None:
    sk = _linked()
    out = unlink_model(sketch_to_data(sk))
    back = sketch_from_data(out.data)
    assert out.links == 1 and out.removed == 2  # the Fix and the coincident
    assert not any(getattr(e, "source", None) for e in back.entities.values())
    assert len(back.entities) == len(sk.entities) - 1
    assert solve(back).solved


def test_unlink_keep_leaves_fixed_copies() -> None:
    sk = _linked()
    out = unlink_model(sketch_to_data(sk), keep=True)
    back = sketch_from_data(out.data)
    assert out.removed == 0 and out.links == 1
    assert len(back.relations) == len(sk.relations)
    assert not any(getattr(e, "source", None) for e in back.entities.values())
