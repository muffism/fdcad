"""Changing the part's units never changes geometry (audit D3 item 1, D702)."""

from __future__ import annotations

import pytest

from fdcad.core import configurations as configs
from fdcad.core.document.model import Document, Param, Variable, new_document
from fdcad.core.equations import solve
from fdcad.core.equations.unit_change import change_units, keep_value
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.units import Kind, UnitSystem
from fdcad.samples.builder import FRONT, SketchBuilder, add_feature, add_sketch, length
from fdcad.samples.make import SAMPLE_DIR, measure

MM, IN = UnitSystem.MM, UnitSystem.IN


def _block() -> Document:
    """The audit's case: a 20 by 10 rectangle extruded 25, all bare numbers, in mm."""
    doc = new_document()
    sk = SketchBuilder()
    sk.rectangle(0, 0, 20, 10)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Sketch 1")
    add_feature(
        doc, "extrude", "Extrude 1", sid, operation="boss", end_condition="blind",
        depth=length("25", 25.0), reverse=False,
    )  # fmt: skip
    return doc


def _size(doc: Document) -> list[float]:
    """Volume, then the bounding box corners."""
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    m = measure(report.body.shape)
    return [float(m["volume"]), *m["bbox"]]


def test_switching_to_inches_keeps_the_body() -> None:
    doc = _block()
    before = _size(doc)
    assert before[0] == pytest.approx(20 * 10 * 25)
    change_units(doc, IN)
    assert _size(doc) == pytest.approx(before)
    change_units(doc, MM)
    assert _size(doc) == pytest.approx(before)


def test_bare_numbers_get_the_old_unit_and_the_file_reopens_the_same() -> None:
    doc = _block()
    change_units(doc, IN)
    assert doc.features[-1].params["depth"].expr == "25mm"
    again = fdef.loads(fdef.dumps(doc))
    assert again.units is IN
    assert _size(again) == pytest.approx(_size(_block()))


@pytest.mark.parametrize(
    ("text", "kind", "expected"),
    [
        ("25", Kind.LENGTH, "25mm"),
        (" 2.5 ", Kind.LENGTH, "2.5mm"),
        ("25mm", Kind.LENGTH, "25mm"),  # has a unit: no change
        ("1in", Kind.LENGTH, "1in"),
        ("=W*2", Kind.LENGTH, "=W*2"),  # a length times a number keeps its unit
        ("=N*2", Kind.LENGTH, "=(N*2)*1mm"),  # a plain number result
        ("10+5mm", Kind.LENGTH, "15.0mm"),  # mixed outside a formula
        ("30", Kind.ANGLE, "30"),  # angles do not depend on the part unit
        ("4", Kind.NUMBER, "4"),
        ("=nope", Kind.LENGTH, "=nope"),  # an error stays as typed
    ],
)
def test_keep_value(text: str, kind: Kind, expected: str) -> None:
    names = {"W": (Kind.LENGTH, 10.0), "N": (Kind.NUMBER, 3.0)}
    assert keep_value(text, kind, MM, IN, names) == expected


def test_inch_part_switching_to_mm_keeps_inches() -> None:
    assert keep_value("2", Kind.LENGTH, IN, MM, {}) == "2in"


def test_variables_configurations_and_table_cells_are_kept() -> None:
    doc = _block()
    ext = doc.features[-1]
    doc.variables.append(Variable("Gap", Kind.LENGTH, "3", 3.0))
    doc.variables.append(Variable("Count", Kind.NUMBER, "4", 4.0))
    ext.params["depth"] = Param("=Count*5", 20.0)
    configs.add(doc, "Long")
    long = next(i for i in configs.items(doc) if i["name"] == "Long")
    long["overrides"][f"{ext.id}.depth"] = {"expr": "40", "value": 40.0}
    before = solve(doc).values
    change_units(doc, IN)
    after = solve(doc).values
    for key, value in before.items():
        assert after[key] == pytest.approx(value), key
    assert next(v for v in doc.variables if v.name == "Count").expr == "4"
    assert next(v for v in doc.variables if v.name == "Gap").expr == "3mm"
    long = next(i for i in configs.items(doc) if i["name"] == "Long")
    assert long["overrides"][f"{ext.id}.depth"]["expr"] == "40mm"


def test_samples_keep_their_volume_in_the_other_unit() -> None:
    for name in ("bracket.fdprt", "plate_with_holes.fdprt", "sheet_metal_bracket.fdprt"):
        doc = fdef.loads((SAMPLE_DIR / name).read_text(encoding="utf-8"))
        before = _size(doc)
        change_units(doc, IN if doc.units is MM else MM)
        assert _size(doc) == pytest.approx(before, rel=1e-9), name
