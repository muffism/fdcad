"""Relations and dimensions switched off (TR109, D829)."""

from __future__ import annotations

import pytest

from fdcad.core import configurations as configs
from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.sketch.model import Dimension, Line, Point, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import solve


def _line() -> tuple[Sketch, str]:
    s = Sketch()
    lid = s.add_line(0, 0, 10, 3)
    return s, lid


def test_an_off_relation_and_dimension_do_nothing_and_are_kept() -> None:
    s, lid = _line()
    rel = s.relate("horizontal", lid)
    rel.off = True
    line = s.entities[lid]
    assert isinstance(line, Line)
    s.dimensions.append(Dimension("d1", "distance", [line.p1, line.p2], Param("20", 20.0)))
    s.dimensions[0].off = True
    solve(s)
    a, b = s.entities[line.p1], s.entities[line.p2]
    assert isinstance(a, Point) and isinstance(b, Point)
    assert b.y - a.y == pytest.approx(3)  # not made horizontal
    back = sketch_from_data(sketch_to_data(s))
    assert back.relations[0].off and back.dimensions[0].off
    rel.off = False
    solve(s)
    assert b.y - a.y == pytest.approx(0, abs=1e-7)
    plain = sketch_to_data(_line()[0])
    assert all("off" not in r for r in plain.get("relations", []))  # old files unchanged


def test_off_in_one_configuration_only() -> None:
    doc = new_document()
    s, lid = _line()
    s.relate("horizontal", lid)
    fid = doc.new_feature_id()
    data = sketch_to_data(s)
    doc.features.append(
        Feature(fid, "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=data)
    )
    path = f"{fid}.r0:off"
    assert configs.get_value(doc, path) is False
    configs.add(doc, "Loose")
    configs.activate(doc, "Loose")
    configs.set_scoped(doc, path, True, "this")
    assert doc.feature(fid).data["relations"][0]["off"] is True
    configs.activate(doc, "Default")
    assert "off" not in doc.feature(fid).data["relations"][0]
