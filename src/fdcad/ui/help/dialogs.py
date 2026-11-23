"""Help menu windows: About, the user guide, the keyboard shortcuts list (D551, D553, D554).

Everything here reads local files only. Nothing opens a network connection
(CLAUDE.md rule 8): links to web pages in the guide are not followed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt, QUrl
from PySide6.QtGui import (
    QStandardItem,
    QStandardItemModel,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableView,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from fdcad import __version__
from fdcad.ui import strings_feedback as feedback
from fdcad.ui import strings_help as text
from fdcad.ui.help.paths import guide_dir, license_files
from fdcad.ui.input.commands import COMMANDS, ShortcutMap, key_text
from fdcad.ui.themes.typography import Role, type_font


def read_text(path: Path) -> str | None:
    """The text of a local file, or None when it is missing or unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


class AboutDialog(QDialog):
    """Version, license, third party licenses and the not affiliated sentence."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aboutDialog")
        self.setWindowTitle(text.ABOUT_TITLE)
        self.resize(640, 480)
        self.tabs = QTabWidget(self)

        about = QWidget()
        lay = QVBoxLayout(about)
        heading = QLabel(text.ABOUT_HEADING.format(version=__version__))
        heading.setObjectName("aboutHeading")
        heading.setFont(type_font(Role.DIALOG_TITLE))
        # The mark beside the name (D1034).
        from PySide6.QtCore import QSize

        from fdcad.ui.help.paths import app_icon

        head = QHBoxLayout()
        self.mark = QLabel()
        self.mark.setObjectName("aboutMark")
        # At the screen's own pixel ratio, so the mark is sharp at 150 and 200
        # percent (D2698); without it Qt gives the 100 percent picture, stretched.
        self.mark.setPixmap(app_icon().pixmap(QSize(56, 56), self.devicePixelRatioF()))
        head.addWidget(self.mark)
        head.addSpacing(8)
        head.addWidget(heading, 1)
        lay.addLayout(head)
        from fdcad.applog import log_folder
        from fdcad.ui.help.diagnostics import build_text

        self.log_folder = log_folder()
        self.build = QLabel(build_text())
        self.build.setObjectName("aboutBuild")
        lay.addWidget(self.build)
        self.labels: list[QLabel] = []
        for body in (
            text.ABOUT_SUMMARY,
            text.ABOUT_COPYRIGHT,
            text.ABOUT_LICENSE,
            text.NOT_AFFILIATED,
        ):
            label = QLabel(body)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(label)
            self.labels.append(label)
        # Opens the notices or the source offer on the Licenses tab (D2867).
        self.notices_link = QLabel(text.ABOUT_NOTICES_LINK)
        self.notices_link.setObjectName("aboutNoticesLink")
        self.notices_link.setWordWrap(True)
        self.notices_link.setTextFormat(Qt.TextFormat.RichText)
        self.notices_link.linkActivated.connect(self.open_document)
        lay.addWidget(self.notices_link)
        lay.addStretch(1)
        logs = QHBoxLayout()
        self.logs = QLabel(feedback.ABOUT_LOGS.format(path=self.log_folder))
        self.logs.setObjectName("aboutLogs")
        self.logs.setWordWrap(True)
        self.logs.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.open_logs = QPushButton(feedback.OPEN_LOG_FOLDER_BUTTON)
        self.open_logs.setObjectName("aboutOpenLogs")
        self.open_logs.clicked.connect(self._open_logs)
        logs.addWidget(self.logs, 1)
        logs.addWidget(self.open_logs)
        lay.addLayout(logs)
        self.tabs.addTab(about, text.ABOUT_TAB)

        licenses = QWidget()
        row = QHBoxLayout(licenses)
        self.documents = QListWidget()
        self.documents.addItems(list(text.LICENSE_DOCS.values()))
        self.documents.setMaximumWidth(200)
        self.viewer = QTextBrowser()
        self.viewer.setOpenLinks(False)
        row.addWidget(self.documents)
        row.addWidget(self.viewer, 1)
        self.tabs.addTab(licenses, text.LICENSES_TAB)
        self._files = license_files()
        self.documents.currentRowChanged.connect(self.show_document)
        self.documents.setCurrentRow(0)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        outer = QVBoxLayout(self)
        outer.addWidget(self.tabs)
        outer.addWidget(buttons)

    def _open_logs(self) -> None:
        from fdcad.ui.errors.message import show_error
        from fdcad.ui.help.diagnostics import open_folder

        if not open_folder(self.log_folder):
            show_error(self, feedback.LOG_FOLDER_FAILED.format(path=self.log_folder))

    def open_document(self, key: str) -> None:
        """Show the Licenses tab at the document named ``key`` of ``LICENSE_DOCS``."""
        keys = list(text.LICENSE_DOCS)
        if key in keys:
            self.tabs.setCurrentIndex(1)
            self.documents.setCurrentRow(keys.index(key))

    def show_document(self, row: int) -> None:
        """Show license text number ``row`` of ``LICENSE_DOCS``."""
        keys = list(text.LICENSE_DOCS)
        if not 0 <= row < len(keys):
            return
        path = self._files[keys[row]]
        content = read_text(path)
        if content is None:
            self.viewer.setPlainText(text.LICENSE_MISSING.format(name=path.name))
        elif path.suffix == ".md":
            self.viewer.setMarkdown(content)
        else:
            self.viewer.setPlainText(content)


class GuideBrowser(QTextBrowser):
    """A text browser that follows links between local guide pages only."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setOpenLinks(True)
        self.setOpenExternalLinks(False)
        self.blocked: str = ""

    def doSetSource(  # noqa: N802 (Qt name)
        self,
        name: QUrl | str,
        type: QTextDocument.ResourceType = QTextDocument.ResourceType.UnknownResource,
    ) -> None:
        """Follow a link when it names a local file; show the address of a web page."""
        name = QUrl(name) if isinstance(name, str) else name
        if name.scheme() not in ("", "file"):
            self.blocked = name.toString()
            self.setToolTip(text.GUIDE_EXTERNAL.format(url=self.blocked))
            return
        super().doSetSource(name, type)
        self._name_headings()
        if name.hasFragment():
            self.scrollToAnchor(name.fragment())

    def _name_headings(self) -> None:
        """Give each heading the anchor a "page.md#heading" link uses (bug hunt F12).

        Qt's Markdown reader names no headings, so such links opened the top of the
        page. The name is the heading text in lower case, with punctuation left out
        and spaces as hyphens, as the guide's links are written.
        """
        block = self.document().begin()
        while block.isValid():
            if block.blockFormat().headingLevel() > 0:
                words = re.sub(r"[^\w\- ]", "", block.text().strip().lower())
                cursor = QTextCursor(block)
                cursor.movePosition(
                    QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
                )
                mark = QTextCharFormat()
                mark.setAnchor(True)
                mark.setAnchorNames([words.replace(" ", "-")])
                cursor.mergeCharFormat(mark)
            block = block.next()


class GuideWindow(QDialog):
    """The user guide, read from the local ``docs/user_guide`` folder (D551)."""

    def __init__(self, parent: QWidget | None = None, folder: Path | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("guideWindow")
        self.setWindowTitle(text.GUIDE_TITLE)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(820, 680)
        self.folder = folder or guide_dir()
        self.browser = GuideBrowser(self)
        bar = QHBoxLayout()
        self.back = QPushButton(text.GUIDE_BACK)
        self.forward = QPushButton(text.GUIDE_FORWARD)
        self.home_button = QPushButton(text.GUIDE_HOME)
        for button in (self.back, self.forward, self.home_button):
            bar.addWidget(button)
        bar.addStretch(1)
        self.back.clicked.connect(self.browser.backward)
        self.forward.clicked.connect(self.browser.forward)
        self.home_button.clicked.connect(self.home)
        self.browser.backwardAvailable.connect(self.back.setEnabled)
        self.browser.forwardAvailable.connect(self.forward.setEnabled)
        self.back.setEnabled(False)
        self.forward.setEnabled(False)
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.browser, 1)
        self.home()

    @property
    def index(self) -> Path:
        """The guide's contents page."""
        return self.folder / "README.md"

    def home(self) -> None:
        """Show the contents page, or say the guide is missing."""
        if self.index.is_file():
            self.browser.setSource(QUrl.fromLocalFile(str(self.index)))
        else:
            self.browser.setPlainText(text.GUIDE_MISSING)

    def show_topic(self, page: Path, heading: str) -> bool:
        """Show ``page`` scrolled to ``heading`` (TR380). False when it is not found."""
        self.browser.setSource(QUrl.fromLocalFile(str(page)))
        self.browser.moveCursor(QTextCursor.MoveOperation.Start)
        found = self.browser.find(heading)
        if found:
            # Put the heading at the top of the window rather than at the bottom.
            self.browser.moveCursor(QTextCursor.MoveOperation.End)
            self.browser.find(heading, QTextDocument.FindFlag.FindBackward)
        return found

    def page(self) -> Path | None:
        """The local page shown now."""
        source = self.browser.source()
        return Path(source.toLocalFile()) if source.isLocalFile() else None


def shortcut_rows(shortcuts: ShortcutMap) -> list[tuple[str, str, str]]:
    """(command, group, keys) for every command, with the user's current keys."""
    rows = []
    for command in COMMANDS:
        keys = ", ".join(key_text(k) for k in shortcuts.keys(command.id))
        rows.append((command.label, command.group, keys))
    return rows


class ShortcutsDialog(QDialog):
    """Every command and its current keys, with a filter (D554)."""

    def __init__(
        self,
        shortcuts: ShortcutMap,
        parent: QWidget | None = None,
        edit: object = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("shortcutsDialog")
        self.setWindowTitle(text.SHORTCUTS_TITLE)
        self.resize(620, 640)
        self.model = QStandardItemModel(0, 3, self)
        self.model.setHorizontalHeaderLabels(list(text.SHORTCUTS_COLUMNS))
        for row in shortcut_rows(shortcuts):
            items = [QStandardItem(value) for value in row]
            for item in items:
                item.setEditable(False)
            self.model.appendRow(items)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(text.SHORTCUTS_FILTER)
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.proxy.setFilterFixedString)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        note = text.SHORTCUTS_NOTE
        if sys.platform == "darwin":
            note = f"{note} {text.SHORTCUTS_MAC_NOTE}"
        label = QLabel(note)
        label.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        if callable(edit):
            change = buttons.addButton(text.SHORTCUTS_EDIT, QDialogButtonBox.ButtonRole.ActionRole)
            change_keys = edit

            def go() -> None:
                self.accept()
                change_keys()

            change.clicked.connect(go)
        lay = QVBoxLayout(self)
        lay.addWidget(self.filter)
        lay.addWidget(self.table, 1)
        lay.addWidget(label)
        lay.addWidget(buttons)

    def visible_rows(self) -> int:
        """Rows that pass the filter."""
        return self.proxy.rowCount()
