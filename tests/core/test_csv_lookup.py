"""Variables read from a CSV table by row label or number (TR198 item 2, D2102)."""

from pathlib import Path

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.equations import csv_lookup
from fdcad.core.equations.edit import apply_rows, rows_for
from fdcad.core.io import fdef
from fdcad.core.units import Kind
from tests.core.equations.test_equations import _plate

TABLE = "Size,Head,Length\nM4,7mm,20\nM6,10mm,30\n"


def _csv(tmp_path: Path, text: str = TABLE) -> Path:
    path = tmp_path / "screws.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_cell_by_label_or_number() -> None:
    table = [["Size", "Head"], ["M4", "7mm"], ["M6", "10mm"]]
    assert csv_lookup.cell(table, "m6", "head") == "10mm"
    assert csv_lookup.cell(table, "1", "Head") == "7mm"
    with pytest.raises(csv_lookup.CsvLookupError, match="no row"):
        csv_lookup.cell(table, "M8", "Head")
    with pytest.raises(csv_lookup.CsvLookupError, match="no column"):
        csv_lookup.cell(table, "M4", "Pitch")


def test_refresh_reads_saved_lookups_again(tmp_path: Path) -> None:
    path = _csv(tmp_path)
    doc = _plate()
    var = doc.variables[0]
    var.lookup = {"file": str(path), "row": "M6", "column": "Head"}
    variables, problems, changed = csv_lookup.refresh(doc, None)
    assert problems == [] and changed == 1
    assert (variables[0].expr, variables[0].value) == ("10mm", 10.0)
    doc.variables = variables
    again = fdef.loads(fdef.dumps(doc))
    assert again.variables[0].lookup == var.lookup
    _csv(tmp_path, TABLE.replace("10mm", "12mm"))
    variables, problems, changed = csv_lookup.refresh(again, None)
    assert variables[0].value == 12.0 and changed == 1
    path.unlink()
    variables, problems, changed = csv_lookup.refresh(again, None)
    assert changed == 0 and len(problems) == 1
    assert variables[0].value == again.variables[0].value  # keeps the last value read


def test_a_file_beside_the_part_is_found(tmp_path: Path) -> None:
    _csv(tmp_path)
    doc = new_document()
    from fdcad.core.document.model import Variable

    doc.variables.append(
        Variable("L", Kind.NUMBER, "1", 1.0, lookup={"file": "gone/screws.csv", "row": "2",
                                                       "column": "Length"})
    )  # fmt: skip
    variables, problems, _changed = csv_lookup.refresh(doc, tmp_path / "part.fdprt")
    assert problems == [] and variables[0].value == 30.0


def test_typing_another_value_stops_the_lookup(tmp_path: Path) -> None:
    doc = _plate()
    doc.variables[0].lookup = {"file": str(_csv(tmp_path)), "row": "M4", "column": "Head"}
    rows = rows_for(doc)
    variables, _f = apply_rows(doc, rows)
    assert variables[0].lookup is not None
    rows[0].expr = "70"
    variables, _f = apply_rows(doc, rows)
    assert variables[0].lookup is None
