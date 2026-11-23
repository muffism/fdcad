"""The first run welcome (D552).

Shown once, on the first start, after the main window is up. Closing it in any
way marks it as seen, so it never comes back by itself; Help, Welcome opens it
again. It is not modal, so the user can start working with it open.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings_help as text
from fdcad.ui.preferences.settings import Settings


class WelcomeDialog(QDialog):
    """A short tour: sketching, the command tabs, the left panel, Preferences, the guide."""

    def __init__(
        self,
        settings: Settings,
        parent: QWidget | None = None,
        open_guide: Callable[[], object] | None = None,
        open_lessons: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("welcomeDialog")
        self.setWindowTitle(text.WELCOME_TITLE)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.settings = settings
        outer = QVBoxLayout(self)
        # The text scrolls instead of being squeezed, so no line is ever cut off at a
        # large font or in a small window (bug hunt F6).
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(area, 1)
        intro = QLabel(text.WELCOME_INTRO)
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.sections: list[QLabel] = []
        for heading, body in text.WELCOME_SECTIONS:
            title = QLabel(f"<b>{heading}</b>")
            label = QLabel(body)
            label.setWordWrap(True)
            lay.addWidget(title)
            lay.addWidget(label)
            self.sections.append(label)
        again = QLabel(text.WELCOME_AGAIN)
        again.setWordWrap(True)
        lay.addStretch(1)
        lay.addWidget(again)
        area.setWidget(page)
        buttons = QDialogButtonBox()
        self.guide_button = buttons.addButton(
            text.WELCOME_OPEN_GUIDE, QDialogButtonBox.ButtonRole.ActionRole
        )
        from fdcad.ui.help.lessons import START_LESSONS

        #: Start the first run lessons (TR291 item 2, D2505).
        self.lessons_button = buttons.addButton(
            START_LESSONS, QDialogButtonBox.ButtonRole.ActionRole
        )
        self.lessons_button.setObjectName("welcome_lessons")
        if open_lessons is not None:
            lessons = open_lessons

            def learn() -> None:
                self.accept()
                lessons()

            self.lessons_button.clicked.connect(learn)
        else:
            self.lessons_button.hide()
        self.start_button = buttons.addButton(
            text.WELCOME_START, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.start_button.setDefault(True)
        buttons.accepted.connect(self.accept)
        if open_guide is not None:
            guide = open_guide

            def go() -> None:
                self.accept()
                guide()

            self.guide_button.clicked.connect(go)
        else:
            self.guide_button.hide()
        outer.addWidget(buttons)
        self._fit(560, outer, lay, buttons)
        self.finished.connect(lambda _result: self.mark_seen())

    def _fit(self, width: int, outer: QVBoxLayout, page: QVBoxLayout, buttons: QWidget) -> None:
        """Open ``width`` wide and tall enough for all the text, within the screen."""
        # Measure with the theme's fonts, padding and button sizes applied (U2, U3).
        self.ensurePolished()
        for child in self.findChildren(QWidget):
            child.ensurePolished()
        margins = outer.contentsMargins()
        area = self.findChild(QScrollArea)
        frame = 2 * area.frameWidth() if area is not None else 0
        # Leave room for the scroll bar, which the styled page may need to wrap around.
        bar = area.verticalScrollBar().sizeHint().width() if area is not None else 0
        inner = width - margins.left() - margins.right() - frame - bar
        widget = page.parentWidget()
        height = widget.heightForWidth(inner) if widget is not None else -1
        if height < 0:
            height = page.totalHeightForWidth(inner)
        height += margins.top() + margins.bottom() + outer.spacing() + frame
        height += buttons.sizeHint().height()
        screen = self.screen()
        if screen is not None:
            height = min(height, screen.availableGeometry().height() * 9 // 10)
        self.resize(width, height)

    def mark_seen(self) -> None:
        """Remember that the welcome was shown, so it is not shown again on start."""
        self.settings.welcome_seen = True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt name)
        """Closing with the title bar button also counts as seen."""
        self.mark_seen()
        super().closeEvent(event)
