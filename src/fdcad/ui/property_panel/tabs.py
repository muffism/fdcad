"""Tabs inside a property panel, so a long panel stays as narrow as the tree (D2790).

A panel with many groups (Fillet, Chamfer) puts them on a few pages under a row
of tabs. One page shows at a time, so the user scrolls less and no page needs to
be wider than the left panel is by default. A group is still shown and hidden
by its form, exactly as without tabs: a page only decides whether its groups are
on screen. A tab whose page has no group to show is hidden.
"""

from __future__ import annotations

from collections.abc import Sequence

import shiboken6
from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import QTabBar, QVBoxLayout, QWidget

from fdcad.ui.themes.style import unit

#: Events that say a group was shown or hidden by its form.
_SHOWS = (QEvent.Type.ShowToParent, QEvent.Type.HideToParent)


class PanelTabs(QObject):
    """A tab bar and one page of groups per tab.

    The bar and the pages are separate widgets, so the panel can keep the bar
    above the scrolling area and put the pages in it.
    """

    #: The key of the tab now shown.
    changed = Signal(str)

    def __init__(self, tabs: Sequence[tuple[str, str, str]], parent: QWidget) -> None:
        """``tabs`` are (key, title, tooltip), in order."""
        super().__init__(parent)
        self.keys = [key for key, _title, _tip in tabs]
        self.bar = QTabBar(parent)
        self.bar.setObjectName("panel_tabs")
        # The tabs share the width of the panel, as the Hole Tool's Type and Positions
        # do and as OK and Cancel do above them (D2803). Left to their own widths they
        # stopped two thirds of the way across, and the row looked unfinished.
        self.bar.setExpanding(True)
        self.bar.setUsesScrollButtons(True)  # never wider than the panel
        self.bar.setDrawBase(False)
        self.pages: dict[str, QWidget] = {}
        self._groups: dict[str, list[QWidget]] = {}
        self._waiting = False
        u = unit(parent.font())
        for index, (key, title, tip) in enumerate(tabs):
            self.bar.addTab(title)
            self.bar.setTabToolTip(index, tip)
            page = QWidget(parent)
            page.setObjectName(f"panel_page_{key}")
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4 * u)  # groups 16 px apart, as without tabs
            page.setVisible(index == 0)
            self.pages[key] = page
            self._groups[key] = []
        self.bar.currentChanged.connect(self._tab_chosen)

    # Contents ---------------------------------------------------------------------

    def add(self, key: str, group: QWidget) -> None:
        """Put ``group`` at the end of the page of tab ``key``."""
        page = self.pages[key]
        layout = page.layout()
        assert layout is not None
        layout.addWidget(group)
        self._groups[key].append(group)
        group.installEventFilter(self)
        self._later()

    def key_of(self, group: QWidget) -> str | None:
        """The tab that holds ``group``."""
        for key, groups in self._groups.items():
            if group in groups:
                return key
        return None

    # The tab on show --------------------------------------------------------------

    def current(self) -> str:
        """The key of the tab now shown."""
        return self.keys[max(self.bar.currentIndex(), 0)]

    def show_tab(self, key: str) -> None:
        """Show the page of tab ``key``."""
        if key in self.keys:
            self.bar.setCurrentIndex(self.keys.index(key))

    def show_group(self, group: QWidget) -> None:
        """Show the tab that holds ``group``, so a field in it can be seen."""
        key = self.key_of(group)
        if key is not None:
            self.show_tab(key)

    def _tab_chosen(self, index: int) -> None:
        for at, key in enumerate(self.keys):
            self.pages[key].setVisible(at == index)
        if 0 <= index < len(self.keys):
            self.changed.emit(self.keys[index])

    # Tabs with nothing to show ----------------------------------------------------

    def has_groups(self, key: str) -> bool:
        """True when a group of tab ``key`` is not hidden by its form."""
        return any(not group.isHidden() for group in self._groups[key])

    def sync(self) -> None:
        """Hide each tab with no group to show; leave such a tab if it is the one shown."""
        self._waiting = False
        if not shiboken6.isValid(self.bar):
            return
        shown = [self.has_groups(key) for key in self.keys]
        current = self.bar.currentIndex()
        # Leave a tab before it goes: the bar would pick the next one, not the first.
        if any(shown) and not (0 <= current < len(shown) and shown[current]):
            self.bar.setCurrentIndex(shown.index(True))
        for index, on in enumerate(shown):
            if self.bar.isTabVisible(index) != on:
                self.bar.setTabVisible(index, on)
        self.bar.setVisible(sum(shown) > 1)

    def _later(self) -> None:
        if not self._waiting:
            self._waiting = True
            QTimer.singleShot(0, self, self.sync)

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # noqa: N802  (Qt override)
        """A form showed or hid a group: look at the tabs again, once per turn."""
        if event.type() in _SHOWS:
            self._later()
        return False

    def discard(self) -> None:
        """Take the bar and the pages off the panel and delete them."""
        for widget in (self.bar, *self.pages.values()):
            widget.hide()
            widget.deleteLater()
        self.deleteLater()


__all__ = ["PanelTabs"]
