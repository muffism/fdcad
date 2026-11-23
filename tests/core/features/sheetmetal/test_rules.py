"""Sheet metal rule library (TR332, D1111)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.sheetmetal.rules import (
    RuleError,
    apply_rule,
    load_rules,
    rule_of,
    save_rules,
)
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import build, folder, plate, sheet_doc


def test_save_load_and_apply_a_rule(tmp_path: Path) -> None:
    source = sheet_doc(3.0, 2.0, kerf=Param("0.2", 0.2))
    rule = rule_of(source.feature(folder(source)), "Steel")
    path = tmp_path / "shared" / "rules.json"
    save_rules(path, {"Steel 3 mm": rule})
    rules = load_rules(path)
    assert set(rules) == {"Steel 3 mm"} and rules["Steel 3 mm"]["material"] == "Steel"
    doc = sheet_doc(1.0, 1.0)
    plate(doc)
    fid = folder(doc)
    edited = apply_rule(doc.feature(fid), "Steel 3 mm", rules["Steel 3 mm"])
    doc.features[[f.id for f in doc.features].index(fid)] = edited
    assert edited.params["rule_name"] == "Steel 3 mm"
    assert edited.params["thickness"] == Param("3", 3.0)
    assert edited.params["kerf"].value == pytest.approx(0.2)
    assert measure(build(doc).body.shape)["volume"] == pytest.approx(100 * 60 * 3)


def test_missing_and_broken_libraries(tmp_path: Path) -> None:
    assert load_rules(tmp_path / "none.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuleError, match="cannot be read"):
        load_rules(bad)
    bad.write_text('{"format": 1}', encoding="utf-8")
    with pytest.raises(RuleError, match="no rules"):
        load_rules(bad)
