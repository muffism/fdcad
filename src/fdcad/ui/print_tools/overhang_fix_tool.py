"""Fix Overhangs command (TR410, D909): a Chamfer on the edges of every flat face that
faces down above the bed, in the print orientation. The faces are found in the
background; the size is asked once; the chamfer is one ordinary feature the user can
edit or undo (CLAUDE.md 5.12: it is offered, then confirmed by the click)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.ui import strings_print as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def ask_size(window: MainWindow, start: float) -> float | None:
    """The chamfer size in mm, or None when cancelled (a seam for tests)."""
    from PySide6.QtWidgets import QInputDialog

    value, ok = QInputDialog.getDouble(
        window, text.OVERHANG_FIX_TITLE, text.OVERHANG_FIX_PROMPT, start, 0.1, 20.0, 2
    )
    return value if ok else None


def fix_overhangs(window: MainWindow) -> bool:
    """Find the faces in the background, then ask the size and add the chamfer."""
    from fdcad.core.naming.select import reference_for
    from fdcad.core.printing import orientation
    from fdcad.core.printing.overhang_fix import DEFAULT_SIZE, overhang_chamfer, underside_faces
    from fdcad.ui.commands.document import AddFeature
    from fdcad.ui.print_tools import jobs

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.VOLUME_NOTHING)
        return False
    body = report.body
    setup = dict(tab.session.document.print_setup or {})

    def work() -> Any:
        try:
            face = orientation.down_face(body, setup)
        except orientation.OrientationError:
            face = None
        up = orientation.build_direction(face)
        found = underside_faces(body, up)
        return [r for r in (reference_for(body, f) for f in found) if r is not None]

    def done(refs: Any) -> None:
        if not refs:
            window.status.setText(text.OVERHANG_FIX_NONE)
            return
        size = ask_size(window, DEFAULT_SIZE)
        if size is None:
            return
        feature = overhang_chamfer(tab.session.document, list(refs), size)
        tab.session.undo.push(AddFeature(tab.session, feature))
        window.status.setText(text.OVERHANG_FIX_DONE.format(name=feature.name, n=len(refs)))

    def failed(message: str) -> None:
        window.status.setText(text.OVERHANG_FAILED.format(reason=message))

    jobs.start(work, done, failed)
    return True
