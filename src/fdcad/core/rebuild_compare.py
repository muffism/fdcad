"""Before and after a change: the volume change per feature (TR289, DECISIONS D2019).

``volume_changes`` compares the last two rebuild reports of a part. Only features
whose result is a new object (the rebuild cache hands back the same object for
features it did not rebuild) are measured, so unchanged features cost nothing.
No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Change:
    """One feature's part volume before and after, in mm³ (None: no body)."""

    feature_id: str
    name: str
    before: float | None
    after: float | None

    @property
    def delta(self) -> float:
        """After less before (0 when either has no body)."""
        if self.before is None or self.after is None:
            return 0.0
        return self.after - self.before


def _volume(result: Any) -> float | None:
    body = getattr(result, "body", None)
    if body is None:
        return None
    from fdcad.core.features.solids import volume_of

    return float(volume_of(body.shape))


def volume_changes(document: Any, before: Any, after: Any, tolerance: float = 1e-6) -> list[Change]:
    """Features (in tree order) whose part volume after them changed between ``before``
    and ``after`` (rebuild reports), or that gained or lost a body."""
    if before is None or after is None:
        return []
    out = []
    old_results, new_results = before.results, after.results
    for feature in document.features:
        old, new = old_results.get(feature.id), new_results.get(feature.id)
        if old is None or new is None or old is new:
            continue
        if getattr(old, "body", None) is getattr(new, "body", None):
            continue
        a, b = _volume(old), _volume(new)
        if a is None and b is None:
            continue
        if a is not None and b is not None and abs(b - a) <= tolerance * max(abs(a), 1.0):
            continue
        out.append(Change(feature.id, feature.name, a, b))
    return out
