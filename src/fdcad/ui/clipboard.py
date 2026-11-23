"""Put FDCAD's own data on the clipboard so the process can exit cleanly (D2617).

On the offscreen and minimal platforms (the UI tests, CI) Qt keeps the clipboard's
data in a store of its own that is freed after Python has shut down. Data made in
Python carries a Python wrapper, and freeing it then ended the process with an
access violation after every test had passed (exit code 139, IDEAS 71). Clearing
the clipboard before Python shuts down frees it while Python is still there.

The real platforms hand the data to the system clipboard when the app closes, so
they keep it: a feature copied before quitting can still be pasted later.
"""

from __future__ import annotations

import atexit

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication

#: Platforms whose clipboard lives only in the process.
IN_PROCESS = frozenset({"offscreen", "minimal"})

_hooked = False


def put(mime: QMimeData) -> None:
    """Put ``mime`` on the clipboard."""
    global _hooked
    QGuiApplication.clipboard().setMimeData(mime)
    if not _hooked:
        _hooked = True
        atexit.register(release)


def release() -> None:
    """Clear an in process clipboard while Python can still free its data."""
    app = QGuiApplication.instance()
    if isinstance(app, QGuiApplication) and QGuiApplication.platformName() in IN_PROCESS:
        QGuiApplication.clipboard().clear()
