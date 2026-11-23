"""Goal Seek and value sweep (TR273, DECISIONS D1020).

Pick a global variable and a measured value (the part's volume, area or mass, or a
value a Measurement or Bounding Box feature measures). Sweep steps the variable
through a range and gives the measured value per step. Goal Seek changes the
variable until the measured value reaches a target. Every trial rebuilds a copy of
the document, so the open part does not change until the user accepts a value.
Values here are in internal units: millimetres for lengths, radians for angles.
Kernel work, run in a kernel job. No Qt.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.units.expressions import Kind

#: The part's own measured values offered first, then those of measuring features.
PART_TARGETS = ("volume@Part", "area@Part", "mass@Part")
#: Most trials Goal Seek makes before it gives up.
MAX_TRIALS = 40


@dataclass(frozen=True)
class Step:
    """One trial: the variable's value and the measured value, or why it failed."""

    value: float
    result: float | None
    error: str = ""


def target_names(doc: Document) -> list[str]:
    """Measured values a trial can read: the part's, then each measuring feature's (by
    its name), as formulas name them."""
    from fdcad.core.equations.engine import MEASURED_VALUES

    out = list(PART_TARGETS)
    for feature in doc.features:
        for name in MEASURED_VALUES.get(feature.type, ()):
            out.append(f"{name}@{feature.name}")
    return out


def variable_text(kind: Kind, value: float) -> str:
    """``value`` (mm or radians) as text a variable can hold, with its unit."""
    if kind is Kind.LENGTH:
        number, unit = value, "mm"
    elif kind is Kind.ANGLE:
        number, unit = math.degrees(value), "deg"
    else:
        number, unit = value, ""
    text = f"{number:.10f}".rstrip("0").rstrip(".")
    return (text if text not in ("", "-0") else "0") + unit


def _measured(doc: Document, target: str) -> float | None:
    from fdcad.core.equations.engine import measured_names
    from fdcad.core.rebuild.engine import PART_KEY

    if target in PART_TARGETS:
        found = doc.measured.get(PART_KEY, {})
        name = target.split("@")[0]
        return float(found[name]) if name in found else None
    names = measured_names(doc)
    return names[target][1] if target in names else None


class Trials:
    """Rebuilds copies of a document with one variable changed. Keeps one rebuild
    engine, so features the variable does not reach are reused between trials."""

    def __init__(self, doc: Document, variable: str, target: str) -> None:
        var = next((v for v in doc.variables if v.name == variable), None)
        if var is None:
            raise ValueError(f"there is no variable called {variable}. Pick a variable.")
        if target not in target_names(doc):
            raise ValueError(f"{target} is not a measured value. Pick a measured value.")
        self.doc = doc
        self.variable = variable
        self.kind = var.kind
        self.target = target
        self.engine = RebuildEngine()
        self.count = 0

    def run(self, value: float, cancelled: Callable[[], bool] = lambda: False) -> Step:
        """Rebuild with the variable at ``value`` and read the measured value."""
        self.count += 1
        doc = copy.deepcopy(self.doc)
        var = next(v for v in doc.variables if v.name == self.variable)
        var.expr = variable_text(self.kind, value)
        var.value = value
        report = self.engine.rebuild(doc, cancelled=cancelled)
        if report.cancelled:
            return Step(value, None, "stopped")
        if report.variable_error:
            return Step(value, None, report.variable_error)
        failed = [
            doc.feature(fid).name
            for fid, result in report.results.items()
            if result.state is FeatureState.ERROR
        ]
        if failed:
            return Step(value, None, f"{failed[0]} failed")
        if self.target in PART_TARGETS:  # stored only for parts with properties
            from fdcad.core.rebuild.engine import _store_part_measures

            _store_part_measures(doc, report.body)
        found = _measured(doc, self.target)
        if found is None:
            return Step(value, None, f"{self.target} has no value")
        return Step(value, found)


def sweep(
    trials: Trials,
    start: float,
    stop: float,
    steps: int,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int, int], None] | None = None,
) -> list[Step]:
    """``steps`` evenly spaced values from ``start`` to ``stop`` (both included)."""
    if steps < 2:
        raise ValueError("a sweep needs at least 2 steps. Enter 2 or more steps.")
    if start == stop:
        raise ValueError("the start and end values are the same. Enter two different values.")
    out: list[Step] = []
    for k in range(steps):
        if cancelled():
            break
        if progress is not None:
            progress(k, steps)
        out.append(trials.run(start + (stop - start) * k / (steps - 1), cancelled))
    return out


@dataclass(frozen=True)
class Seek:
    """What Goal Seek found: the value, the measured value there and every trial."""

    value: float
    result: float
    trials: list[Step]


def goal_seek(
    trials: Trials,
    goal: float,
    low: float,
    high: float,
    tolerance: float | None = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> Seek:
    """Find a value between ``low`` and ``high`` where the measured value is ``goal``,
    within ``tolerance`` (by default a millionth of the goal, at least 1e-9). Raises
    ValueError with what to do when the goal is not reached in the range."""
    if low == high:
        raise ValueError("the search range is empty. Enter two different values.")
    low, high = min(low, high), max(low, high)
    tol = tolerance if tolerance is not None else max(abs(goal) * 1e-6, 1e-9)
    done: list[Step] = []

    def f(x: float) -> float | None:
        step = trials.run(x, cancelled)
        done.append(step)
        return None if step.result is None else step.result - goal

    def stopped() -> None:
        if cancelled():
            raise ValueError("Goal Seek was stopped. Click Run to start again.")

    # Bracket: the ends first, then a few values between them.
    xs = [low + (high - low) * k / 8 for k in range(9)]
    xs = [xs[0], xs[-1], *xs[1:-1]]
    known: list[tuple[float, float]] = []
    pair: tuple[tuple[float, float], tuple[float, float]] | None = None
    for x in xs:
        stopped()
        y = f(x)
        if y is None:
            continue
        if abs(y) <= tol:
            return Seek(x, y + goal, done)
        known.append((x, y))
        known.sort()
        for left, right in pairwise(known):
            if (left[1] < 0) != (right[1] < 0):
                pair = (left, right)
                break
        if pair is not None:
            break
    if pair is None:
        if not known:
            reason = done[0].error if done else "no trial built"
            raise ValueError(
                f"no value in the range builds ({reason}). Check the part builds, or "
                "change the range."
            )
        nearest = min(known, key=lambda p: abs(p[1]))
        raise ValueError(
            f"the target is not reached between the range ends; the nearest result was "
            f"{nearest[1] + goal:.6g}. Widen the range or change the target."
        )
    (a, fa), (b, fb) = pair
    # Illinois false position: keeps the bracket, converges fast on smooth values.
    side = 0
    while len(done) < MAX_TRIALS:
        stopped()
        c = b - fb * (b - a) / (fb - fa)
        if not a < c < b:
            c = (a + b) / 2
        fc = f(c)
        if fc is None:  # a value that does not build: halve towards a good end
            c = (a + b) / 2
            fc = f(c)
            if fc is None:
                raise ValueError(
                    f"the part does not build near {c:.6g} ({done[-1].error}). Narrow the range."
                )
        if abs(fc) <= tol or abs(b - a) <= 1e-12 * max(1.0, abs(a), abs(b)):
            return Seek(c, fc + goal, done)
        if (fc < 0) == (fb < 0):
            b, fb = c, fc
            if side == 1:
                fa /= 2
            side = 1
        else:
            a, fa = c, fc
            if side == -1:
                fb /= 2
            side = -1
    good = [(s.value, s.result) for s in done if s.result is not None]
    best = min(good, key=lambda p: abs(p[1] - goal))
    raise ValueError(
        f"Goal Seek did not reach the target in {MAX_TRIALS} trials; the nearest result was "
        f"{best[1]:.6g} at {best[0]:.6g}. Use a looser tolerance or a narrower range."
    )
