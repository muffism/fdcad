"""Merge Into Sketch from the feature tree (TR122 item 1, D986)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession


def same_plane_sketches(session: DocumentSession, fid: str) -> list[str]:
    """Ids of the other sketches drawn on the same plane or face as ``fid``."""
    doc = session.document
    source = doc.feature(fid)
    plane = source.refs.get("plane")
    return [
        f.id
        for f in doc.features
        if f.type == "sketch"
        and f.id != fid
        and f.refs.get("plane") == plane
        and not f.refs.get("derived_from")
    ]


def ask_target(session: DocumentSession, fid: str, parent: Any) -> str | None:
    """The sketch to merge into, or None when cancelled (a seam for tests)."""
    from PySide6.QtWidgets import QInputDialog

    doc = session.document
    ids = same_plane_sketches(session, fid)
    names = [doc.feature(i).name for i in ids]
    chosen, ok = QInputDialog.getItem(
        parent, strings.MERGE_SKETCH_TITLE, strings.MERGE_SKETCH_PROMPT, names, 0, False
    )
    return ids[names.index(chosen)] if ok and chosen in names else None


def merge_into(session: DocumentSession, fid: str, parent: Any, report: Any) -> bool:
    """Merge sketch ``fid`` into another on the same plane and delete it, one undo step."""
    from fdcad.core.document.dependencies import children_of
    from fdcad.core.sketch.merge import merge
    from fdcad.core.sketch.model import sketch_from_data, sketch_to_data
    from fdcad.ui.commands.document import DeleteFeature
    from fdcad.ui.equations.commands import DocumentChange

    doc = session.document
    name = doc.feature(fid).name
    if children_of(doc, fid):
        report(strings.MERGE_SKETCH_USED.format(name=name))
        return False
    if not same_plane_sketches(session, fid):
        report(strings.MERGE_SKETCH_NONE.format(name=name))
        return False
    target = ask_target(session, fid, parent)
    if target is None:
        return False
    other = sketch_from_data(doc.feature(fid).data)

    def change(d: Any) -> None:
        feature = d.feature(target)
        kept = sketch_from_data(feature.data)
        merge(kept, other)
        feature.data.update(sketch_to_data(kept))

    session.undo.beginMacro(strings.MERGE_SKETCH_TITLE)
    session.undo.push(DocumentChange(session, strings.MERGE_SKETCH_TITLE, change))
    session.undo.push(DeleteFeature(session, fid))
    session.undo.endMacro()
    report(strings.MERGE_SKETCH_DONE.format(name=name, target=doc.feature(target).name))
    return True
