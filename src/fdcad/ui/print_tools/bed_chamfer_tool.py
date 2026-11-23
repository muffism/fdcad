"""Bed Edge Chamfer command (TR177, DECISIONS D779).

Chamfers every edge of the face on the bed: the print orientation's face, else
the one picked flat face. The size is asked once (0.4 mm to start) and the
chamfer is added as one ordinary feature, which the user can edit or undo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fdcad.ui import strings_print as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def ask_size(window: MainWindow, start: float) -> float | None:
    """The chamfer size in mm, or None when cancelled (a seam for tests)."""
    from PySide6.QtWidgets import QInputDialog

    value, ok = QInputDialog.getDouble(
        window, text.BED_CHAMFER_TITLE, text.BED_CHAMFER_PROMPT, start, 0.05, 5.0, 2
    )
    return value if ok else None


def bed_chamfer(window: MainWindow) -> bool:
    """Add the chamfer. False when there is no bed face or the size was cancelled."""
    from fdcad.core.naming.select import is_planar_face, reference_for
    from fdcad.core.printing.bed_chamfer import DEFAULT_SIZE
    from fdcad.core.printing.bed_chamfer import bed_chamfer as make
    from fdcad.ui.commands.document import AddFeature

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.VOLUME_NOTHING)
        return False
    ref = (tab.session.document.print_setup or {}).get("down_face")
    if not isinstance(ref, dict):
        picked = [s for s in tab.selection if is_planar_face(s)]
        found = reference_for(report.body, picked[0]) if len(picked) == 1 else None
        if found is None:
            window.status.setText(text.BED_CHAMFER_PICK)
            return False
        ref = found
    size = ask_size(window, DEFAULT_SIZE)
    if size is None:
        return False
    feature = make(tab.session.document, ref, size)
    tab.session.undo.push(AddFeature(tab.session, feature))
    window.status.setText(text.BED_CHAMFER_DONE.format(name=feature.name))
    return True
