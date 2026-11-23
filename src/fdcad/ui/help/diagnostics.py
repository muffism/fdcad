"""Help, Diagnostics: system info for bug reports and the log folder (U10.3, U9.4, D677).

Everything is read locally; nothing is sent anywhere (CLAUDE.md rules 8 and 9).
"""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QUrl, qVersion
from PySide6.QtGui import QDesktopServices, QGuiApplication

from fdcad import __version__
from fdcad.ui import strings_feedback as text
from fdcad.ui.help.privacy import scrub

#: OpenGL ``glGetString`` names.
GL_VENDOR, GL_RENDERER, GL_VERSION = 0x1F00, 0x1F01, 0x1F02


def build_date() -> str | None:
    """The date this build was made (the app file's date), or None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        stamp = Path(sys.executable).stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(stamp, UTC).strftime("%Y-%m-%d")


def build_text() -> str:
    """The build date line for About, or that FDCAD runs from source."""
    date = build_date()
    return text.ABOUT_BUILD.format(date=date) if date else text.ABOUT_BUILD_SOURCE


def opengl_info() -> dict[str, str]:
    """OpenGL vendor, renderer and version from a small offscreen context, or why not."""
    try:
        from PySide6.QtGui import QOffscreenSurface, QOpenGLContext

        context = QOpenGLContext()
        if not context.create():
            return {"OpenGL": "not available"}
        surface = QOffscreenSurface()
        surface.setFormat(context.format())
        surface.create()
        if not context.makeCurrent(surface):
            return {"OpenGL": "not available"}
        gl = context.functions()
        info = {
            "OpenGL": str(gl.glGetString(GL_VERSION) or "unknown"),
            "GPU": str(gl.glGetString(GL_RENDERER) or "unknown"),
            "GPU vendor": str(gl.glGetString(GL_VENDOR) or "unknown"),
        }
        context.doneCurrent()
        surface.destroy()
        return info
    except Exception as exc:  # any driver trouble only means "unknown"
        return {"OpenGL": f"not available ({type(exc).__name__})"}


def screens() -> list[str]:
    """Each screen: name, size in logical pixels and display scaling."""
    out = []
    for screen in QGuiApplication.screens():
        size = screen.geometry()
        scale = round(screen.devicePixelRatio() * 100)
        out.append(f"{screen.name() or 'screen'}: {size.width()} x {size.height()}, {scale} %")
    return out


def system_info(theme: str = "", log_folder: Path | None = None) -> str:
    """Plain text for a bug report: version, OS, Qt, OpenGL, GPU, scaling and theme."""
    import PySide6

    rows: dict[str, str] = {
        "FDCAD": __version__,
        "Build": build_text(),
        "OS": platform.platform(),
        "Machine": platform.machine(),
        "Python": platform.python_version(),
        "Qt": qVersion(),
        "PySide6": PySide6.__version__,
        "Qt platform": QGuiApplication.platformName(),
    }
    try:
        import OCP

        rows["OCP"] = str(getattr(OCP, "__version__", "installed"))
    except ImportError:
        rows["OCP"] = "missing"
    rows.update(opengl_info())
    for n, line in enumerate(screens(), start=1):
        rows[f"Screen {n}"] = line
    if theme:
        rows["Theme"] = theme
    if log_folder is not None:
        rows["Log folder"] = scrub(str(log_folder))  # no user name in a report (D2871)
    width = max(len(key) for key in rows)
    return "\n".join(f"{key + ':':<{width + 1}} {value}" for key, value in rows.items())


def copy_system_info(theme: str = "", log_folder: Path | None = None) -> str:
    """Put the system info on the clipboard and return it."""
    info = system_info(theme, log_folder)
    QGuiApplication.clipboard().setText(info)
    return info


def open_folder(folder: Path) -> bool:
    """Open ``folder`` in the file manager, making it first. False when that failed."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
