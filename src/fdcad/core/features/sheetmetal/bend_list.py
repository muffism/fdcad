"""The bend list of a sheet metal part and the bend order (TR282, DECISIONS D1110).

``bend_rows`` lists every bend of a sheet model in a stable order, numbered from 1,
for the Bend Table window; ``rip_rows`` lists the Rip features beside them (D2310).
``bend_order`` reads the Flat Pattern's ``bend_order`` text (bend numbers in the
order they are bent, such as "3, 1, 2") into the step of each bend, which the flat
pattern files carry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureError
from fdcad.core.features.sheetmetal.model import SheetModel


@dataclass(frozen=True)
class BendRow:
    """One bend as the Bend Table shows it (mm and degrees)."""

    number: int
    bid: str
    owner: str
    radius: float
    angle: float
    allowance: float
    direction: str
    length: float


def bend_rows(model: SheetModel) -> list[BendRow]:
    """Every bend of ``model``, numbered from 1 in the order the bends were made."""
    out = []
    for k, bend in enumerate(model.bends.values(), start=1):
        out.append(
            BendRow(
                k,
                bend.bid,
                bend.owner,
                bend.radius,
                math.degrees(bend.angle),
                bend.allowance,
                "up" if bend.up > 0 else "down",
                bend.length,
            )
        )
    return out


@dataclass(frozen=True)
class RipRow:
    """One Rip feature as the Bend Table lists it (TR282, D2310)."""

    number: int
    fid: str
    kind: str  # "sketch", "edge", "sketch_edge" or "tube"
    gap: float


def rip_rows(features: list[Feature]) -> list[RipRow]:
    """Every Rip feature in ``features`` that is not suppressed, numbered from 1."""
    from fdcad.core.document.model import Param

    out: list[RipRow] = []
    for f in features:
        if f.type != "rip" or f.suppressed:
            continue
        refs = f.refs
        if refs.get("tube_faces"):
            kind = "tube"
        elif refs.get("sketch") and refs.get("edges"):
            kind = "sketch_edge"
        else:
            kind = "sketch" if refs.get("sketch") else "edge"
        gap = f.params.get("gap")
        out.append(RipRow(len(out) + 1, f.id, kind, gap.value if isinstance(gap, Param) else 0.0))
    return out


def bend_order(feature: Feature, model: SheetModel) -> dict[str, int]:
    """Bend id to its step in the bending order (from 1), from ``bend_order``.

    Bends the list leaves out follow in their own order. Raises FeatureError for a
    number that is not a bend or is listed twice.
    """
    raw = feature.params.get("bend_order")
    bids = list(model.bends)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    listed: list[int] = []
    for word in raw.split(","):
        word = word.strip()
        if not word:
            continue
        if not word.isdigit() or not 1 <= int(word) <= len(bids):
            raise FeatureError(
                f"{feature.name}: the bend order must list bend numbers from 1 to {len(bids)}. "
                "Fix the bend order."
            )
        if int(word) in listed:
            raise FeatureError(
                f"{feature.name}: bend {word} is listed twice in the bend order. "
                "Remove the repeated number."
            )
        listed.append(int(word))
    rest = [k for k in range(1, len(bids) + 1) if k not in listed]
    return {bids[k - 1]: step for step, k in enumerate([*listed, *rest], start=1)}
