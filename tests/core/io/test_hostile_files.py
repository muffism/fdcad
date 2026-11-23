"""Damaged and hostile part files and formulas (audit D12 items 7 and 8, D709)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.io import fdef
from fdcad.core.io.migrations import FileFormatError
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.samples.make import SAMPLE_DIR


def test_very_deep_nesting_is_a_damaged_file() -> None:
    with pytest.raises(FileFormatError, match="damaged"):
        fdef.loads("[" * 100_000 + "]" * 100_000)


def test_a_number_with_thousands_of_digits_is_a_damaged_file() -> None:
    text = (SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8")
    text = text.replace('"next_id": 11', '"next_id": ' + "9" * 5000, 1)
    with pytest.raises(FileFormatError, match="damaged"):
        fdef.loads(text)


@pytest.mark.parametrize("raw", ['{"format": "fdef", "features": 5}', "[1, 2]", '"text"'])
def test_values_of_the_wrong_form_are_a_damaged_file(raw: str) -> None:
    with pytest.raises(FileFormatError):
        fdef.loads(raw)


def test_a_huge_file_is_refused_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "big.fdprt"
    path.write_text((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(fdef, "MAX_FILE", 100)
    with pytest.raises(FileFormatError, match="larger than FDCAD opens"):
        fdef.load(path)


@pytest.mark.parametrize("text", ["=" + "(" * 5000 + "1" + ")" * 5000, "=" + "-" * 5000 + "1"])
def test_very_deep_formulas_give_a_formula_error(text: str) -> None:
    with pytest.raises(ExpressionError, match="levels deep"):
        evaluate(text, Kind.LENGTH, UnitSystem.MM)
    assert evaluate("=" + "(" * 50 + "2" + ")" * 50, Kind.NUMBER, UnitSystem.MM) == 2


@pytest.mark.parametrize("text", ["=1e308*10", "=floor(1e308*10)", "=10^400"])
def test_infinite_results_give_a_formula_error(text: str) -> None:
    """Audit D3 item 13 (D723): inf was accepted and only the save refused it."""
    with pytest.raises(ExpressionError):
        evaluate(text, Kind.NUMBER, UnitSystem.MM)


def test_a_failed_save_leaves_the_old_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit D3 item 15, spec 2 section 21 item 10 (D723): the new file is flushed and
    read back before it replaces the old one."""
    import os

    path = tmp_path / "part.fdprt"
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    fdef.save(doc, path)
    before = path.read_text(encoding="utf-8")

    def full_disk(_fd: int) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", full_disk)
    doc.features[-1].name = "Changed"
    with pytest.raises(OSError):
        fdef.save(doc, path)
    assert path.read_text(encoding="utf-8") == before
    assert [p.name for p in tmp_path.iterdir()] == ["part.fdprt"]  # no temporary left


def test_ids_are_checked_on_load() -> None:
    """Audit D3 item 7 (D723): repeated ids, a low next id and a dangling rollback."""
    import json

    data = json.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    low = {**data, "next_id": 2, "rollback": "f999"}
    doc = fdef.loads(json.dumps(low))
    assert doc.next_id > max(int(f.id[1:]) for f in doc.features)
    assert doc.rollback is None
    twice = {**data, "features": [*data["features"], data["features"][-1]]}
    with pytest.raises(FileFormatError, match="used twice"):
        fdef.loads(json.dumps(twice))


def test_values_from_a_newer_fdcad_still_open() -> None:
    """Audit D5 item 2, E item 7.10 (D726): one extra key in a parameter made the whole
    file damaged; a list value did too."""
    import json

    data = json.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    feature = next(f for f in data["features"] if f["type"] == "extrude")
    depth = feature["params"]["depth"]
    feature["params"]["depth"] = {**depth, "unit": "mm"}
    feature["params"]["future"] = [1, 2, 3]
    doc = fdef.loads(json.dumps(data))
    ext = doc.feature(feature["id"])
    assert ext.params["depth"].expr == depth["expr"]  # type: ignore[union-attr]
    assert ext.params["future"] == [1, 2, 3]
    again = json.loads(fdef.dumps(doc))
    assert next(f for f in again["features"] if f["id"] == ext.id)["params"]["future"] == [1, 2, 3]


def test_unknown_keys_from_a_newer_fdcad_are_kept() -> None:
    """Audit D5 item 1 (D726): graph nodes, saved views and tree folders lost them."""
    import json

    from fdcad.samples.graphs import SAMPLE_DIR as GRAPHS

    data = json.loads((GRAPHS / "lattice_block.fdprt").read_text(encoding="utf-8"))
    node = data["graphs"][0]["nodes"][0]
    node["colour"] = "red"
    node["ui"]["collapsed"] = True
    data["views"] = [
        {"name": "Mine", "center": [0, 0, 0], "direction": [0, 0, 1], "up": [0, 1, 0],
         "distance": 100, "scale": 1, "lens": "wide"}
    ]  # fmt: skip
    data["tree"] = {"folders": [{"name": "Ribs", "features": [], "open": False}], "pins": [1]}
    again = json.loads(fdef.dumps(fdef.loads(json.dumps(data))))
    kept = again["graphs"][0]["nodes"][0]
    assert kept["colour"] == "red" and kept["ui"]["collapsed"] is True
    assert again["views"][0]["lens"] == "wide"
    assert again["tree"]["folders"][0]["open"] is False and again["tree"]["pins"] == [1]


def test_a_part_with_a_byte_order_mark_opens() -> None:
    """Audit D5 item 5 (D738): a byte order mark made the file "not valid JSON"."""
    text = (SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8")
    assert fdef.loads(chr(0xFEFF) + text).features


def test_a_count_a_hair_off_a_whole_number_is_accepted() -> None:
    """Audit B item 29 (D738): a formula giving 4.9999999 failed "must be a whole number"."""
    from fdcad.core.document.model import Feature, Param
    from fdcad.core.features.linear_pattern import count_of

    f = Feature("f9", "linear_pattern", "Pattern 1", params={"count1": Param("=a", 4.9999999)})
    assert count_of(f, "count1") == 5


def test_a_repeated_key_is_refused() -> None:
    """Audit D5 item 5 (D738): the last of two equal keys won without a word."""
    text = (SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8")
    broken = text.replace('"format"', '"format": "x", "format"', 1)
    with pytest.raises(fdef.FileFormatError, match="appears twice"):
        fdef.loads(broken)


@pytest.mark.parametrize(("text", "suppressed"), [("false", False), ("True", True)])
def test_suppressed_written_as_text(text: str, suppressed: bool) -> None:
    """Audit D5 item 4 (D744): "false" as text read as suppressed."""
    import json

    data = json.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    data["features"][-1]["suppressed"] = text
    assert fdef.loads(json.dumps(data)).features[-1].suppressed is suppressed
    data["features"][-1]["suppressed"] = 3
    with pytest.raises(fdef.FileFormatError):
        fdef.loads(json.dumps(data))


@pytest.mark.parametrize("schema", [0, -1, 1.5, "2", None, 3, 99])
def test_only_known_schema_versions_open(schema: object) -> None:
    """Audit D3 item 25 (D744): only schemas 1 and 2 were tested; others must be refused."""
    import json

    data = json.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    data["schema"] = schema
    with pytest.raises(fdef.FileFormatError):
        fdef.loads(json.dumps(data))
