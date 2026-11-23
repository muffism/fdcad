"""Jog Line (TUTORIAL_REVIEW_SPEC TR52, DECISIONS D902).

A line breaks at a point into two parallel pieces joined by a short step: the first
piece keeps its start, the second is shifted sideways by ``depth`` (signed, to the
left of the line's direction when positive), and a step line ``width`` long along
the line joins them. The pieces get Parallel and the step's ends are shared, so
the jog can be dimensioned. No Qt.
"""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Line, Sketch

Vec = tuple[float, float]


class JogError(ValueError):
    """The jog cannot be made; the message says what to change."""


def jog(sketch: Sketch, lid: str, at: Vec, depth: float, width: float | None = None) -> list[str]:
    """Jog line ``lid`` at the point of it nearest ``at``. Returns [first piece, step,
    second piece]."""
    line = sketch.entities.get(lid)
    if not isinstance(line, Line):
        raise JogError("Jog Line works on a line. Click a line.")
    a, b = sketch.xy(line.p1), sketch.xy(line.p2)
    length = math.dist(a, b)
    if length < 1e-9:
        raise JogError("The line has no length. Click another line.")
    if abs(depth) < 1e-9:
        raise JogError("The jog needs a depth. Click to one side of the line.")
    width = abs(depth) if width is None else abs(width)
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -uy, ux
    s = (at[0] - a[0]) * ux + (at[1] - a[1]) * uy
    lo, hi = s - width / 2, s + width / 2
    if lo <= 1e-6 or hi >= length - 1e-6:
        raise JogError("The step does not fit there. Click nearer the middle of the line.")
    p1 = (a[0] + ux * lo, a[1] + uy * lo)
    p2 = (a[0] + ux * hi + nx * depth, a[1] + uy * hi + ny * depth)
    end = (b[0] + nx * depth, b[1] + ny * depth)
    # The first piece keeps the line (and its relations at the start); its end moves in.
    sketch.point(line.p2).x, sketch.point(line.p2).y = p1
    old_end = line.p2
    step = sketch.add_line(*p1, *p2)
    second = sketch.add_line(*p2, *end)
    step_line, second_line = sketch.entities[step], sketch.entities[second]
    assert isinstance(step_line, Line) and isinstance(second_line, Line)
    sketch.entities.pop(step_line.p1, None)
    step_line.p1 = old_end
    sketch.entities.pop(second_line.p1, None)
    second_line.p1 = step_line.p2
    sketch.relate("parallel", lid, second)
    return [lid, step, second]
