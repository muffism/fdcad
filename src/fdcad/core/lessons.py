"""First run lessons that check the result (TUTORIAL_REVIEW_SPEC_2 TR291 item 2,
DECISIONS D2505).

A lesson is a short list of steps. Each step has a check that reads the part as
it is after the last rebuild (and whether it is saved), so a step is ticked when
the part shows it, whichever way the user got there. A ticked step stays
ticked. Pure Python, no Qt.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState


@dataclass(frozen=True)
class Context:
    """What a check reads: the part, its last rebuild report, and whether it is saved."""

    doc: Document
    report: Any = None
    saved: bool = False


@dataclass(frozen=True)
class Step:
    """One step: what to do, and the check that ticks it."""

    text: str
    check: Callable[[Context], bool]


@dataclass(frozen=True)
class Lesson:
    """A named list of steps."""

    key: str
    title: str
    steps: tuple[Step, ...]


def _operation(feature: Any) -> str:
    raw = feature.params.get("operation", "boss")
    return str(getattr(raw, "value", raw))


def _built(ctx: Context, types: tuple[str, ...], operation: str | None = None) -> list[str]:
    """Ids of features of these types that rebuilt without an error, not suppressed;
    with ``operation``, only extrudes and revolves that "boss" or "cut"."""
    report = ctx.report
    if report is None:
        return []
    out = []
    for f in ctx.doc.features:
        if f.type not in types or f.suppressed:
            continue
        cut_type = f.type in ("extrude", "revolve")
        if operation is not None and cut_type and _operation(f) != operation:
            continue
        result = report.results.get(f.id)
        if result is not None and result.state is not FeatureState.ERROR:
            out.append(f.id)
    return out


def _sketches(ctx: Context) -> list[Any]:
    """The solved sketches of the part (their rebuild output)."""
    report = ctx.report
    out = []
    for fid in _built(ctx, ("sketch",)):
        output = report.results[fid].sketch
        if output is not None:
            out.append(output)
    return out


def _lines(output: Any) -> int:
    from fdcad.core.sketch.model import Line

    return sum(
        1
        for e in output.model.entities.values()
        if isinstance(e, Line) and not getattr(e, "construction", False)
    )


def has_rectangle(ctx: Context) -> bool:
    """A sketch with four or more lines (a rectangle or more)."""
    return any(_lines(s) >= 4 for s in _sketches(ctx))


def has_full_sketch(ctx: Context) -> bool:
    """A sketch with lines that is fully defined."""
    from fdcad.core.sketch.solver import SketchStatus

    return any(_lines(s) >= 1 and s.solve.status is SketchStatus.FULL for s in _sketches(ctx))


def _has(types: tuple[str, ...]) -> Callable[[Context], bool]:
    def check(ctx: Context) -> bool:
        return bool(_built(ctx, types))

    return check


def has_solid(ctx: Context) -> bool:
    """An extrude or revolve (not a cut) that built, and a solid body."""
    report = ctx.report
    return bool(_built(ctx, ("extrude", "revolve"), "boss")) and bool(
        report is not None and report.body_count > 0
    )


def has_cut(ctx: Context) -> bool:
    """An extruded or revolved cut, or a hole, that built."""
    return bool(_built(ctx, ("extrude", "revolve"), "cut")) or bool(_built(ctx, ("hole",)))


def is_saved(ctx: Context) -> bool:
    """The part has been saved with no changes since."""
    return ctx.saved and bool(ctx.doc.features)


LESSONS: tuple[Lesson, ...] = (
    Lesson(
        "first_part",
        "Your First Part",
        (
            Step("Start a sketch on a plane and draw a rectangle.", has_rectangle),
            Step(
                "Fully define the sketch with dimensions and relations "
                "(Fully Define Sketch can do it for you).",
                has_full_sketch,
            ),
            Step("Extrude the sketch into a solid.", has_solid),
            Step("Round some edges with a fillet.", _has(("fillet",))),
            Step("Save the part.", is_saved),
        ),
    ),
    Lesson(
        "holes_patterns",
        "Cuts, Holes and Patterns",
        (
            Step("Make a solid with Extrude.", has_solid),
            Step("Cut into it with Extruded Cut or the Hole Tool.", has_cut),
            Step(
                "Repeat the cut with a linear or circular pattern.",
                _has(("linear_pattern", "circular_pattern")),
            ),
            Step("Mirror a feature or the body about a plane.", _has(("mirror",))),
        ),
    ),
)

BY_KEY = {lesson.key: lesson for lesson in LESSONS}


def update(lesson: Lesson, done: set[int], ctx: Context) -> set[int]:
    """The steps done after this check: the ones done before, plus each step whose check
    passes now. A check that fails with an error does not tick its step."""
    out = set(done)
    for i, step in enumerate(lesson.steps):
        if i in out:
            continue
        try:
            ok = step.check(ctx)
        except Exception:
            ok = False
        if ok:
            out.add(i)
    return out


def next_step(lesson: Lesson, done: set[int]) -> int | None:
    """The first step not done, or None when the lesson is finished."""
    return next((i for i in range(len(lesson.steps)) if i not in done), None)
