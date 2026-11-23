"""Replace Everywhere (TR277, D838): pick the new item for every feature that uses one."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.core.document.model import Document, Feature
    from fdcad.ui.session import DocumentSession

#: Feature types that are planes: a plane is replaced by another plane.
_PLANES = ("plane", "ref_plane")


def candidates(doc: Document, fid: str) -> list[Feature]:
    """Items that can take the place of ``fid``: the same kind, built before its first
    user (so every user can still use it), not ``fid`` itself."""
    from fdcad.core.naming.replace import users_of

    old = doc.feature(fid)
    users = users_of(doc, {"feature": fid})
    order = {f.id: i for i, f in enumerate(doc.features)}
    first = min((order[u] for u in users), default=len(doc.features))
    planes = old.type in _PLANES
    out = []
    for f in doc.features:
        if f.id == fid or order[f.id] >= first:
            continue
        if (f.type in _PLANES) if planes else (f.type == old.type):
            out.append(f)
    return out


class ReplaceDialog(QDialog):
    """The new item and Delete Old."""

    def __init__(
        self, name: str, items: list[Feature], delete_old: bool, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("replace_dialog")
        self.setWindowTitle(strings.REPLACE_EVERYWHERE)
        intro = QLabel(strings.REPLACE_INTRO.format(name=name))
        intro.setWordWrap(True)
        self.choice = QComboBox()
        for f in items:
            self.choice.addItem(f.name, f.id)
        self.delete_old = QCheckBox(strings.REPLACE_DELETE_OLD)
        self.delete_old.setChecked(delete_old)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.choice)
        layout.addWidget(self.delete_old)
        layout.addWidget(buttons)


def ask(
    name: str, items: list[Feature], delete_old: bool, parent: QWidget | None
) -> tuple[str, bool] | None:
    """The new item's id and Delete Old, or None when cancelled (a seam for tests)."""
    dialog = ReplaceDialog(name, items, delete_old, parent)
    accepted = bool(dialog.exec())
    found = (str(dialog.choice.currentData()), dialog.delete_old.isChecked())
    dialog.deleteLater()
    return found if accepted and dialog.choice.count() else None


def replace_everywhere(
    session: DocumentSession, fid: str, delete_old: bool, parent: QWidget | None, status: object
) -> bool:
    """Ask, then switch every user of ``fid`` to the chosen item as one undo step."""
    from fdcad.core.naming.replace import replace_everywhere as swap
    from fdcad.core.naming.replace import users_of
    from fdcad.ui.commands.document import DeleteFeature, ReplaceFeature

    doc = session.document
    say = getattr(status, "setText", None)
    if not users_of(doc, {"feature": fid}):
        if say is not None:
            say(strings.REPLACE_NO_USERS.format(name=doc.feature(fid).name))
        return False
    items = candidates(doc, fid)
    if not items:
        if say is not None:
            say(strings.REPLACE_NONE.format(name=doc.feature(fid).name))
        return False
    found = ask(doc.feature(fid).name, items, delete_old, parent)
    if found is None:
        return False
    new_id, drop = found
    edited = swap(doc, {"feature": fid}, {"feature": new_id})
    session.undo.beginMacro(strings.REPLACE_UNDO.format(name=doc.feature(fid).name))
    for feature in edited.values():
        session.undo.push(ReplaceFeature(session, feature))
    if drop:
        session.undo.push(DeleteFeature(session, fid))
    session.undo.endMacro()
    if say is not None:
        say(strings.REPLACE_DONE.format(n=len(edited), name=doc.feature(new_id).name))
    return True
