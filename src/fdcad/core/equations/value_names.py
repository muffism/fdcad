"""Names the user gives to dimensions and feature values (TUTORIAL_REVIEW_SPEC TR32, D698).

A sketch dimension keeps its name in its own ``name`` key; a feature value in
the feature's ``value_names`` key (value to name). Formulas then refer to it as
``"wall@Shell 1"``; the automatic name (``"thickness@Shell 1"``, ``"d1@Sketch 1"``)
keeps working, so older formulas never break. Naming or renaming a value
rewrites every formula that used the old name in the same step. No Qt.
"""

from __future__ import annotations

import copy
from typing import Any

from fdcad.core.document.model import Document, Feature
from fdcad.core.equations.rename import Rewrite, value_rename_rewrite

#: Feature data key holding ``{value: name}``.
VALUE_NAMES = "value_names"


class ValueNameError(ValueError):
    """The name cannot be used; the message says why."""


def value_name(feature: Feature, target: str) -> str:
    """The name of value ``target`` of ``feature`` (a parameter or a dimension id): the
    user's name, else the automatic one (``target`` itself)."""
    if feature.type == "sketch":
        for dim in feature.data.get("dimensions", []):
            if isinstance(dim, dict) and dim.get("id") == target:
                name = dim.get("name")
                return name if isinstance(name, str) and name else target
        return target
    names = feature.data.get(VALUE_NAMES)
    if isinstance(names, dict):
        name = names.get(target)
        if isinstance(name, str) and name:
            return name
    return target


def _targets(feature: Feature) -> list[str]:
    if feature.type == "sketch":
        return [
            str(d.get("id"))
            for d in feature.data.get("dimensions", [])
            if isinstance(d, dict) and isinstance(d.get("id"), str)
        ]
    return list(feature.params)


def name_problem(feature: Feature, target: str, name: str) -> str:
    """Why ``name`` cannot name value ``target``, or "" when it can ("" clears it)."""
    from fdcad.core.equations.engine import VARIABLE_NAME

    clean = name.strip()
    if not clean:
        return ""
    if not VARIABLE_NAME.match(clean):
        return (
            "Type a name that starts with a letter and has only letters, digits and "
            "underscores, for example wall or hole_depth."
        )
    from fdcad.core.units.expressions import reserved_name

    clash = reserved_name(clean)  # TR310 (D919)
    if clash:
        return clash
    for other in _targets(feature):
        if other == target:
            continue
        if clean == other or clean == value_name(feature, other):
            return f"{feature.name} already has a value called {clean}. Choose another name."
    return ""


def renamed_values(before: Feature, after: Feature) -> list[tuple[str, str]]:
    """(old name, new name) for each value whose name an edit changed, where the old
    name was the user's own (automatic names keep working, so they need no rewrite)."""
    out = []
    for target in _targets(after):
        old, new = value_name(before, target), value_name(after, target)
        if old != new and old != target:
            out.append((old, new))
    return out


def set_value_name(feature: Feature, target: str, name: str) -> None:
    """Store ``name`` for value ``target`` in ``feature`` ("" removes it). No checks."""
    _set(feature, target, name.strip())


def _set(feature: Feature, target: str, name: str) -> None:
    if feature.type == "sketch":
        for dim in feature.data.get("dimensions", []):
            if isinstance(dim, dict) and dim.get("id") == target:
                if name:
                    dim["name"] = name
                else:
                    dim.pop("name", None)
        return
    names: dict[str, Any] = dict(feature.data.get(VALUE_NAMES) or {})
    if name:
        names[target] = name
    else:
        names.pop(target, None)
    if names:
        feature.data[VALUE_NAMES] = names
    else:
        feature.data.pop(VALUE_NAMES, None)


def name_value(doc: Document, fid: str, target: str, name: str) -> Rewrite:
    """Edited copies of everything that changes when value ``target`` of feature ``fid``
    is named ``name`` ("" goes back to the automatic name): the feature itself, and
    every formula that used the old name. ``doc`` is not changed. Raises ValueNameError."""
    feature = doc.feature(fid)
    problem = name_problem(feature, target, name)
    if problem:
        raise ValueNameError(problem)
    clean = name.strip()
    old = value_name(feature, target)
    new = clean or target
    out = value_rename_rewrite(doc, feature, old, new) if old != new else Rewrite()
    edited = copy.deepcopy(out.features.get(fid, feature))
    _set(edited, target, clean)
    out.features[fid] = edited
    return out


__all__ = [
    "VALUE_NAMES",
    "ValueNameError",
    "name_problem",
    "name_value",
    "renamed_values",
    "set_value_name",
    "value_name",
]
