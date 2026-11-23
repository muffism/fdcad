"""Sum, average, smallest, largest and count of a design table column (TR198, D966).

Only cells with a value that reads are counted: empty cells (the configuration keeps
its value) and cells that do not read are left out. Text and tick box columns have
no summary. Values are internal (mm, radians or plain numbers). No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

from fdcad.core import design_table as dt
from fdcad.core.document.model import Document, Param
from fdcad.core.units import Kind


@dataclass(frozen=True)
class Summary:
    """The numbers of one column."""

    kind: Kind
    count: int
    total: float
    average: float
    smallest: float
    largest: float


def column_summary(doc: Document, table: dt.Table, column: int) -> Summary | None:
    """The summary of column ``column`` (0 is the first value column), or None when it
    has no number values."""
    if not 0 <= column < len(table.columns):
        return None
    path = table.columns[column]
    try:
        kind = dt.value_kind(doc, path)
    except dt.DesignTableError:
        return None
    if not isinstance(kind, Kind):
        return None
    names = {v.name: (v.kind, v.value) for v in doc.variables}
    values: list[float] = []
    for _name, cells in table.rows:
        text = cells[column] if column < len(cells) else ""
        if not text.strip():
            continue
        try:
            value = dt.parse_cell(doc, path, text, names)
        except dt.DesignTableError:
            continue
        if isinstance(value, Param):
            values.append(value.value)
    if not values:
        return None
    total = sum(values)
    return Summary(kind, len(values), total, total / len(values), min(values), max(values))
