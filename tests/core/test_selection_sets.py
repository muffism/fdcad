"""Selection sets (TR94, D944)."""

from __future__ import annotations

import pytest
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

from fdcad.core.appearance import Target, with_color
from fdcad.core.naming.names import faces_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.selection_sets import (
    KEY,
    SelectionSetError,
    names_for,
    resolve,
    sets_of,
    users_of,
    with_set,
)
from tests.core.features.phase3_parts import block_with_hole_and_boss
from tests.core.features.test_features import body


def _part():  # type: ignore[no-untyped-def]
    doc, ids = block_with_hole_and_boss()
    named = body(rebuild(doc), ids["boss"])
    return doc, ids, named


def _store(doc, *sets) -> None:  # type: ignore[no-untyped-def]
    out: list = []
    for s in sets:
        out = with_set(out, s)
    doc.extra[KEY] = out


def test_picked_items_come_back_by_name() -> None:
    doc, _ids, named = _part()
    from OCP.TopExp import TopExp_Explorer

    face = faces_of(named.shape)[0]
    exp = TopExp_Explorer(named.shape, TopAbs_EDGE)
    edge = exp.Current()
    names = names_for(named, [face, edge, face])
    assert len(names) == 2
    _store(doc, {"name": "Mine", "items": [*names, "nothing/here"]})
    found = resolve(doc, named, "Mine")
    assert found.missing == 1
    assert any(s.IsSame(face) for s in found.shapes)
    assert any(s.IsSame(edge) for s in found.shapes)


def test_rules_and_combinations() -> None:
    doc, ids, named = _part()
    boss_faces = [f for n, f in named.faces if n.startswith(f"{ids['boss']}/")]
    assert boss_faces
    doc.appearance = with_color(doc.appearance, Target("feature", ids["boss"]), "#FF0000")
    _store(
        doc,
        {"name": "Boss", "rule": {"kind": "feature", "feature": ids["boss"]}},
        {"name": "Red", "rule": {"kind": "colour", "colour": "#ff0000"}},
        {"name": "Long", "rule": {"kind": "edge_length", "min": 30.0}},
        {"name": "All", "rule": {"kind": "feature", "feature": ids["plate"]}},
        {"name": "Both", "combine": {"op": "union", "of": ["Boss", "All"]}},
        {"name": "NotBoss", "combine": {"op": "subtract", "of": ["Both", "Boss"]}},
        {"name": "RedBoss", "combine": {"op": "intersect", "of": ["Boss", "Red"]}},
    )
    boss = resolve(doc, named, "Boss").shapes
    assert len(boss) == len({id(f) for f in boss})
    red = resolve(doc, named, "Red").shapes
    assert red and all(any(r.IsSame(b) for b in boss) for r in red)
    assert all(s.ShapeType() == TopAbs_EDGE for s in resolve(doc, named, "Long").shapes)
    both = resolve(doc, named, "Both").shapes
    not_boss = resolve(doc, named, "NotBoss").shapes
    assert not any(any(s.IsSame(b) for b in boss) for s in not_boss)
    assert len(not_boss) < len(both)
    assert all(s.ShapeType() == TopAbs_FACE for s in resolve(doc, named, "RedBoss").shapes)
    assert users_of(sets_of(doc), "Boss") == ["Both", "NotBoss", "RedBoss"]


def test_errors_say_what_to_do() -> None:
    doc, _ids, named = _part()
    _store(doc, {"name": "Loop", "combine": {"op": "union", "of": ["Loop"]}})
    for name in ("Loop", "Missing"):
        with pytest.raises(SelectionSetError) as info:
            resolve(doc, named, name)
        assert ". " in str(info.value)
    with pytest.raises(SelectionSetError):
        with_set([], {"name": "  "})
    # Saving under an existing name replaces that set.
    sets = with_set(with_set([], {"name": "A", "items": []}), {"name": "A", "items": ["x"]})
    assert sets == [{"name": "A", "items": ["x"]}]
