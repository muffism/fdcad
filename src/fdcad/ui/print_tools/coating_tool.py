"""Print, Coating Allowance (TR307, DECISIONS D1214).

The command asks for the part's coating thickness and keeps it in the print
setup (one undo step). STL and 3MF export and Open in Slicer then shrink every
face by it (``coated``), in the export job.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QInputDialog

from fdcad.ui import strings_print as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def coated(part: Any, coat: float, faces: Any) -> tuple[Any, Any, str]:
    """``part`` shrunk by the coating allowance, its moved face colours and a status
    note; unchanged with no coating. Kernel work: call it in a job."""
    if coat <= 0:
        return part, faces, ""
    from fdcad.core.io.export import ExportError
    from fdcad.core.printing.coating import allowed

    try:
        out, moved = allowed(part, coat, list(faces) if faces else None)
    except ValueError:
        raise ExportError(
            "A body is too thin for the coating allowance. Enter a thinner coating."
        ) from None
    return out, moved if faces else faces, text.COATING_APPLIED.format(coat=f"{coat:g}")


def set_coating(window: MainWindow, value: float | None = None) -> None:
    """Ask for the coating thickness (``value`` skips the question) and keep it."""
    from fdcad.core.printing.coating import COATING, LIMIT, thickness
    from fdcad.ui.commands.print_setup import SetPrintSetupKey

    tab = window.current
    if tab is None:
        window.status.setText(text.HEIGHTS_NO_PART)
        return
    now = thickness(tab.session.document.print_setup)
    if value is None:
        value, ok = QInputDialog.getDouble(
            window, text.COATING_TITLE, text.COATING_PROMPT, now, 0.0, LIMIT, 3
        )
        if not ok:
            return
    if abs(value - now) < 1e-9:
        return
    tab.session.undo.push(
        SetPrintSetupKey(tab.session, COATING, value if value > 0 else None, text.COATING_UNDO)
    )
    window.status.setText(
        text.COATING_SET.format(coat=f"{value:g}") if value > 0 else text.COATING_OFF
    )
