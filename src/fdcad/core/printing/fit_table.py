"""Fit values by size and direction (TR412, D1919). No Qt.

A small table refines the printer's single fit tolerance (the gap per side, D311):
each row is ``<hole|outside> <flat|upright|any> <up to diameter> <gap>`` and an
optional nozzle size, such as ``hole upright 6 0.25 0.4``. Holes printed upright
(their axis along the printer's up) come out smaller than flat ones, and small holes
more than large ones, so the gap is looked up by the hole's diameter band and its
direction, for the nozzle in use when rows name one.
"""

from __future__ import annotations

from dataclasses import dataclass

KINDS = ("hole", "outside")
DIRECTIONS = ("flat", "upright", "any")


@dataclass(frozen=True)
class FitRow:
    """One row: sizes up to ``up_to`` mm across of ``kind`` printed ``direction`` get
    ``gap`` mm per side; ``nozzle`` (mm) limits the row to that nozzle, 0 for any."""

    kind: str
    direction: str
    up_to: float
    gap: float
    nozzle: float = 0.0


def parse_fit_table(text: str) -> list[FitRow]:
    """The rows of ``text``, one per line; blank lines and lines starting with # are
    skipped. Raises ValueError naming the line that is wrong."""
    out: list[FitRow] = []
    for number, line in enumerate(text.splitlines(), start=1):
        words = line.split()
        if not words or words[0].startswith("#"):
            continue
        if len(words) not in (4, 5) or words[0] not in KINDS or words[1] not in DIRECTIONS:
            raise ValueError(
                f"Line {number} must read like hole upright 6 0.25, with an optional nozzle."
            )
        try:
            values = [float(w) for w in words[2:]]
        except ValueError:
            raise ValueError(f"Line {number} has a size that is not a number.") from None
        if values[0] <= 0 or values[1] < 0 or (len(values) == 3 and values[2] <= 0):
            raise ValueError(f"Line {number} needs sizes above 0 and a gap of 0 or more.")
        out.append(
            FitRow(words[0], words[1], values[0], values[1], values[2] if len(values) == 3 else 0.0)
        )
    return out


def fit_for(
    rows: list[FitRow],
    diameter: float,
    kind: str,
    upright: bool,
    nozzle: float,
    default: float,
) -> tuple[float, FitRow | None]:
    """The gap per side for a size: the row of the right kind and direction (or any)
    and nozzle (or none named) with the smallest band that holds ``diameter``, rows
    naming the direction and the nozzle first. ``default`` (and no row) when none
    fits."""
    want = "upright" if upright else "flat"
    best: tuple[tuple[int, int, float], FitRow] | None = None
    for row in rows:
        if row.kind != kind or row.direction not in (want, "any") or diameter > row.up_to + 1e-9:
            continue
        if row.nozzle and abs(row.nozzle - nozzle) > 1e-6:
            continue
        key = (0 if row.direction == want else 1, 0 if row.nozzle else 1, row.up_to)
        if best is None or key < best[0]:
            best = (key, row)
    if best is None:
        return default, None
    return best[1].gap, best[1]


__all__ = ["DIRECTIONS", "KINDS", "FitRow", "fit_for", "parse_fit_table"]
