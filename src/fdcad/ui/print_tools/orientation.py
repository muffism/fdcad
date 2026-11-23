"""Print orientation: lay a picked face flat on the bed (PLAN Phase 2, DECISIONS D353).

The orientation changes exports only, never the model. Setting and clearing it
are undoable commands.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_print as text

if TYPE_CHECKING:
    from fdcad.core.printing.profiles import PrinterProfile
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


def print_shape_work(tab: DocumentTab, profile: PrinterProfile) -> Callable[[], tuple[Any, str]]:
    """A function for a background job: the shape to print and a note for the status bar.

    A face that can no longer be found gives the model as it is, with a note.
    """
    from fdcad.core.printing import orientation

    report = tab.session.report
    assert report is not None and report.body is not None
    body = report.body
    setup = dict(tab.session.document.print_setup or {})
    from fdcad.ui.print_tools.fit_tool import tab_fit

    fit = tab_fit(tab)  # Scale to Fit Printer (TR185)

    def work() -> tuple[Any, str]:
        try:
            face = orientation.down_face(body, setup)
        except orientation.OrientationError as exc:
            return body.shape, text.ORIENT_LOST.format(reason=exc)
        return orientation.print_shape(body.shape, face, profile, fit), ""

    return work


def print_colored_work(
    tab: DocumentTab, profile: PrinterProfile, colored: list[tuple[Any, str]]
) -> Callable[[], tuple[Any, list[tuple[Any, str]], str]]:
    """Like ``print_shape_work``, also moving the coloured faces with the part (D714)."""
    from fdcad.core.printing import orientation

    report = tab.session.report
    assert report is not None and report.body is not None
    body = report.body
    setup = dict(tab.session.document.print_setup or {})
    from fdcad.ui.print_tools.fit_tool import tab_fit

    fit = tab_fit(tab)

    def work() -> tuple[Any, list[tuple[Any, str]], str]:
        try:
            face = orientation.down_face(body, setup)
        except orientation.OrientationError as exc:
            return body.shape, list(colored), text.ORIENT_LOST.format(reason=exc)
        shape, faces = orientation.print_shape_faces(body.shape, face, profile, colored, fit)
        return shape, faces, ""

    return work


def print_transform_work(
    tab: DocumentTab, profile: PrinterProfile
) -> Callable[[], tuple[Any, str]]:
    """For a background job: the placement onto the bed as a gp_Trsf (None when no face
    is laid flat), for a 3MF that keeps the model and moves it in its build item (TR381).
    A face that can no longer be found gives None and a note."""
    from fdcad.core.printing import orientation

    report = tab.session.report
    assert report is not None and report.body is not None
    body = report.body
    setup = dict(tab.session.document.print_setup or {})
    from fdcad.ui.print_tools.fit_tool import tab_fit

    fit = tab_fit(tab)

    def work() -> tuple[Any, str]:
        try:
            face = orientation.down_face(body, setup)
        except orientation.OrientationError as exc:
            return None, text.ORIENT_LOST.format(reason=exc)
        if face is None and fit is None:
            return None, ""
        return orientation.placement(body.shape, face, profile, fit), ""

    return work


def thumbnail(tab: DocumentTab, size: int = 256) -> bytes | None:
    """A PNG picture of the 3D view for a 3MF package (TR381), or None without a view."""
    from PySide6.QtCore import QBuffer, QIODevice

    render = getattr(tab.viewport, "render_image", None)
    image = render(size, size) if render is not None else None
    if image is None or image.isNull():
        return None
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data().data())


class OrientationTool:
    """Lay Face Flat and Clear Print Orientation."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.waiting: DocumentTab | None = None

    def lay_flat(self) -> None:
        """Use the one picked flat face, or wait for the next face picked in the view."""
        tab = self.window.current
        if tab is None or tab.session.report is None or tab.session.report.body is None:
            self.window.status.setText(text.VOLUME_NOTHING)
            return
        if len(tab.selection) == 1:
            self.take(tab, tab.selection[0])
            return
        self.waiting = tab
        signal = getattr(tab.viewport, "selection_changed", None)
        if signal is not None:
            signal.connect(self._picked)
        self.window.status.setText(text.ORIENT_PICK)

    def _picked(self, shapes: list[Any]) -> None:
        tab = self.waiting
        if tab is None:
            return
        if self.window.editing or tab is not self.window.current:
            # Another tool took over: its picks are not for the print orientation.
            self._stop_waiting()
            return
        if len(shapes) != 1:
            return
        self._stop_waiting()
        self.take(tab, shapes[0])

    def _stop_waiting(self) -> None:
        tab, self.waiting = self.waiting, None
        signal = getattr(tab.viewport, "selection_changed", None) if tab is not None else None
        if signal is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                signal.disconnect(self._picked)

    def take(self, tab: DocumentTab, shape: Any) -> bool:
        """Lay ``shape`` flat when it is a flat face with a name. True when it was set."""
        from fdcad.core.naming.select import is_planar_face, reference_for
        from fdcad.ui.commands.print_setup import SetPrintSetup

        report = tab.session.report
        if report is None or report.body is None:
            return False
        if not is_planar_face(shape):
            self.window.status.setText(text.ORIENT_NOT_FLAT)
            return False
        ref = reference_for(report.body, shape)
        if ref is None:
            self.window.status.setText(text.ORIENT_NO_NAME)
            return False
        tab.session.undo.push(SetPrintSetup(tab.session, ref, text.UNDO_ORIENT))
        self.window.status.setText(text.ORIENT_SET)
        return True

    def clear(self) -> None:
        """Print the part as modelled again."""
        self._stop_waiting()
        tab = self.window.current
        if tab is None:
            return
        if (tab.session.document.print_setup or {}).get("down_face") is None:
            self.window.status.setText(text.ORIENT_CLEARED)
            return
        from fdcad.ui.commands.print_setup import SetPrintSetup

        tab.session.undo.push(SetPrintSetup(tab.session, None, text.UNDO_CLEAR_ORIENT))
        self.window.status.setText(text.ORIENT_CLEARED)
