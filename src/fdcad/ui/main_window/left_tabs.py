"""The left panel's tabs: one icon each, with the name as tooltip (D436).

Five named tabs did not fit the panel width and were cut off ("Prope...").
An icon per tab always fits; hovering shows the name. The Errors tab shows
its count beside the icon when there are errors; its warning mark is drawn
in the warning colour only then, and plain otherwise (U8.3, D673).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QTabWidget, QWidget

from fdcad.ui import icons, strings, strings_config

#: Tab name to icon name.
ICONS = {
    strings.TAB_TREE: "tree.part",
    strings.TAB_PROPERTIES: "field.value",
    strings.TAB_VARIABLES: "tools.equations",
    strings.TAB_ERRORS: "tree.warning_mark",
    strings_config.TAB_CONFIGURATIONS: "tools.configurations",
}
#: Tabs whose icon is a status mark: plain until there is something to report.
STATUS_TABS = {strings.TAB_ERRORS}


class LeftTabs(QTabWidget):
    """Tab widget whose known tabs show an icon instead of their name."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("left_tabs")
        self.setDocumentMode(True)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.TextElideMode.ElideNone)
        size = max(18, self.fontMetrics().height() + 4)
        self.setIconSize(QSize(size, size))

    def tabInserted(self, index: int) -> None:  # noqa: N802  (Qt override)
        """Swap a known tab's name for its icon and keep the name as the tooltip."""
        super().tabInserted(index)
        name = super().tabText(index)
        if name in ICONS:
            self.setTabIcon(index, icons.icon(ICONS[name], plain=name in STATUS_TABS))
            self.setTabToolTip(index, name)
            super().setTabText(index, "")

    def name(self, index: int) -> str:
        """The tab's name (its tooltip for icon tabs)."""
        return self.tabToolTip(index) or super().tabText(index)

    def set_count(self, widget: QWidget, name: str, count: int) -> None:
        """Show ``count`` beside a tab's icon (none for 0) and in its tooltip."""
        index = self.indexOf(widget)
        if index < 0:
            return
        super().setTabText(index, str(count) if count else "")
        self.setTabToolTip(index, strings.TAB_ERRORS_COUNT.format(count=count) if count else name)
        if name in ICONS:
            self.setTabIcon(index, icons.icon(ICONS[name], plain=not count))

    def refresh_icons(self) -> None:
        """Draw the icons again, for example after a theme change."""
        for i in range(self.count()):
            name = self.tabToolTip(i)
            key = next((k for k in ICONS if name == k or name.startswith(k + " (")), None)
            if key is not None:
                quiet = key in STATUS_TABS and not super().tabText(i)
                self.setTabIcon(i, icons.icon(ICONS[key], plain=quiet))
