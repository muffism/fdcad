"""Messages, status feedback, window details and diagnostics (UI_POLISH_SPEC U8, U9, U10)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QEvent, QRect, QSettings
from PySide6.QtGui import QDesktopServices, QGuiApplication, QUndoCommand
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from fdcad import applog
from fdcad.ui import strings
from fdcad.ui import strings_feedback as text
from fdcad.ui.errors import message as message_module
from fdcad.ui.errors.handler import ErrorHandler
from fdcad.ui.errors.message import ErrorMessage, details_text
from fdcad.ui.help import diagnostics
from fdcad.ui.main_window import dev_overlay, feedback, window_details
from fdcad.ui.main_window.window import MainWindow
from tests.core.features.test_features import plate
from tests.ui.test_workflow import _folders, new_part, window  # noqa: F401

# Error messages (U8.2) ------------------------------------------------------------------


def test_error_message_hides_the_details_and_copies_them(qtbot: QtBot) -> None:
    try:
        raise ValueError("bad thing")
    except ValueError as exc:
        details = details_text(exc, "Opening part.fdprt")
    box = ErrorMessage("Could not open part.fdprt: it is damaged. Open a backup.", details)
    qtbot.addWidget(box)
    assert "Traceback" not in box.text() and "ValueError" not in box.text()
    assert box.defaultButton() is box.ok and box.escapeButton() is box.ok
    assert box.detailedText() == details and "ValueError: bad thing" in details
    assert "Opening part.fdprt" in details and "FDCAD" in details
    box.show()
    assert box.copy_button is not None
    box.copy_button.click()
    assert QGuiApplication.clipboard().text() == details
    assert box.isVisible()  # copying does not close the box
    assert box.copy_button.text() == text.COPIED


def test_error_message_without_details_has_no_copy_button(qtbot: QtBot) -> None:
    box = ErrorMessage("Something failed. Try again.")
    qtbot.addWidget(box)
    assert box.copy_button is None and box.detailedText() == ""


@pytest.fixture
def shown(monkeypatch: pytest.MonkeyPatch) -> list[ErrorMessage]:
    """Error boxes that would have been shown, without waiting for a click."""
    boxes: list[ErrorMessage] = []

    def fake_exec(self: ErrorMessage) -> int:
        boxes.append(self)
        return 0

    monkeypatch.setattr(message_module.ErrorMessage, "exec", fake_exec)
    return boxes


def test_a_damaged_file_names_the_file_and_keeps_the_trace_behind_details(
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
    shown: list[ErrorMessage],
) -> None:
    bad = tmp_path / "broken.fdprt"
    bad.write_text("{ not json", encoding="utf-8")
    window.open_path(bad)
    assert len(shown) == 1
    box = shown[0]
    assert "broken.fdprt" in box.text() and "Traceback" not in box.text()
    assert str(bad) in box.details and "Traceback" in box.details


def test_a_failed_save_shows_the_message_with_details(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
    shown: list[ErrorMessage],
) -> None:
    tab = new_part(qtbot, window)
    folder = tmp_path / "folder_not_file.fdprt"
    folder.mkdir()
    assert window._save_to(tab, folder) is False
    assert len(shown) == 1 and "folder_not_file.fdprt" in shown[0].text()
    assert "Saving" in shown[0].details


# Status feedback (U8.1, U8.4) ------------------------------------------------------------


def test_save_confirms_in_the_status_bar_and_clears_the_mark(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    doc, _ext = plate()
    from fdcad.ui.session import DocumentSession

    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    session.undo.push(QUndoCommand("Change"))
    assert window.isWindowModified() and "[*]" in window.windowTitle()
    target = tmp_path / "bracket.fdprt"
    assert window._save_to(tab, target)
    assert window.status.text() == text.SAVED.format(name="bracket.fdprt")
    assert window.windowTitle() == "bracket.fdprt[*] \N{MIDDLE DOT} FDCAD"
    assert not window.isWindowModified()


def test_progress_waits_300_ms_and_offers_cancel(qtbot: QtBot) -> None:
    host = _StatusHost()
    qtbot.addWidget(host)
    host.show()
    stopped: list[bool] = []
    fb = feedback.StatusFeedback(host)  # type: ignore[arg-type]
    host.statusBar().addPermanentWidget(fb.cancel_button)
    fb.begin("rebuild", lambda: stopped.append(True))
    assert not host.progress.isVisible()  # quick work never flickers
    qtbot.waitUntil(host.progress.isVisible, timeout=2000)
    assert fb.cancel_button.isVisible()
    fb.cancel_button.click()
    assert stopped == [True]
    fb.end("rebuild")
    assert not host.progress.isVisible() and not fb.cancel_button.isVisible()


def test_quick_work_shows_no_progress(qtbot: QtBot) -> None:
    host = _StatusHost()
    qtbot.addWidget(host)
    host.show()
    fb = feedback.StatusFeedback(host)  # type: ignore[arg-type]
    fb.begin("export")
    fb.end("export")
    qtbot.wait(feedback.DELAY_MS + 100)
    assert not host.progress.isVisible()


def test_confirmations_fade_back_to_ready(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feedback, "FLASH_MS", 50)
    host = _StatusHost()
    qtbot.addWidget(host)
    fb = feedback.StatusFeedback(host)  # type: ignore[arg-type]
    fb.flash("Exported part.step")
    assert host.status.text() == "Exported part.step"
    qtbot.waitUntil(lambda: host.status.text() == strings.READY, timeout=1000)
    fb.flash("Saved part.fdprt")
    host.status.setText("Rebuilt in 0.10 s")  # something newer stays
    qtbot.wait(150)
    assert host.status.text() == "Rebuilt in 0.10 s"


class _StatusHost(QMainWindow):
    """Just the status bar parts StatusFeedback uses."""

    def __init__(self) -> None:
        super().__init__()
        from PySide6.QtWidgets import QLabel, QProgressBar

        self.status = QLabel(strings.READY)
        self.progress = QProgressBar()
        self.progress.hide()
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(self.progress)


# Empty states and safe defaults (U8.3, U8.5) ---------------------------------------------


def test_empty_recent_files_say_so(window: MainWindow) -> None:  # noqa: F811
    window.settings.clear_recent()
    window._fill_recent()
    labels = [a.text() for a in window.recent_menu.actions()]
    assert text.NO_RECENT in labels
    empty = next(a for a in window.recent_menu.actions() if a.text() == text.NO_RECENT)
    assert not empty.isEnabled()


def test_empty_tree_says_what_to_do_first(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    hint = window.empty_tree_hint
    new_part(qtbot, window)
    qtbot.waitUntil(hint.isVisible, timeout=2000)
    assert "sketch" in hint.text().lower() and hint.is_empty()
    doc, _ext = plate()
    from fdcad.ui.session import DocumentSession

    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    qtbot.waitUntil(lambda: not hint.isVisible(), timeout=2000)


def test_closing_unsaved_defaults_to_save_and_names_the_loss(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = new_part(qtbot, window)
    tab.session.undo.push(QUndoCommand("Change"))
    asked: list[tuple[Any, ...]] = []

    def question(*args: Any) -> QMessageBox.StandardButton:
        asked.append(args)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", question)
    assert window.close_tab(window.tabs.indexOf(tab)) is False
    assert "lost" in asked[0][2]
    assert asked[0][4] == QMessageBox.StandardButton.Save


# Window details (U9) -----------------------------------------------------------------------


def test_window_title_names_the_file_and_fdcad() -> None:
    assert window_details.window_title(None) == "FDCAD"

    class Fake:
        path = Path("/parts/bracket.fdprt")
        title = "bracket*"
        is_dirty = True

    assert window_details.window_title(Fake()) == "bracket.fdprt[*] \N{MIDDLE DOT} FDCAD"  # type: ignore[arg-type]
    Fake.path = None  # type: ignore[assignment]
    Fake.title = "Untitled*"
    assert window_details.window_title(Fake()).startswith("Untitled[*]")  # type: ignore[arg-type]


def test_window_remembers_size_place_and_panels(qtbot: QtBot, tmp_path: Path) -> None:
    store = QSettings(str(tmp_path / "w.ini"), QSettings.Format.IniFormat)
    memory = window_details.WindowMemory(store)
    first = QMainWindow()
    qtbot.addWidget(first)
    assert memory.restore_geometry(first) is False  # first start
    screen = QGuiApplication.primaryScreen().availableGeometry()
    first.setGeometry(screen.left() + 40, screen.top() + 60, 700, 500)
    first.show()
    memory.save(first)
    second = QMainWindow()
    qtbot.addWidget(second)
    assert memory.restore_geometry(second)
    assert second.geometry().size() == first.geometry().size()
    assert memory.restore_state(second)
    assert memory.maximized() is False


def test_window_on_a_missing_monitor_opens_on_a_visible_screen() -> None:
    screen = QGuiApplication.primaryScreen().availableGeometry()
    gone = QRect(screen.right() + 5000, screen.top(), 800, 600)
    moved = window_details.visible_rect(gone)
    assert screen.contains(moved.topLeft()) and moved.size() == gone.size()
    huge = QRect(screen.right() + 5000, 0, screen.width() * 3, screen.height() * 3)
    assert screen.contains(window_details.visible_rect(huge))
    seen = QRect(screen.left() + 10, screen.top() + 10, 400, 300)
    assert window_details.visible_rect(seen) == seen


def test_dark_title_bar_asks_windows(qtbot: QtBot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)
    calls: list[tuple[int, int]] = []

    class Dwm:
        def __init__(self, ok: set[int]) -> None:
            self.ok = ok

        def DwmSetWindowAttribute(self, hwnd: int, attribute: int, value: Any, size: int) -> int:  # noqa: N802
            calls.append((attribute, value._obj.value))
            return 0 if attribute in self.ok else -1

    assert window_details.set_dark_title_bar(widget, True, Dwm({20}))
    assert calls == [(20, 1)]
    calls.clear()
    assert window_details.set_dark_title_bar(widget, False, Dwm({19}))  # older Windows 10
    assert calls == [(20, 0), (19, 0)]
    assert not window_details.set_dark_title_bar(widget, True, Dwm(set()))
    import sys

    if sys.platform != "win32":
        assert window_details.set_dark_title_bar(widget, True) is False


def test_about_shows_build_and_log_folder(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fdcad.ui.help.dialogs import AboutDialog

    monkeypatch.setattr(applog, "log_folder", lambda: tmp_path / "logs")
    opened: list[str] = []
    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        staticmethod(lambda url: opened.append(url.toLocalFile()) or True),
    )
    about = AboutDialog()
    qtbot.addWidget(about)
    assert about.build.text() in (text.ABOUT_BUILD_SOURCE,) or about.build.text().startswith(
        "Built"
    )
    assert str(tmp_path / "logs") in about.logs.text()
    about.open_logs.click()
    assert [Path(p) for p in opened] == [tmp_path / "logs"] and (tmp_path / "logs").is_dir()


def test_build_date_from_the_app_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import os
    import sys

    assert diagnostics.build_date() is None  # from source
    exe = tmp_path / "FDCAD.exe"
    exe.write_bytes(b"")
    os.utime(exe, (1_793_000_000, 1_793_000_000))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert diagnostics.build_date() == "2026-10-26"
    assert diagnostics.build_text() == "Built 2026-10-26"


# Debugging (U10) ---------------------------------------------------------------------------


def test_uncaught_errors_are_logged_and_shown_once(
    qtbot: QtBot, caplog: pytest.LogCaptureFixture
) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    handler = ErrorHandler(lambda: parent)
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        error = exc
    with caplog.at_level(logging.CRITICAL, logger="fdcad"):
        handler.handle(RuntimeError, error, error.__traceback__)
    assert "Uncaught error" in caplog.text and "boom" in caplog.text
    box = handler.box
    assert box is not None and box.isVisible()
    assert box.text() == text.UNEXPECTED and "boom" not in box.text()
    assert "RuntimeError: boom" in box.details
    handler.handle(RuntimeError, error, error.__traceback__)  # while the box is open
    assert handler.suppressed == 1 and handler.count == 2
    box.close()
    qtbot.waitUntil(lambda: handler.box is None, timeout=2000)
    assert QApplication.instance() is not None  # the app keeps running


def test_worker_thread_errors_are_shown_on_the_ui_thread(qtbot: QtBot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    handler = ErrorHandler(lambda: parent)

    def work() -> None:
        try:
            raise OSError("disk gone")
        except OSError as exc:
            handler.handle(OSError, exc, exc.__traceback__)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: handler.box is not None, timeout=2000)
    assert handler.box is not None and handler.box.text() == text.UNEXPECTED_THREAD
    handler.box.close()


def test_install_makes_it_the_one_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    handler = ErrorHandler()
    handler.install()
    assert sys.excepthook == handler.handle
    assert threading.excepthook == handler.handle_thread


def test_qt_warnings_go_to_the_log(caplog: pytest.LogCaptureFixture) -> None:
    from PySide6.QtCore import QtMsgType

    with caplog.at_level(logging.WARNING, logger="fdcad.qt"):
        applog.qt_message(QtMsgType.QtWarningMsg, None, "QPixmap: bad thing")
        applog.qt_message(QtMsgType.QtDebugMsg, None, "chatter")
    assert "QPixmap: bad thing" in caplog.text and "chatter" not in caplog.text


def test_building_the_window_and_opening_panels_raises_no_qt_warning(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    qtlog: Any,
) -> None:
    """U10.2: any Qt warning while building the window and opening each panel fails."""
    from fdcad.ui.help.dialogs import AboutDialog, ShortcutsDialog
    from fdcad.ui.preferences.dialog import PreferencesDialog

    new_part(qtbot, window)
    assert window.left is not None
    for index in range(window.left.count()):
        window.left.setCurrentIndex(index)
        qtbot.wait(10)
    for dialog in (
        PreferencesDialog(window.settings, window),
        AboutDialog(window),
        ShortcutsDialog(window.commands.shortcuts, window),
    ):
        dialog.show()
        qtbot.wait(10)
        dialog.close()
    window.help.show_welcome().close()
    window.help.open_guide().close()
    bad = [
        r.message
        for r in qtlog.records
        if r.type.name in ("QtWarningMsg", "QtCriticalMsg", "QtFatalMsg")
        # The offscreen test platform cannot do some window manager calls; not an app problem.
        and not r.message.startswith("This plugin does not support")
    ]
    assert bad == []


def test_system_info_for_bug_reports(qtbot: QtBot, tmp_path: Path) -> None:
    info = diagnostics.copy_system_info("light (showing light)", tmp_path)
    for key in (
        "FDCAD:",
        "OS:",
        "Qt:",
        "PySide6:",
        "OpenGL:",
        "Screen 1:",
        "Theme:",
        "Log folder:",
    ):
        assert key in info, key
    assert " %" in info  # display scaling
    assert QGuiApplication.clipboard().text() == info


def test_help_diagnostics_menu(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    help_menu = window.help
    assert help_menu.diagnostics.title() == text.DIAGNOSTICS
    names = [a.objectName() for a in help_menu.diagnostics.actions()]
    assert names == ["help.system_info", "help.report", "help.log_folder"]
    info = help_menu.copy_system_info()
    assert "FDCAD:" in info and window.status.text() == text.SYSTEM_INFO_COPIED
    monkeypatch.setattr(diagnostics, "open_folder", lambda _folder: True)
    assert help_menu.open_log_folder()


def test_developer_overlay_is_off_until_chosen(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from fdcad.ui.preferences.dialog import PreferencesDialog

    tab = new_part(qtbot, window)
    overlays = window.dev_overlays
    assert overlays.overlays and not overlays.overlays[-1].isVisible()
    dialog = PreferencesDialog(window.settings, window)
    qtbot.addWidget(dialog)
    assert not dialog.overlay_box.isChecked()
    dialog.overlay_box.setChecked(True)
    dialog.accept()
    assert dev_overlay.overlay_enabled(window.settings.store)
    overlays.refresh()
    overlay = overlays.overlays[-1]
    assert overlay.isVisible() and overlay.parentWidget() is tab
    overlay.set_rebuild(0.25)
    assert "0.25 s" in overlay.text()


def test_overlay_times_paint_events(qtbot: QtBot) -> None:
    from PySide6.QtGui import QPaintEvent
    from PySide6.QtWidgets import QLabel

    host = QWidget()
    qtbot.addWidget(host)
    view = QLabel("view", host)
    host.resize(300, 200)
    view.resize(300, 200)
    overlay = dev_overlay.DevOverlay(host, view)
    overlay.set_shown(True)
    host.show()
    assert overlay.frame_ms is None or overlay.frame_ms >= 0
    overlay.eventFilter(view, QPaintEvent(view.rect()))
    assert overlay.frame_ms is not None and overlay.frame_ms >= 0
    overlay.refresh()
    assert "ms" in overlay.text()
    assert overlay.eventFilter(view, QEvent(QEvent.Type.Resize)) is False
