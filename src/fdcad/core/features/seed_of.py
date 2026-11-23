"""The seed feature of a pattern copy (TR142 item 2, D1016).

Pattern and mirror copies name their faces ``<fid>/instance<i>.<j>/<seed face>`` and
``<fid>/mirror<k>/<seed face>`` (core/features/patterns.py). From a face name this
finds the pattern and, when it copies features, the first seed feature. No Qt.
"""

from __future__ import annotations

import re

from fdcad.core.document.model import Document

_COPY = re.compile(r"(?:^|[(|])(f\d+)/(?:instance\d+\.\d+|mirror\d+)/")


def seed_of(doc: Document, face_name: str) -> str | None:
    """The id of the seed feature behind a copied face, or None (not a copy, or a copy
    of faces or bodies, which have no seed feature)."""
    match = _COPY.search(face_name)
    if match is None:
        return None
    pattern = next((f for f in doc.features if f.id == match.group(1)), None)
    if pattern is None:
        return None
    for ref in pattern.refs.get("features") or []:
        if isinstance(ref, dict) and isinstance(ref.get("feature"), str):
            seed = str(ref["feature"])
            if any(f.id == seed for f in doc.features):
                return seed
    return None


_INSTANCE = re.compile(r"(?:^|[(|])(f\d+)/instance(\d+)\.(\d+)/")


def instance_of(doc: Document, face_name: str) -> tuple[str, tuple[int, int]] | None:
    """The pattern and instance number a copied face belongs to (TR59 item 3, D1900),
    or None when the face is not on a pattern copy of features. The outermost pattern
    wins for a pattern of patterns, since its instance numbers are the ones shown."""
    match = _INSTANCE.search(face_name)
    if match is None or seed_of(doc, face_name) is None:
        return None
    return match.group(1), (int(match.group(2)), int(match.group(3)))


def add_instance_values(text: str, index: tuple[int, int]) -> str:
    """``text`` (a Copy values list) with an entry for ``index`` started at its end,
    such as "3: depth 8; 2.2: " (TR59 item 3, D1900). An entry already there is kept."""
    label = str(index[0]) if index[1] == 1 else f"{index[0]}.{index[1]}"
    groups = [g.strip() for g in text.split(";") if g.strip()]
    if any(g.partition(":")[0].strip() == label for g in groups):
        return "; ".join(groups)
    return "; ".join([*groups, f"{label}: "])
