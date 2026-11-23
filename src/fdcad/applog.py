"""Local log file (PLAN Phase 1). Nothing is ever sent anywhere (CLAUDE.md rule 9).

``setup`` starts the log file and logs uncaught errors until the UI installs its
own handler (``fdcad.ui.errors.handler``). ``capture_qt_messages`` sends Qt's
warnings (bad style sheets, missing icons and the like) to the log too (U10.2).
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import IO

from fdcad import __version__

log = logging.getLogger("fdcad")
qt_log = logging.getLogger("fdcad.qt")


def setup(folder: Path) -> Path | None:
    """Log to ``folder/fdcad.log`` (1 MB, three old files kept) and log uncaught errors."""
    path = folder / "fdcad.log"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.info("FDCAD %s started", __version__)

    def hook(kind: type[BaseException], value: BaseException, tb: TracebackType | None) -> None:
        log.critical("Uncaught error", exc_info=(kind, value, tb))
        sys.__excepthook__(kind, value, tb)

    sys.excepthook = hook
    _watch_native_faults(folder)
    return path


#: The file native fault reports go to; kept open for as long as FDCAD runs.
_fault_file: IO[str] | None = None


def _watch_native_faults(folder: Path) -> None:
    """Write what every thread was doing to ``crash.log`` when the kernel faults
    (D1035). Without it a native crash leaves nothing to send with a bug report."""
    global _fault_file
    import faulthandler

    try:
        _fault_file = open(folder / "crash.log", "a", encoding="utf-8")  # noqa: SIM115
        _fault_file.write(f"\n--- FDCAD {__version__} started ---\n")
        _fault_file.flush()
        faulthandler.enable(file=_fault_file, all_threads=True)
    except (OSError, ValueError, RuntimeError):
        _fault_file = None


def log_folder() -> Path:
    """The folder that holds ``fdcad.log``: the first file handler's folder, or the default."""
    for handler in log.handlers:
        if isinstance(handler, RotatingFileHandler):
            return Path(handler.baseFilename).parent
    from fdcad.ui.main_window.recovery import data_dir

    return data_dir() / "logs"


def qt_message(mode: object, context: object, message: str) -> None:
    """A Qt message handler: write Qt's debug, info, warning and error messages to the log."""
    from PySide6.QtCore import QtMsgType

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    where = getattr(context, "category", "") or "qt"
    qt_log.log(levels.get(mode, logging.WARNING), "%s: %s", where, message)  # type: ignore[call-overload]


def capture_qt_messages() -> None:
    """Send every Qt message to the log from now on (U10.2)."""
    from PySide6.QtCore import qInstallMessageHandler

    qInstallMessageHandler(qt_message)
