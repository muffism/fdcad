"""Formulas follow a feature rename (IDEAS.md item 3, DECISIONS D527).

Formulas name feature values as ``"depth@Extrude 1"`` (D390). When a feature or
sketch is renamed, every quoted name whose text after the last ``@`` is exactly
the old name gets the new name. Only whole names match, so renaming
"Extrude 1" leaves ``"depth@Extrude 10"`` alone, and the id form
``"depth@f6"`` never changes. Names cannot be written without quotes (``@``
and spaces are not name characters), so only quoted names are rewritten.

Places searched: feature values and sketch dimensions, suppression formulas,
global variables, configuration overrides, design table cells and graph node
formulas. Pure Python: no Qt, no kernel.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.document.model import Document, Feature, Param, Variable
from fdcad.core.units.expressions import quoted_spans

_SUPPRESSION = "suppression"
#: Graph node settings that hold a formula without its leading ``=``.
_FORMULA_SETTINGS = ("formula",)
#: Changes the names in one formula text (``implicit``: a graph formula setting).
Fix = Callable[..., str]


def rename_in_formula(text: str, old: str, new: str, implicit: bool = False) -> str:
    """``text`` with every quoted ``"<value>@<old>"`` changed to ``"<value>@<new>"``.

    Only formulas (text starting with ``=``) hold names; with ``implicit`` the
    text is a formula even without the ``=`` (graph formula settings).
    """
    old = old.strip()
    if not old or old == new.strip() or '"' in new or old not in text:
        return text
    source = text
    if implicit and not text.lstrip().startswith("="):
        source = "=" + text
    spans = quoted_spans(source)
    if not spans:
        return text
    out: list[str] = []
    last = 0
    changed = False
    for start, end in spans:
        inner = source[start:end]
        target, at, owner = inner.rpartition("@")
        if not at or owner.strip() != old:
            continue
        lead = owner[: len(owner) - len(owner.lstrip())]
        trail = owner[len(owner.rstrip()) :]
        out.append(source[last:start])
        out.append(f"{target}@{lead}{new.strip()}{trail}")
        last = end
        changed = True
    if not changed:
        return text
    out.append(source[last:])
    result = "".join(out)
    return result[1:] if source is not text else result


@dataclass
class Rewrite:
    """Edited copies of everything a rename changes. Empty fields changed nothing."""

    features: dict[str, Feature] = field(default_factory=dict)
    variables: list[Variable] | None = None
    configurations: dict[str, Any] | None = None
    graphs: list[Any] | None = None

    @property
    def empty(self) -> bool:
        """True when no formula used the old name."""
        return (
            not self.features
            and self.variables is None
            and self.configurations is None
            and self.graphs is None
        )


def _param(value: Any, fix: Fix) -> Any:
    """A Param or stored ``{"expr", "value"}`` with its formula renamed, else None."""
    if isinstance(value, Param):
        expr = fix(value.expr)
        return Param(expr, value.value) if expr != value.expr else None
    if isinstance(value, dict) and isinstance(value.get("expr"), str):
        expr = fix(value["expr"])
        return {**value, "expr": expr} if expr != value["expr"] else None
    return None


def _feature(feature: Feature, fix: Fix) -> Feature | None:
    edited: Feature | None = None

    def work() -> Feature:
        nonlocal edited
        if edited is None:
            edited = copy.deepcopy(feature)
        return edited

    for name, value in feature.params.items():
        renamed = _param(value, fix)
        if renamed is not None:
            work().params[name] = renamed
    rule = feature.data.get(_SUPPRESSION)
    if isinstance(rule, str):
        renamed_rule = fix(rule)
        if renamed_rule != rule:
            work().data[_SUPPRESSION] = renamed_rule
    dims = feature.data.get("dimensions")
    if isinstance(dims, list):
        for i, dim in enumerate(dims):
            if not isinstance(dim, dict):
                continue
            renamed = _param(dim.get("param"), fix)
            if renamed is not None:
                work().data["dimensions"][i]["param"] = renamed
    return edited


def _configurations(block: Any, fix: Fix) -> dict[str, Any] | None:
    if not isinstance(block, dict):
        return None
    edited = copy.deepcopy(block)
    changed = False
    for item in edited.get("items") or []:
        overrides = item.get("overrides") if isinstance(item, dict) else None
        if not isinstance(overrides, dict):
            continue
        for path, value in overrides.items():
            renamed = _param(value, fix)
            if renamed is not None:
                overrides[path] = renamed
                changed = True
    table = edited.get("design_table")
    if isinstance(table, dict):
        for row in table.get("rows") or []:
            values = row.get("values") if isinstance(row, dict) else None
            if not isinstance(values, list):
                continue
            for i, cell in enumerate(values):
                if isinstance(cell, str):
                    renamed_cell = fix(cell)
                    if renamed_cell != cell:
                        values[i] = renamed_cell
                        changed = True
    return edited if changed else None


def _graphs(graphs: list[Any], fix: Fix) -> list[Any] | None:
    edited = copy.deepcopy(graphs)
    changed = False
    for graph in edited:
        for node in getattr(graph, "nodes", []):
            for key, value in node.params.items():
                if isinstance(value, str) and key in _FORMULA_SETTINGS:
                    renamed_text = fix(value, True)
                    if renamed_text != value:
                        node.params[key] = renamed_text
                        changed = True
                    continue
                renamed = _param(value, fix)
                if renamed is not None:
                    node.params[key] = renamed
                    changed = True
    return edited if changed else None


def rename_rewrite(doc: Document, old: str, new: str) -> Rewrite:
    """Edited copies of the features, variables, configurations and graphs whose
    formulas name ``old`` (a feature's display name), changed to ``new``.

    ``doc`` is not changed; the caller applies the copies in one undoable step.
    """
    if not old.strip() or old.strip() == new.strip():
        return Rewrite()

    def fix(text: str, implicit: bool = False) -> str:
        return rename_in_formula(text, old, new, implicit)

    return _rewrite(doc, fix)


def _rewrite(doc: Document, fix: Fix) -> Rewrite:
    """Edited copies of everything whose formulas ``fix`` changes."""
    out = Rewrite()
    for feature in doc.features:
        edited = _feature(feature, fix)
        if edited is not None:
            out.features[feature.id] = edited
    variables = [dataclasses.replace(v, expr=fix(v.expr)) for v in doc.variables]
    if any(a.expr != b.expr for a, b in zip(variables, doc.variables, strict=True)):
        out.variables = variables
    out.configurations = _configurations(doc.configurations, fix)
    if doc.graphs:
        out.graphs = _graphs(doc.graphs, fix)
    return out


def rename_value_in_formula(
    text: str, owners: tuple[str, ...], old: str, new: str, implicit: bool = False
) -> str:
    """``text`` with every quoted ``"<old>@<owner>"`` changed to ``"<new>@<owner>"`` for
    the owner names in ``owners`` (a feature's name and id): a value was named (TR32)."""
    if not old or old == new or old not in text:
        return text
    source = text
    if implicit and not text.lstrip().startswith("="):
        source = "=" + text
    spans = quoted_spans(source)
    out: list[str] = []
    last = 0
    changed = False
    for start, end in spans:
        target, at, owner = source[start:end].rpartition("@")
        if not at or target.strip() != old or owner.strip() not in owners:
            continue
        out.append(source[last:start])
        out.append(f"{new}@{owner}")
        last = end
        changed = True
    if not changed:
        return text
    out.append(source[last:])
    result = "".join(out)
    return result[1:] if source is not text else result


def value_rename_rewrite(doc: Document, feature: Feature, old: str, new: str) -> Rewrite:
    """Edited copies of everything whose formulas name the value ``old`` of ``feature``
    (``"old@Feature name"`` or ``"old@f6"``), changed to ``new`` (TR32, D698)."""
    owners = (feature.name.strip(), feature.id)
    if not old or old == new:
        return Rewrite()

    def fix(text: str, implicit: bool = False) -> str:
        return rename_value_in_formula(text, owners, old, new, implicit)

    return _rewrite(doc, fix)


__all__ = [
    "Rewrite",
    "rename_in_formula",
    "rename_rewrite",
    "rename_value_in_formula",
    "value_rename_rewrite",
]
