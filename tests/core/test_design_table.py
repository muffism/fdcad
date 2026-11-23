"""Design tables: rows are configurations, columns are values, stored in the file, CSV
import and export (PLAN Phase 4, PHASE4_SPEC P4.10 item 3, D392)."""

import json

import pytest

from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from tests.core.equations.test_equations import _plate


def _table(doc_ext: str) -> dt.Table:
    return dt.Table(
        ["var.Width", f"{doc_ext}.depth", f"{doc_ext}.suppressed"],
        [
            ("Default", ["60", "10", "U"]),
            ("Long", ["90", "=Width / 3", "U"]),
            ("Off", ["", "5", "S"]),
        ],
    )


def test_apply_makes_configurations_and_stores_the_table() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    dt.apply(doc, _table(ext))
    assert configs.names(doc) == ["Default", "Long", "Off"]
    assert configs.active_name(doc) == "Default"
    configs.activate(doc, "Long")
    assert doc.variables[0].expr == "90"
    assert doc.feature(ext).params["depth"] == Param("=Width / 3", 20.0)
    configs.activate(doc, "Off")
    assert doc.feature(ext).suppressed
    assert doc.variables[0].expr == "60"  # empty cell: kept as it was
    stored = dt.stored(doc)
    assert stored is not None and stored.columns == _table(ext).columns
    assert [r[0] for r in stored.rows] == ["Default", "Long", "Off"]


def test_table_is_saved_in_the_file_and_kept_in_step() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    dt.apply(doc, _table(ext))
    configs.activate(doc, "Long")
    doc.feature(ext).params["depth"] = Param("33", 33.0)  # an edit outside the table
    data = json.loads(fdef.dumps(doc))
    assert data["schema"] == 2
    table = data["configurations"]["design_table"]
    assert table["columns"] == ["var.Width", f"{ext}.depth", f"{ext}.suppressed"]
    assert table["rows"][1] == {"config": "Long", "values": ["90", "33", "U"]}
    again = fdef.loads(fdef.dumps(doc))
    assert dt.stored(again) == dt.stored(fdef.loads(fdef.dumps(again)))


def test_bad_cells_are_refused_and_nothing_changes() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    before = fdef.dumps(doc)
    bad = dt.Table([f"{ext}.depth"], [("Default", ["10"]), ("Bad", ["=Width +"])])
    with pytest.raises(dt.DesignTableError, match='Row "Bad", column'):
        dt.apply(doc, bad)
    with pytest.raises(dt.DesignTableError, match="names no value"):
        dt.apply(doc, dt.Table(["f99.depth"], [("Default", ["1"])]))
    with pytest.raises(dt.DesignTableError, match="two rows"):
        dt.apply(doc, dt.Table([f"{ext}.depth"], [("A", ["1"]), ("A", ["2"])]))
    with pytest.raises(dt.DesignTableError, match="S or U"):
        dt.apply(doc, dt.Table([f"{ext}.suppressed"], [("Default", ["maybe"])]))
    assert fdef.dumps(doc) == before


def test_delete_missing_rows_deletes_configurations() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    dt.apply(doc, _table(ext))
    dt.apply(doc, dt.Table([f"{ext}.depth"], [("Default", ["10"]), ("Long", ["20"])]), True)
    assert configs.names(doc) == ["Default", "Long"]


def test_csv_round_trip_and_spreadsheet_quirks() -> None:
    table = dt.Table(["var.Width", "f6.end_condition"], [("A, wide", ["2 1/2in", "blind"])])
    text = dt.to_csv(table)
    assert text.splitlines()[0] == "Configuration,var.Width,f6.end_condition"
    assert dt.from_csv(text) == table
    # A byte order mark, blank lines and short rows are fine.
    loose = "﻿Configuration,var.Width,f6.depth\n\nBig,80\n"
    assert dt.from_csv(loose) == dt.Table(["var.Width", "f6.depth"], [("Big", ["80", ""])])
    with pytest.raises(dt.DesignTableError, match="empty"):
        dt.from_csv("\n")
    with pytest.raises(dt.DesignTableError, match="value column"):
        dt.from_csv("Configuration\nA\n")


def test_csv_with_semicolons_or_tabs_from_decimal_comma_spreadsheets() -> None:
    want = dt.Table(["var.Width", "f6.depth"], [("Big", ["80", "2,5"])])
    assert dt.from_csv("Configuration;var.Width;f6.depth\nBig;80;2,5\n") == want
    assert dt.from_csv("Configuration\tvar.Width\tf6.depth\nBig\t80\t2,5\n") == want


def test_from_configurations_and_remove() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    configs.add(doc, "Long")
    configs.activate(doc, "Long")
    configs.set_scoped(doc, f"{ext}.depth", Param("30", 30.0), "this")
    table = dt.from_configurations(doc, [f"{ext}.depth", f"{ext}.reverse"])
    assert table.rows == [("Default", ["10", "false"]), ("Long", ["30", "false"])]
    dt.apply(doc, table)
    dt.remove(doc)
    assert dt.stored(doc) is None
    assert configs.names(doc) == ["Default", "Long"]


def test_csv_cells_a_spreadsheet_would_run_are_kept_as_text() -> None:
    """Audit D12 item 9 (D745): names and formulas starting with = + - @ were written as
    live spreadsheet formulas. Numbers such as -5mm stay plain, and import undoes it."""
    from fdcad.core.design_table import Table, from_csv, to_csv

    table = Table(
        ["var.W", "f6.depth"], [("=HYPERLINK(1)", ["=W*2", "-5mm"]), ("@a", ["+3", "10"])]
    )
    text = to_csv(table)
    assert "'=HYPERLINK(1),'=W*2,-5mm" in text and "'@a,+3,10" in text
    assert from_csv(text).rows == table.rows
