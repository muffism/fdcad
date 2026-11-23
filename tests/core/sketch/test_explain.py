"""Explain a relation (TR237, D920)."""

from __future__ import annotations

from fdcad.core.sketch.explain import explain, item_name
from fdcad.core.sketch.model import RELATION_TYPES, Relation, Sketch


def test_every_relation_type_is_explained() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(0, 5, 10, 5)
    c = s.add_circle(0, 0, 3)
    assert item_name(s, a) == f"line {a}" and item_name(s, c) == f"circle {c}"
    for rtype in RELATION_TYPES:
        text = explain(s, Relation(rtype, [a, b, c, a], 2.0))
        assert text.endswith(".") and "relation between" not in text, rtype
    assert (
        explain(s, Relation("parallel", [a, b]))
        == f"Keeps line {a} and line {b} pointing the same way."
    )
    assert "2 times" in explain(s, Relation("length_ratio", [a, b], 2.0))


def test_gone_items_and_switched_off() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    text = explain(s, Relation("perpendicular", [a, "e99"], off=True))
    assert "missing item e99" in text and "is gone" in text and "switched off" in text
