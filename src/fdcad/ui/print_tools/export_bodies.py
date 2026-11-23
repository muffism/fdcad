"""File, Export, Bodies: each body of the part to its own file (spec 2 section 20 item 13,
DECISIONS D714).

After Split for Printing the pieces are separate bodies; Export STL and 3MF write them
all into one file. This writes one file per body, in a folder the user picks. STL and
3MF follow the print orientation set with Lay Face Flat, as Export STL does: the whole
part is laid flat and every body keeps its place in it (one orientation per part).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QFileDialog, QInputDialog

from fdcad.ui import strings_print as text
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

#: Choice label to save_bodies format key.
FORMATS = {"STL": "stl", "3MF": "3mf", "STEP": "step", "FDCAD Part": "fdef"}


def export_bodies(window: MainWindow) -> jobs.Job | None:
    """Ask for a folder and a format, then write each body in the background."""
    from fdcad.core.appearance import part_color
    from fdcad.core.features.solids import solids
    from fdcad.ui.preferences.print_settings import active_profile

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.BODIES_NOTHING)
        return None
    if tab.session.is_rebuilding or report.cancelled:
        window.status.setText(text.BODIES_WAIT)
        return None
    pieces = solids(report.body.shape)
    if len(pieces) < 2:
        window.status.setText(text.BODIES_ONE)
        return None
    folder = QFileDialog.getExistingDirectory(window, text.BODIES_FOLDER)
    if not folder:
        return None
    choice, ok = QInputDialog.getItem(
        window, text.BODIES_TITLE, text.BODIES_FORMAT, list(FORMATS), 0, False
    )
    if not ok or choice not in FORMATS:
        return None
    fmt = FORMATS[choice]
    doc = tab.session.document
    units, color = doc.units, part_color(doc.appearance)
    part = tab.session.title.rstrip("*") or text.BODIES_PART
    body = report.body
    setup = dict(doc.print_setup or {})
    profile = active_profile(window.settings)

    def work() -> str:
        from fdcad.core.io.save_bodies import save_bodies
        from fdcad.core.printing import orientation

        shapes: list[Any] = list(pieces)
        note = ""
        if fmt in ("stl", "3mf"):
            try:
                face = orientation.down_face(body, setup)
            except orientation.OrientationError as exc:
                face, note = None, text.ORIENT_LOST.format(reason=exc)
            if face is not None:
                trsf = orientation.placement(body.shape, face, profile)
                shapes = [orientation.moved(s, trsf) for s in shapes]
        named = [(f"{part} body {k}", s) for k, s in enumerate(shapes, start=1)]
        written = save_bodies(named, folder, fmt, units, color=color)
        done = text.BODIES_DONE.format(n=len(written), folder=folder)
        return f"{done} {note}".strip()

    return jobs.start(
        work,
        window.status.setText,
        lambda reason: window.status.setText(text.BODIES_FAILED.format(reason=reason)),
    )
