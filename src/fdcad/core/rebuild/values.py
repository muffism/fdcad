"""Re-evaluate typed values from their expressions (FDEF_SPEC 3.3).

When a variable changes, every value whose expression uses it gets a new
internal value here, before the rebuild. The typed text is never changed.
Values are solved together by the equations engine, so feature values may use
each other (``"depth@Extrude 1"``) and suppression formulas set suppression
(DECISIONS D390).
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document, Param
from fdcad.core.equations.engine import Cell, Solution, solve
from fdcad.core.units import Kind


def _sketch_param(raw: dict[str, Any]) -> Param | None:
    param: Any = raw.get("param")
    if isinstance(param, dict) and {"expr", "value"} <= set(param):
        value = param["value"]
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None  # a damaged value: the sketch reports it (round 10e, D634)
        param = Param(str(param["expr"]), float(value))
        raw["param"] = param
    return param if isinstance(param, Param) else None


def refresh_values(
    doc: Document,
    variables: dict[str, tuple[Kind, float]] | None = None,
    solution: Solution | None = None,
) -> set[str]:
    """Re-evaluate every typed value. Returns the ids of features whose values changed.

    A value whose text has an error keeps its old value. The values come from
    solving the whole part. ``variables`` holds values set from outside the part's
    own formulas, such as a node graph's Set Variable output (Phase 7): they replace
    those variables' typed text for this solve only, and the typed text is kept.
    """
    if solution is not None:
        solved = solution
    else:
        solved = solve(doc, _overrides(doc, variables) if variables else ())
    values = solved.values
    changed: set[str] = set()
    for feature in doc.features:
        for name, value in feature.params.items():
            new = values.get(f"param:{feature.id}:{name}")
            if isinstance(value, Param) and new is not None and new != value.value:
                value.value = new
                changed.add(feature.id)
        if feature.type == "sketch":
            for raw in feature.data.get("dimensions", []):
                if not isinstance(raw, dict):
                    continue
                param = _sketch_param(raw)
                new = values.get(f"dim:{feature.id}:{raw.get('id')}")
                if param is not None and new is not None and new != param.value:
                    param.value = new
                    changed.add(feature.id)
        rule = values.get(f"suppress:{feature.id}")
        if rule is not None and feature.suppressed != (rule != 0):
            feature.suppressed = rule != 0
            changed.add(feature.id)
        flags = feature.data.get("flag_rules")
        for name in flags if isinstance(flags, dict) else ():
            on = values.get(f"flag:{feature.id}:{name}")
            if on is not None and feature.params.get(name) is not (on != 0):
                feature.params[name] = on != 0  # a tick box set by its formula (TR275)
                changed.add(feature.id)
    for var in doc.variables:
        new = values.get(f"var:{var.name}")
        if new is not None:
            var.value = new
    return changed


_UNITS = {Kind.LENGTH: "mm", Kind.ANGLE: "rad", Kind.NUMBER: ""}


def _overrides(doc: Document, variables: dict[str, tuple[Kind, float]]) -> list[Cell]:
    """Cells that pin variables to the values in ``variables`` where they differ."""
    from fdcad.core.rebuild.engine import document_variables

    try:
        own = {name: value for name, (_kind, value) in document_variables(doc).items()}
    except Exception:  # a broken formula: pin every given value
        own = {}
    out: list[Cell] = []
    for v in doc.variables:
        given = variables.get(v.name)
        if given is None or own.get(v.name) == given[1]:
            continue
        text = f"{given[1]!r}{_UNITS[v.kind]}"
        out.append(Cell(f"var:{v.name}", "variable", v.name, v.kind, text))
    return out
