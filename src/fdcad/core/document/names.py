"""Rules for feature names typed in the feature tree.

Formulas name feature values as ``"depth@Extrude 1"`` or ``"depth@f6"`` (D390),
so a feature name must not hold a quote or the @ sign, and must not be the name
or id of another feature: the formula would then point at the wrong feature.
"""

from __future__ import annotations

from fdcad.core.document.model import Document


def rename_problem(doc: Document, fid: str, name: str) -> str | None:
    """Why feature ``fid`` cannot be renamed to ``name``, or None when it can."""
    old = doc.feature(fid).name
    clean = name.strip()
    if '"' in clean or "@" in clean:
        return (
            f"Cannot rename {old}: names cannot hold quotes or the @ sign. "
            "Remove them and try again."
        )
    for other in doc.features:
        if other.id == fid:
            continue
        if other.name == clean:
            return (
                f"Cannot rename {old}: another feature is already named {clean}. "
                "Type a different name."
            )
        if other.id == clean:
            return f"Cannot rename {old}: {clean} is the id of {other.name}. Type a different name."
    return None


def usable_name(name: str, taken: set[str], limit: int, fallback: str) -> str:
    """``name`` made fit for a list whose names must be unique, ignoring case, and at
    most ``limit`` characters long: spaces trimmed, cut to length, and a number added
    when it is taken (``taken`` holds casefolded names). An empty name becomes
    ``fallback`` and a number (audit D5 item 4, D2679)."""
    clean = name.strip()[:limit].strip()
    if clean and clean.casefold() not in taken:
        return clean
    base = clean or fallback
    n = 2 if clean else 1
    while True:
        tail = f" {n}"
        candidate = base[: limit - len(tail)].rstrip() + tail
        if candidate.casefold() not in taken:
            return candidate
        n += 1
