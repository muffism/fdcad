"""The node editor's title bar (UI review item P7, D2745).

Qt draws the float and close buttons of a panel that can float 10 px wide,
whatever the style sheet says. This bar takes their place: the panel's name,
then two buttons of 24 px, the smallest size for something to click (U3.3).

The bar handles no mouse press of its own, so Qt still drags the panel by it,
docks it where it is dropped and floats or docks it on a double click.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import QDockWidget, QHBoxLayout, QLabel, QToolButton, QWidget

from fdcad.ui.icons import icon
from fdcad.ui.node_editor import strings
from fdcad.ui.themes.style import unit
from fdcad.ui.themes.typography import Role, type_font


class DockTitleBar(QWidget):
    """Name, Float (or Dock) and Close for one ``QDockWidget``."""

    def __init__(self, dock: QDockWidget) -> None:
        super().__init__(dock)
        self.dock = dock
        self.setObjectName("dock_title_bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        u = unit(self.font())
        self.title = QLabel(dock.windowTitle())
        self.title.setObjectName("dock_title")
        self.title.setFont(type_font(Role.TITLE))
        dock.windowTitleChanged.connect(self.title.setText)
        self.float_button = self._button("dock_float")
        self.float_button.clicked.connect(self.toggle_floating)
        self.close_button = self._button("dock_close")
        self.close_button.setAccessibleName(strings.TITLE_CLOSE)
        self.close_button.setToolTip(strings.TITLE_CLOSE_TIP)
        self.close_button.clicked.connect(dock.close)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3 * u, u, 2 * u, u)
        layout.setSpacing(u)
        layout.addWidget(self.title, 1)
        layout.addWidget(self.float_button)
        layout.addWidget(self.close_button)
        dock.topLevelChanged.connect(lambda _floating: self.refresh())
        dock.featuresChanged.connect(lambda _features: self.refresh())
        self.refresh()

    def _button(self, name: str) -> QToolButton:
        u = unit(self.font())
        button = QToolButton(self)
        button.setObjectName(name)
        button.setAutoRaise(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setIconSize(QSize(4 * u, 4 * u))
        button.setMinimumSize(QSize(6 * u, 6 * u))  # 24 px target size (U3.3)
        # As Qt's own title buttons: a click must not take the keys from the canvas.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def toggle_floating(self) -> None:
        """Float a docked panel; dock a floating one where it was."""
        self.dock.setFloating(not self.dock.isFloating())

    def refresh(self) -> None:
        """The icons in the current theme's colours, the word for what the first button
        does now, and only the buttons the panel allows."""
        floating = self.dock.isFloating()
        self.float_button.setIcon(icon("ui.dock_panel" if floating else "ui.float_panel"))
        self.float_button.setAccessibleName(strings.TITLE_DOCK if floating else strings.TITLE_FLOAT)
        self.float_button.setToolTip(
            strings.TITLE_DOCK_TIP if floating else strings.TITLE_FLOAT_TIP
        )
        self.close_button.setIcon(icon("ui.close_tab"))
        features = self.dock.features()
        feature = QDockWidget.DockWidgetFeature
        self.float_button.setVisible(bool(features & feature.DockWidgetFloatable))
        self.close_button.setVisible(bool(features & feature.DockWidgetClosable))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802  (Qt override)
        """The theme changed: the two icons take the new colours."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange) and hasattr(
            self, "close_button"
        ):
            self.refresh()
