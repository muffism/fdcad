"""Display mode and transparency per body from the Solid Bodies menu (TR216, D1606)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.core.body_modes import KEY, body_modes, set_body_display, with_body_mode
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

DISPLAY_MODE = "Display Mode"
MODE_LABELS = {
    "": "As the View",
    "shaded_edges": "Shaded With Edges",
    "shaded": "Shaded",
    "wireframe": "Wireframe",
}
TRANSPARENCY = "Transparency..."
TRANSPARENCY_TITLE = "Body Transparency"
TRANSPARENCY_PROMPT = "How see through body {number} is, in percent (0 is solid):"
UNDO = "Body Display {number}"


class SetBodyDisplay(DocumentCommand):
    """Change the bodies' display modes and transparency: one undo step, no rebuild."""

    def __init__(self, session: Any, entries: dict[str, Any], text: str) -> None:
        super().__init__(session, text)
        self.before = session.document.appearance.get(KEY)
        self.after = entries

    def apply(self) -> None:
        """Store the new block."""
        set_body_display(self.session.document, self.after)

    def revert(self) -> None:
        """Store the old block."""
        set_body_display(
            self.session.document, self.before if isinstance(self.before, dict) else {}
        )

    def redo(self) -> None:
        """Draw the part again."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Draw the part again as before."""
        self.revert()
        self.session.display_changed.emit()


def current(tab: DocumentTab, index: int) -> tuple[str, float]:
    """The mode and transparency of body ``index``."""
    report = tab.session.report
    modes = body_modes(tab.session.document, report.body if report is not None else None)
    return modes[index] if 0 <= index < len(modes) else ("", 0.0)


def set_mode(
    tab: DocumentTab, index: int, mode: str | None = None, transparency: float | None = None
) -> bool:
    """Give body ``index`` a mode and/or transparency as one undo step. False when
    nothing changed."""
    report = tab.session.report
    body = report.body if report is not None else None
    entries = with_body_mode(tab.session.document, body, index, mode, transparency)
    old = tab.session.document.appearance.get(KEY) or {}
    if entries == old:
        return False
    tab.session.undo.push(SetBodyDisplay(tab.session, entries, UNDO.format(number=index + 1)))
    return True


def ask_transparency(window: MainWindow, tab: DocumentTab, index: int) -> bool:
    """Ask for body ``index``'s transparency in percent and set it."""
    from PySide6.QtWidgets import QInputDialog

    start = round(current(tab, index)[1] * 100)
    value, ok = QInputDialog.getInt(
        window,
        TRANSPARENCY_TITLE,
        TRANSPARENCY_PROMPT.format(number=index + 1),
        start,
        0,
        90,
        10,
    )
    if not ok:
        return False
    return set_mode(tab, index, transparency=value / 100)


def solids_with_modes(tab: DocumentTab) -> list[tuple[Any, str, float]]:
    """Each body with its own mode or transparency, as (solid, mode, transparency)."""
    from fdcad.core.features.solids import solids

    report = tab.session.report
    body = report.body if report is not None else None
    if body is None or not tab.session.document.appearance.get(KEY):
        return []
    modes = body_modes(tab.session.document, body)
    parts = solids(body.shape)
    return [(parts[i], m, t) for i, (m, t) in enumerate(modes) if i < len(parts) and (m or t)]
