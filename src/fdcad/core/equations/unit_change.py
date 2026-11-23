"""Changing the part's units never changes geometry (PLAN.md section 7 item 1,
audit 2026-11-02 D3 item 1, DECISIONS D702).

A length typed as a bare number ("25") takes the part's unit (D66), so a plain
unit switch would turn 25 mm into 25 inches. Before the switch, every length
whose value depends on the part unit is rewritten so it keeps its value: a bare
number gets the old unit ("25" becomes "25mm"), a formula whose result is a plain
number is multiplied by one old unit ("=w*2" becomes "=(w*2)*1mm"), and any other
text that mixes bare numbers and units outside a formula becomes its value in the
old unit. Texts with units, angles and plain numbers are left alone.

Places searched: feature values and sketch dimensions, global variables,
configuration overrides, design table cells and graph node formulas. Pure Python:
no Qt, no kernel.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import re
from collections.abc import Mapping
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.equations.engine import _param_kind, dimension_kind, solve
from fdcad.core.equations.rename import Rewrite
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.core.units.expressions import MM_PER_UNIT

#: The unit written after a rewritten bare number.
_SUFFIX = {UnitSystem.MM: "mm", UnitSystem.IN: "in"}
_BARE = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\Z")

Names = Mapping[str, tuple[Kind, float]]


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def keep_value(
    text: str, kind: Kind | str | None, old: UnitSystem, new: UnitSystem, names: Names
) -> str:
    """``text`` rewritten so it gives the same value in ``new`` units as in ``old``.

    Unchanged when the value does not depend on the part unit, or the text does not
    evaluate (an error stays an error, worded the same).
    """
    if kind is not Kind.LENGTH or old is new or not text.strip():
        return text
    try:
        before = evaluate(text, Kind.LENGTH, old, names)
        after = evaluate(text, Kind.LENGTH, new, names)
    except ExpressionError:
        return text
    if _same(before, after):
        return text
    suffix = _SUFFIX[old]
    stripped = text.strip()
    if _BARE.match(stripped):
        out = f"{stripped}{suffix}"
    elif stripped.startswith("="):
        out = f"=({stripped[1:].strip()})*1{suffix}"
    else:
        out = f"{before / MM_PER_UNIT[old]!r}{suffix}"
    try:
        if _same(evaluate(out, Kind.LENGTH, new, names), before):
            return out
    except ExpressionError:
        pass
    return f"{before / MM_PER_UNIT[old]!r}{suffix}"


def _param(value: Any, kind: Kind | str | None, fix: Any) -> Any:
    """A Param or stored ``{"expr", "value"}`` with its text kept, else None."""
    if isinstance(value, Param):
        expr = fix(value.expr, kind)
        return Param(expr, value.value) if expr != value.expr else None
    if isinstance(value, dict) and isinstance(value.get("expr"), str):
        expr = fix(value["expr"], kind)
        return {**value, "expr": expr} if expr != value["expr"] else None
    return None


def _feature(feature: Feature, fix: Any) -> Feature | None:
    edited: Feature | None = None
    for name, value in feature.params.items():
        kept = _param(value, _param_kind(feature, name), fix)
        if kept is not None:
            edited = edited or copy.deepcopy(feature)
            edited.params[name] = kept
    dims = feature.data.get("dimensions") if feature.type == "sketch" else None
    if isinstance(dims, list):
        for i, dim in enumerate(dims):
            if not isinstance(dim, dict):
                continue
            kept = _param(dim.get("param"), dimension_kind(str(dim.get("type"))), fix)
            if kept is not None:
                edited = edited or copy.deepcopy(feature)
                edited.data["dimensions"][i]["param"] = kept
    return edited


def _path_kind(doc: Document, path: str) -> Kind | str | None:
    from fdcad.core.design_table import DesignTableError, value_kind

    try:
        return value_kind(doc, path)
    except DesignTableError:
        return None


def _configurations(doc: Document, fix: Any) -> dict[str, Any] | None:
    block = doc.configurations
    if not isinstance(block, dict):
        return None
    edited = copy.deepcopy(block)
    changed = False
    for item in edited.get("items") or []:
        overrides = item.get("overrides") if isinstance(item, dict) else None
        if not isinstance(overrides, dict):
            continue
        for path, value in overrides.items():
            kept = _param(value, _path_kind(doc, path), fix)
            if kept is not None:
                overrides[path] = kept
                changed = True
    table = edited.get("design_table")
    if isinstance(table, dict):
        columns = [c if isinstance(c, str) else "" for c in table.get("columns") or []]
        kinds = [_path_kind(doc, c) for c in columns]
        for row in table.get("rows") or []:
            values = row.get("values") if isinstance(row, dict) else None
            if not isinstance(values, list):
                continue
            for i, cell in enumerate(values):
                if isinstance(cell, str) and i < len(kinds):
                    kept_cell = fix(cell, kinds[i])
                    if kept_cell != cell:
                        values[i] = kept_cell
                        changed = True
    return edited if changed else None


def _graphs(graphs: list[Any], fix: Any) -> list[Any] | None:
    from fdcad.core.graph.nodes.base import NODE_TYPES
    from fdcad.core.graph.types import PortType

    edited = copy.deepcopy(graphs)
    changed = False
    for graph in edited:
        for node in getattr(graph, "nodes", []):
            ntype = NODE_TYPES.get(node.type)
            if ntype is None:
                continue
            lengths = {p.name for p in ntype.inputs if p.type is PortType.LENGTH}
            for key, value in node.params.items():
                # Graph inputs keep their value; only formulas are worked out again.
                if key not in lengths or not isinstance(value, Param):
                    continue
                if not value.expr.strip().startswith("="):
                    continue
                kept = _param(value, Kind.LENGTH, fix)
                if kept is not None:
                    node.params[key] = kept
                    changed = True
    return edited if changed else None


def unit_change_rewrite(doc: Document, new: UnitSystem) -> Rewrite:
    """Edited copies of everything whose value would change when ``doc`` switches
    to ``new`` units. ``doc`` is not changed; the caller applies the copies and the
    new unit in one undoable step."""
    old = doc.units
    if old is new:
        return Rewrite()
    names = dict(solve(doc).namespace)

    def fix(text: str, kind: Kind | str | None) -> str:
        return keep_value(text, kind, old, new, names)

    out = Rewrite()
    for feature in doc.features:
        edited = _feature(feature, fix)
        if edited is not None:
            out.features[feature.id] = edited
    variables = [dataclasses.replace(v, expr=fix(v.expr, v.kind)) for v in doc.variables]
    if any(a.expr != b.expr for a, b in zip(variables, doc.variables, strict=True)):
        out.variables = variables
    out.configurations = _configurations(doc, fix)
    if doc.graphs:
        out.graphs = _graphs(doc.graphs, fix)
    return out


def apply_rewrite(doc: Document, rewrite: Rewrite) -> None:
    """Put the copies of ``rewrite`` into ``doc``."""
    for i, feature in enumerate(doc.features):
        if feature.id in rewrite.features:
            doc.features[i] = copy.deepcopy(rewrite.features[feature.id])
    if rewrite.variables is not None:
        doc.variables = copy.deepcopy(rewrite.variables)
    if rewrite.configurations is not None:
        doc.configurations = copy.deepcopy(rewrite.configurations)
    if rewrite.graphs is not None:
        doc.graphs = copy.deepcopy(rewrite.graphs)


def change_units(doc: Document, new: UnitSystem) -> None:
    """Switch ``doc`` to ``new`` units, keeping every value (no undo; see SetUnits)."""
    apply_rewrite(doc, unit_change_rewrite(doc, new))
    doc.units = new
