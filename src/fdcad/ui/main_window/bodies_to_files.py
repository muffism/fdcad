"""Bodies to Part Files: each body to its own file in one command (TR280, D2421).

The picked bodies (or every body) go to a folder: as linked FDCAD parts that follow
the master part (each holds an Insert Part of one body, D2420), as plain FDCAD
parts, or as STEP, STL or 3MF files. Exports run on a worker (CLAUDE.md rule 2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThreadPool

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

#: Choice key to the label in the format list, in list order.
FORMATS = {
    "linked": "Linked FDCAD parts (follow this part)",
    "fdef": "FDCAD parts",
    "step": "STEP files",
    "stl": "STL files",
    "3mf": "3MF files",
}


def picked_bodies(window: MainWindow) -> list[int]:
    """The 0 based indices of the bodies the selection touches, or every body."""
    from fdcad.core.features.solids import solids

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        return []
    every = solids(report.body.shape)
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    out: list[int] = []
    for shape in tab.selection:
        for index, solid in enumerate(every):
            explorer = TopExp_Explorer(solid, TopAbs_FACE)
            while explorer.More():
                if explorer.Current().IsSame(shape) and index not in out:
                    out.append(index)
                    break
                explorer.Next()
    return out or list(range(len(every)))


def run(window: MainWindow, fmt: str | None = None, folder: str | None = None) -> bool:
    """Ask for the format and folder, then write the files. False when cancelled or
    nothing could be written (the status bar says why)."""
    from PySide6.QtWidgets import QFileDialog, QInputDialog

    tab = window.current
    if tab is None or tab.session.report is None or tab.session.report.body is None:
        window.status.setText(strings.BODIES_FILES_NONE)
        return False
    if fmt is None:
        label, ok = QInputDialog.getItem(
            window, strings.BODIES_FILES, strings.BODIES_FILES_PROMPT, list(FORMATS.values()), 0,
            False,
        )  # fmt: skip
        if not ok:
            return False
        fmt = next(k for k, v in FORMATS.items() if v == label)
    session = tab.session
    if fmt == "linked" and session.path is None:
        window.status.setText(strings.BODIES_FILES_SAVE_FIRST)
        return False
    if folder is None:
        folder = QFileDialog.getExistingDirectory(window, strings.BODIES_FILES)
        if not folder:
            return False
    indices = picked_bodies(window)
    stem = session.path.stem if session.path is not None else (session.name or "Part")
    names = [f"{stem} body {k + 1}" for k in indices]
    if fmt == "linked":
        from fdcad.core.io.export import ExportError
        from fdcad.core.io.save_bodies import save_linked_parts

        try:
            assert session.path is not None
            written = save_linked_parts(
                session.path, [(n, k + 1) for n, k in zip(names, indices, strict=True)], folder,
                session.document.units,
            )  # fmt: skip
        except ExportError as exc:
            window.status.setText(str(exc))
            return False
        window.status.setText(strings.BODIES_FILES_DONE.format(count=len(written), folder=folder))
        return True
    _export(window, fmt, folder, indices, names)
    return True


def _export(
    window: MainWindow, fmt: str, folder: str, indices: list[int], names: list[str]
) -> None:
    """Write the bodies with the export writers on a worker."""
    from fdcad.core.appearance import part_color
    from fdcad.core.features.solids import solids
    from fdcad.ui.background import start_job
    from fdcad.ui.body_tools.form_widget import _CountJob

    tab = window.current
    assert tab is not None and tab.session.report is not None
    body = tab.session.report.body
    assert body is not None
    units, color = tab.session.document.units, part_color(tab.session.document.appearance)
    shape = body.shape

    def work() -> tuple[int, list[str]]:
        from fdcad.core.io.export import ExportError
        from fdcad.core.io.save_bodies import save_bodies

        every = solids(shape)
        pairs = [(n, every[k]) for n, k in zip(names, indices, strict=True)]
        try:
            return len(save_bodies(pairs, folder, fmt, units, color=color)), [folder]
        except ExportError as exc:
            return -1, [str(exc)]

    job = _CountJob(work)

    def done(count: int, info: Any) -> None:
        lines = list(info) if isinstance(info, list) else []
        if count < 0:
            window.status.setText(lines[0] if lines else strings.BODIES_FILES_NONE)
        else:
            window.status.setText(strings.BODIES_FILES_DONE.format(count=count, folder=folder))

    job.signals.done.connect(done)
    window._bodies_jobs = getattr(window, "_bodies_jobs", set()) | {job}  # keep it alive
    start_job(QThreadPool.globalInstance(), job)
