"""Design tables: configurations as rows, values as columns (PLAN Phase 4, FDEF_SPEC 9, D392).

The table is stored in the configurations block as ``{"columns": [paths],
"rows": [{"config": name, "values": [text]}]}``. Columns are configuration
paths (``var.Width``, ``f6.depth``, ``f5.d1``, ``f9.suppressed``). Cells hold
typed text: an expression for typed values, ``S`` or ``U`` for suppression,
``true`` or ``false`` for tick box settings and the plain word for choices.
An empty cell leaves that configuration's value as it is.

The rows are always rebuilt from the configurations when the file is written,
so the table and the configurations never disagree. Pure Python: no Qt.
"""

from __future__ import annotations

import copy
import csv
import io
import re
from dataclasses import dataclass, field
from typing import Any

from fdcad.core import configurations as configs
from fdcad.core.document.model import Document, Param
from fdcad.core.equations.engine import dimension_kind, solve
from fdcad.core.units import ExpressionError, Kind, evaluate

CONFIG_HEADER = "Configuration"
_TRUE = {"s", "suppressed", "yes", "y", "true", "1", "on"}
_FALSE = {"u", "unsuppressed", "no", "n", "false", "0", "off"}
#: Columns that are not configured values (TR90 item 1, D2100): the configuration's
#: description, and a custom property's value in each configuration.
DESCRIPTION = "config.description"
PROP_PREFIX = "prop."
_COLOR = re.compile(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?\Z")


#: The theme column (TR331, D2103): a theme name per row, kept in the entry's ``theme``.
THEME = "config.theme"
_ITEM_KEYS = {DESCRIPTION: "description", THEME: "theme"}


def is_meta(path: str) -> bool:
    """True for a description, theme or custom property column."""
    return path in _ITEM_KEYS or path.startswith(PROP_PREFIX)


def meta_exists(doc: Document, path: str) -> bool:
    """True when a description or property column names something of this part."""
    if path in _ITEM_KEYS:
        return True
    if path.startswith(PROP_PREFIX):
        from fdcad.core.properties import rows

        name = path[len(PROP_PREFIX) :]
        return any(row.name == name for row in rows(doc))
    return False


def column_exists(doc: Document, path: str) -> bool:
    """True when a column names a value, the description or a property of this part."""
    return meta_exists(doc, path) if is_meta(path) else configs.path_exists(doc, path)


def meta_text(doc: Document, config: str, path: str) -> str:
    """The description or property text of one configuration."""
    if path in _ITEM_KEYS:
        item = next((i for i in configs.items(doc) if i["name"] == config), {})
        return str(item.get(_ITEM_KEYS[path]) or "")
    from fdcad.core.properties import rows

    name = path[len(PROP_PREFIX) :]
    row = next((r for r in rows(doc) if r.name == name), None)
    return row.text_for(config) if row is not None else ""


def set_meta(doc: Document, config: str, path: str, value: str) -> None:
    """Store the description or property text of one configuration. A property value
    equal to the shared value is not kept as the configuration's own."""
    if path in _ITEM_KEYS:
        for item in configs.items(doc):
            if item["name"] == config:
                if value:
                    item[_ITEM_KEYS[path]] = value
                else:
                    item.pop(_ITEM_KEYS[path], None)
        return
    name = path[len(PROP_PREFIX) :]
    for raw in doc.properties:
        if isinstance(raw, dict) and str(raw.get("name", "")).strip() == name:
            own = dict(raw.get("configs") or {})
            if value == str(raw.get("value", "")):
                own.pop(config, None)
            else:
                own[config] = value
            if own:
                raw["configs"] = own
            else:
                raw.pop("configs", None)


class DesignTableError(ValueError):
    """The table cannot be applied. The message names the row and column."""


@dataclass
class Table:
    """A design table in memory: column paths and one row of texts per configuration."""

    columns: list[str] = field(default_factory=list)
    rows: list[tuple[str, list[str]]] = field(default_factory=list)

    def to_data(self) -> dict[str, Any]:
        """The file form (FDEF_SPEC 9 item 3)."""
        return {
            "columns": list(self.columns),
            "rows": [{"config": name, "values": list(values)} for name, values in self.rows],
        }

    @classmethod
    def from_data(cls, raw: Any) -> Table:
        """Read the file form; anything unreadable gives an empty table."""
        if not isinstance(raw, dict):
            return cls()
        columns = [str(c) for c in raw.get("columns", []) if isinstance(c, str)]
        rows = []
        for row in raw.get("rows", []):
            if isinstance(row, dict) and isinstance(row.get("config"), str):
                values = [str(v) for v in row.get("values", [])]
                values += [""] * (len(columns) - len(values))
                rows.append((row["config"], values[: len(columns)]))
        return cls(columns, rows)


def stored(doc: Document) -> Table | None:
    """The part's design table, or None."""
    configs.items(doc)  # makes sure the block is valid
    raw = doc.configurations.get("design_table")
    return Table.from_data(raw) if raw else None


def value_kind(doc: Document, path: str) -> Kind | str:
    """A path's kind: a unit kind for typed values, or ``bool``, ``color`` or ``text``."""
    if is_meta(path):
        return "text"
    if path == configs.PART_COLOR:
        return "color"
    if path == configs.PART_COLORS:
        raise DesignTableError(
            "Face and body colours cannot be a table column. "
            "Use Colours by Configuration in the Configurations tab instead."
        )
    head, _, tail = path.partition(".")
    if head + "." == configs.VAR_PREFIX:
        var = next((v for v in doc.variables if v.name == tail), None)
        if var is None:
            raise DesignTableError(
                f'There is no variable named "{tail}". '
                "Add it in Global Variables or delete the column."
            )
        if var.type == "text":  # TR417 (D2104)
            return "text"
        if var.type == "yes_no":
            return "bool"
        return var.kind
    feature = next((f for f in doc.features if f.id == head), None)
    if feature is None:
        raise DesignTableError(
            f'There is no feature with id "{head}". Delete the column for the deleted feature.'
        )
    if tail == configs.SUPPRESSED or tail.endswith((configs.DRIVING, configs.OFF)):
        return "bool"
    if tail == configs.PLANE and feature.type == "sketch" and tail not in feature.params:
        return "plane"
    value = feature.params.get(tail)
    if isinstance(value, Param):
        from fdcad.core.features import REGISTRY

        ftype = REGISTRY.get(feature.type)
        kind = ftype.kind_of(tail) if ftype is not None else None
        return kind or Kind.NUMBER
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "text"
    if isinstance(value, int | float):
        return Kind.NUMBER
    for dim in feature.data.get("dimensions", []):
        if isinstance(dim, dict) and dim.get("id") == tail:
            return dimension_kind(str(dim.get("type")))
    raise DesignTableError(
        f'{feature.name} has no value named "{tail}". Delete the column or pick another value.'
    )


def cell_text(value: Any, path: str) -> str:
    """A value as table text."""
    if isinstance(value, Param):
        return value.expr
    if isinstance(value, bool):
        if path.endswith("." + configs.SUPPRESSED):
            return "S" if value else "U"
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def parse_cell(doc: Document, path: str, typed: str, names: dict[str, tuple[Kind, float]]) -> Any:
    """Table text as a value for ``path``. Raises DesignTableError."""
    kind = value_kind(doc, path)
    text = typed.strip()
    if kind == "bool":
        word = text.lower()
        if word in _TRUE:
            return True
        if word in _FALSE:
            return False
        raise DesignTableError(
            f'"{typed}" is not S or U (or true or false). Type S to suppress or U to unsuppress.'
        )
    if kind == "text":
        return text
    if kind == "plane":
        wanted = text.casefold()
        plane = next(
            (f for f in doc.features if f.type == "plane" and f.name.casefold() == wanted), None
        )
        if plane is None:
            raise DesignTableError(f'There is no plane named "{typed}". Type the name of a plane.')
        return {"feature": plane.id}
    if kind == "color":
        if not _COLOR.match(text):
            raise DesignTableError(
                f'"{typed}" is not a colour. Type it as # and six hex digits, such as #3366CC.'
            )
        return text.upper()
    assert isinstance(kind, Kind)
    try:
        return Param(text, evaluate(text, kind, doc.units, names))
    except ExpressionError as exc:
        raise DesignTableError(str(exc)) from exc


def doc_text(doc: Document, value: Any, path: str) -> str:
    """A value as table text, with a sketch plane shown by the plane's name (TR197)."""
    if isinstance(value, dict) and path.endswith("." + configs.PLANE):
        fid = value.get("feature")
        plane = next((f for f in doc.features if f.id == fid), None)
        return plane.name if plane is not None else "(face)"
    return cell_text(value, path)


def from_configurations(doc: Document, columns: list[str]) -> Table:
    """The table that shows the configurations' current values for ``columns``."""
    configs.sync_active(doc)
    rows = []
    for item in configs.items(doc):
        overrides = item["overrides"]
        values = []
        for path in columns:
            if is_meta(path):
                values.append(meta_text(doc, str(item["name"]), path))
            elif path in overrides:
                values.append(doc_text(doc, configs.as_value(overrides[path]), path))
            elif configs.path_exists(doc, path):
                values.append(doc_text(doc, configs.get_value(doc, path), path))
            else:
                values.append("")
        rows.append((str(item["name"]), values))
    return Table(list(columns), rows)


def apply(doc: Document, table: Table, delete_missing: bool = False) -> None:
    """Make the configurations match the table, and store the table (P4.10 item 3).

    New row names add configurations; with ``delete_missing`` configurations
    without a row are deleted. Raises DesignTableError and leaves the part
    unchanged on any bad cell.
    """
    if len(set(table.columns)) != len(table.columns):
        raise DesignTableError("A column is listed twice. Delete one of them.")
    for path in table.columns:
        if not column_exists(doc, path):
            raise DesignTableError(
                f'Column "{path}" names no value of this part. Delete the column or rename it.'
            )
    seen: set[str] = set()
    for name, _values in table.rows:
        clean = " ".join(name.split())
        if not clean:
            raise DesignTableError("A row has no configuration name. Enter one.")
        if clean in seen:
            raise DesignTableError(f'Configuration "{clean}" has two rows. Delete one.')
        seen.add(clean)
    if not table.rows:
        raise DesignTableError("The table has no rows. Add a configuration.")
    table = _with_themes(doc, table)
    names = solve(doc).namespace
    parsed: list[tuple[str, dict[str, Any]]] = []
    for name, values in table.rows:
        cells: dict[str, Any] = {}
        for path, typed in zip(table.columns, values, strict=False):
            if not typed.strip() or is_meta(path) or typed.strip() == "(face)":
                continue
            try:
                cells[path] = parse_cell(doc, path, typed, names)
            except DesignTableError as exc:
                raise DesignTableError(f'Row "{name}", column "{path}": {exc}') from exc
        parsed.append((" ".join(name.split()), cells))
    configs.sync_active(doc)
    for name, _cells in parsed:
        if name not in configs.names(doc):
            configs.add(doc, name)
    if delete_missing:
        for name in configs.names(doc):
            if name not in seen:
                configs.delete(doc, name)
    active = configs.active_name(doc)
    for name, values in table.rows:
        for path, typed in zip(table.columns, values, strict=False):
            if is_meta(path) and typed.strip():
                set_meta(doc, " ".join(name.split()), path, typed.strip())
    for path in table.columns:
        if is_meta(path):
            continue
        current = configs.get_value(doc, path)
        for item in configs.items(doc):
            item["overrides"].setdefault(path, current)
    for name, cells in parsed:
        item = next(i for i in configs.items(doc) if i["name"] == name)
        item["overrides"].update(cells)
    configs.normalize(doc)
    run_rules(doc)
    for path, value in next(i for i in configs.items(doc) if i["name"] == active)[
        "overrides"
    ].items():
        configs.set_value(doc, path, value)
    doc.configurations["design_table"] = from_configurations(doc, table.columns).to_data()


def _with_themes(doc: Document, table: Table) -> Table:
    """The table with each row's empty cells filled from its theme, and a column added
    for every value a used theme sets (TR331, D2103). Raises DesignTableError."""
    from fdcad.core import config_rules

    if THEME not in table.columns:
        return table
    try:
        filled = [
            (name, config_rules.theme_filled(doc, table.columns, values))
            for name, values in table.rows
        ]
    except config_rules.RuleError as exc:
        raise DesignTableError(str(exc)) from exc
    columns = list(table.columns)
    for _name, cells in filled:
        columns += [p for p in cells if p not in columns]
    rows = []
    for (name, values), (_n, cells) in zip(table.rows, filled, strict=True):
        own = dict(zip(table.columns, values, strict=False))
        rows.append((name, [own.get(p, "") if p == THEME else cells.get(p, "") for p in columns]))
    return Table(columns, rows)


def run_rules(doc: Document) -> int:
    """Run the configuration rules in every configuration and show the active one's
    values (TR331, D2103). Returns how many values changed. Raises DesignTableError."""
    from fdcad.core import config_rules

    if not config_rules.rules(doc):
        return 0
    configs.sync_active(doc)
    count = 0
    work = copy.deepcopy(doc)
    shared: dict[str, Any] = {}  # values a rule changed that are not configured
    for item in configs.items(doc):
        for path, value in shared.items():
            configs.set_value(work, path, value)
        for path, value in item["overrides"].items():
            configs.set_value(work, path, value)
        try:
            changed = config_rules.apply(work)
        except config_rules.RuleError as exc:
            raise DesignTableError(str(exc)) from exc
        for path in changed:
            shared.setdefault(path, configs.get_value(doc, path))
            item["overrides"][path] = configs.get_value(work, path)
        count += len(changed)
    configs.normalize(doc)
    active = configs.active_name(doc)
    for item in configs.items(doc):
        if item["name"] == active:
            for path, value in item["overrides"].items():
                configs.set_value(doc, path, value)
    return count


def remove(doc: Document) -> None:
    """Remove the design table. The configurations keep their values."""
    doc.configurations["design_table"] = None


#: First characters a spreadsheet reads as the start of a formula.
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
#: A plain number, with an optional unit, such as "-5mm" or "+3".
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?\s*[A-Za-z\"]*")


def _guarded(cell: str) -> str:
    """A cell a spreadsheet would run as a formula, with a leading apostrophe so it stays
    text (audit D12 item 9, D745). Numbers such as "-5mm" are left alone."""
    if cell.startswith(_FORMULA_START) and not _NUMBER.fullmatch(cell):
        return "'" + cell
    return cell


def _unguarded(cell: str) -> str:
    """``_guarded`` undone on import."""
    if cell.startswith("'") and cell[1:].startswith(_FORMULA_START):
        return cell[1:]
    return cell


def to_csv(table: Table) -> str:
    """The table as CSV text: a header row, then one row per configuration."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow([CONFIG_HEADER, *table.columns])
    for name, values in table.rows:
        writer.writerow([_guarded(name), *(_guarded(v) for v in values)])
    return out.getvalue()


def _delimiter(text: str) -> str:
    """The cell separator, read from the header row: a comma, or the semicolon or tab
    that spreadsheets using a decimal comma write instead."""
    header = next((line for line in text.splitlines() if line.strip()), "")
    if "," in header:
        return ","
    for other in (";", "\t"):
        if other in header:
            return other
    return ","


def from_csv(text: str) -> Table:
    """Read CSV text written by ``to_csv`` or a spreadsheet. Raises DesignTableError."""
    sample = text.lstrip("﻿")
    try:
        reader = csv.reader(io.StringIO(sample), delimiter=_delimiter(sample))
        rows = [r for r in reader if any(c.strip() for c in r)]
    except csv.Error as exc:
        raise DesignTableError(
            f"The CSV file cannot be read ({exc}). Save it again as CSV from the spreadsheet."
        ) from exc
    if not rows:
        raise DesignTableError("The CSV file is empty. Choose a CSV file with a header row.")
    header = [c.strip() for c in rows[0]]
    if len(header) < 2:
        raise DesignTableError(
            "The first CSV row needs a configuration column and at least one value column. "
            "Add a header row to the file."
        )
    columns = header[1:]
    body = []
    for row in rows[1:]:
        values = [_unguarded(c.strip()) for c in row[1:]]
        values += [""] * (len(columns) - len(values))
        body.append((_unguarded(row[0].strip()), values[: len(columns)]))
    return Table(columns, body)


def sync_rows(doc: Document) -> dict[str, Any] | None:
    """The stored table with rows rebuilt from the configurations (for saving)."""
    raw = doc.configurations.get("design_table") if isinstance(doc.configurations, dict) else None
    if not raw:
        return None
    table = Table.from_data(raw)
    columns = [c for c in table.columns if column_exists(doc, c)]
    rows = []
    active = configs.active_name(doc)
    for item in configs.items(doc):
        values = []
        for path in columns:
            if is_meta(path):
                values.append(meta_text(doc, str(item["name"]), path))
                continue
            if item["name"] == active or path not in item["overrides"]:
                value = configs.get_value(doc, path)
            else:
                value = configs.as_value(item["overrides"][path])
            values.append(doc_text(doc, value, path))
        rows.append((str(item["name"]), values))
    return Table(columns, rows).to_data()
