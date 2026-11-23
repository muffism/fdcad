"""The Help menu and the first run welcome (D551 to D554).

``HelpMenu`` fills the Help menu: Welcome, Open User Guide, Keyboard Shortcuts,
Diagnostics (Copy System Info, Report a Problem, Open Log Folder; U10.3, D2871)
and About FDCAD. The
user guide and the welcome are not modal, so the user can keep working with
them open; About and the shortcuts list are modal.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from fdcad.ui import strings_feedback as feedback
from fdcad.ui import strings_help as text

if TYPE_CHECKING:
    from fdcad.ui.help.dialogs import GuideWindow
    from fdcad.ui.help.lessons import LessonPanel
    from fdcad.ui.help.welcome import WelcomeDialog
    from fdcad.ui.main_window.window import MainWindow


class HelpMenu:
    """The Help menu's commands for one main window."""

    def __init__(self, window: MainWindow, menu: QMenu) -> None:
        self.window = window
        self.guide: GuideWindow | None = None
        self.welcome: WelcomeDialog | None = None
        self.lessons: LessonPanel | None = None
        self.actions: dict[str, QAction] = {}
        from fdcad.ui.help.lessons import MENU as LESSONS_MENU

        for key, label, slot in (
            ("welcome", text.WELCOME, self.show_welcome),
            ("lessons", LESSONS_MENU, self.show_lessons),  # TR291 item 2 (D2505)
            ("guide", text.USER_GUIDE, self.open_guide),
            ("shortcuts", text.SHORTCUTS, self.show_shortcuts),
            ("whats_new", text.WHATS_NEW, self.show_whats_new),  # TR291 item 3 (D2018)
            ("about", text.ABOUT, self.show_about),
        ):
            if key == "about":
                menu.addSeparator()
            action = QAction(label, window)
            action.setObjectName(f"help.{key}")
            action.triggered.connect(lambda _checked=False, s=slot: s())
            menu.addAction(action)
            self.actions[key] = action
        self.actions["about"].setMenuRole(QAction.MenuRole.AboutRole)
        # Help for This Tool (TR380 item 2, D1002), a command so it can take a key.
        tool_help = window.commands.add("help.tool", self.help_for_tool)
        menu.insertAction(self.actions["shortcuts"], tool_help)
        self.diagnostic_actions: dict[str, QAction] = {}
        diagnostics = QMenu(feedback.DIAGNOSTICS, menu)
        diagnostics.setObjectName("help.diagnostics")
        menu.insertMenu(self.actions["about"], diagnostics)
        tools: tuple[tuple[str, str, Callable[[], object]], ...] = (
            ("system_info", feedback.COPY_SYSTEM_INFO, self.copy_system_info),
            ("report", feedback.REPORT_A_PROBLEM, self.report_problem),  # D2871
            ("log_folder", feedback.OPEN_LOG_FOLDER, self.open_log_folder),
        )
        for key, label, tool in tools:
            action = QAction(label, window)
            action.setObjectName(f"help.{key}")
            action.triggered.connect(lambda _checked=False, s=tool: s())
            diagnostics.addAction(action)
            self.diagnostic_actions[key] = action
        self.diagnostics = diagnostics

    def copy_system_info(self) -> str:
        """Copy version, OS, Qt, OpenGL, GPU, scaling and theme for a bug report."""
        from fdcad.applog import log_folder
        from fdcad.ui.help.diagnostics import copy_system_info
        from fdcad.ui.themes.theme import current

        chosen = self.window.settings.theme.value
        theme = f"{chosen} (showing {current().value})"
        info = copy_system_info(theme, log_folder())
        self.window.feedback.flash(feedback.SYSTEM_INFO_COPIED)
        return info

    def report_problem(self) -> bool:
        """Save a problem report and open the mail app with it (D2871). FDCAD sends
        nothing: the user checks the message and presses Send."""
        from fdcad.ui.help.report import send_report

        opened = send_report(self.window, summary=feedback.REPORT_FROM_HELP)
        if opened:
            self.window.feedback.flash(feedback.REPORT_READY)
        return opened

    def open_log_folder(self) -> bool:
        """Open the folder with ``fdcad.log`` in the file manager."""
        from fdcad.applog import log_folder
        from fdcad.ui.errors.message import show_error
        from fdcad.ui.help.diagnostics import open_folder

        folder = log_folder()
        if open_folder(folder):
            return True
        show_error(self.window, feedback.LOG_FOLDER_FAILED.format(path=folder))
        return False

    def show_about(self) -> None:
        """The About box: version, license, third party licenses."""
        from fdcad.ui.help.dialogs import AboutDialog

        dialog = AboutDialog(self.window)
        dialog.exec()
        dialog.deleteLater()  # closed dialogs stayed alive (D637)

    def open_guide(self) -> GuideWindow:
        """Show the local user guide (reuses the open guide window)."""
        from fdcad.ui.help.dialogs import GuideWindow

        if self.guide is None:
            self.guide = GuideWindow(self.window)
        self.guide.show()
        self.guide.raise_()
        self.guide.activateWindow()
        return self.guide

    def tool_labels(self) -> list[str]:
        """Names to look up, most specific first: the open panel's feature, the sketch
        tool in use, then the last command run."""
        from fdcad.ui.input.commands import BY_ID

        out: list[str] = []
        panel = getattr(self.window, "panel", None)
        feature = getattr(panel, "feature", None) if panel is not None else None
        if feature is not None and panel is not None and panel.isVisible():
            command = BY_ID.get(f"feature.{feature.type}")
            out.append(command.label if command is not None else feature.type.replace("_", " "))
        sketch = getattr(self.window, "sketch_mode", None)
        canvas = getattr(sketch, "canvas", None)
        tool = getattr(canvas, "tool", None)
        if tool is not None and getattr(tool, "label", None):
            out.append(str(tool.label))
        last = self.window.commands.last
        if last is not None and last in BY_ID:
            out.append(BY_ID[last].label)
        return [label.replace("&", "") for label in out]

    def help_for_tool(self) -> GuideWindow:
        """Open the guide at the section for the tool in use, or at its contents."""
        from fdcad.ui.help.topics import find_topic

        guide = self.open_guide()
        found = find_topic(guide.folder, self.tool_labels())
        if found is not None:
            guide.show_topic(*found)
        else:
            guide.home()
        return guide

    def show_lessons(self) -> LessonPanel:
        """Open the lessons window (TR291 item 2, D2505); it keeps its place."""
        from fdcad.ui.help.lessons import LessonPanel

        if self.lessons is None:
            self.lessons = LessonPanel(self.window)
        self.lessons.open()
        return self.lessons

    def show_whats_new(self) -> object:
        """What's New: the newest changes, read from the change log (TR291, D2018)."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

        from fdcad.ui.help.paths import changelog_path

        dialog = QDialog(self.window)
        dialog.setObjectName("whats_new")
        dialog.setWindowTitle(text.WHATS_NEW_TITLE)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setObjectName("whats_new_text")
        browser.setMarkdown(newest_changes(changelog_path()) or text.WHATS_NEW_MISSING)
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(640, 520)
        dialog.exec()
        dialog.deleteLater()
        return dialog

    def show_shortcuts(self) -> None:
        """The list of every command and its current keys."""
        from fdcad.ui.help.dialogs import ShortcutsDialog

        dialog = ShortcutsDialog(
            self.window.commands.shortcuts, self.window, edit=self.window.preferences
        )
        dialog.exec()
        dialog.deleteLater()

    def show_welcome(self) -> WelcomeDialog:
        """Show the welcome (Help, Welcome, or the first start)."""
        from fdcad.ui.help.welcome import WelcomeDialog

        if self.welcome is None:
            self.welcome = WelcomeDialog(
                self.window.settings, self.window, self.open_guide, self.show_lessons
            )
        self.welcome.show()
        self.welcome.raise_()
        return self.welcome

    def first_run(self) -> WelcomeDialog | None:
        """Show the welcome if it was never closed before; called once at start."""
        if self.window.settings.welcome_seen:
            return None
        return self.show_welcome()


def newest_changes(path: Path, sections: int = 2) -> str:
    """The first ``sections`` version sections of the change log as Markdown, or ""."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    out: list[str] = []
    seen = 0
    for line in lines:
        if line.startswith("## "):
            seen += 1
            if seen > sections:
                break
        if seen:
            out.append(line)
    return "\n".join(out).strip()
