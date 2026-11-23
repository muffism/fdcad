"""Body folders in the Solid Bodies folder (TR153 item 1, D2106): Move to Folder on a
body row, and Hide, Show, Colour, Delete, Rename and Remove on a folder row."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QInputDialog, QWidget

from fdcad.core import body_folders
from fdcad.ui import strings_config as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.body_display import BodyDisplay
    from fdcad.ui.main_window.window import DocumentTab


def ask_folder(parent: QWidget, current: str) -> str | None:
    """Ask for a folder name (tests replace this). None when cancelled."""
    typed, ok = QInputDialog.getText(
        parent, text.BODY_FOLDER_TITLE, text.BODY_FOLDER_PROMPT, text=current
    )
    return typed if ok else None


def _body(tab: DocumentTab) -> Any:
    report = tab.session.report
    return report.body if report is not None else None


def _store(tab: DocumentTab, value: dict[str, str], label: str) -> None:
    from fdcad.ui.commands.print_setup import SetPrintSetupKey

    if value != body_folders.stored(tab.session.document):
        tab.session.undo.push(
            SetPrintSetupKey(tab.session, body_folders.BODY_FOLDERS, value, label)
        )


def move_to_folder(display: BodyDisplay, tab: DocumentTab, indices: list[int]) -> bool:
    """Put bodies in a folder (a new or an existing one); empty takes them out."""
    doc, named = tab.session.document, _body(tab)
    now = body_folders.folders_of(doc, named)
    current = next((now[i] for i in indices if 0 <= i < len(now) and now[i]), "") or ""
    typed = ask_folder(display.window, current)
    if typed is None:
        return False
    _store(tab, body_folders.with_folder(doc, named, indices, typed), text.BODY_FOLDER_UNDO)
    return True


def folder_action(display: BodyDisplay, tab: DocumentTab, op: str, folder: str) -> bool:
    """Run a folder row command on the folder's bodies."""
    doc, named = tab.session.document, _body(tab)
    indices = body_folders.members(doc, named, folder)
    if op in ("hide", "show"):
        if not indices:
            return False
        display.set_hidden(tab, indices, op == "hide")
        return True
    if op == "colour":
        from fdcad.core.appearance import Target
        from fdcad.ui.appearance.entries import change_color

        targets = [Target("body", str(i + 1)) for i in indices]
        return change_color(tab.session, targets, folder, display.window)
    if op == "delete":
        return delete_bodies(display, tab, indices, folder)
    if op == "rename":
        typed = ask_folder(display.window, folder)
        if typed is None:
            return False
        _store(tab, body_folders.renamed(doc, folder, typed), text.BODY_FOLDER_UNDO)
        return True
    if op == "remove":
        _store(tab, body_folders.renamed(doc, folder, ""), text.BODY_FOLDER_UNDO)
        return True
    return False


def delete_bodies(display: BodyDisplay, tab: DocumentTab, indices: list[int], folder: str) -> bool:
    """Add a Delete Body feature for the folder's bodies (one undo step)."""
    from fdcad.core.document.model import Feature
    from fdcad.core.features.names import default_name
    from fdcad.core.features.solids import solids
    from fdcad.core.naming.select import reference_for
    from fdcad.ui.commands.document import AddFeature

    named = _body(tab)
    if named is None or not indices:
        return False
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    all_solids = solids(named.shape)
    refs = []
    for i in indices:
        if not 0 <= i < len(all_solids):
            continue
        face = TopExp_Explorer(all_solids[i], TopAbs_FACE).Current()
        ref = reference_for(named, face)
        if ref is not None:
            refs.append(ref)
    if not refs:
        display.window.status.setText(text.BODY_FOLDER_NO_DELETE)
        return False
    doc = tab.session.document
    feature = Feature(
        doc.new_feature_id(),
        "delete_body",
        default_name(doc, "delete_body"),
        params={"option": "delete"},
        refs={"bodies": refs},
    )
    tab.session.undo.push(AddFeature(tab.session, feature))
    display.window.status.setText(text.BODY_FOLDER_DELETED.format(count=len(refs), folder=folder))
    return True
