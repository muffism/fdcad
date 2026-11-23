"""Equations to and from a text file (TR25, DECISIONS D749).

The file is plain UTF-8 text a person can read and edit:

    # FDCAD equations
    [variables]
    "Width" = 40mm
    "Depth" = ="Width" / 2  // half the width
    [suppression]
    "Fillet 1" = =if("Width" > 30, 0, 1)
    [equations]
    "depth@Extrude 1" = ="Depth"

Each row is a quoted name, `` = ``, the value exactly as typed in the equations
manager, and an optional comment after ``//``. Lines starting with ``#`` and
blank lines are skipped. The sections match the manager's three sections.

``merge`` puts the rows of a file into the part's rows: a row with the same
name in the same section is replaced, new rows are added, and rows the file
does not name are kept. Equations and suppression formulas for values or
features the part does not have are left out and reported. Pure Python: no Qt,
no kernel, and reading the file never runs code (CLAUDE.md 5.10).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fdcad.core.document.model import Document
from fdcad.core.equations.edit import Row, find_feature, find_value, quote, rows_for, unquote

#: Section names in the file, by manager section.
SECTIONS = {"variable": "variables", "feature": "suppression", "equation": "equations"}
_BY_HEADER = {v: k for k, v in SECTIONS.items()}
#: The usual file name ending.
SUFFIX = ".txt"
#: Larger files are refused (hostile file limits, audit D12).
MAX_BYTES = 1_000_000
MAX_ROWS = 10_000
_COMMENT = "//"
HEADER = "# FDCAD equations"


class EquationFileError(ValueError):
    """The file cannot be read. The message names the line and what to do."""


@dataclass
class Merged:
    """The rows after a merge, and what the file named that the part does not have."""

    rows: list[Row]
    changed: int = 0
    skipped: list[str] = field(default_factory=list)


def to_text(rows: list[Row]) -> str:
    """The rows as file text, section by section."""
    lines = [HEADER]
    for section, header in SECTIONS.items():
        chosen = [r for r in rows if r.section == section]
        if not chosen:
            continue
        lines.append(f"[{header}]")
        for row in chosen:
            line = f"{quote(row.name)} = {row.expr.strip()}"
            if row.comment.strip():
                line += f"  {_COMMENT} {row.comment.strip()}"
            lines.append(line)
    return "\n".join(lines) + "\n"


def _split_comment(value: str) -> tuple[str, str]:
    """``value`` without its ``//`` comment, and the comment. A ``//`` inside quotes
    is part of a name, not a comment."""
    inside = False
    for i, ch in enumerate(value):
        if ch == '"':
            inside = not inside
        elif not inside and value.startswith(_COMMENT, i):
            return value[:i].strip(), value[i + len(_COMMENT) :].strip()
    return value.strip(), ""


def from_text(text: str) -> list[Row]:
    """The rows of file text. Raises EquationFileError for a line that is not a row."""
    if len(text.encode("utf-8", "surrogatepass")) > MAX_BYTES:
        raise EquationFileError(
            f"the file is larger than {MAX_BYTES // 1_000_000} MB. "
            "Check that it is an equations file, or split it."
        )
    text = text.removeprefix("﻿")  # a byte order mark some editors add
    rows: list[Row] = []
    section = "variable"
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            header = line[1:-1].strip().lower()
            if header not in _BY_HEADER:
                names = ", ".join(f"[{h}]" for h in SECTIONS.values())
                raise EquationFileError(
                    f"line {number}: unknown section [{header}]. Use one of {names}."
                )
            section = _BY_HEADER[header]
            continue
        if not line.startswith('"'):
            raise EquationFileError(
                f'line {number}: a row starts with a quoted name. Write it as "Width" = 40mm.'
            )
        end = line.find('"', 1)
        rest = line[end + 1 :].lstrip() if end > 0 else ""
        if end <= 1 or not rest.startswith("="):
            raise EquationFileError(
                f'line {number}: a row needs a quoted name, then =. Write it as "Width" = 40mm.'
            )
        value, comment = _split_comment(rest[1:])
        if not value:
            raise EquationFileError(f"line {number}: the value is empty. Type a value after =.")
        rows.append(Row(section, line[1:end].strip(), value, comment))
        if len(rows) > MAX_ROWS:
            raise EquationFileError(
                f"the file has more than {MAX_ROWS:,} rows. "
                "Check that it is an equations file, or split it."
            )
    return rows


def _known(doc: Document, row: Row) -> bool:
    if row.section == "feature":
        return find_feature(doc, row.name) is not None
    if row.section == "equation":
        return find_value(doc, row.name) is not None
    return True


def merge(doc: Document, current: list[Row], incoming: list[Row]) -> Merged:
    """``current`` with the file's rows put in (see the module notes)."""
    out = list(current)
    index = {(r.section, unquote(r.name)): i for i, r in enumerate(out)}
    merged = Merged(out)
    for row in incoming:
        if not _known(doc, row):
            merged.skipped.append(unquote(row.name))
            continue
        key = (row.section, unquote(row.name))
        if key in index:
            old = out[index[key]]
            if (old.expr.strip(), old.comment.strip()) != (row.expr.strip(), row.comment.strip()):
                # Keep the kind of an existing variable; only the text changes.
                out[index[key]] = Row(old.section, old.name, row.expr, row.comment, old.kind)
                merged.changed += 1
        else:
            index[key] = len(out)
            out.append(row)
            merged.changed += 1
    return merged


def resolve(link: str, part_path: Path | None) -> Path:
    """Where a linked file is: the stored path, or, when that is gone, a file of the
    same name next to the part (a folder of parts and their file moved together)."""
    path = Path(link)
    if not path.is_absolute() and part_path is not None:
        path = part_path.parent / path
    if not path.exists() and part_path is not None:
        beside = part_path.parent / Path(link).name
        if beside.exists():
            return beside
    return path


def read_file(path: Path) -> list[Row]:
    """The rows of an equations file. Raises EquationFileError or OSError."""
    if path.stat().st_size > MAX_BYTES:
        raise EquationFileError(
            f"the file is larger than {MAX_BYTES // 1_000_000} MB. "
            "Check that it is an equations file, or split it."
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EquationFileError("the file is not UTF-8 text. Save it again as UTF-8 text.") from exc
    return from_text(text)


def read_linked(doc: Document, part_path: Path | None) -> Merged | None:
    """The part's rows with its linked file put in, or None when it has no link.
    Raises EquationFileError or OSError when the file cannot be read."""
    if not doc.equations_file:
        return None
    rows = read_file(resolve(doc.equations_file, part_path))
    return merge(doc, rows_for(doc), rows)
