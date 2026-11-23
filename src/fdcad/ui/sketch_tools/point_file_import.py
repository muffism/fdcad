"""Sketch, Points from File (TR415 item 2, D933): X and Y rows of a text file become
plain sketch points, as one sketch undo step."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


def choose_file(canvas: SketchCanvas) -> str:
    """Ask for the file; tests replace this. "" when cancelled."""
    from PySide6.QtWidgets import QFileDialog

    path, _f = QFileDialog.getOpenFileName(
        canvas, strings.POINT_FILE_TITLE, "", strings.POINT_FILE_FILTER
    )
    return path


def points_from_file(canvas: SketchCanvas, path: str | None = None) -> list[str]:
    """Read the file and add its points. Returns the new point ids."""
    from fdcad.core.sketch.point_file import PointFileError, add_points, read_points

    chosen = path if path is not None else choose_file(canvas)
    if not chosen:
        return []
    try:
        text = Path(chosen).read_text(encoding="utf-8-sig")
        points, skipped = read_points(text, canvas.units)
    except (OSError, UnicodeDecodeError) as exc:
        canvas.status_message.emit(strings.POINT_FILE_UNREADABLE.format(reason=exc))
        return []
    except PointFileError as exc:
        canvas.status_message.emit(str(exc))
        return []
    made: list[str] = []
    canvas.run(lambda: made.extend(add_points(canvas.edit.sketch, points)))
    canvas.selection = list(made)
    canvas.selection_changed.emit()
    note = strings.POINT_FILE_DONE.format(count=len(made))
    if skipped:
        note += " " + strings.POINT_FILE_SKIPPED.format(count=skipped)
    canvas.status_message.emit(note)
    return made
