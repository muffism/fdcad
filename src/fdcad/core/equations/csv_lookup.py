"""Variables read from a CSV table (TR198 item 2, D2102).

A variable may carry ``lookup = {"file": path, "row": text, "column": text}``. The
row is found by its label in the first column (ignoring case), or, when no label
matches and the text is a whole number, by its position (1 is the first row under
the header). The column is found by its header (ignoring case). The cell becomes the
variable's typed value, worked out like any typed value.

The file is read only when the lookup is set, when the part opens and on Rebuild,
the same moments as a linked equations file (TR25, D749): evaluation never reads a
file, and the value read last is saved in the part, so it opens without the file.
Pure Python: no Qt, no kernel, and reading never runs code (CLAUDE.md 5.10).
"""

from __future__ import annotations

import csv
import dataclasses
import io
from pathlib import Path
from typing import Any

from fdcad.core.document.model import Document, Variable
from fdcad.core.equations.text_file import resolve
from fdcad.core.units import ExpressionError, evaluate

#: Larger files are refused (hostile file limits, audit D12).
MAX_BYTES = 5_000_000


class CsvLookupError(ValueError):
    """The value cannot be read. The message says what to fix."""


def lookup_of(var: Variable) -> dict[str, str] | None:
    """The variable's CSV lookup, or None."""
    raw = var.lookup
    if not isinstance(raw, dict) or not all(
        isinstance(raw.get(k), str) for k in ("file", "row", "column")
    ):
        return None
    return {k: str(raw[k]) for k in ("file", "row", "column")}


def read_table(path: Path) -> list[list[str]]:
    """The rows of a CSV file (comma, semicolon or tab). Raises CsvLookupError or OSError."""
    if path.stat().st_size > MAX_BYTES:
        raise CsvLookupError(
            f"{path.name} is larger than {MAX_BYTES // 1_000_000} MB. Choose a smaller CSV file."
        )
    text = path.read_text(encoding="utf-8-sig")
    header = next((line for line in text.splitlines() if line.strip()), "")
    delimiter = "," if "," in header else next((d for d in ";\t" if d in header), ",")
    try:
        return [
            [c.strip() for c in row]
            for row in csv.reader(io.StringIO(text), delimiter=delimiter)
            if any(c.strip() for c in row)
        ]
    except csv.Error as exc:
        raise CsvLookupError(
            f"{path.name} cannot be read as CSV ({exc}). Save it again as CSV."
        ) from exc


def cell(table: list[list[str]], row: str, column: str) -> str:
    """The cell at ``row`` (a label or a 1 based position) and ``column`` (a header).
    Raises CsvLookupError."""
    if len(table) < 2:
        raise CsvLookupError("The CSV file needs a header row and at least one row of values.")
    header = [h.casefold() for h in table[0]]
    wanted = column.strip().casefold()
    if wanted not in header:
        raise CsvLookupError(
            f'The CSV file has no column "{column}". Enter one of: {", ".join(table[0][1:])}.'
        )
    index = header.index(wanted)
    body = table[1:]
    label = row.strip().casefold()
    found = next((r for r in body if r and r[0].casefold() == label), None)
    if found is None and label.isdigit() and 1 <= int(label) <= len(body):
        found = body[int(label) - 1]
    if found is None:
        raise CsvLookupError(
            f'The CSV file has no row "{row}". Enter a label from its first column '
            f"or a row number from 1 to {len(body)}."
        )
    value = found[index] if index < len(found) else ""
    if not value:
        raise CsvLookupError(f'Row "{row}", column "{column}" is empty. Fill it in the CSV file.')
    return value


def read_value(
    var: Variable, lookup: dict[str, str], part_path: Path | None, doc: Document
) -> Variable:
    """The variable with the value read from its CSV file. Raises CsvLookupError or OSError."""
    text = cell(read_table(resolve(lookup["file"], part_path)), lookup["row"], lookup["column"])
    try:
        value = evaluate(text, var.kind, doc.units, {})
    except ExpressionError as exc:
        raise CsvLookupError(f'"{text}" is not a value for {var.name}: {exc}') from exc
    return dataclasses.replace(var, expr=text, value=value, lookup=dict(lookup))


def refresh(doc: Document, part_path: Path | None) -> tuple[list[Variable], list[str], int]:
    """Read every variable's CSV value again: the new variables list, a problem per
    variable that could not be read (it keeps its last value) and how many changed."""
    out: list[Variable] = []
    problems: list[str] = []
    changed = 0
    for var in doc.variables:
        lookup = lookup_of(var)
        if lookup is None:
            out.append(var)
            continue
        try:
            new = read_value(var, lookup, part_path, doc)
        except (CsvLookupError, OSError, UnicodeDecodeError) as exc:
            problems.append(f"{var.name}: {exc}")
            out.append(var)
            continue
        if (new.expr, new.value) != (var.expr, var.value):
            changed += 1
        out.append(new)
    return out, problems, changed


def has_lookups(doc: Document) -> bool:
    """True when some variable is read from a CSV file."""
    return any(lookup_of(v) is not None for v in doc.variables)


def to_data(lookup: dict[str, Any]) -> dict[str, str]:
    """The saved form."""
    return {k: str(lookup[k]) for k in ("file", "row", "column")}
