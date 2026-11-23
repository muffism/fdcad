"""Design table column summary (TR198 item 1, D966)."""

from __future__ import annotations

import pytest

from fdcad.core import design_table as dt
from fdcad.core.table_summary import column_summary
from fdcad.core.units import Kind
from tests.core.equations.test_equations import _plate


def test_number_columns_sum_and_skip_empty_cells() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    table = dt.Table(
        ["var.Width", f"{ext}.depth", f"{ext}.suppressed"],
        [
            ("Default", ["60", "10", "U"]),
            ("Long", ["90", "=Width / 3", "U"]),
            ("Off", ["", "5", "S"]),
        ],
    )
    width = column_summary(doc, table, 0)
    assert width is not None and width.kind is Kind.LENGTH
    assert (width.count, width.total, width.smallest, width.largest) == (2, 150.0, 60.0, 90.0)
    assert width.average == pytest.approx(75.0)
    depth = column_summary(doc, table, 1)
    assert depth is not None and depth.count == 3
    assert column_summary(doc, table, 2) is None  # S and U have no numbers
    assert column_summary(doc, table, 5) is None
