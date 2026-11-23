"""Hole and thread list (TR316, D924)."""

from __future__ import annotations

import pytest

from fdcad.core.hole_table import rows, to_csv
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.units import UnitSystem
from tests.core.features.test_hole import add_hole, on_top, points_sketch


def test_one_row_per_hole_with_tags_and_csv() -> None:
    doc, _ext, sk, top = on_top([(10, 10), (40, 40)])
    add_hole(doc, sk, face=top, diameter=5.0, depth=6.0)
    sk2 = points_sketch(doc, top, [(25, 25)])
    add_hole(doc, sk2, face=top, diameter=4.0, end_condition="through_all")
    results = rebuild(doc)
    found = rows(doc, results)
    assert [r.tag for r in found] == ["A1", "A2", "B1"]
    assert found[0].count == 2 and found[0].diameter == 5.0 and found[0].depth == 6.0
    assert found[2].depth == "Through" and found[2].kind == "Simple"
    assert {round(r.position[2], 6) for r in found} == {10.0}
    xs = sorted(round(r.position[0], 6) for r in found[:2])
    assert xs == pytest.approx([10.0, 40.0])
    text = to_csv(found, UnitSystem.MM)
    lines = text.strip().splitlines()
    assert lines[0].startswith("Tag,Feature,Type,Size,Diameter (mm),Depth (mm)")
    assert len(lines) == 4 and lines[3].split(",")[5] == "Through"
    inch = to_csv(found, UnitSystem.IN).splitlines()
    assert "(in)" in inch[0] and inch[1].split(",")[4] == f"{5 / 25.4:.4f}"


def test_suppressed_and_empty() -> None:
    doc, _ext, sk, top = on_top([(10, 10)])
    fid = add_hole(doc, sk, face=top, diameter=5.0, depth=6.0)
    doc.feature(fid).suppressed = True
    assert rows(doc, rebuild(doc)) == []
