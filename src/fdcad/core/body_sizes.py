"""Select bodies by size (TUTORIAL_REVIEW_SPEC TR70, DECISIONS D894).

After an import or a split a part often has many small bodies. :func:`sizes` gives
each body's volume and a reference to it; :func:`pick` chooses the bodies smaller
(or larger) than a percent of the largest one. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BodySize:
    """One body: its index in the part, its volume (mm3) and a reference to it."""

    index: int
    volume: float
    ref: dict[str, Any] | None


def sizes(named: Any) -> list[BodySize]:
    """Every body of the part with its volume (kernel work: run off the UI thread)."""
    from fdcad.core.features.solids import solids, volume_of
    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.select import reference_for

    out = []
    for i, solid in enumerate(solids(named.shape)):
        faces = faces_of(solid)
        ref = reference_for(named, faces[0]) if faces else None
        out.append(BodySize(i, volume_of(solid), ref))
    return out


def pick(bodies: list[BodySize], percent: float, larger: bool = False) -> list[BodySize]:
    """The bodies below ``percent`` of the largest volume (or above it with ``larger``)."""
    if not bodies:
        return []
    limit = max(b.volume for b in bodies) * percent / 100.0
    if larger:
        return [b for b in bodies if b.volume > limit]
    return [b for b in bodies if b.volume < limit]
