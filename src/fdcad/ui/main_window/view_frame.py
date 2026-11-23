"""Set the current view as Front, any standard view or Home, and Reset (TR333, D955).

The part keeps its own view frame (core/document/view_frame.py); the standard view
commands and Home look along the turned directions. Changing it is one undo step
that rebuilds nothing.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QInputDialog

from fdcad.core.document import view_frame as vf
from fdcad.ui import strings
from fdcad.ui.commands.document import DocumentCommand
from fdcad.ui.viewport.views import STANDARD_VIEWS, Vec3

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.session import DocumentSession

#: Views that can be set from the current camera, in the order the list shows them.
SETTABLE = ("front", "back", "left", "right", "top", "bottom", "home")


class SetViewFrame(DocumentCommand):
    """Replace the part's view frame as one undo step. Nothing to rebuild."""

    def __init__(self, session: DocumentSession, value: dict[str, Any] | None, label: str) -> None:
        super().__init__(session, label)
        self.before = copy.deepcopy(session.document.extra.get(vf.KEY))
        self.after = copy.deepcopy(value)

    def _put(self, value: dict[str, Any] | None) -> None:
        if value:
            self.session.document.extra[vf.KEY] = copy.deepcopy(value)
        else:
            self.session.document.extra.pop(vf.KEY, None)

    def apply(self) -> None:
        """Store the new frame."""
        self._put(self.after)

    def revert(self) -> None:
        """Put the old frame back."""
        self._put(self.before)

    def redo(self) -> None:
        """Store only; the solid does not change."""
        self.apply()

    def undo(self) -> None:
        """Restore only; the solid does not change."""
        self.revert()


def view_directions(extra: dict[str, Any], name: str) -> tuple[Vec3, Vec3] | None:
    """Eye direction and up vector of a standard view or "home" in this part."""
    if name == "home":
        home = vf.home_of(extra)
        if home is not None:
            return home
        name = "iso"
    if name not in STANDARD_VIEWS:
        return None
    frame = vf.frame_of(extra)
    eye, up = STANDARD_VIEWS[name]
    return vf.turn(frame, eye), vf.turn(frame, up)


class ViewFrame:
    """The window's Home, Set Current View As and Reset Standard Views commands."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window

    def _extra(self) -> dict[str, Any]:
        tab = self.window.current
        session = getattr(tab, "session", None)
        return session.document.extra if session is not None else {}

    def look(self, name: str) -> bool:
        """Turn the active view to a standard view or Home of this part."""
        found = view_directions(self._extra(), name)
        if found is None:
            return False
        self.window._call_view("look", *found)
        return True

    def ask_view(self) -> str | None:
        """Which view the camera becomes, or None (a seam for tests)."""
        names = [strings.VIEW_FRAME_NAMES[n] for n in SETTABLE]
        chosen, ok = QInputDialog.getItem(
            self.window, strings.VIEW_SET_AS, strings.VIEW_SET_AS_PROMPT, names, 0, False
        )
        return SETTABLE[names.index(chosen)] if ok and chosen in names else None

    def set_current_as(self, name: str | None = None) -> bool:
        """Make the current camera the chosen view; the others turn with Front."""
        tab = self.window.current
        session = getattr(tab, "session", None)
        if session is None:
            return False
        camera = self.window._call_view("eye_up")
        if camera is None:
            self.window.statusBar().showMessage(strings.VIEW_FRAME_NO_VIEW)
            return False
        name = name or self.ask_view()
        if name is None:
            return False
        extra = session.document.extra
        try:
            if name == "home":
                value = vf.with_home(extra, camera)
            else:
                frame = vf.frame_for(STANDARD_VIEWS[name], *camera)
                value = vf.with_frame(extra, frame)
        except vf.ViewFrameError as exc:
            self.window.statusBar().showMessage(str(exc))
            return False
        label = strings.VIEW_FRAME_NAMES[name]
        session.undo.push(SetViewFrame(session, value, strings.VIEW_SET_AS_DONE.format(view=label)))
        self.window.statusBar().showMessage(strings.VIEW_SET_AS_DONE.format(view=label))
        return True

    def reset(self) -> bool:
        """Put the standard views and Home back to the factory directions."""
        session = getattr(self.window.current, "session", None)
        if session is None or vf.KEY not in session.document.extra:
            self.window.statusBar().showMessage(strings.VIEW_FRAME_NOTHING)
            return False
        session.undo.push(SetViewFrame(session, None, strings.VIEW_RESET))
        self.window.statusBar().showMessage(strings.VIEW_RESET_DONE)
        return True
