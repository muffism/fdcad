"""Sketch points from a text file (TUTORIAL_REVIEW_SPEC_2 TR415 item 2, D933).

Each line with two numbers (X and Y, split by commas, spaces, tabs or semicolons)
gives one plain sketch point. A third number (Z) is ignored, and lines that are not
two numbers, such as a header, are skipped and counted. Values are in the part's
units. No Qt.
"""

from __future__ import annotations

import re

from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem

#: The most points one file adds.
MAX_POINTS = 10000
_SPLIT = re.compile(r"[,\s;]+")


class PointFileError(ValueError):
    """The text has no points; the message says what to change."""


def read_points(text: str, units: UnitSystem) -> tuple[list[tuple[float, float]], int]:
    """The points in millimetres, and how many lines were skipped."""
    scale = 25.4 if units is UnitSystem.IN else 1.0
    points: list[tuple[float, float]] = []
    skipped = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in _SPLIT.split(line) if p]
        try:
            x, y = float(parts[0]), float(parts[1])
        except (IndexError, ValueError):
            skipped += 1
            continue
        points.append((x * scale, y * scale))
    if not points:
        raise PointFileError("The file has no lines with two numbers. Use one X, Y pair per line.")
    if len(points) > MAX_POINTS:
        raise PointFileError(
            f"The file has {len(points)} points; at most {MAX_POINTS} can be read. Split the file."
        )
    return points, skipped


def add_points(sketch: Sketch, points: list[tuple[float, float]]) -> list[str]:
    """Add the points to the sketch; returns their ids."""
    return [sketch.add_point(x, y) for x, y in points]
