"""Rows of the equations manager and how they change the part (DECISIONS D390).

The manager shows three sections:

- ``variable``: every global variable.
- ``feature``: features whose suppression is set by a formula.
- ``equation``: feature values (parameters and sketch dimensions) whose typed
  text is a formula.

``rows_for`` reads the rows from a part; ``apply_rows`` turns edited rows into
the new variable list and edited copies of the changed features, which the UI
applies as one undoable command. Pure Python: no Qt, no kernel.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from fdcad.core.document.model import Document, Feature, Param, Variable
from fdcad.core.equations.engine import (
    FLAG_RULES,
    VARIABLE_NAME,
    cells,
    dimension_kind,
    is_flag,
    param_name,
    solve,
)
from fdcad.core.units import ExpressionError, Kind
from fdcad.core.units.expressions import MM_PER_UNIT, result_kind

#: Key in ``Feature.data`` for comments by value name ("suppressed" for suppression).
COMMENTS = "comments"
#: Key in ``Feature.data`` for the suppression formula.
SUPPRESSION = "suppression"
#: Feature data key: value name to the formula of a disabled equation (TR194, D830).
OFF_EQUATIONS = "off_equations"


@dataclass
class Row:
    """One row of the manager. ``name`` is shown in quotes; ``expr`` starts with ``=``."""

    section: str
    name: str
    expr: str
    comment: str = ""
    kind: Kind | None = None  # variables only; None picks it from the value
    #: An equation kept but not used (TR194, D830): the value stays a plain number.
    disabled: bool = False


class EquationError(ValueError):
    """A row cannot be applied. The message says which row and what to do."""


def unquote(text: str) -> str:
    """``"Width"`` to ``Width``; text without quotes is only stripped."""
    t = text.strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        return t[1:-1].strip()
    return t.strip('"').strip()


def quote(name: str) -> str:
    """The name as the manager shows it: ``"Width"``."""
    return f'"{unquote(name)}"'


def _comment(feature: Feature, target: str) -> str:
    comments = feature.data.get(COMMENTS)
    return str(comments.get(target, "")) if isinstance(comments, dict) else ""


def rows_for(doc: Document) -> list[Row]:
    """The manager's rows, section by section, in tree order."""
    rows = [Row("variable", v.name, v.expr, v.comment, v.kind) for v in doc.variables]
    for feature in doc.features:
        rule = feature.data.get(SUPPRESSION)
        if isinstance(rule, str) and rule.strip():
            rows.append(Row("feature", feature.name, rule, _comment(feature, "suppressed")))
        flags = feature.data.get(FLAG_RULES)
        for name, expr in sorted(flags.items()) if isinstance(flags, dict) else ():
            if isinstance(expr, str) and expr.strip():
                label = f"{name}@{feature.name}"
                rows.append(Row("feature", label, expr, _comment(feature, f"flag:{name}")))
    for cell in cells(doc):
        if cell.section != "equation" or not cell.fid or not cell.target:
            continue
        feature = doc.feature(cell.fid)
        off = feature.data.get(OFF_EQUATIONS)
        if cell.is_formula:
            rows.append(Row("equation", cell.name, cell.expr, _comment(feature, cell.target)))
        elif isinstance(off, dict) and isinstance(off.get(cell.target), str):
            comment = _comment(feature, cell.target)
            rows.append(Row("equation", cell.name, off[cell.target], comment, disabled=True))
    return rows


def _set_off(feature: Feature, target: str, expr: str | None) -> bool:
    """Keep ``expr`` as the disabled formula of ``target`` (None removes it). True when
    something changed."""
    off = dict(feature.data.get(OFF_EQUATIONS) or {})
    before = off.get(target)
    if expr is None:
        off.pop(target, None)
    else:
        off[target] = expr
    if off:
        feature.data[OFF_EQUATIONS] = dict(sorted(off.items()))
    else:
        feature.data.pop(OFF_EQUATIONS, None)
    return before != expr


def find_value(doc: Document, name: str) -> tuple[Feature, str, Kind] | None:
    """The feature, value name and kind that ``depth@Extrude 1`` (or ``depth@f6``) names."""
    text = unquote(name)
    if "@" not in text:
        return None
    target, _, owner = text.rpartition("@")
    owner = owner.strip()
    for cell in cells(doc):
        if cell.section != "equation" or cell.target != target.strip() or cell.fid is None:
            continue
        feature = doc.feature(cell.fid)
        if owner in (feature.name, feature.id):
            return feature, cell.target, cell.kind
    return None


def find_flag(doc: Document, name: str) -> tuple[Feature, str] | None:
    """The feature and tick box that ``reverse@Extrude 1`` names (TR275), or None."""
    text = unquote(name)
    if "@" not in text:
        return None
    flag, _, owner = text.rpartition("@")
    feature = next((f for f in doc.features if owner.strip() in (f.name, f.id)), None)
    if feature is None or not is_flag(feature.type, flag.strip()):
        return None
    return feature, flag.strip()


def find_feature(doc: Document, name: str) -> Feature | None:
    """The feature with this display name (or id)."""
    text = unquote(name)
    return next((f for f in doc.features if text in (f.name, f.id)), None)


def plain_text(value: float, kind: Kind, doc: Document) -> str:
    """A value as plain typed text in the part's unit (lengths) or degrees (angles)."""
    if kind is Kind.LENGTH:
        return f"{value / MM_PER_UNIT[doc.units]:.10g}"
    if kind is Kind.ANGLE:
        return f"{math.degrees(value):.10g}"
    return f"{value:.10g}"


def _set_comment(feature: Feature, target: str, text: str) -> None:
    comments = dict(feature.data.get(COMMENTS) or {})
    if text.strip():
        comments[target] = text.strip()
    else:
        comments.pop(target, None)
    if comments:
        feature.data[COMMENTS] = dict(sorted(comments.items()))
    else:
        feature.data.pop(COMMENTS, None)


def _value_param(feature: Feature, target: str) -> Param | None:
    value = feature.params.get(target)
    if isinstance(value, Param):
        return value
    for dim in feature.data.get("dimensions", []):
        if isinstance(dim, dict) and dim.get("id") == target:
            param = dim.get("param")
            if isinstance(param, dict):
                param = Param(str(param["expr"]), float(param["value"]))
                dim["param"] = param
            return param if isinstance(param, Param) else None
    return None


def apply_rows(
    doc: Document, rows: list[Row], strict: bool = False
) -> tuple[list[Variable], dict[str, Feature]]:
    """The new variable list and edited copies of the changed features.

    Raises EquationError for a row that names nothing, or a name used twice;
    with ``strict`` (the manager's OK) also for a variable name no formula can
    use. Values are not checked here; the solution shows errors per row.
    """
    work = copy.deepcopy(doc)
    old_vars = {v.name: v for v in doc.variables}
    variables: list[Variable] = []
    seen: set[str] = set()
    names_so_far = solve(doc).namespace
    for row in rows:
        if row.section != "variable":
            continue
        name = unquote(row.name)
        if name in seen:
            raise EquationError(f'"{name}" is defined twice. Rename one of them.')
        if strict and not VARIABLE_NAME.match(name):
            # A name no formula can use: refused at OK, unlike value errors (D390).
            raise EquationError(
                f'"{name}" is not a valid variable name. '
                "Use letters, digits and underscores, starting with a letter."
            )
        from fdcad.core.units.expressions import reserved_name

        clash = reserved_name(name) if strict and name not in old_vars else None
        if clash:  # TR310 (D919); names in parts made before are kept
            raise EquationError(clash)
        seen.add(name)
        kind = row.kind or (old_vars[name].kind if name in old_vars else None)
        if kind is None:
            try:
                kind = result_kind(row.expr, doc.units, names_so_far)
            except ExpressionError:
                kind = Kind.NUMBER
        old = old_vars.get(name)
        value = old.value if old is not None else 0.0
        allowed = old.allowed if old is not None else None  # kept through edits (TR274)
        # A CSV lookup (TR198, D2102) stays while the value is the one read.
        lookup = old.lookup if old is not None and old.expr == row.expr.strip() else None
        from fdcad.core.equations.variable_types import guess_type

        variables.append(
            Variable(
                name,
                kind,
                row.expr.strip(),
                value,
                row.comment.strip(),
                allowed,
                lookup,
                guess_type(row.expr, old),  # TR417 (D2104)
                old.group if old is not None else "",
            )
        )
    work.variables = variables

    touched: set[str] = set()
    wanted_rules: dict[str, Row] = {}
    wanted_flags: dict[tuple[str, str], Row] = {}
    for row in rows:
        if row.section != "feature":
            continue
        flag = find_flag(work, row.name)
        if flag is not None:  # a tick box set by a formula (TR275)
            if (flag[0].id, flag[1]) in wanted_flags:
                raise EquationError(f'"{unquote(row.name)}" has two formulas. Delete one.')
            wanted_flags[(flag[0].id, flag[1])] = row
            continue
        feature = find_feature(work, row.name)
        if feature is None:
            raise EquationError(
                f'No feature is named "{unquote(row.name)}". Type the name as the tree shows it.'
            )
        if feature.id in wanted_rules:
            raise EquationError(f'"{feature.name}" has two suppression formulas. Delete one.')
        wanted_rules[feature.id] = row
    for feature in work.features:
        rule_row = wanted_rules.get(feature.id)
        old_rule = feature.data.get(SUPPRESSION)
        new_rule = rule_row.expr.strip() if rule_row is not None else None
        if new_rule != old_rule:
            if new_rule:
                feature.data[SUPPRESSION] = new_rule
            else:
                feature.data.pop(SUPPRESSION, None)
            touched.add(feature.id)
        comment = rule_row.comment if rule_row is not None else ""
        if comment.strip() != _comment(feature, "suppressed"):
            _set_comment(feature, "suppressed", comment)
            touched.add(feature.id)
        old_flags = dict(feature.data.get(FLAG_RULES) or {})
        new_flags = {
            name: row.expr.strip() for (fid, name), row in wanted_flags.items() if fid == feature.id
        }
        if new_flags != old_flags:
            if new_flags:
                feature.data[FLAG_RULES] = dict(sorted(new_flags.items()))
            else:
                feature.data.pop(FLAG_RULES, None)
            touched.add(feature.id)
        for name in set(old_flags) | set(new_flags):
            flag_row = wanted_flags.get((feature.id, name))
            note = flag_row.comment if flag_row is not None else ""
            if note.strip() != _comment(feature, f"flag:{name}"):
                _set_comment(feature, f"flag:{name}", note)
                touched.add(feature.id)

    wanted: dict[tuple[str, str], Row] = {}
    for row in rows:
        if row.section != "equation":
            continue
        found = find_value(work, row.name)
        if found is None:
            raise EquationError(
                f'"{unquote(row.name)}" is not a feature value. '
                'Use the form "depth@Extrude 1" or pick a dimension in the view.'
            )
        feature, target, _kind = found
        if (feature.id, target) in wanted:
            raise EquationError(f'"{unquote(row.name)}" has two equations. Delete one.')
        wanted[(feature.id, target)] = row
    for cell in cells(doc):
        if cell.section != "equation" or cell.fid is None or cell.target is None:
            continue
        feature = work.feature(cell.fid)
        param = _value_param(feature, cell.target)
        if param is None:
            continue
        eq_row = wanted.get((cell.fid, cell.target))
        if eq_row is not None and eq_row.disabled:
            # Kept but not used: the value keeps its number as plain text (TR194).
            if param.expr.startswith("="):
                param.expr = plain_text(param.value, cell.kind, doc)
                touched.add(feature.id)
            if _set_off(feature, cell.target, eq_row.expr.strip()):
                touched.add(feature.id)
            if eq_row.comment.strip() != _comment(feature, cell.target):
                _set_comment(feature, cell.target, eq_row.comment)
                touched.add(feature.id)
        elif eq_row is not None:
            if _set_off(feature, cell.target, None):
                touched.add(feature.id)
            if param.expr != eq_row.expr.strip():
                param.expr = eq_row.expr.strip()
                touched.add(feature.id)
            if eq_row.comment.strip() != _comment(feature, cell.target):
                _set_comment(feature, cell.target, eq_row.comment)
                touched.add(feature.id)
        elif cell.is_formula:
            # The equation was deleted: the value keeps its current number as plain text.
            param.expr = plain_text(param.value, cell.kind, doc)
            _set_comment(feature, cell.target, "")
            touched.add(feature.id)
        elif _set_off(feature, cell.target, None):  # a disabled equation was deleted
            _set_comment(feature, cell.target, "")
            touched.add(feature.id)
    return variables, {fid: work.feature(fid) for fid in touched}


@dataclass
class RowResult:
    """What one row evaluates to: a value with its kind, or an error message."""

    value: float | None
    kind: Kind
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True when the row is valid and evaluates."""
        return self.error is None and self.value is not None


def preview(doc: Document, rows: list[Row]) -> list[RowResult]:
    """Solve the part as the rows would leave it; one result per row, in order."""
    try:
        variables, features = apply_rows(doc, rows)
    except EquationError as exc:
        return [RowResult(None, Kind.NUMBER, str(exc)) for _ in rows]
    work = copy.copy(doc)
    work.variables = variables
    work.features = [features.get(f.id, f) for f in doc.features]
    solution = solve(work)
    kinds = {c.key: c.kind for c in cells(work)}
    out: list[RowResult] = []
    for row in rows:
        if row.disabled:
            out.append(RowResult(None, Kind.NUMBER))
            continue
        key = ""
        if row.section == "variable":
            key = f"var:{unquote(row.name)}"
        elif row.section == "feature":
            flag = find_flag(work, row.name)
            if flag is not None:
                key = f"flag:{flag[0].id}:{flag[1]}"
            else:
                feature = find_feature(work, row.name)
                key = f"suppress:{feature.id}" if feature else ""
        else:
            found = find_value(work, row.name)
            if found is not None:
                feature, target, _kind = found
                is_param = isinstance(feature.params.get(target), Param)
                key = f"{'param' if is_param else 'dim'}:{feature.id}:{target}"
        kind = kinds.get(key, Kind.NUMBER)
        if key in solution.errors:
            out.append(RowResult(None, kind, solution.errors[key]))
        else:
            out.append(RowResult(solution.values.get(key), kind))
    return out


def value_names(doc: Document) -> list[str]:
    """Every feature value a row can name, for completion: ``depth@Extrude 1``."""
    return [c.name for c in cells(doc) if c.section == "equation"]


__all__ = [
    "EquationError",
    "Row",
    "RowResult",
    "apply_rows",
    "dimension_kind",
    "find_feature",
    "find_value",
    "param_name",
    "plain_text",
    "preview",
    "quote",
    "rows_for",
    "unquote",
    "value_names",
]
