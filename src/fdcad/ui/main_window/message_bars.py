"""Message bars at the top of the view (TR203, D959).

An information or warning bar stays until the user closes it, or until the code
that showed it takes it away. Don't Show Again hides that message for good; the
Preferences dialog lists hidden messages and can bring them back. Each message has
a key, so showing it twice keeps one bar.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from fdcad.ui import strings

LEVELS = ("info", "warning")


def edge_colour(level: str) -> str:
    """The colour of a bar's left edge in the current theme. A warning has the warning
    colour. A notice is neutral, the muted text colour (D2700): green is kept for
    "this worked", which a notice does not say, and cobalt for what a tool acts on."""
    from fdcad.ui.themes.theme import chrome, palette

    return palette().state_warning if level == "warning" else chrome().muted


class MessageBar(QFrame):
    """One bar: a mark, the text, Don't Show Again and a cross that closes it."""

    closed = Signal(str)  # the key
    never = Signal(str)  # the key: Don't Show Again

    def __init__(
        self,
        key: str,
        text: str,
        level: str,
        parent: QWidget | None = None,
        action: tuple[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self.level = level if level in LEVELS else "info"
        self.setObjectName(f"message_bar_{self.level}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        from fdcad.ui.themes.style import unit

        u = unit(self.font())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3 * u, u, u, u)
        layout.setSpacing(2 * u)
        # A mark too, so the kind of message never shows by colour alone (U4.4,
        # D2694): the warning triangle, or the information mark in the text colour.
        self.mark = QLabel()
        self.mark.setObjectName("message_mark")
        self.mark.setFixedSize(QSize(4 * u, 4 * u))
        layout.addWidget(self.mark)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.label, 1)
        #: An optional button that does what the message asks (TR220: Save).
        self.action_button: QPushButton | None = None
        if action is not None:
            label, slot = action
            self.action_button = QPushButton(label)
            self.action_button.setObjectName("message_action")
            self.action_button.clicked.connect(lambda: slot())
            layout.addWidget(self.action_button)
        # Don't Show Again and Close are quiet, flat buttons: the button that does
        # what the message asks is the only outlined one, so it leads (D2694).
        self.never_button = QPushButton(strings.MESSAGE_NEVER)
        self.never_button.setObjectName("message_never")
        self.never_button.setFlat(True)
        self.never_button.clicked.connect(lambda: self.never.emit(self.key))
        layout.addWidget(self.never_button)
        # Close is a cross (D2701): the word is its accessible name and starts its
        # tooltip, and the button is a 24 px square (U3.3).
        self.close_button = QPushButton()
        self.close_button.setObjectName("message_close")
        self.close_button.setFlat(True)
        self.close_button.setIconSize(QSize(4 * u, 4 * u))
        self.close_button.setMinimumSize(QSize(6 * u, 6 * u))
        self.close_button.setAccessibleName(strings.MESSAGE_CLOSE)
        self.close_button.setToolTip(strings.MESSAGE_CLOSE_TIP)
        self.close_button.clicked.connect(lambda: self.closed.emit(self.key))
        layout.addWidget(self.close_button)
        self.restyle()

    def restyle(self) -> None:
        """Colours and the mark in the current theme (again after the theme changes)."""
        from fdcad.ui.icons import icon

        found = (
            icon("tree.warning_mark")
            if self.level == "warning"
            else icon("ui.info_mark", plain=True)
        )
        self.mark.setPixmap(found.pixmap(self.mark.size(), self.devicePixelRatioF()))
        self.close_button.setIcon(icon("ui.close_tab"))
        self._style()

    def _style(self) -> None:
        from fdcad.ui.themes.states import mix, radii
        from fdcad.ui.themes.style import unit
        from fdcad.ui.themes.theme import chrome

        u = unit(self.font())
        edge = edge_colour(self.level)
        fill = mix(chrome().raised, edge, 0.08)  # the edge colour, very light (D1034)
        self.setStyleSheet(
            f"QFrame#{self.objectName()} {{ background: {fill}; border: 1px solid "
            f"{mix(chrome().raised, edge, 0.45)}; border-left: {u}px solid {edge}; "
            f"border-radius: {radii(u)[0]}px; }}"
            f"QFrame#{self.objectName()} QLabel {{ background: transparent; }}"
        )

    def set_text(self, text: str) -> None:
        """Change the bar's text."""
        self.label.setText(text)


class MessageBars(QWidget):
    """The bars of one part's view, newest at the bottom."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("message_bars")
        from fdcad.ui.themes.style import unit

        # The bars are cards with air round them, on the colour of the view's top, so
        # the strip of tools above, the bars and the view read as one area (D2694).
        u = unit(self.font())
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(2 * u, 0, 2 * u, 2 * u)
        self.box.setSpacing(u)
        self.bars: dict[str, MessageBar] = {}
        self.restyle()
        #: Where hidden messages are kept (the app's Settings); None keeps none.
        self.settings: Any = None
        self.hide()

    def restyle(self) -> None:
        """The current theme's colours, for the stack and every bar on it. The window
        calls this when the theme changes, as it does for the strip of view tools."""
        from fdcad.ui.themes.theme import palette

        self.setStyleSheet(f"QWidget#message_bars {{ background: {palette().viewport_top}; }}")
        for bar in self.bars.values():
            bar.restyle()

    def hidden(self) -> set[str]:
        """Keys of the messages the user chose not to see again."""
        return set(getattr(self.settings, "hidden_messages", []) or [])

    def show_message(
        self, key: str, text: str, level: str = "info", action: tuple[str, Any] | None = None
    ) -> MessageBar | None:
        """Show (or update) the bar for ``key``, with an optional (label, callable)
        button. None when that message is hidden."""
        if key in self.hidden():
            return None
        bar = self.bars.get(key)
        if bar is not None:
            bar.set_text(text)
            return bar
        bar = MessageBar(key, text, level, self, action)
        bar.closed.connect(self.close_message)
        bar.never.connect(self.never_again)
        self.bars[key] = bar
        self.box.addWidget(bar)
        self.show()
        return bar

    def close_message(self, key: str) -> None:
        """Take the bar for ``key`` away, if it shows."""
        bar = self.bars.pop(key, None)
        if bar is not None:
            self.box.removeWidget(bar)
            bar.deleteLater()
        if not self.bars:
            self.hide()

    def never_again(self, key: str) -> None:
        """Hide ``key`` for good and close its bar."""
        if self.settings is not None:
            self.settings.hide_message(key)
        self.close_message(key)
