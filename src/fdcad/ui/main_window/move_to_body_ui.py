"""Move to Body... on a feature row (TR155, D2107)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QInputDialog, QWidget

from fdcad.core import move_to_body
from fdcad.ui import strings_config as text

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession


def offered(session: DocumentSession, fid: str) -> bool:
    """True when the feature can act on another body: it has a Bodies box and the
    part has two or more bodies before it."""
    from fdcad.core.features.solids import solids

    feature = next((f for f in session.document.features if f.id == fid), None)
    if feature is None or feature.type not in move_to_body.TYPES:
        return False
    results = getattr(session.report, "results", None)
    body = move_to_body.bodies_before(session.document, feature, results)
    return body is not None and len(solids(body.shape)) > 1


def ask_body(parent: QWidget, labels: list[str], current: int) -> int | None:
    """Ask which body (tests replace this). None when cancelled."""
    picked, ok = QInputDialog.getItem(
        parent, text.MOVE_BODY_TITLE, text.MOVE_BODY_PROMPT, labels, max(current, 0), False
    )
    return labels.index(picked) if ok and picked in labels else None


def move_feature(parent: QWidget, session: DocumentSession, fid: str) -> bool:
    """Ask for a body and make the feature act on it only (one undo step)."""
    from fdcad.core.body_titles import labels_of
    from fdcad.ui.commands.document import ReplaceFeature

    doc = session.document
    feature = doc.feature(fid)
    results = getattr(session.report, "results", None)
    body = move_to_body.bodies_before(doc, feature, results)
    labels = labels_of(doc, body)
    current = move_to_body.current_body(doc, feature, results)
    index = ask_body(parent, labels, current if current is not None else -1)
    if index is None:
        return False
    status = getattr(parent.window(), "status", None)
    try:
        edited = move_to_body.moved(doc, feature, results, index)
    except move_to_body.MoveToBodyError as exc:
        if status is not None:
            status.setText(str(exc))
        return False
    if edited == feature:
        return False
    session.undo.push(
        ReplaceFeature(session, edited, text.MOVE_BODY_UNDO.format(name=feature.name))
    )
    if status is not None:
        status.setText(text.MOVE_BODY_DONE.format(name=feature.name, body=labels[index]))
    return True
