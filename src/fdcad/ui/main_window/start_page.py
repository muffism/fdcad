"""The start page (TUTORIAL_REVIEW_SPEC_2 TR218 item 2, DECISIONS D2504).

While no part is open, the document area shows the start page: New Part and
Open buttons and the recent parts as pictures, pinned parts first. A part's
menu pins or unpins it, removes it from the list or shows its folder. Double
click or Enter opens a part. Files dropped on the window open as before (D765).
Each save keeps a small picture in the part file and a copy in a cache folder.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui.icons import icon

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

TITLE = "Start"
NAME = "FDCAD"
WHAT = "Parametric part modeler"
RECENT = "Recent Parts"
NEW_PART = "New Part"
OPEN = "Open..."
NONE_YET = "No recent parts yet. Use New Part or Open, or drop a part file here."
DROP_HINT = "Drop a part file on the window to open it."
MENU_OPEN = "Open"
MENU_PIN = "Pin"
MENU_UNPIN = "Unpin"
MENU_REMOVE = "Remove from List"
MENU_FOLDER = "Show in Folder"
PINNED_MARK = "Pinned: "
#: A part whose name another listed part has too: its folder tells them apart.
SAME_NAME = "{name} ({folder})"
MISSING = "{name} is no longer on disk. Use Remove from List, or Open to find it."
#: Picture size on the start page and in the part file (logical pixels).
PICTURE = 128
#: Size of the mark in the head.
MARK = 44
#: Item data role holding a row's file path.
PATH_ROLE = Qt.ItemDataRole.UserRole + 1


def cache_folder() -> Path:
    """Where the start page keeps copies of the part pictures."""
    from fdcad.ui.main_window.recovery import data_dir

    return data_dir() / "thumbnails"


def placeholder(size: int, ratio: float = 1.0) -> QPixmap:
    """The picture of a part that has none yet: a quiet tile in the theme's colours
    with the part icon in its middle, at the icon's own size (D1034)."""
    from PySide6.QtCore import QRect, QRectF
    from PySide6.QtGui import QColor, QPainter, QPen

    from fdcad.ui.themes import theme

    chrome = theme.chrome()
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(chrome.surface))
    painter.setPen(QPen(QColor(chrome.border), 1))
    inset = size * 0.06
    painter.drawRoundedRect(QRectF(inset, inset, size - 2 * inset, size - 2 * inset), 10, 10)
    side = round(size * 0.38)
    corner = (size - side) // 2
    icon("tree.part").paint(painter, QRect(corner, corner, side, side))
    painter.end()
    return pixmap


def entries(recent: list[str], pinned: list[str]) -> list[tuple[str, bool]]:
    """The parts to list: pinned ones first (in pin order), then the other recent ones."""
    out = [(p, True) for p in pinned]
    out += [(p, False) for p in recent if p not in pinned]
    return out


def open_folder(path: Path) -> bool:
    """Show the folder holding ``path`` in the system file browser."""
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))))


def keep_thumbnail(tab: DocumentTab, path: Path) -> bytes | None:
    """Put a picture of the 3D view in the part before it is saved (no picture without
    a 3D view, such as on the offscreen test platform: the old one stays)."""
    from fdcad.core.io.thumbnail import set_thumbnail
    from fdcad.ui.print_tools.orientation import thumbnail

    try:
        png = thumbnail(tab, PICTURE)
    except Exception:  # a picture must never stop a save
        png = None
    set_thumbnail(tab.session.document, png)
    return png


def saved(path: Path, png: bytes | None) -> None:
    """After a save: keep the picture's copy for the start page."""
    from fdcad.core.io.thumbnail import write_cache

    if png:
        write_cache(cache_folder(), path, png)


class StartPage(QWidget):
    """Recent parts with pictures, shown over the empty document area."""

    def __init__(self, window: MainWindow, parent: QWidget) -> None:
        super().__init__(parent)
        self.main = window
        self.setObjectName("start_page")
        self.setAutoFillBackground(True)
        # So the style sheet's colour for the page (the panel colour) is painted: a
        # plain widget ignores it, and the page was the window's darker grey (D2695).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        from fdcad.ui.help.paths import app_icon
        from fdcad.ui.themes.typography import Role, type_font

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(12)
        # The head (D1034): the mark and the name on the left, the two ways to
        # start on the right, New Part as the main button.
        head = QHBoxLayout()
        head.setSpacing(12)
        mark = QLabel()
        mark.setObjectName("start_mark")
        mark.setPixmap(app_icon().pixmap(QSize(MARK, MARK), self.devicePixelRatioF()))
        head.addWidget(mark)
        words = QVBoxLayout()
        words.setSpacing(0)
        name = QLabel(NAME)
        name.setObjectName("start_name")
        name.setFont(type_font(Role.DIALOG_TITLE))
        what = QLabel(WHAT)
        what.setObjectName("start_what")
        what.setEnabled(False)  # the theme's muted text colour
        words.addStretch(1)
        words.addWidget(name)
        words.addWidget(what)
        words.addStretch(1)
        head.addLayout(words)
        head.addStretch(1)
        self.new_button = QPushButton(NEW_PART)  # no icon: none reads on the accent
        self.new_button.setObjectName("start_new_part")
        self.new_button.setProperty("main", True)  # the accent fill (themes.style)
        self.open_button = QPushButton(icon("file.open"), OPEN)
        self.open_button.setObjectName("start_open")
        self.new_button.clicked.connect(lambda: window.commands.trigger("file.new"))
        self.open_button.clicked.connect(lambda: window.commands.trigger("file.open"))
        head.addWidget(self.open_button)
        head.addWidget(self.new_button)
        layout.addLayout(head)
        layout.addSpacing(8)
        title = QLabel(RECENT)
        title.setObjectName("start_title")
        title.setFont(type_font(Role.TITLE))
        layout.addWidget(title)
        self.list = QListWidget()
        self.list.setObjectName("start_recent")
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(PICTURE, PICTURE))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        # Icon mode takes drops itself; leave file drops to the window (D765).
        self.list.setDragEnabled(False)
        self.list.setAcceptDrops(False)
        self.list.viewport().setAcceptDrops(False)
        self.list.setWordWrap(True)
        self.list.setSpacing(8)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu_at)
        self.list.itemActivated.connect(self._activated)
        layout.addWidget(self.list, 1)
        # The empty state (D2695): the words sit in the middle of the place where
        # the parts will be, in a dashed outline of the list's size. Before, an
        # empty white card filled the page with a line of text under it.
        self.empty = QLabel(NONE_YET)
        self.empty.setObjectName("start_empty")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty, 1)
        self.drop_hint = QLabel(DROP_HINT)
        self.drop_hint.setEnabled(False)
        layout.addWidget(self.drop_hint)
        self._pictures: dict[str, QIcon] = {}

    def refresh(self) -> None:
        """List the recent and pinned parts again."""
        from fdcad.core.io.thumbnail import read_thumbnail

        settings = self.main.settings
        self.list.clear()
        fallback = QIcon(placeholder(PICTURE, self.devicePixelRatioF()))
        listed = entries(settings.recent_files, settings.pinned_files)
        # Parts with the same name in different folders also show their folder, so
        # two "bracket" tiles can be told apart (D1034).
        stems = [Path(path).stem.lower() for path, _pinned in listed]
        for path, pinned in listed:
            name = Path(path).stem
            if stems.count(name.lower()) > 1:
                name = SAME_NAME.format(name=name, folder=Path(path).parent.name)
            item = QListWidgetItem((PINNED_MARK if pinned else "") + name)
            item.setData(PATH_ROLE, path)
            item.setToolTip(path)
            picture = self._pictures.get(path)
            if picture is None:
                png = read_thumbnail(cache_folder(), path)
                pixmap = QPixmap()
                if png is not None and pixmap.loadFromData(png, "PNG"):
                    picture = QIcon(pixmap)
                    self._pictures[path] = picture
            item.setIcon(picture or fallback)
            self.list.addItem(item)
        none = self.list.count() == 0
        self.empty.setVisible(none)
        self.list.setVisible(not none)
        self.drop_hint.setVisible(not none)  # the empty state says it already

    def path_of(self, item: QListWidgetItem) -> str:
        """The file of a row."""
        return str(item.data(PATH_ROLE))

    def _activated(self, item: QListWidgetItem) -> None:
        self.open(self.path_of(item))

    def open(self, path: str) -> None:
        """Open a listed part, or say it is gone."""
        if not os.path.isfile(path):
            self.main.status.setText(MISSING.format(name=Path(path).name))
            return
        self.main.open_path(Path(path))

    def menu_for(self, item: QListWidgetItem) -> QMenu:
        """The menu of one part: Open, Pin or Unpin, Remove from List, Show in Folder."""
        path = self.path_of(item)
        pinned = path in self.main.settings.pinned_files
        menu = QMenu(self)
        menu.addAction(MENU_OPEN, lambda: self.open(path))
        menu.addAction(MENU_UNPIN if pinned else MENU_PIN, lambda: self.pin(path, not pinned))
        menu.addAction(MENU_REMOVE, lambda: self.remove(path))
        menu.addAction(MENU_FOLDER, lambda: open_folder(Path(path)))
        return menu

    def _menu_at(self, pos: QPoint) -> None:
        item = self.list.itemAt(pos)
        if item is not None:
            self.menu_for(item).exec(self.list.viewport().mapToGlobal(pos))

    def pin(self, path: str, on: bool) -> None:
        """Pin or unpin a part."""
        self.main.settings.set_pinned(path, on)
        self.refresh()

    def remove(self, path: str) -> None:
        """Take a part off the start page (and the recent files)."""
        settings = self.main.settings
        settings.set_pinned(path, False)
        settings.remove_recent(path)
        self._pictures.pop(path, None)
        self.refresh()


class _Follower(QObject):
    """Keeps the start page over the document area and shown only with no part open."""

    def __init__(self, page: StartPage, area: QWidget) -> None:
        super().__init__(page)
        self.page, self.area = page, area
        area.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.area and event.type() == QEvent.Type.Resize:
            self.page.setGeometry(self.area.rect())
        return False


def update(window: MainWindow) -> None:
    """Show the start page when no part is open, else hide it."""
    page: Any = getattr(window, "start_page", None)
    if page is None:
        return
    empty = window.tabs.count() == 0
    if empty:
        page.setGeometry(window.tabs.rect())
        page.refresh()
        page.show()
        page.raise_()
    else:
        page.hide()


def install(window: MainWindow) -> StartPage:
    """Create the start page over the document tabs."""
    page = StartPage(window, window.tabs)
    window.start_page = page
    _Follower(page, window.tabs)
    window.tabs.currentChanged.connect(lambda _i: update(window))
    update(window)
    return page
