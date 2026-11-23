"""Empty states: what a place says while it has nothing to show (U8.3, D2702).

One line in the muted colour, centred in the place the content will take
(DESIGN_LANGUAGE section 3 item 9). Three forms share the look:

* ``empty_label``: a label that takes the content's place in a layout. ``boxed``
  gives it the dashed outline of the start page (D2695), for a whole page.
  ``compact`` drops the air round it, for a line inside a small card.
* ``EmptyOverlay``: a label over a list or table that has no rows. The view keeps
  its size, so nothing moves when the first row arrives.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QWidget


def empty_label(
    text: str, boxed: bool = False, compact: bool = False, parent: QWidget | None = None
) -> QLabel:
    """A centred, muted line for a place with nothing in it yet."""
    label = QLabel(text, parent)
    label.setObjectName("empty_box" if boxed else "empty_state")
    if compact:
        label.setProperty("compact", True)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class EmptyOverlay(QLabel):
    """A muted line in the middle of a list or table while it has no rows."""

    def __init__(self, view: QAbstractItemView, text: str) -> None:
        super().__init__(text, view.viewport())
        self.setObjectName("empty_state")
        self.view = view
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Clicks go to the view under it, so it still takes focus and its menu.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        model = view.model()
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset):
            signal.connect(self.refresh)
        view.viewport().installEventFilter(self)
        self.refresh()

    def is_empty(self) -> bool:
        """True when the view has no rows."""
        return bool(self.view.model().rowCount() == 0)

    def refresh(self, *_args: object) -> None:
        """Fill the view's own area and show only while it has no rows."""
        self.setGeometry(self.view.viewport().rect())
        self.setVisible(self.is_empty())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Follow the view's size."""
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(self.view.viewport().rect())
        return False
