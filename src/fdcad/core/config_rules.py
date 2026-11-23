"""Configuration rules, themes and trial values (TR331, D2103).

Rules live in the configurations block (``rules``), in order::

    {"if": "var.Width", "test": ">", "value": "50mm",
     "then": "f6.depth", "choices": ["10", "20"], "off": false}

A rule holds when the value at ``if`` passes the test. Then the value at ``then``
must be one of ``choices``; when it is not, applying the rule sets it to the first
choice. Rules run top to bottom, so a later rule sees what an earlier one set.
Rules that are off are skipped. Every rebuild lists the rules that are not met
(next to the allowed value warnings, TR274), so a value edited anywhere is checked;
values change only when the user applies the rules or applies the design table.

Themes (``themes``) are named sets of values: ``{"Steel": {"var.Thick": "2mm",
"part.color": "#778899"}}``. A design table ``theme`` column picks one per row and
fills the row's empty cells from it. Pure Python: no Qt, no kernel.
"""

from __future__ import annotations

import copy
from typing import Any

from fdcad.core import configurations as configs
from fdcad.core.document.model import Document, Param

TESTS = (">", ">=", "<", "<=", "=", "!=")
#: The design table column that picks a theme for each row.
THEME = "config.theme"
_TOLERANCE = 1e-9


class RuleError(ValueError):
    """A rule or theme cannot be used. The message says what to fix."""


def _block(doc: Document) -> dict[str, Any]:
    configs.items(doc)  # makes the block valid
    return doc.configurations


def rules(doc: Document) -> list[dict[str, Any]]:
    """The part's rules, in order; damaged entries are left out."""
    raw = _block(doc).get("rules")
    return [
        r
        for r in (raw if isinstance(raw, list) else [])
        if isinstance(r, dict)
        and isinstance(r.get("if"), str)
        and isinstance(r.get("then"), str)
        and r.get("test") in TESTS
        and isinstance(r.get("choices"), list)
    ]


def set_rules(doc: Document, new: list[dict[str, Any]]) -> None:
    """Store the rules after checking each one. Raises RuleError."""
    for i, rule in enumerate(new, start=1):
        problem = rule_problem(doc, rule)
        if problem:
            raise RuleError(f"Rule {i}: {problem}")
    if new:
        _block(doc)["rules"] = copy.deepcopy(new)
    else:
        _block(doc).pop("rules", None)


def themes(doc: Document) -> dict[str, dict[str, str]]:
    """The part's themes: name to values (path to typed text)."""
    raw = _block(doc).get("themes")
    if not isinstance(raw, dict):
        return {}
    return {
        str(name): {str(k): str(v) for k, v in values.items()}
        for name, values in raw.items()
        if isinstance(values, dict)
    }


def set_themes(doc: Document, new: dict[str, dict[str, str]]) -> None:
    """Store the themes after checking every value. Raises RuleError."""
    from fdcad.core import design_table as dt
    from fdcad.core.equations.engine import solve

    names = solve(doc).namespace
    for theme, values in new.items():
        if not theme.strip():
            raise RuleError("A theme has no name. Enter one.")
        for path, typed in values.items():
            if not dt.column_exists(doc, path):
                raise RuleError(f'Theme "{theme}": "{path}" names no value. Pick a value.')
            if not dt.is_meta(path):
                try:
                    dt.parse_cell(doc, path, typed, names)
                except dt.DesignTableError as exc:
                    raise RuleError(f'Theme "{theme}", {path}: {exc}') from exc
    if new:
        _block(doc)["themes"] = copy.deepcopy(new)
    else:
        _block(doc).pop("themes", None)


# Values ---------------------------------------------------------------------------------


def _parse(doc: Document, path: str, typed: str) -> Any:
    from fdcad.core import design_table as dt
    from fdcad.core.equations.engine import solve

    try:
        return dt.parse_cell(doc, path, typed, solve(doc).namespace)
    except dt.DesignTableError as exc:
        raise RuleError(f"{path}: {exc}") from exc


def _number(value: Any) -> float | None:
    if isinstance(value, Param):
        return value.value
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    return None


def _same(a: Any, b: Any) -> bool:
    na, nb = _number(a), _number(b)
    if na is not None and nb is not None:
        return abs(na - nb) <= _TOLERANCE * max(1.0, abs(na), abs(nb))
    return str(a).strip().casefold() == str(b).strip().casefold()


def passes(doc: Document, rule: dict[str, Any]) -> bool:
    """True when the rule's condition holds for the live values. Raises RuleError."""
    current = configs.get_value(doc, rule["if"])
    wanted = _parse(doc, rule["if"], str(rule.get("value", "")))
    test = str(rule["test"])
    if test in ("=", "!="):
        return _same(current, wanted) is (test == "=")
    a, b = _number(current), _number(wanted)
    if a is None or b is None:
        raise RuleError(f"{rule['if']} is not a number. Use = or != to test it.")
    return {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[test]


def rule_problem(doc: Document, rule: dict[str, Any]) -> str:
    """Why a rule cannot be used, or ""."""
    for key in ("if", "then"):
        path = str(rule.get(key, ""))
        if not configs.path_exists(doc, path):
            return f'"{path}" names no value of this part. Pick a value.'
    if rule.get("test") not in TESTS:
        return f"The test must be one of {' '.join(TESTS)}. Pick one."
    choices = rule.get("choices")
    if not isinstance(choices, list) or not [c for c in choices if str(c).strip()]:
        return "It has no choices. Enter at least one value, separated by commas."
    try:
        passes(doc, rule)
        for choice in choices:
            _parse(doc, str(rule["then"]), str(choice))
    except (RuleError, configs.ConfigurationError) as exc:
        return str(exc)
    return ""


def _met(doc: Document, rule: dict[str, Any]) -> bool:
    current = configs.get_value(doc, rule["then"])
    return any(_same(current, _parse(doc, rule["then"], str(c))) for c in rule["choices"])


def unmet(doc: Document) -> list[tuple[int, dict[str, Any]]]:
    """The rules (number from 1, rule) that hold but whose value is not a choice."""
    out = []
    for i, rule in enumerate(rules(doc), start=1):
        if rule.get("off"):
            continue
        try:
            if passes(doc, rule) and not _met(doc, rule):
                out.append((i, rule))
        except (RuleError, configs.ConfigurationError):
            continue
    return out


def warnings(doc: Document) -> list[str]:
    """A message for every rule that is not met (shown after a rebuild)."""
    return [
        f"Rule {i}: {rule['then']} should be one of {', '.join(map(str, rule['choices']))} "
        f"when {rule['if']} {rule['test']} {rule.get('value', '')}. "
        "Use Apply Rules in the design table to set it."
        for i, rule in unmet(doc)
    ]


def apply(doc: Document) -> list[str]:
    """Run the rules top to bottom on the live values, setting each unmet value to its
    first choice. Returns the paths changed. Raises RuleError for a broken rule."""
    changed = []
    for rule in rules(doc):
        if rule.get("off"):
            continue
        try:
            holds = passes(doc, rule) and not _met(doc, rule)
        except configs.ConfigurationError as exc:
            raise RuleError(str(exc)) from exc
        if holds:
            configs.set_value(doc, rule["then"], _parse(doc, rule["then"], str(rule["choices"][0])))
            changed.append(str(rule["then"]))
    return changed


# Trial values ---------------------------------------------------------------------------


def trial(doc: Document, columns: list[str], values: list[str]) -> Document:
    """A copy of the part with a row of design table values put in and the rules run,
    without adding a configuration (TR331 item 3). Raises RuleError."""
    from fdcad.core import design_table as dt

    work = copy.deepcopy(doc)
    filled = theme_filled(work, columns, values)
    for path, typed in filled.items():
        if dt.is_meta(path) or not typed.strip():
            continue
        configs.set_value(work, path, _parse(work, path, typed))
    apply(work)
    return work


def theme_filled(doc: Document, columns: list[str], values: list[str]) -> dict[str, str]:
    """A row's cells by path, with empty cells filled from the row's theme (the theme
    column itself is left out). Cells typed in the row win. Raises RuleError."""
    cells = dict(zip(columns, values, strict=False))
    name = cells.pop(THEME, "").strip()
    if not name:
        return cells
    found = next((v for k, v in themes(doc).items() if k.casefold() == name.casefold()), None)
    if found is None:
        raise RuleError(f'There is no theme named "{name}". Pick one of the themes.')
    out = dict(found)
    out.update({k: v for k, v in cells.items() if v.strip()})
    return out
