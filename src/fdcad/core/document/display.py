"""Show and hide state of sketches and planes, saved in the part (FDEF_SPEC 10 items 4, 5).

A finished sketch shows until a feature uses it; a plane is hidden unless shown
on purpose. ``appearance.hidden`` lists sketches hidden on purpose and
``appearance.shown`` lists sketches and planes shown on purpose. Both keys are
left out while empty, so parts that never used them save exactly as before.
"""

from __future__ import annotations

from fdcad.core.document.model import Document

HIDDEN = "hidden"
SHOWN = "shown"


def _ids(doc: Document, key: str) -> set[str]:
    value = doc.appearance.get(key)
    if not isinstance(value, list):
        return set()
    return {str(v) for v in value if isinstance(v, str)}


def hidden_ids(doc: Document) -> set[str]:
    """Ids of sketches hidden on purpose."""
    return _ids(doc, HIDDEN)


def shown_ids(doc: Document) -> set[str]:
    """Ids of sketches and planes shown on purpose."""
    return _ids(doc, SHOWN)


def set_display(doc: Document, hidden: set[str], shown: set[str]) -> None:
    """Store the show and hide state. Ids of features that no longer exist are dropped."""
    existing = {f.id for f in doc.features}
    for key, ids in ((HIDDEN, hidden), (SHOWN, shown)):  # this order: canonical form
        doc.appearance.pop(key, None)
        kept = sorted(ids & existing, key=lambda fid: (len(fid), fid))
        if kept:
            doc.appearance[key] = kept
    if "hidden_bodies" in doc.appearance:  # stays last (FDEF_SPEC 10.1, D410)
        doc.appearance["hidden_bodies"] = doc.appearance.pop("hidden_bodies")
