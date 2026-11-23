"""FDCAD entry point."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QFileOpenEvent, QGuiApplication
from PySide6.QtWidgets import QApplication

from fdcad.ui.gui_thread import off_gui_thread

#: How long after the window is ready the first start welcome opens.
WELCOME_DELAY_MS = 700
#: Objects that live as long as the app (the instance server, the Dock menu).
_KEEP: list[object] = []


class _FileOpenFilter(QObject):
    """macOS sends double clicked part files as file open events, not arguments."""

    def __init__(self, open_path: object) -> None:
        super().__init__()
        self.open_path = open_path
        self.pending: list[Path] = []

    def eventFilter(self, _obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if off_gui_thread():
            return False  # an exit from outside: the event may be gone (IDEAS 48, D2659)
        if isinstance(event, QFileOpenEvent) and event.file():
            path = Path(event.file())
            if callable(self.open_path):
                self.open_path(path)
            else:
                self.pending.append(path)
            return True
        return False


def _close_boot_picture() -> None:
    """Close the picture the single file build shows while it unpacks (D1034). The
    app's own start picture, the same drawing, is on screen by now. ``pyi_splash``
    only exists in that build."""
    if "_PYI_SPLASH_IPC" not in os.environ:
        return  # not the single file build: importing the module would complain
    try:
        import pyi_splash

        pyi_splash.close()
    except Exception:  # the picture is a nicety: never stop the start for it
        pass


def main(argv: list[str] | None = None) -> int:
    """Start the app. Part file arguments (`.fdprt`, or an older `.fdef`) are opened."""
    started = time.perf_counter()
    args = sys.argv if argv is None else argv
    from fdcad import portable

    portable_data = portable.enable()  # D1033: before any folder or preference is read
    from fdcad.ui import safe_graphics

    marker_dir: Path | None = None
    safe, why = False, ""
    if QApplication.instance() is None:  # TR219 (D2016): decided before Qt starts
        from fdcad.ui.main_window.recovery import data_dir

        marker_dir = data_dir()
        safe, why = safe_graphics.wanted(args, marker_dir, safe_graphics.read_setting())
        if safe:
            safe_graphics.use_software()
        safe_graphics.mark_start(marker_dir)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(args)
    assert isinstance(app, QApplication)
    app.setApplicationName("FDCAD")
    app.setOrganizationName("FDCAD")
    from fdcad.ui.help.paths import app_icon

    icon = app_icon()
    app.setWindowIcon(icon)  # the app icon (D557), bolder at small sizes (D672)
    splash = None
    quiet = os.environ.get("FDCAD_BUNDLE_CHECK") or os.environ.get("FDCAD_STARTUP_REPORT")
    if not quiet and app.platformName() not in ("offscreen", "minimal"):
        from fdcad.ui.splash import show_splash

        splash = show_splash(icon)  # something on screen while the window loads (D1033)
    _close_boot_picture()

    from fdcad import applog
    from fdcad.ui.main_window.recovery import data_dir
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.preferences.settings import Settings
    from fdcad.ui.themes.theme import apply_theme

    applog.setup(data_dir() / "logs")
    applog.capture_qt_messages()  # Qt warnings go to the log (U10.2)
    from fdcad.ui.errors.handler import ErrorHandler

    errors = ErrorHandler()
    errors.install()  # one handler for uncaught errors (U10.1)
    settings = Settings()
    from fdcad.ui import system_integration as system

    checking = os.environ.get("FDCAD_BUNDLE_CHECK") or os.environ.get("FDCAD_STARTUP_REPORT")
    if not checking:
        # TR379 (D948): system recent list, Dock menu, one window. A portable copy
        # leaves no trace in the system's recent list (D1033).
        system.enable(portable_data is None)
        parts = [Path(a) for a in args[1:] if a.lower().endswith((".fdprt", ".fdef"))]
        if parts and system.hand_off(parts):
            return 0  # the FDCAD already running opens them
    from fdcad.ui.themes.theme import set_colour_safe

    set_colour_safe(settings.colour_safe)  # TR292
    settings.apply_number_style()  # TR350 (D949)
    apply_theme(app, settings.theme)
    file_filter = _FileOpenFilter(None)
    app.installEventFilter(file_filter)

    window = MainWindow(settings)
    if settings.large_controls:  # TR294 (D2017): tree rows too
        from fdcad.ui.accessibility import apply_large_controls

        apply_large_controls(window, True)
    errors.parent_widget = lambda: window
    from fdcad.ui import strings_extra
    from fdcad.ui.input.key_position import KeyPositionFilter

    keys = KeyPositionFilter(  # TR354 (D2020): shortcuts from other layouts and IMEs
        window.commands.trigger_key,
        lambda: window.status.setText(strings_extra.SHORTCUTS_PAUSED),
    )
    app.installEventFilter(keys)
    _KEEP.append(keys)
    if not checking:

        def bring_forward() -> None:
            if window.isMinimized():
                window.showNormal()
            window.raise_()
            window.activateWindow()

        server = system.InstanceServer(window.open_path, bring_forward)
        server.listen()
        dock = system.dock_menu(window.new_part, lambda: settings.recent_files, window.open_path)
        _KEEP.extend([server, dock])  # alive while the app runs
    from fdcad.ui.main_window.window_details import set_dark_title_bar
    from fdcad.ui.themes.theme import is_dark

    window.memory.restore_geometry(window)  # size and place from the last run (U9.1)
    set_dark_title_bar(window, is_dark())  # before showing, so it never flashes light (U9.5)
    if window.memory.maximized():
        window.showMaximized()
    else:
        window.show()
    if splash is not None:
        from fdcad.ui.splash import finish as finish_splash

        finish_splash(splash, window)
    visible = time.perf_counter() - started
    if marker_dir is not None:
        safe_graphics.clear_start(marker_dir)
    if safe:
        from fdcad.ui import strings_extra

        window.status.setText(strings_extra.SAFE_GRAPHICS_ON[why])

    def finish() -> None:
        # Show the window first, then load the kernel (lazy startup, PLAN 11.3).
        window.finish_setup()
        from fdcad.ui.main_window import crash_guard

        crash_guard.collect(window)  # D1035: before any part opens
        window.recover()
        file_filter.open_path = window.open_path
        from fdcad.core.io.fdef import is_part_file

        paths = [Path(a) for a in args[1:] if is_part_file(a)]
        if not paths and not file_filter.pending and settings.reopen_last:
            # TR218 (D961): the saved parts that were open last time, if still there.
            paths = [Path(p) for p in settings.last_session if Path(p).is_file()]
        for path in [*paths, *file_filter.pending]:
            window.open_path(path)
        if window.tabs.count() == 0:
            from fdcad.ui.session import DocumentSession

            blank = DocumentSession.new(settings.default_units, window)
            blank.auto_blank = True  # replaced by the first part opened, if unused (D1033)
            window.add_session(blank)
        check_path = os.environ.get("FDCAD_BUNDLE_CHECK")
        if check_path:
            # Used by the packaging smoke test; not set in normal use.
            from fdcad.ui.bundle_check import bundle_problems

            problems = bundle_problems()
            Path(check_path).write_text(json.dumps({"problems": problems}), encoding="utf-8")
            QTimer.singleShot(0, app.quit)
            return
        report_path = os.environ.get("FDCAD_STARTUP_REPORT")
        if not report_path:
            # The welcome, on the first start only (D552). A moment later, so the 3D
            # view has drawn its first frame and is not a white area behind it (D1034).
            QTimer.singleShot(WELCOME_DELAY_MS, window.help.first_run)
        if report_path:
            # Used by the startup budget test (PLAN 11.2 item 1); not set in normal use.
            from fdcad.sysinfo import private_memory, process_memory

            tab = window.current
            if tab is not None:
                tab.session.wait(30000)
            app.processEvents()
            data = {
                "visible": visible,
                "ready": time.perf_counter() - started,
                "memory": process_memory(),
                "private": private_memory(),
            }
            Path(report_path).write_text(json.dumps(data), encoding="utf-8")
            QTimer.singleShot(0, app.quit)

    QTimer.singleShot(0, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
