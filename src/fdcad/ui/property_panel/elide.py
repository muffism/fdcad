"""A drop down that is narrower than its entry ends the entry with "..." (D2800).

Qt cuts the words of a drop down at the edge of the box, in the middle of a
letter: "Sketch prof". A panel that must fit the left panel's default width
(D2791) has drop downs narrower than their longest entry, so there the entry on
show ends with an ellipsis, and the tooltip starts with the whole entry. The
list that drops down keeps the width of its longest entry (D2742).

``elide_when_cut`` is for a drop down that is not editable. It changes nothing
while the entry fits.
"""

from __future__ import annotations

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QHelpEvent, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QToolTip,
)

#: Set on a drop down once its entry is drawn by ``_Elider``.
_ELIDES = "elides_entry"


def shown_text(box: QComboBox) -> str:
    """The words a drop down shows: its entry, or its placeholder with none chosen."""
    if box.currentIndex() < 0 and box.placeholderText():
        return str(box.placeholderText())
    return str(box.currentText())


def text_room(box: QComboBox) -> int:
    """Pixels a drop down has for the words of its entry, in the current style."""
    option = QStyleOptionComboBox()
    box.initStyleOption(option)
    field = box.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxEditField, box
    )
    room = int(field.width())
    if not option.currentIcon.isNull():
        room -= int(option.iconSize.width()) + 4
    return room


def is_cut(box: QComboBox) -> bool:
    """True when the entry on show is wider than the room the drop down has for it."""
    if box.isEditable():
        return False
    return bool(box.fontMetrics().horizontalAdvance(shown_text(box)) > text_room(box))


def elided_text(box: QComboBox) -> str:
    """The entry as it is drawn: whole, or ending with an ellipsis when it is cut."""
    words = shown_text(box)
    if not is_cut(box):
        return words
    return str(box.fontMetrics().elidedText(words, Qt.TextElideMode.ElideRight, text_room(box)))


class _Elider(QObject):
    """Draws a cut entry with an ellipsis and gives its whole text as the tooltip."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802  (Qt override)
        """Paint and tooltip of a drop down whose entry is cut; all else is Qt's."""
        if not isinstance(watched, QComboBox) or not shiboken6.isValid(watched):
            return False
        kind = event.type()
        if kind == QEvent.Type.Paint and is_cut(watched):
            self._paint(watched)
            return True
        if kind == QEvent.Type.ToolTip and isinstance(event, QHelpEvent) and is_cut(watched):
            own = watched.toolTip()
            words = shown_text(watched)
            QToolTip.showText(event.globalPos(), f"{words}\n{own}" if own else words, watched)
            event.accept()
            return True
        return False

    @staticmethod
    def _paint(box: QComboBox) -> None:
        """As ``QComboBox.paintEvent``, with the entry elided."""
        painter = QStylePainter(box)
        painter.setPen(box.palette().color(QPalette.ColorRole.Text))
        option = QStyleOptionComboBox()
        box.initStyleOption(option)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        if box.currentIndex() < 0 and box.placeholderText():
            option.palette.setBrush(QPalette.ColorRole.ButtonText, option.palette.placeholderText())
        option.currentText = elided_text(box)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)
        painter.end()


_elider: _Elider | None = None


def elide_when_cut(box: QComboBox) -> None:
    """From now on ``box`` shows an entry it has no room for with an ellipsis at its
    end, and its tooltip then starts with the whole entry."""
    global _elider
    if box.property(_ELIDES):
        return
    if _elider is None or not shiboken6.isValid(_elider):
        _elider = _Elider(QApplication.instance())
    box.setProperty(_ELIDES, True)
    box.installEventFilter(_elider)


__all__ = ["elide_when_cut", "elided_text", "is_cut", "shown_text", "text_room"]
