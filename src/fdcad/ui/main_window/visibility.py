"""Which sketches show in the 3D view, and which feature uses which sketch (C1, W5).

A finished sketch shows its curves. Once a feature uses it, it hides, unless
the user showed it on purpose. Planes are hidden unless shown on purpose. The
choices are saved in the file (``fdcad.core.document.display``, D114).
Pure Python, no Qt.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document, Feature

#: Feature types that consume a sketch through ``refs.sketch``.
SKETCH_USERS = ("extrude", "revolve")


def sketch_of(feature: Feature) -> str | None:
    """Id of the sketch ``feature`` uses, or None."""
    ref = feature.refs.get("sketch")
    if isinstance(ref, dict) and isinstance(ref.get("feature"), str):
        return str(ref["feature"])
    return None


def sketch_users(doc: Document) -> dict[str, str]:
    """Sketch id to the id of the first feature that uses it."""
    out: dict[str, str] = {}
    for feature in doc.features:
        sid = sketch_of(feature)
        if sid is not None and sid not in out:
            out[sid] = feature.id
    return out


def shared_sketch(doc: Document, feature: Feature) -> Feature | None:
    """The sketch ``feature`` uses when an earlier feature uses it too (T5.3.5), else None."""
    sid = sketch_of(feature)
    if sid is None or sketch_users(doc).get(sid) in (None, feature.id):
        return None
    try:
        return doc.feature(sid)
    except KeyError:
        return None


def unused_sketches(doc: Document) -> list[str]:
    """Finished sketches that no feature uses yet, in tree order."""
    used = sketch_users(doc)
    return [
        f.id for f in doc.features if f.type == "sketch" and not f.suppressed and f.id not in used
    ]


def visible_sketches(
    doc: Document, built: set[str] | dict[str, Any], hidden: set[str], shown: set[str]
) -> list[str]:
    """Sketches to draw in the 3D view.

    ``built`` holds the ids that built in the last rebuild, so sketches below the
    rollback bar or suppressed ones are left out.
    """
    used = sketch_users(doc)
    out = []
    for f in doc.features:
        if f.type != "sketch" or f.id not in built or f.id in hidden:
            continue
        if f.id in used and f.id not in shown:
            continue
        out.append(f.id)
    return out


def visible_planes(
    doc: Document,
    built: set[str] | dict[str, Any],
    shown: set[str],
    hidden: set[str] | None = None,
) -> list[str]:
    """Planes on show that are built (not suppressed or below the rollback bar).

    Default planes show only when shown on purpose; reference planes (P2.10) show
    until hidden on purpose (D251).
    """
    out = []
    for f in doc.features:
        if f.id not in built:
            continue
        if (f.type == "plane" and f.id in shown) or (
            f.type == "ref_plane" and f.id not in (hidden or set())
        ):
            out.append(f.id)
    return out


#: Reference geometry drawn as lines and points: axes, points, coordinate systems.
DATUM_TYPES = ("ref_axis", "ref_point", "coord_system")


def visible_datums(doc: Document, built: set[str] | dict[str, Any], hidden: set[str]) -> list[str]:
    """Reference axes, points and coordinate systems on show: built and not hidden (D251)."""
    return [
        f.id for f in doc.features if f.type in DATUM_TYPES and f.id in built and f.id not in hidden
    ]


def toggle(fid: str, doc: Document, hidden: set[str], shown: set[str], visible: bool) -> None:
    """Show (``visible``) or hide sketch or plane ``fid`` on purpose."""
    if doc.feature(fid).type in ("ref_plane", *DATUM_TYPES):
        shown.discard(fid)
        if visible:
            hidden.discard(fid)
        else:
            hidden.add(fid)
        return
    if doc.feature(fid).type == "plane":
        hidden.discard(fid)
        if visible:
            shown.add(fid)
        else:
            shown.discard(fid)
        return
    used = fid in sketch_users(doc)
    if visible:
        hidden.discard(fid)
        if used:
            shown.add(fid)
    else:
        shown.discard(fid)
        hidden.add(fid)
