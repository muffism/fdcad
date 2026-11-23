"""Custom properties (TR82, owner decision approved in D750; DECISIONS D810).

A part holds named rows (``Document.properties``): text, number, date or yes or
no, such as description, part number or revision. A value starting with "="
is a formula: it may use the part's variables, feature values and measured
values, among them the part's own ``"volume@Part"``, ``"area@Part"`` and
``"mass@Part"`` (grams, from the part's material). A row may hold its own value
for a configuration (``configs``), used while that configuration is active.

Plain number rows (not formulas) are names in equations: ``"Width@Properties"``.
Formula rows are worked out after the equations, so they can use anything but
cannot be used by equations (that would be a loop). Saved in the part. No Qt.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.units import ExpressionError, Kind, evaluate

KINDS = ("text", "number", "date", "yes_no")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_ ]*\Z")


@dataclass(frozen=True)
class Row:
    """One property: its name, kind, value text and per configuration values."""

    name: str
    kind: str
    value: str
    configs: tuple[tuple[str, str], ...] = ()

    def to_data(self) -> dict[str, Any]:
        """The form saved in the part."""
        out: dict[str, Any] = {"name": self.name, "kind": self.kind, "value": self.value}
        if self.configs:
            out["configs"] = dict(self.configs)
        return out

    def text_for(self, config: str) -> str:
        """The value text used while ``config`` is active."""
        return dict(self.configs).get(config, self.value)


@dataclass(frozen=True)
class Shown:
    """A worked out row: what to show, the number (number and yes or no rows), and why
    it failed (empty when it did not)."""

    name: str
    kind: str
    text: str
    number: float | None = None
    error: str = ""


def rows(doc: Document) -> list[Row]:
    """The part's properties; damaged rows are left out."""
    out = []
    for raw in doc.properties:
        if not isinstance(raw, dict):
            continue
        name, kind, value = raw.get("name"), raw.get("kind", "text"), raw.get("value", "")
        if not isinstance(name, str) or not name.strip() or kind not in KINDS:
            continue
        configs = raw.get("configs") if isinstance(raw.get("configs"), dict) else {}
        pairs = tuple((str(k), str(v)) for k, v in (configs or {}).items())
        out.append(Row(name.strip(), str(kind), str(value), pairs))
    return out


def name_problem(name: str, others: list[str]) -> str:
    """Why ``name`` cannot name a property, or ""."""
    clean = name.strip()
    if not _NAME.match(clean):
        return "Start the name with a letter and use letters, digits, spaces and underscores."
    if clean in others:
        return f"A property called {clean} already exists. Choose another name."
    return ""


def equation_names(doc: Document) -> dict[str, tuple[Kind, float]]:
    """Plain number rows as equation names: ``"Width@Properties"``."""
    from fdcad.core import configurations as configs

    active = configs.active_name(doc)
    out: dict[str, tuple[Kind, float]] = {}
    for row in rows(doc):
        text = row.text_for(active).strip()
        if row.kind != "number" or text.startswith("="):
            continue
        try:
            out[f"{row.name}@Properties"] = (Kind.NUMBER, float(text))
        except ValueError:
            continue
    return out


def shown(doc: Document) -> list[Shown]:
    """Every row worked out for the active configuration."""
    from fdcad.core import configurations as configs
    from fdcad.core.equations.engine import solve

    active = configs.active_name(doc)
    names = dict(solve(doc).namespace)
    part = doc.measured.get("__part__", {})
    for key, value in part.items():  # only property formulas see these (no loops)
        names[f"{key}@Part"] = (Kind.NUMBER, float(value))
    from fdcad.core.named_items import MEASURED_KEY

    for key, value in doc.measured.get(MEASURED_KEY, {}).items():  # TR152 (D2105)
        names[key] = (Kind.NUMBER, float(value))
    out = []
    for row in rows(doc):
        out.append(_work(row, row.text_for(active).strip(), names, doc))
    return out


def _work(row: Row, text: str, names: dict[str, tuple[Kind, float]], doc: Document) -> Shown:
    try:
        if text.startswith("="):
            number = evaluate(text, Kind.NUMBER, doc.units, names)
            if row.kind == "yes_no":
                return Shown(row.name, row.kind, "Yes" if number else "No", 1.0 if number else 0.0)
            if row.kind == "date":
                raise ExpressionError("Type the date as YYYY-MM-DD, not as a formula.")
            return Shown(row.name, row.kind, f"{number:.6g}", number)
        if row.kind == "number":
            number = float(text) if text else 0.0
            return Shown(row.name, row.kind, f"{number:g}", number)
        if row.kind == "yes_no":
            yes = text.lower() in ("yes", "true", "1", "y")
            if text and not yes and text.lower() not in ("no", "false", "0", "n"):
                raise ValueError("Type yes or no.")
            return Shown(row.name, row.kind, "Yes" if yes else "No", 1.0 if yes else 0.0)
        if row.kind == "date" and text:
            datetime.date.fromisoformat(text)
        return Shown(row.name, row.kind, text)
    except (ExpressionError, ValueError) as exc:
        message = str(exc)
        if row.kind == "number" and "could not convert" in message:
            message = "Type a number, or a formula starting with =."
        if row.kind == "date" and "isoformat" in message:
            message = "Type the date as YYYY-MM-DD."
        return Shown(row.name, row.kind, "", None, message)


def metadata(doc: Document) -> dict[str, str]:
    """The rows as text, for file metadata (3MF); rows that failed are left out."""
    return {s.name: s.text for s in shown(doc) if not s.error and s.text}
