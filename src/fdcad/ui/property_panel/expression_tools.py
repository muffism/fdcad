"""Expressions in feature panel fields (TOOL_SPEC T14.6).

Every number field takes a plain value or an expression starting with ``=``
that can use global variables and functions (PLAN section 7). While a field
holds an expression, a small button at its start switches between the
expression (editable) and its result (read only).

Typing ``="Name"`` with a new name and pressing Enter offers to make a global
variable called Name holding the field's last good value; after Yes the field
links to it as ``=Name``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QStackedWidget, QToolButton

from fdcad.core.document.model import Param
from fdcad.core.units import Kind
from fdcad.core.units.variables import requested_variable, valid_name
from fdcad.ui import strings_extra as text

if TYPE_CHECKING:
    from fdcad.ui.property_panel.panel import ValueField

#: Makes the variable after asking: (name, kind, typed text, value) -> True when made.
CreateVariable = Callable[[str, Kind, str, float], bool]


def is_formula(value: str) -> bool:
    """True when the text is an expression (starts with ``=``)."""
    return value.strip().startswith("=")


class ExpressionTools(QObject):
    """The expression and value switch and the ``="Name"`` request for one field."""

    def __init__(self, field: ValueField) -> None:
        super().__init__(field)
        from fdcad.ui.icons import icon

        self.field = field
        self.create: CreateVariable | None = None
        self.last_good: Param | None = field.param()
        self.button = QToolButton(field)
        self.button.setObjectName("expression_toggle")
        self.button.setAutoRaise(True)
        self.button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.button.setIcon(icon("field.value"))
        self.button.setToolTip(text.SHOW_RESULT)
        self.button.clicked.connect(self.toggle)
        self.result = QLineEdit(field)
        self.result.setObjectName("field_result")
        self.result.setReadOnly(True)
        self.stack = QStackedWidget(field)
        layout = field.layout()
        assert layout is not None
        layout.removeWidget(field.edit)
        self.stack.addWidget(field.edit)
        self.stack.addWidget(self.result)
        self.stack.setSizePolicy(field.edit.sizePolicy())
        self.stack.setMaximumHeight(field.edit.sizeHint().height())
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        row.addWidget(self.button)
        row.addWidget(self.stack, 1)
        layout.insertLayout(0, row)  # type: ignore[attr-defined]
        field.edit.textChanged.connect(self._changed)
        field.edit.installEventFilter(self)
        field.edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        field.edit.customContextMenuRequested.connect(self._context_menu)
        self._changed()

    def context_menu(self) -> Any:
        """The field's right click menu: the usual edit items, plus the configurations it
        applies to while the part has more than one (P4.10 item 2)."""
        from fdcad.ui.equations.scope import add_scope_menu

        menu = self.field.edit.createStandardContextMenu()
        add_scope_menu(menu, self.field)
        return menu

    def _context_menu(self, pos: Any) -> None:
        menu = self.context_menu()
        menu.exec(self.field.edit.mapToGlobal(pos))
        menu.deleteLater()

    # Expression and value ------------------------------------------------------------

    @property
    def showing_result(self) -> bool:
        """True while the field shows the expression's result instead of the expression."""
        return self.stack.currentWidget() is self.result

    def toggle(self) -> None:
        """Switch between the expression and its result (T14.6.2)."""
        if self.showing_result:
            self.stack.setCurrentWidget(self.field.edit)
            self.button.setIcon(_icon("field.value"))
            self.button.setToolTip(text.SHOW_RESULT)
            self.field.edit.setFocus()
            return
        param = self.field.param()
        if param is None:
            return
        from fdcad.ui.property_panel.panel import format_value

        self.result.setText(format_value(param.value, self.field.kind, self.field.units))
        self.stack.setCurrentWidget(self.result)
        self.button.setIcon(_icon("field.expression"))
        self.button.setToolTip(text.SHOW_EXPRESSION)

    def _changed(self, *_args: object) -> None:
        value = self.field.edit.text()
        self.button.setVisible(is_formula(value) and requested_variable(value) is None)
        name = requested_variable(value)
        if name is not None:
            self.field.info.setText(text.VARIABLE_PRESS_ENTER.format(name=name))
            return
        param = self.field.param()
        if param is not None:
            self.last_good = param
        if not is_formula(value) and self.showing_result:
            self.toggle()

    # New variables -------------------------------------------------------------------

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802
        """Enter on ``="Name"`` makes the variable instead of accepting the panel."""
        if (
            watched is self.field.edit
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and requested_variable(self.field.edit.text()) is not None
        ):
            self.try_new_variable(self.field.edit.text())
            return True
        return super().eventFilter(watched, event)

    def try_new_variable(self, typed: str) -> bool:
        """Handle ``="Name"``: link to it, or make it after a confirm. False for other text."""
        name = requested_variable(typed)
        if name is None:
            return False
        field = self.field
        if not valid_name(name):
            field.info.setText(text.VARIABLE_BAD_NAME.format(name=name))
            return True
        from fdcad.core.units.expressions import reserved_name

        clash = reserved_name(name)
        if clash and name not in field.variables:  # TR310 (D919)
            field.info.setText(clash)
            return True
        if name in field.variables:
            field.edit.setText(f"={name}")  # already there: just use it
            return True
        good = self.last_good
        if good is None or self.create is None:
            field.info.setText(text.VARIABLE_NO_VALUE)
            return True
        expr = good.expr if not is_formula(good.expr) else _plain(good, field)
        if self.create(name, field.kind, expr, good.value):
            field.variables[name] = (field.kind, good.value)
            field.edit.setText(f"={name}")
        else:
            field.edit.setText(good.expr)
        return True


def _plain(param: Param, field: ValueField) -> str:
    """A formula's current value as typed text, for a new variable."""
    from fdcad.ui.property_panel.panel import typed_angle, typed_length

    if field.kind is Kind.ANGLE:
        return typed_angle(param.value)
    if field.kind is Kind.LENGTH:
        return typed_length(param.value, field.units) + field.units.value
    return f"{param.value:g}"


def _icon(name: str) -> Any:
    from fdcad.ui.icons import icon

    return icon(name)
