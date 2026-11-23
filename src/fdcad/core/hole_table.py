"""Hole and thread list (TUTORIAL_REVIEW_SPEC_2 TR316, DECISIONS D924).

One row per hole made by a Hole feature (its position from the last rebuild) and per
cosmetic or modelled thread mark of other features, with a tag per feature (A1, A2,
B1), the type, size, diameter, depth, thread and how many holes the feature makes.
Lengths are in the part's units. No Qt.
"""

from __future__ import annotations

import csv
import io
import string
from dataclasses import dataclass
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.units import UnitSystem

COLUMNS = ("Tag", "Feature", "Type", "Size", "Diameter", "Depth", "Thread", "Count", "X", "Y", "Z")
_TYPE_WORDS = {
    "simple": "Simple",
    "counterbore": "Counterbore",
    "countersink": "Countersink",
    "tapped": "Tapped",
    "heat_set_insert": "Heat set insert",
    "magnet": "Magnet pocket",
    "dowel": "Dowel",
    "bearing": "Bearing seat",
    "counterdrill": "Counterdrill",
    "pipe_tapped": "Tapered pipe tapped",  # TR145 (D1511)
}


@dataclass(frozen=True)
class HoleRow:
    """One hole or thread."""

    tag: str
    feature: str
    kind: str
    size: str
    diameter: float | None
    depth: float | str | None  # a length, or "Through"
    thread: str
    count: int
    position: tuple[float, float, float]


def _num(feature: Feature, key: str) -> float | None:
    value = feature.params.get(key)
    return value.value if isinstance(value, Param) else None


def _letters(n: int) -> str:
    out = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        out = string.ascii_uppercase[r] + out
    return out


def rows(doc: Document, results: dict[str, Any]) -> list[HoleRow]:
    """The holes and threads of the last rebuild, in tree order."""
    out: list[HoleRow] = []
    group = 0
    for feature in doc.features:
        if feature.suppressed:
            continue
        result = results.get(feature.id)
        if result is None:
            continue
        holes = (
            list(getattr(result, "extras", {}).get("holes", [])) if feature.type == "hole" else []
        )
        marks = list(getattr(result, "threads", []))
        if not holes and not marks:
            continue
        tag = _letters(group)
        group += 1
        if holes:
            kind = str(feature.params.get("hole_type", "simple"))
            end = str(feature.params.get("end_condition", "blind"))
            depth: float | str | None = _num(feature, "depth") if end == "blind" else None
            if end == "through_all":
                depth = "Through"
            size = str(feature.params.get("size", ""))
            thread = size if kind in ("tapped", "pipe_tapped") else ""
            grade = str(feature.params.get("thread_class", "none") or "none")
            if thread and grade != "none":  # TR393 (D1507): "M5 6H"
                thread = f"{thread} {grade}"
            for k, origin in enumerate(holes, 1):
                out.append(
                    HoleRow(
                        f"{tag}{k}",
                        feature.name,
                        _TYPE_WORDS.get(kind, kind.replace("_", " ").capitalize()),
                        size,
                        _num(feature, "diameter"),
                        depth,
                        thread,
                        len(holes),
                        (float(origin[0]), float(origin[1]), float(origin[2])),
                    )
                )
            continue
        for k, mark in enumerate(marks, 1):
            name = f"M{mark.diameter:g}x{mark.pitch:g}"
            out.append(
                HoleRow(
                    f"{tag}{k}",
                    feature.name,
                    "Internal thread" if mark.internal else "External thread",
                    name,
                    mark.diameter,
                    mark.length,
                    name,
                    len(marks),
                    (float(mark.origin[0]), float(mark.origin[1]), float(mark.origin[2])),
                )
            )
    return out


def cells(row: HoleRow, units: UnitSystem) -> list[str]:
    """The row as text, lengths in the part's units."""
    inch = units is UnitSystem.IN

    def length(v: float | str | None) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        return f"{v / 25.4:.4f}" if inch else f"{v:.3f}".rstrip("0").rstrip(".")

    x, y, z = row.position
    return [
        row.tag,
        row.feature,
        row.kind,
        row.size,
        length(row.diameter),
        length(row.depth),
        row.thread,
        str(row.count),
        length(x),
        length(y),
        length(z),
    ]


def to_csv(found: list[HoleRow], units: UnitSystem) -> str:
    """The table as CSV text with a header row naming the length unit."""
    unit = "in" if units is UnitSystem.IN else "mm"
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [f"{c} ({unit})" if c in ("Diameter", "Depth", "X", "Y", "Z") else c for c in COLUMNS]
    )
    for row in found:
        writer.writerow(cells(row, units))
    return buffer.getvalue()
