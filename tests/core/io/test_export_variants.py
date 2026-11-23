"""Batch export over variable values (TR368, D904)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.document.model import Param, Variable, new_document
from fdcad.core.io.export_variants import (
    BatchError,
    combinations,
    default_template,
    export_variants,
    parse_values,
)
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import Kind
from tests.core.features.test_features import add_extrude, add_sketch, rect


def test_values_and_combinations() -> None:
    assert parse_values("10, 20,30") == ["10", "20", "30"]
    assert parse_values("10..20 step 5") == ["10", "15", "20"]
    assert parse_values("3..1") == ["3", "2", "1"]
    with pytest.raises(BatchError):
        parse_values("1..10 step -1")
    combos = combinations({"w": ["1", "2"], "h": ["5", "6", "7"]})
    assert len(combos) == 6 and combos[0] == {"w": "1", "h": "5"}
    assert default_template(["w", "h"]) == "{part} w{w} h{h}"


def test_each_combination_is_exported(tmp_path: Path) -> None:
    doc = new_document()
    doc.variables.append(Variable("depth", Kind.LENGTH, "5", 5.0))
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    doc.feature(fid).params["depth"] = Param("depth", 5.0)
    combos = combinations({"depth": parse_values("5, 8")})
    out = export_variants(doc, combos, tmp_path, "step", "Block", "{part} {depth}")
    assert [o.ok for o in out] == [True, True]
    assert (tmp_path / "Block 5.step").exists() and (tmp_path / "Block 8.step").exists()
    assert "depth = 8" in (tmp_path / "Export log.txt").read_text(encoding="utf-8")
    assert doc.variables[0].expr == "5"  # the part itself is unchanged
