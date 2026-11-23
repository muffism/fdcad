"""The header of a side panel (D2692, D2701, D2743).

Two rows: the tool's icon and name, then OK and Cancel at equal width across
the panel. OK is the main button and both are words only. The property panel
and the sketch panel build this layout themselves; the Reference Geometry and
Section View panels use this widget, so all four open with one header.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStyle, QVBoxLayout, QWidget

from fdcad.ui import strings
from fdcad.ui.icons import icon
from fdcad.ui.themes.style import unit
from fdcad.ui.themes.typography import Role, type_font


class PanelHeader(QWidget):
    """Icon, name, OK and Cancel. The panel connects the two buttons itself."""

    def __init__(self, title: str, icon_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel_header")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        u = unit(self.font())
        self.icon_name = icon_name
        self.icon = QLabel()
        self.icon.setObjectName("panel_icon")
        self.title = QLabel(title)
        self.title.setObjectName("panel_title")
        self.title.setFont(type_font(Role.TITLE))
        self.title.setTextFormat(Qt.TextFormat.PlainText)  # a feature's name is the user's
        self.ok_button = QPushButton(strings.OK)
        self.ok_button.setObjectName("panel_ok")
        self.cancel_button = QPushButton(strings.CANCEL)
        rows = QVBoxLayout(self)
        rows.setContentsMargins(3 * u, 3 * u, 3 * u, 3 * u)  # 12 px panel padding (U2.2)
        rows.setSpacing(2 * u)
        #: The row of the name: a panel may add small buttons at its right.
        self.name_row = QHBoxLayout()
        self.name_row.setSpacing(2 * u)
        self.name_row.addWidget(self.icon)
        self.name_row.addWidget(self.title, 1)
        actions = QHBoxLayout()
        actions.setSpacing(2 * u)
        actions.addWidget(self.ok_button, 1)
        actions.addWidget(self.cancel_button, 1)
        rows.addLayout(self.name_row)
        rows.addLayout(actions)
        self.refresh_icon()

    def set_title(self, text: str) -> None:
        """Show ``text`` as the name."""
        self.title.setText(text)

    def refresh_icon(self) -> None:
        """Draw the icon in the current theme's colours, at the screen's pixel ratio."""
        size = self.style().pixelMetric(QStyle.PixelMetric.PM_LargeIconSize)
        found = icon(self.icon_name) if self.icon_name else None
        self.icon.setVisible(found is not None and not found.isNull())
        if found is not None and not found.isNull():
            self.icon.setFixedSize(QSize(size, size))
            self.icon.setPixmap(found.pixmap(QSize(size, size), self.devicePixelRatioF()))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802  (Qt override)
        """The theme changed: the icon takes the new colours."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange) and hasattr(
            self, "icon"
        ):
            self.refresh_icon()
