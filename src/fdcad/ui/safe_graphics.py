"""Safe start without graphics hardware (TR219, DECISIONS D2016).

Software drawing is used when FDCAD starts with ``--safe-graphics``, when the
``FDCAD_SAFE_GRAPHICS`` environment variable is 1, when Preferences has Safe
graphics ticked, or when the last start did not get as far as showing the
window (a start marker is left in the data folder until then, so a graphics
driver that crashes the start makes the next start safe). It must be decided
before the QApplication exists: Qt is told to use its software OpenGL, and the
Mesa variables ask a Mesa driver for its software rasteriser.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

FLAG = "--safe-graphics"
ENV = "FDCAD_SAFE_GRAPHICS"
#: The QSettings key of the Preferences tick.
KEY = "view/safe_graphics"
MARKER = "starting.marker"


def wanted(args: list[str], marker_dir: Path | None, setting: bool) -> tuple[bool, str]:
    """Whether to use software drawing, and why ("flag", "env", "setting", "crash" or "")."""
    if FLAG in args:
        return True, "flag"
    if os.environ.get(ENV, "") == "1":
        return True, "env"
    if setting:
        return True, "setting"
    if marker_dir is not None and (marker_dir / MARKER).is_file():
        return True, "crash"
    return False, ""


def use_software() -> None:
    """Ask Qt and Mesa for software drawing. Call before the QApplication exists."""
    from PySide6.QtCore import QCoreApplication, Qt

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    os.environ.setdefault("GALLIUM_DRIVER", "llvmpipe")


def mark_start(marker_dir: Path) -> None:
    """Leave the start marker; :func:`clear_start` removes it once the window shows."""
    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / MARKER).write_text("starting\n", encoding="utf-8")
    except OSError:
        pass


def clear_start(marker_dir: Path) -> None:
    """The window is up: the start worked."""
    with contextlib.suppress(OSError):
        (marker_dir / MARKER).unlink(missing_ok=True)


def read_setting() -> bool:
    """The Preferences tick, read before the QApplication exists."""
    from fdcad import portable

    value = portable.settings().value(KEY, "false")
    return str(value).lower() == "true"
