"""Solve every typed value of a part together (equations manager, DECISIONS D390).

A *cell* is one value with typed text:

- ``variable``: a global variable, referenced as ``Width`` or ``"Width"``.
- ``equation``: a feature value (a typed parameter or a sketch dimension),
  referenced as ``"depth@Extrude 1"`` or ``"d1@Sketch 1"``. The feature id
  works too: ``"depth@f6"``.
- ``feature``: a feature's suppression set by a formula (``suppression`` key of
  the feature). Nonzero means suppressed; ``suppressed`` and ``unsuppressed``
  are names for 1 and 0. Nothing can refer to it.

Cells are evaluated in dependency order. Cells that refer to each other in a
loop get a circular reference error; cells that use a cell with an error get
an error too. Every other cell still evaluates, so one bad equation never
stops the rest. Pure Python: no kernel and no Qt.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.units import ExpressionError, Kind, evaluate
from fdcad.core.units.expressions import references

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
#: What a global variable name may look like.
VARIABLE_NAME = _NAME
SECTIONS = ("variable", "feature", "equation")
#: Names a suppression formula may use for its two states.
SUPPRESSION_NAMES: dict[str, tuple[Kind, float]] = {
    "suppressed": (Kind.NUMBER, 1.0),
    "unsuppressed": (Kind.NUMBER, 0.0),
    # Tick box formulas (TR275, D837) give on or off the same way.
    "true": (Kind.NUMBER, 1.0),
    "false": (Kind.NUMBER, 0.0),
}


@dataclass(frozen=True)
class Cell:
    """One typed value of the part.

    ``key`` is unique and stable: ``var:Width``, ``param:f6:depth``,
    ``dim:f5:d1`` or ``suppress:f9``. ``name`` is how formulas refer to it
    (empty for suppression cells, which nothing can use).
    """

    key: str
    section: str
    name: str
    kind: Kind
    expr: str
    fid: str | None = None
    target: str | None = None

    @property
    def is_formula(self) -> bool:
        """True when the typed text is a formula (starts with ``=``)."""
        return self.expr.strip().startswith("=")


@dataclass
class Solution:
    """Values and errors by cell key, and every name formulas can use."""

    values: dict[str, float] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    namespace: dict[str, tuple[Kind, float]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)

    def error_for(self, keys: Iterable[str]) -> str | None:
        """The first error among ``keys``, or None."""
        return next((self.errors[k] for k in keys if k in self.errors), None)


def dimension_kind(dim_type: str) -> Kind:
    """Unit kind of a sketch dimension type."""
    return Kind.ANGLE if dim_type == "angle" else Kind.LENGTH


def _param_kind(feature: Feature, name: str) -> Kind | None:
    from fdcad.core.features import REGISTRY

    ftype = REGISTRY.get(feature.type)
    return ftype.kind_of(name) if ftype is not None else None


def param_name(feature: Feature, target: str) -> str:
    """How formulas refer to a feature value: ``depth@Extrude 1``, or the user's name
    for it, ``wall@Shell 1`` (TR32)."""
    from fdcad.core.equations.value_names import value_name

    return f"{value_name(feature, target)}@{feature.name}"


def cells(doc: Document) -> list[Cell]:
    """Every cell of the part, variables first, then the features in tree order."""
    from fdcad.core.equations.variable_types import is_text, number_expr

    # Text variables are not names formulas use (TR417, D2104).
    out = [
        Cell(f"var:{v.name}", "variable", v.name, v.kind, number_expr(v))
        for v in doc.variables
        if not is_text(v)
    ]
    for feature in doc.features:
        for name, value in feature.params.items():
            if isinstance(value, Param):
                kind = _param_kind(feature, name)
                if kind is not None:
                    out.append(
                        Cell(
                            f"param:{feature.id}:{name}",
                            "equation",
                            param_name(feature, name),
                            kind,
                            value.expr,
                            feature.id,
                            name,
                        )
                    )
        if feature.type == "sketch":
            for dim in feature.data.get("dimensions", []):
                param = dim.get("param") if isinstance(dim, dict) else None
                expr = param.expr if isinstance(param, Param) else None
                if isinstance(param, dict) and isinstance(param.get("expr"), str):
                    expr = param["expr"]
                did = dim.get("id") if isinstance(dim, dict) else None
                if expr is None or not isinstance(did, str):
                    continue
                out.append(
                    Cell(
                        f"dim:{feature.id}:{did}",
                        "equation",
                        param_name(feature, did),
                        dimension_kind(str(dim.get("type"))),
                        expr,
                        feature.id,
                        did,
                    )
                )
        rule = feature.data.get("suppression")
        if isinstance(rule, str) and rule.strip():
            out.append(Cell(f"suppress:{feature.id}", "feature", "", Kind.NUMBER, rule, feature.id))
        flags = feature.data.get(FLAG_RULES)
        if isinstance(flags, dict):
            for name, expr in sorted(flags.items()):
                if isinstance(expr, str) and expr.strip() and is_flag(feature.type, name):
                    out.append(
                        Cell(
                            f"flag:{feature.id}:{name}",
                            "feature",
                            "",
                            Kind.NUMBER,
                            expr,
                            feature.id,
                            name,
                        )
                    )
    return out


#: Feature data key: tick box name to the formula that sets it (TR275, D837).
FLAG_RULES = "flag_rules"


def is_flag(ftype: str, name: str) -> bool:
    """True when ``name`` is an on or off setting (a tick box) of feature type ``ftype``."""
    from fdcad.core.features import REGISTRY

    found = REGISTRY.get(ftype)
    spec = next((p for p in found.params if p.name == name), None) if found else None
    return (
        spec is not None
        and spec.kind is None
        and not spec.choices
        and isinstance(spec.default, bool)
    )


def _aliases(doc: Document, cell: Cell) -> list[str]:
    if not cell.name:
        return []
    names = [cell.name]
    if cell.fid is not None and cell.target is not None:
        names.append(f"{cell.target}@{cell.fid}")
        # A named value keeps its automatic name too, so older formulas work (TR32).
        try:
            owner = doc.feature(cell.fid).name
        except KeyError:
            owner = ""
        auto = f"{cell.target}@{owner}"
        if owner and auto not in names:
            names.append(auto)
        short = cell.name.rpartition("@")[0]
        if short != cell.target:
            names.append(f"{short}@{cell.fid}")
    return names


def _strongly_connected(graph: dict[str, list[str]]) -> list[list[str]]:
    """Tarjan's algorithm without recursion. Components come out dependencies first."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    out: list[list[str]] = []
    counter = 0
    for root in graph:
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, i = work.pop()
            if i == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            deps = graph[node]
            if i < len(deps):
                work.append((node, i + 1))
                nxt = deps[i]
                if nxt not in index:
                    work.append((nxt, 0))
                elif nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
                continue
            for dep in deps:
                if dep in on_stack:
                    low[node] = min(low[node], low[dep])
            if low[node] == index[node]:
                comp: list[str] = []
                while True:
                    top = stack.pop()
                    on_stack.discard(top)
                    comp.append(top)
                    if top == node:
                        break
                out.append(comp)
    return out


def _cycle_text(names: list[str], variables_only: bool) -> str:
    path = " -> ".join([*names, names[0]])
    what = "variables" if variables_only else "values"
    return f"Circular reference: {path}. Change one of these {what}."


#: Values a feature type measures while it builds, which formulas may read (TR57).
MEASURED_VALUES: dict[str, tuple[str, ...]] = {
    "fill_pattern": ("count",),
    "hole": ("count",),  # TR397 (D1508): how many holes the feature made
    "bounding_box": ("length", "width", "height", "volume"),  # TR69 (D809)
    "sensor": ("value",),  # TR86 (D1022)
    "flatten": (  # TR172 (D1106): flat pattern data for quoting
        "blank_area",
        "outer_cut_length",
        "inner_cut_length",
        "cut_outs",
        "bends",
        "flat_length",
        "flat_width",
    ),
    "measurement": (  # TR190 (D818)
        "distance",
        "length",
        "diameter",
        "radius",
        "area",
        "angle",
        "dx",
        "dy",
        "dz",
        "volume",
    ),
}


#: Where the app keeps the printer in use's values in ``Document.measured`` (TR180).
PRINTER_KEY = "__printer__"


def printer_names(doc: Document) -> dict[str, tuple[Kind, float]]:
    """The printer's fit values as equation names (TR180, D812): ``"fit_tolerance@Printer"``
    (the gap per side), and the diameter change of each fit preset,
    ``"clearance_fit@Printer"``, ``"slip_fit@Printer"`` and ``"press_fit@Printer"``.
    The app sets the printer in use; without one, FDCAD's default tolerance is used."""
    from fdcad.core.features.hole_data import DEFAULT_FIT_TOLERANCE, fit_offset

    found = doc.measured.get(PRINTER_KEY, {})
    tol = float(found.get("fit_tolerance", DEFAULT_FIT_TOLERANCE))
    out = {"fit_tolerance@Printer": (Kind.LENGTH, tol)}
    for fit in ("clearance", "slip", "press"):
        out[f"{fit}_fit@Printer"] = (Kind.LENGTH, fit_offset(fit, tol))
    return out


def measured_names(doc: Document) -> dict[str, tuple[Kind, float]]:
    """Read only names for measured values: ``count@Fill Pattern 1`` and ``count@f7``.

    The value is the one the last rebuild measured (0 before the first rebuild).
    """
    from fdcad.core.properties import equation_names

    out: dict[str, tuple[Kind, float]] = dict(equation_names(doc))  # TR82 (D810)
    out.update(printer_names(doc))  # TR180 (D812)
    for feature in doc.features:
        for name in MEASURED_VALUES.get(feature.type, ()):
            value = float(doc.measured.get(feature.id, {}).get(name, 0.0))
            out[f"{name}@{feature.name}"] = (Kind.NUMBER, value)
            out[f"{name}@{feature.id}"] = (Kind.NUMBER, value)
    return out


def solve(doc: Document, extra: Iterable[Cell] = ()) -> Solution:
    """Evaluate every cell. ``extra`` adds cells that are being edited (equations manager)."""
    all_cells = cells(doc)
    replaced = {c.key: c for c in extra}
    all_cells = [replaced.pop(c.key, c) for c in all_cells] + list(replaced.values())
    by_key: dict[str, Cell] = {}
    solution = Solution()
    solution.namespace.update(measured_names(doc))
    name_to_key: dict[str, str] = {}
    for cell in all_cells:
        if cell.key in by_key:
            continue
        by_key[cell.key] = cell
        if cell.section == "variable":
            if not _NAME.match(cell.name):
                solution.errors[cell.key] = (
                    f"Invalid variable name '{cell.name}'. Use letters, digits and "
                    "underscores, starting with a letter."
                )
                continue
            if cell.name in name_to_key:
                solution.errors[cell.key] = (
                    f"Variable '{cell.name}' is defined twice. Rename one of them."
                )
                continue
        for alias in _aliases(doc, cell):
            name_to_key.setdefault(alias, cell.key)

    graph: dict[str, list[str]] = {}
    for key, cell in by_key.items():
        used = references(cell.expr)
        graph[key] = sorted({name_to_key[n] for n in used if n in name_to_key})

    for comp in _strongly_connected(graph):
        cyclic = len(comp) > 1 or comp[0] in graph[comp[0]]
        if cyclic:
            members = [k for k in by_key if k in comp]  # document order
            names = [by_key[k].name or k for k in members]
            only_vars = all(by_key[k].section == "variable" for k in members)
            text = _cycle_text(names, only_vars)
            for key in members:
                solution.errors.setdefault(key, text)
            continue
        key = comp[0]
        solution.order.append(key)
        _evaluate_cell(doc, by_key[key], graph[key], by_key, solution)
    return solution


def _evaluate_cell(
    doc: Document, cell: Cell, deps: list[str], by_key: dict[str, Cell], solution: Solution
) -> None:
    if cell.key in solution.errors:
        return
    bad = next((d for d in deps if d in solution.errors), None)
    if bad is not None:
        solution.errors[cell.key] = (
            f'Uses "{by_key[bad].name}", which has an error. Fix that value first.'
        )
        return
    names = solution.namespace
    if cell.section == "feature":
        names = {**SUPPRESSION_NAMES, **names}
    try:
        value = evaluate(cell.expr, cell.kind, doc.units, names)
    except ExpressionError as exc:
        solution.errors[cell.key] = str(exc)
        return
    solution.values[cell.key] = value
    for alias in _aliases(doc, cell):
        solution.namespace.setdefault(alias, (cell.kind, value))


def namespace(doc: Document) -> dict[str, tuple[Kind, float]]:
    """Every name a formula in this part can use, with its kind and value.

    Raises ExpressionError when a global variable has an error, like
    ``evaluate_variables``, so callers keep their variable error messages.
    """
    return namespace_from(doc, solve(doc))


def namespace_from(doc: Document, solution: Solution) -> dict[str, tuple[Kind, float]]:
    """``namespace`` from a solution already made for ``doc``, without solving again."""
    for v in doc.variables:
        message = solution.errors.get(f"var:{v.name}")
        if message is not None:
            if message.startswith("Circular reference") or message.startswith("Invalid"):
                raise ExpressionError(message)
            if message.startswith("Variable "):
                raise ExpressionError(message)
            raise ExpressionError(f"Variable '{v.name}': {message}")
    return solution.namespace
