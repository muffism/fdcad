"""Explode Pattern: one independent feature per pattern copy (TR270 item 1, D1902).

Each copy becomes its own pattern feature that keeps only that copy (the ``only``
key, an ``[i, j]`` pair), so it can be edited, suppressed or deleted alone, and its
values changed with Copy values (D1900). The first copy keeps the pattern's id, so
later features that use faces of that copy still find them. No Qt.
"""

from __future__ import annotations

import copy
from typing import Any

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import BuildContext, FeatureError, FeatureResult

#: Pattern types that can be exploded: those whose copies are numbered instances.
EXPLODE_TYPES = (
    "linear_pattern",
    "circular_pattern",
    "sketch_pattern",
    "table_pattern",
    "point_pattern",
    "pattern_chain",
)


def only(feature: Feature) -> tuple[int, int] | None:
    """The one instance an exploded copy keeps, or None for a whole pattern."""
    raw = feature.data.get("only")
    if isinstance(raw, list) and len(raw) == 2 and all(isinstance(v, int) for v in raw):
        return raw[0], raw[1]
    return None


def can_explode(feature: Feature) -> bool:
    """True for a whole pattern of numbered copies."""
    return feature.type in EXPLODE_TYPES and only(feature) is None


def _label(index: tuple[int, int]) -> str:
    return str(index[0]) if index[1] == 1 else f"{index[0]}.{index[1]}"


def explode(doc: Document, fid: str, results: dict[str, FeatureResult]) -> list[Feature]:
    """One feature per copy the pattern ``fid`` makes now (skipped copies left out),
    the first with the pattern's own id. New ones get new ids; the document's features
    are not changed. Raises FeatureError when the pattern cannot be exploded."""
    from fdcad.core.features import REGISTRY
    from fdcad.core.features.patterns import region_skips, skipped
    from fdcad.core.features.preview import body_before

    pattern = doc.feature(fid)
    ftype: Any = REGISTRY.get(pattern.type)
    if not can_explode(pattern) or ftype is None:
        raise FeatureError(
            f"{pattern.name}: only a whole Linear, Circular, Sketch, Table, Point Pattern or "
            "Pattern Chain can be exploded. Pick one of those."
        )
    ctx = BuildContext(doc, body_before(doc, pattern, results), results, owner=pattern.name)
    found, _issues = ftype.placements(pattern, ctx)
    gone = skipped(pattern) | region_skips(pattern, ctx, found)
    indices = [p.index for p in found if p.index not in gone]
    if not indices:
        raise FeatureError(
            f"{pattern.name}: the pattern makes no copies to explode. Raise the count first."
        )
    out: list[Feature] = []
    for n, index in enumerate(indices):
        feature = copy.deepcopy(pattern)
        if n:
            feature.id = doc.new_feature_id()
        feature.name = f"{pattern.name} copy {_label(index)}"
        feature.data["only"] = list(index)
        feature.data.pop("skip", None)
        feature.refs.pop("region", None)
        out.append(feature)
    return out


__all__ = ["EXPLODE_TYPES", "can_explode", "explode", "only"]
