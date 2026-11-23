"""Sheet metal rule library (TR332, DECISIONS D1111).

A rule is a named set of the Sheet Metal folder's values: thickness, bend radius,
unfold rule (method, K-factor, allowance), reliefs, corner relief and kerf (the cutting
gap), with the material it is meant for as a note. Rules live in a shared JSON file,
outside any part. Applying a rule copies its values into the part's Sheet Metal folder
(one undoable edit) and records the rule's name there, so a part never depends on the
library file. A feature's own bend values (its Own Bend Values group) still override
the rule.

File layout: ``{"format": 1, "rules": {"<name>": {"<key>": value}}}`` where a length or
number is ``{"text": "2", "value": 2.0}`` (mm) and a choice is a string.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from fdcad.core.document.model import Feature, Param

#: Folder params a rule holds: numbers, then choices.
NUMBER_KEYS = (
    "thickness",
    "radius",
    "k_factor",
    "allowance",
    "relief_ratio",
    "relief_width",
    "relief_depth",
    "corner_relief_size",
    "kerf",
)
CHOICE_KEYS = ("method", "relief", "relief_by", "corner_relief")
FORMAT = 1


class RuleError(ValueError):
    """A rule library file that cannot be read or written."""


def rule_of(folder: Feature, material: str = "") -> dict[str, Any]:
    """The rule values of a Sheet Metal folder, with the material it is for (a note)."""
    out: dict[str, Any] = {"material": material} if material else {}
    for key in NUMBER_KEYS:
        item = folder.params.get(key)
        if isinstance(item, Param):
            out[key] = {"text": item.expr, "value": float(item.value)}
    for key in CHOICE_KEYS:
        item = folder.params.get(key)
        if isinstance(item, str):
            out[key] = item
    return out


def apply_rule(folder: Feature, name: str, rule: dict[str, Any]) -> Feature:
    """A copy of ``folder`` with the rule's values and its name in ``rule_name``."""
    edited = copy.deepcopy(folder)
    for key in NUMBER_KEYS:
        item = rule.get(key)
        if isinstance(item, dict) and isinstance(item.get("value"), int | float):
            edited.params[key] = Param(str(item.get("text", item["value"])), float(item["value"]))
    for key in CHOICE_KEYS:
        item = rule.get(key)
        if isinstance(item, str):
            edited.params[key] = item
    edited.params["rule_name"] = name
    edited.params.pop("gauge", None)  # a rule sets its own thickness and radius (D542)
    return edited


def load_rules(path: str | os.PathLike[str]) -> dict[str, dict[str, Any]]:
    """The rules in a library file; an empty library when the file does not exist."""
    target = Path(path)
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuleError(
            f"The rule library {target.name} cannot be read. Check the file, or choose "
            "another library."
        ) from exc
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, dict):
        raise RuleError(
            f"The rule library {target.name} has no rules list. Check the file, or choose "
            "another library."
        )
    return {str(k): v for k, v in rules.items() if isinstance(v, dict)}


def save_rules(path: str | os.PathLike[str], rules: dict[str, dict[str, Any]]) -> None:
    """Write the library file (sorted by name, so the shared file diffs cleanly)."""
    target = Path(path)
    text = json.dumps({"format": FORMAT, "rules": dict(sorted(rules.items()))}, indent=2)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8", newline="\n")
    except OSError as exc:
        raise RuleError(
            f"Could not write the rule library {target.name} ({exc.strerror}). "
            "Check the folder, then save again."
        ) from exc
