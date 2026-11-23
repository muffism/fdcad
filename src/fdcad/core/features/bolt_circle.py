"""Bolt circle shorthand for hole positions (TUTORIAL_REVIEW_SPEC_2 TR407, D913).

"5x100" means five holes evenly spaced on a 100 mm circle (the size is typed like
any length, so "6x4in" or "4x=pcd" with a variable work too). A start angle turns
the first hole from the X axis. No Qt.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

from fdcad.core.units import Kind, UnitSystem, evaluate

#: The most holes one bolt circle makes.
MAX_HOLES = 360
_SHORTHAND = re.compile(r"^\s*(\d+)\s*[xX\u00d7*]\s*(.+?)\s*$")


class BoltCircleError(ValueError):
    """The shorthand cannot be read; the message says what to type."""


def parse(
    text: str, units: UnitSystem, variables: Mapping[str, tuple[Kind, float]] | None = None
) -> tuple[int, float]:
    """(count, circle diameter in mm) from text such as "5x100"."""
    from fdcad.core.units import ExpressionError

    m = _SHORTHAND.match(text)
    if not m:
        raise BoltCircleError("Type the hole count and the circle diameter, for example 5x100.")
    count = int(m.group(1))
    if not 2 <= count <= MAX_HOLES:
        raise BoltCircleError(f"Type between 2 and {MAX_HOLES} holes.")
    try:
        size = evaluate(m.group(2), Kind.LENGTH, units, variables)
    except ExpressionError as exc:
        raise BoltCircleError(f"After the x: {exc}") from exc
    if size <= 0:
        raise BoltCircleError("The circle diameter must be above zero. Type a larger size.")
    return count, size


def points(
    centre: tuple[float, float], count: int, diameter: float, start: float = 0.0
) -> list[tuple[float, float]]:
    """The hole positions, counter clockwise from ``start`` (radians from X)."""
    r = diameter / 2
    return [
        (
            centre[0] + r * math.cos(start + math.tau * k / count),
            centre[1] + r * math.sin(start + math.tau * k / count),
        )
        for k in range(count)
    ]
