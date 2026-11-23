"""The value box on a value label in the 3D view (owner note 7, TOOL_SPEC T5.2.3, T6.3.2, T15).

Clicking a value label (beside a drag handle, or at the first pick of a feature
without handles) opens the value box there with the panel field's text
selected. Enter or OK applies it to the panel field (so the preview follows)
and closes the box; the rebuild arrow applies and keeps it open. Tab and
Shift+Tab apply and move the box to the next or previous label of the feature
(T15.3). Escape or the cross closes it and puts back every value changed since
the box opened. A wrong value keeps the box open and says what is wrong. The
wheel and the Up and Down keys step the value (D144).

Values go through ``panel.set_text``, the same path as typing in the panel
field, so OK on the panel stays the one undoable command (T15.8).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QPoint
from PySide6.QtWidgets import QWidget

from fdcad.ui.property_panel.stepping import Stepper
from fdcad.ui.sketch_tools.value_box import ValueBox


def _field(panel: Any, param: str) -> Any:
    if panel is None:
        return None
    field = panel.values.get(param)
    form = getattr(panel, "form", None)
    if field is None and form is not None:
        field = form.fields.get(param)
    return field


class HandleValueEditor(QObject):
    """Opens and closes the value box for a value of the panel's feature."""

    def __init__(
        self,
        panel: Any,
        parent: QObject | None = None,
        order: Callable[[], list[str]] | None = None,
        locate: Callable[[str], QPoint | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel = panel
        self.box: ValueBox | None = None
        self.param: str | None = None
        #: The parameter the box was last opened on (typing opens it there again, T15.4).
        self.last_param: str | None = None
        #: The labels in Tab order, and where each one is in the host (None: unknown).
        self.order = order or (lambda: [])
        self.locate = locate or (lambda _param: None)
        self._host: QWidget | None = None
        self._pos = QPoint(0, 0)
        #: Field text before this box session changed it, to put back on Escape.
        self._before: dict[str, str] = {}

    def open(
        self, param: str, host: QWidget, pos: QPoint, typed: str | None = None
    ) -> ValueBox | None:
        """Open the box for ``param`` at ``pos`` in ``host`` coordinates.

        ``typed`` replaces the value, as when a digit is typed in the view (T15.4).
        """
        keep = dict(self._before) if self.box is not None else {}
        field = _field(self.panel, param)
        if field is None:
            return None
        self.close(restore=False)
        self._before = keep
        top = host.window()
        box = ValueBox(field.edit.text(), top)
        box.stepper = Stepper(box.edit, field.kind, lambda: field.units)  # type: ignore[attr-defined]
        box.tab_moves = True
        box.accepted.connect(lambda: self._apply(close=True))
        box.applied.connect(lambda: self._apply(close=False))
        box.rejected.connect(self.cancel)
        box.tabbed.connect(self.move)
        at = host.mapTo(top, pos) if host is not top else pos
        box.open_at(max(0, at.x()), max(0, at.y()))
        if typed:
            box.start_typing(typed)
        self.box, self.param, self.last_param = box, param, param
        self._host, self._pos = host, pos
        return box

    def _apply(self, close: bool) -> bool:
        if self.box is None or self.param is None:
            return False
        field = _field(self.panel, self.param)
        previous = field.edit.text() if field is not None else None
        error = self.panel.set_text(self.param, self.box.text())
        if error is not None:
            self.box.show_error(error)
            return False
        if previous is not None:
            self._before.setdefault(self.param, previous)
        if close:
            self.close(restore=False)
        return True

    def move(self, step: int) -> ValueBox | None:
        """Apply, then open the box on the next (``step`` 1) or previous (-1) label."""
        if self.box is None or self.param is None or self._host is None:
            return None
        if not self._apply(close=False):
            return self.box
        names = self.order()
        if self.param not in names or len(names) < 2:
            return self.box
        nxt = names[(names.index(self.param) + step) % len(names)]
        set_active = getattr(self.panel, "set_active_param", None)
        if set_active is not None:
            set_active(nxt)  # a handle value follows its handle (T5.2.3)
        pos = self.locate(nxt) or self._pos
        return self.open(nxt, self._host, pos)

    def cancel(self) -> None:
        """Escape or the cross: close and put back what this box changed (T15.9)."""
        self.close(restore=True)

    def close(self, restore: bool = False) -> None:
        """Close the box, if open. With ``restore`` the changed fields go back."""
        before, self._before = self._before, {}
        if restore:
            for name, text in before.items():
                field = _field(self.panel, name)
                if field is not None and field.edit.text() != text:
                    field.edit.setText(text)
        if self.box is not None:
            self.box.hide()
            self.box.deleteLater()
        self.box, self.param = None, None
