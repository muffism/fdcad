"""Edit a finished part the way a user does, one number at a time, and check it.

Every stress part so far was built forward, feature by feature (bike frame, gearbox,
sheet part, machine bed). Users mostly change features that are already there. For
each number of each feature (and each variable), ``storm`` nudges it by one percent,
rebuilds with the same engine as the app does (reusing what did not change), and checks:

* no feature that built before fails now (a warning is allowed: the part is new);
* a new engine, building the edited part from nothing, gives the same material and
  the same face names: the reused results were right for the edited part;
* putting the number back gives the first part again, to the same face names.

Run on part files: ``python -m tests.core.features.edit_storm part.fdprt ...``. On a
large part ``--part=K/N`` edits numbers K, K+N, K+2N and so on, so N runs share the work.
"""

from __future__ import annotations

import copy
import math
import re
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine, RebuildReport

STEP = 1.01  # one percent
#: Nudge down instead: one percent less, and one less for a count (``--down``).
DOWN = False


@dataclass
class Look:
    """What a rebuild came to, to compare two rebuilds."""

    failed: frozenset[str]
    volume: float
    names: tuple[str, ...]

    @classmethod
    def of(cls, report: RebuildReport) -> Look:
        failed = frozenset(
            fid for fid, r in report.results.items() if r.state is FeatureState.ERROR
        )
        body = report.body
        volume, names = 0.0, ()
        if body is not None:
            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(body.shape, props, 1e-7)
            volume = float(props.Mass())
            names = tuple(sorted(n for n, _f in body.faces))
        return cls(failed, volume, names)

    def differs(self, other: Look) -> str:
        """Empty when the two are the same part; else what differs."""
        out = []
        if abs(self.volume - other.volume) > 1e-6 * max(abs(other.volume), 1.0):
            out.append(f"volume {self.volume:.6f} against {other.volume:.6f}")
        if self.names != other.names:
            a, b = set(self.names), set(other.names)
            out.append(f"names: {sorted(a - b)[:4]} only here, {sorted(b - a)[:4]} only there")
        if self.failed != other.failed:
            out.append(f"failed {sorted(self.failed)} against {sorted(other.failed)}")
        return "; ".join(out)


@dataclass
class Storm:
    """The edits made and what went wrong."""

    edits: int = 0
    problems: list[str] = field(default_factory=list)
    seconds: float = 0.0


_NUMBER = re.compile(r"^\s*([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)(.*)$")
_COUNTS = ("count", "number", "instances", "copies", "teeth", "sides", "rows", "columns")


def _nudged(expr: str, value: float, name: str) -> tuple[str, float] | None:
    """The typed text and value one step on: one percent more, keeping the unit the
    user typed, or one more for a count (less and one less with ``DOWN``); None for
    formulas, names and full turns."""
    found = _NUMBER.match(expr)
    if found is None or not value:
        return None
    number, unit = float(found.group(1)), found.group(2)
    if unit.strip() and not unit.strip().isalpha() and unit.strip() not in ('"', "°"):
        return None  # a formula: "2*x", "10 + 5"
    if any(word in name.lower() for word in _COUNTS) and number.is_integer():
        more = -1 if DOWN else 1
        if number + more < 1:
            return None
        return f"{int(number) + more}{unit}", value * (number + more) / number
    factor = 1 / STEP if DOWN else STEP
    if math.isclose(abs(value), math.tau) and "angle" in name.lower():
        return None  # a full turn: any change opens the shape, not a small edit (D2602)
    if "angle" in name.lower() and abs(value) * STEP > math.tau:
        factor = 1 / STEP  # nearly a full turn: one percent less
    return f"{number * factor!r}{unit}", value * factor


def _edits(doc: Document) -> Iterator[tuple[str, Callable[[bool], None]]]:
    """Each number of the part: what it is, and a switch between nudged and as it was."""
    for variable in doc.variables:
        step = _nudged(variable.expr, variable.value, variable.name)
        if step is not None:
            was = (variable.expr, variable.value)

            def put_var(on: bool, v: Any = variable, s: Any = step, w: Any = was) -> None:
                v.expr, v.value = s if on else w

            yield f"variable {variable.name}", put_var
    for feature in doc.features:
        if feature.suppressed:
            continue
        for name, param in list(feature.params.items()):
            if not isinstance(param, Param):
                continue
            step = _nudged(param.expr, param.value, name)
            if step is None:
                continue

            def put_param(
                on: bool, f: Any = feature, n: str = name, s: Any = step, w: Any = param
            ) -> None:
                f.params[n] = Param(*s) if on else copy.deepcopy(w)

            yield f"{feature.name} {name}", put_param
        yield from _dimension_edits(feature)
    for graph in doc.graphs:
        for node in graph.nodes:
            for name, param in list(node.params.items()):
                if not isinstance(param, Param):
                    continue
                step = _nudged(param.expr, param.value, name)
                if step is None:
                    continue

                def put_node(
                    on: bool, n: Any = node, k: str = name, s: Any = step, w: Any = param
                ) -> None:
                    n.params[k] = Param(*s) if on else copy.deepcopy(w)

                yield f"{graph.name} {node.id} {node.type} {name}", put_node


def _dimension_edits(feature: Any) -> Iterator[tuple[str, Callable[[bool], None]]]:
    """Each driving dimension of a sketch, as a user types a new value into it. A
    linked dimension is left out: the app changes all of its link together."""
    if feature.type != "sketch":
        return
    for raw in feature.data.get("dimensions", []):
        if not isinstance(raw, dict) or not raw.get("driving", True) or raw.get("off"):
            continue
        if raw.get("link"):
            continue
        param = raw.get("param")
        if isinstance(param, dict):
            param = Param(str(param.get("expr", "")), float(param.get("value", 0.0)))
        if not isinstance(param, Param):
            continue
        step = _nudged(param.expr, param.value, str(raw.get("type", "")))
        if step is None:
            continue

        def put_dim(on: bool, r: Any = raw, s: Any = step, w: Any = param) -> None:
            r["param"] = Param(*s) if on else copy.deepcopy(w)

        yield f"{feature.name} {raw.get('name') or raw.get('id')}", put_dim


def storm(
    doc: Document,
    every: int = 1,
    fresh_every: int = 1,
    limit: int | None = None,
    log: Callable[[str], None] | None = None,
    offset: int = 0,
) -> Storm:
    """Edit every ``every``-th number of ``doc`` in turn (on a copy), checking each,
    starting from number ``offset``. A new engine checks every ``fresh_every``-th edit
    (it builds the whole part)."""
    started = time.perf_counter()
    doc = copy.deepcopy(doc)
    engine = RebuildEngine()
    first = Look.of(engine.rebuild(doc))
    out = Storm()
    for k, (what, put) in enumerate(list(_edits(doc))):
        before = len(out.problems)
        if (k - offset) % every or k < offset:
            continue
        if limit is not None and out.edits >= limit:
            break
        out.edits += 1
        put(True)
        edited = Look.of(engine.rebuild(doc))
        new = sorted(edited.failed - first.failed)
        if new:
            out.problems.append(f"{what} nudged: these fail now: {new}")
        if out.edits % fresh_every == 0:
            fresh = Look.of(RebuildEngine().rebuild(doc))
            if diff := edited.differs(fresh):
                out.problems.append(f"{what} nudged: kept results differ from new: {diff}")
        put(False)
        back = Look.of(engine.rebuild(doc))
        if diff := back.differs(first):
            out.problems.append(f"{what} put back: not the first part: {diff}")
        if log is not None:
            log(f"{out.edits:4} {what}")
            for problem in out.problems[before:]:
                log(f"PROBLEM {problem}")  # at once: a long run may be stopped
    out.seconds = time.perf_counter() - started
    return out


def main(paths: list[str]) -> int:
    """Storm each part file; print what went wrong."""
    every = 1
    fresh = 1
    offset = 0
    global DOWN
    for arg in list(paths):
        if arg == "--down":
            DOWN = True
            paths.remove(arg)
        elif arg.startswith("--part="):  # --part=K/N: numbers K, K+N, ... (one of N runs)
            offset, every = (int(v) for v in arg.split("=", 1)[1].split("/"))
            paths.remove(arg)
        elif arg.startswith("--every="):
            every = int(arg.split("=", 1)[1])
            paths.remove(arg)
        elif arg.startswith("--fresh="):
            fresh = int(arg.split("=", 1)[1])
            paths.remove(arg)
    for path in paths:
        doc = fdef.load(Path(path))
        doc.solid = {}
        result = storm(
            doc, every, fresh, log=lambda line: print("  ", line, flush=True), offset=offset
        )
        print(f"{Path(path).name}: {result.edits} edits in {result.seconds:.0f} s", flush=True)
        for problem in result.problems:
            print("   PROBLEM", problem, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
