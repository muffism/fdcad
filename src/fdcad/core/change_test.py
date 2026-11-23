"""Change test (TR287, DECISIONS D774).

On a copy of the part, each typed value (feature values and sketch dimensions
typed as plain numbers, and global variables) is stepped up and down by a set
percent, one at a time, and the part is rebuilt. A value whose step makes a
feature fail, or changes how many faces the part has, is reported, with the safe
range: how many steps each way still rebuild with the same faces. Nothing in the
part changes. Kernel work, run in a kernel job (CLAUDE.md 5.2); it can be
stopped between rebuilds.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.names import faces_of
from fdcad.core.rebuild.engine import RebuildEngine


@dataclass(frozen=True)
class Value:
    """One value the test steps: where it is and what it is called."""

    label: str  # "depth@Extrude 1", "d1@Sketch 1" or a variable name
    fid: str | None  # the feature, or None for a variable
    key: str  # the parameter name, the dimension id, or the variable name
    kind: str  # "param", "dimension" or "variable"
    value: float


@dataclass
class ValueResult:
    """What stepping one value did. ``down`` and ``up`` are the steps that still rebuild
    with the same faces (0 when the first step already breaks it)."""

    value: Value
    down: int
    up: int
    problem: str = ""  # the first failure or face change, in words

    @property
    def safe(self) -> bool:
        """True when every step tried kept the part as it is."""
        return not self.problem


@dataclass
class ChangeTest:
    """The whole result."""

    percent: float
    steps: int
    results: list[ValueResult] = field(default_factory=list)
    stopped: bool = False


def values_of(doc: Document) -> list[Value]:
    """Every value typed as a plain number (formulas follow other values and are left)."""
    out: list[Value] = []
    for v in doc.variables:
        if not v.expr.strip().startswith("=") and v.value != 0:
            out.append(Value(v.name, None, v.name, "variable", v.value))
    for f in doc.features:
        if f.suppressed:
            continue
        for name, p in f.params.items():
            if isinstance(p, Param) and not p.expr.strip().startswith("=") and p.value > 0:
                out.append(Value(f"{name}@{f.name}", f.id, name, "param", p.value))
        for d in f.data.get("dimensions", []) if f.type == "sketch" else []:
            param = d.get("param") if isinstance(d, dict) else None
            expr = str(param.get("expr", "")) if isinstance(param, dict) else ""
            value = float(param.get("value", 0)) if isinstance(param, dict) else 0.0
            if d.get("driving", True) and not expr.strip().startswith("=") and value > 0:
                out.append(Value(f"{d['id']}@{f.name}", f.id, str(d["id"]), "dimension", value))
    return out


def _set(doc: Document, v: Value, number: float) -> None:
    text = f"{number:.10g}"
    if v.kind == "variable":
        for var in doc.variables:
            if var.name == v.key:
                # Keep the unit the value was typed in: scale the stored text's number.
                var.expr = _scaled(var.expr, number / v.value)
                var.value = number
    elif v.kind == "param":
        old = doc.feature(str(v.fid)).params[v.key]
        assert isinstance(old, Param)
        doc.feature(str(v.fid)).params[v.key] = Param(_scaled(old.expr, number / v.value), number)
    else:
        for d in doc.feature(str(v.fid)).data.get("dimensions", []):
            if isinstance(d, dict) and d.get("id") == v.key:
                expr = str(d["param"].get("expr", text)) if isinstance(d["param"], dict) else text
                d["param"] = {"expr": _scaled(expr, number / v.value), "value": number}


def _scaled(expr: str, factor: float) -> str:
    """The typed text with its number scaled, its unit kept ("20mm" to "22mm")."""
    import re

    match = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)(.*)$", expr)
    if match is None:
        return expr
    return f"{float(match.group(1)) * factor:.10g}{match.group(2)}"


def _shape(doc: Document, engine: RebuildEngine) -> tuple[str, int]:
    """("", face count) when the part rebuilds, else (the first error, 0)."""
    report = engine.rebuild(doc)
    for f in doc.features:
        result = report.results.get(f.id)
        if result is not None and result.state is FeatureState.ERROR:
            message = result.issues[0].message if result.issues else f"{f.name} failed."
            return message, 0
    body = report.body
    return "", len(faces_of(body.shape)) if body is not None else 0


def run(
    doc: Document,
    percent: float = 10.0,
    steps: int = 2,
    values: list[Value] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> ChangeTest:
    """Step every value up and down ``steps`` times by ``percent`` (see the module notes)."""
    if not 0 < percent < 100:
        raise ValueError("the step must be between 0 and 100 percent. Type another step.")
    out = ChangeTest(percent, steps)
    engine = RebuildEngine()
    base_error, base_faces = _shape(copy.deepcopy(doc), engine)
    if base_error:
        raise ValueError(f"the part does not rebuild now: {base_error}")
    chosen = values_of(doc) if values is None else values
    for index, v in enumerate(chosen):
        if cancelled():
            out.stopped = True
            break
        if progress is not None:
            progress(index, len(chosen), v.label)
        reach = {}
        problem = ""
        for sign in (-1, 1):
            good = 0
            for k in range(1, steps + 1):
                number = v.value * (1 + sign * percent / 100 * k)
                if number <= 0:
                    break
                work = copy.deepcopy(doc)
                _set(work, v, number)
                error, faces = _shape(work, engine)
                if error or faces != base_faces:
                    if not problem:
                        word = "down" if sign < 0 else "up"
                        problem = (
                            f"{k * percent:g}% {word}: {error}"
                            if error
                            else f"{k * percent:g}% {word}: the part has {faces} faces "
                            f"instead of {base_faces}."
                        )
                    break
                good = k
            reach[sign] = good
        out.results.append(ValueResult(v, reach[-1], reach[1], problem))
    return out
