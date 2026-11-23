"""Thread tolerance classes (TUTORIAL_REVIEW_SPEC_2 TR393, DECISIONS D1507).

A tapped hole or a modelled thread can carry a tolerance class. Metric classes
follow ISO 965-1: a tolerance grade and a position letter, capital for internal
threads (``6H``) and small for external ones (``6g``). Inch classes follow ASME
B1.1: ``1B`` to ``3B`` internal, ``1A`` to ``3A`` external.

The class sets the allowance: the gap the position letter leaves between the
thread and its basic size. FDCAD uses it as extra clearance on a modelled
thread, half the diameter allowance per side. The fundamental deviations come
from the published formulas: metric e, f and g (and G) are 50 + 11P, 30 + 11P
and 15 + 11P micrometres with P the pitch in mm; H and h are 0. Inch classes 1A
and 2A have an allowance of 0.3 times the class 2A pitch diameter tolerance,
0.0015 D^(1/3) + 0.0015 sqrt(9P) + 0.015 P^(2/3) inches (D and P in inches);
3A and every B class have none.
"""

from __future__ import annotations

import math

INCH = 25.4

METRIC_INTERNAL = ("6H", "4H", "5H", "7H", "6G", "7G")
METRIC_EXTERNAL = ("6g", "4h", "6h", "8g", "6f", "6e")
INCH_INTERNAL = ("2B", "1B", "3B")
INCH_EXTERNAL = ("2A", "1A", "3A")
CLASSES = METRIC_INTERNAL + METRIC_EXTERNAL + INCH_INTERNAL + INCH_EXTERNAL

_METRIC_BASE_UM = {"e": 50.0, "f": 30.0, "g": 15.0, "h": 0.0}


def choices(inch: bool, internal: bool) -> tuple[str, ...]:
    """The classes offered for an inch or metric, internal or external thread."""
    if inch:
        return INCH_INTERNAL if internal else INCH_EXTERNAL
    return METRIC_INTERNAL if internal else METRIC_EXTERNAL


def is_internal(name: str) -> bool:
    """True for a class of internal threads (a hole's)."""
    return name in METRIC_INTERNAL or name in INCH_INTERNAL


def allowance(name: str, pitch: float, major: float) -> float:
    """The diameter allowance in mm that the class leaves (0 for H, h, 3A and B).

    Raises ValueError for a name that is not a class.
    """
    if name not in CLASSES:
        raise ValueError(f"'{name}' is not a thread class")
    if name in INCH_INTERNAL or name in INCH_EXTERNAL:
        if name not in ("1A", "2A"):
            return 0.0
        d, p = major / INCH, pitch / INCH
        td2 = 0.0015 * d ** (1 / 3) + 0.0015 * math.sqrt(9 * p) + 0.015 * p ** (2 / 3)
        return float(0.3 * td2 * INCH)
    letter = name[-1].lower()
    return (_METRIC_BASE_UM[letter] + (11.0 * pitch if letter != "h" else 0.0)) / 1000.0
