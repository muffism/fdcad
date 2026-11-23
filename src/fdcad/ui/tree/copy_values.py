"""Copy Values to Others and Edit by Rule (TR160, D957).

Both change feature values through the core (core/copy_values.py) on a copy of
the part and push the result as one undo step that rebuilds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import copy_values as core
from fdcad.core.document.model import Document, Param
from fdcad.core.units import ExpressionError, Kind, evaluate
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

_ID = Qt.ItemDataRole.UserRole


def type_label(ftype: str) -> str:
    """A readable name for a feature type."""
    return ftype.replace("_", " ").capitalize()


def value_label(name: str) -> str:
    """A readable name for a value."""
    return name.replace("_", " ").capitalize()


def _push(session: DocumentSession, label: str, change: Any) -> None:
    from fdcad.ui.equations.commands import DocumentChange

    session.undo.push(DocumentChange(session, label, change))


# Copy Values ------------------------------------------------------------------------


def others_of_kind(doc: Document, fid: str) -> list[str]:
    """Ids of the other features of the same kind, in tree order."""
    ftype = doc.feature(fid).type
    return [f.id for f in doc.features if f.type == ftype and f.id != fid]


class CopyValuesDialog(QDialog):
    """Tick the features that take the source's values; none start ticked."""

    def __init__(self, doc: Document, source: str, parent: QWidget | None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.COPY_VALUES_TITLE)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(strings.COPY_VALUES_PROMPT.format(name=doc.feature(source).name)))
        self.items = QListWidget()
        self.items.setObjectName("copy_values_targets")
        for fid in others_of_kind(doc, source):
            item = QListWidgetItem(doc.feature(fid).name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(_ID, fid)
            self.items.addItem(item)
        layout.addWidget(self.items)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen(self) -> list[str]:
        """The ticked feature ids."""
        out: list[str] = []
        for row in range(self.items.count()):
            item = self.items.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(str(item.data(_ID)))
        return out


def ask_targets(doc: Document, source: str, parent: QWidget | None) -> list[str] | None:
    """The ticked targets, or None when cancelled (a seam for tests)."""
    dialog = CopyValuesDialog(doc, source, parent)
    try:
        return dialog.chosen() if dialog.exec() == QDialog.DialogCode.Accepted else None
    finally:
        dialog.deleteLater()


def copy_values_to_others(
    session: DocumentSession, source: str, parent: QWidget | None, report: Any
) -> int:
    """Copy Values: ask which features take ``source``'s values, then copy. Returns how
    many changed."""
    doc = session.document
    if not others_of_kind(doc, source):
        report(strings.COPY_VALUES_NONE.format(name=doc.feature(source).name))
        return 0
    targets = ask_targets(doc, source, parent)
    if not targets:
        return 0
    changed: list[str] = []

    def change(d: Document) -> None:
        changed.extend(core.copy_values(d, source, targets))

    try:
        _push(session, strings.COPY_VALUES_TITLE, change)
    except core.CopyValuesError as exc:
        report(str(exc))
        return 0
    report(strings.COPY_VALUES_DONE.format(count=len(changed), name=doc.feature(source).name))
    return len(changed)


# Edit by Rule -----------------------------------------------------------------------


def _kind(ftype: str, param: str) -> Kind:
    from fdcad.core.features import REGISTRY

    found = REGISTRY.get(ftype)
    kind = found.kind_of(param) if found is not None else None
    if kind is None:
        return Kind.ANGLE if "angle" in param else Kind.LENGTH
    return kind


class EditByRuleDialog(QDialog):
    """Pick a kind of feature, a value and a test; the list shows what the rule finds,
    and OK sets the new value on all of them."""

    def __init__(self, session: DocumentSession, parent: QWidget | None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle(strings.EDIT_BY_RULE_TITLE)
        doc = session.document
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.ftype = QComboBox()
        self.ftype.setObjectName("rule_type")
        seen: dict[str, None] = {}
        for f in doc.features:
            if core.number_params(doc, f.type):
                seen.setdefault(f.type)
        for ftype in seen:
            self.ftype.addItem(type_label(ftype), ftype)
        self.param = QComboBox()
        self.param.setObjectName("rule_value")
        self.test = QComboBox()
        self.test.setObjectName("rule_test")
        for test in core.TESTS:
            self.test.addItem(test, test)
        self.limit = QLineEdit()
        self.limit.setObjectName("rule_limit")
        self.new_value = QLineEdit()
        self.new_value.setObjectName("rule_new_value")
        form.addRow(strings.RULE_TYPE, self.ftype)
        form.addRow(strings.RULE_VALUE, self.param)
        form.addRow(strings.RULE_TEST, self.test)
        form.addRow(strings.RULE_LIMIT, self.limit)
        self.found = QListWidget()
        self.found.setObjectName("rule_found")
        layout.addWidget(QLabel(strings.RULE_FOUND))
        layout.addWidget(self.found)
        set_form = QFormLayout()
        set_form.addRow(strings.RULE_NEW_VALUE, self.new_value)
        layout.addLayout(set_form)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.ftype.currentIndexChanged.connect(self._fill_params)
        for signal in (self.param.currentIndexChanged, self.test.currentIndexChanged):
            signal.connect(self.refresh)
        self.limit.textChanged.connect(self.refresh)
        self._fill_params()

    def _fill_params(self) -> None:
        self.param.blockSignals(True)
        self.param.clear()
        ftype = self.ftype.currentData()
        if ftype:
            for name in core.number_params(self.session.document, ftype):
                self.param.addItem(value_label(name), name)
        self.param.blockSignals(False)
        self.refresh()

    def _evaluate(self, text: str) -> float | None:
        ftype, param = self.ftype.currentData(), self.param.currentData()
        if not ftype or not param or not text.strip():
            return None
        doc = self.session.document
        variables = {v.name: (v.kind, v.value) for v in doc.variables}
        try:
            return evaluate(text, _kind(ftype, param), doc.units, variables)
        except ExpressionError as exc:
            self.message.setText(str(exc))
            return None

    def rule(self) -> core.Rule | None:
        """The rule as set, or None while it is not complete."""
        limit = self._evaluate(self.limit.text())
        ftype, param = self.ftype.currentData(), self.param.currentData()
        if limit is None or not ftype or not param:
            return None
        return core.Rule(ftype, param, str(self.test.currentData()), limit)

    def matches(self) -> list[str]:
        """Ids of the features the rule finds now."""
        rule = self.rule()
        return core.find(self.session.document, rule) if rule is not None else []

    def refresh(self) -> None:
        """Show what the rule finds."""
        self.message.clear()
        self.found.clear()
        doc = self.session.document
        for fid in self.matches():
            self.found.addItem(doc.feature(fid).name)

    def value(self) -> Param | None:
        """The new value as typed, or None when it does not read."""
        text = self.new_value.text().strip()
        number = self._evaluate(text)
        return Param(text, number) if number is not None else None


def ask_rule(
    session: DocumentSession, parent: QWidget | None
) -> tuple[list[str], str, Param | None] | None:
    """The features found, the value name and the new value (None when it does not
    read), or None when cancelled (a seam for tests)."""
    dialog = EditByRuleDialog(session, parent)
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.matches(), str(dialog.param.currentData() or ""), dialog.value()
    finally:
        dialog.deleteLater()


def edit_by_rule(session: DocumentSession | None, parent: QWidget | None, report: Any) -> int:
    """Edit by Rule: find features by a rule and set one value on all of them."""
    if session is None:
        return 0
    doc = session.document
    if not any(core.number_params(doc, f.type) for f in doc.features):
        report(strings.RULE_NOTHING)
        return 0
    chosen = ask_rule(session, parent)
    if chosen is None:
        return 0
    fids, param, value = chosen
    if not fids or value is None:
        report(strings.RULE_INCOMPLETE)
        return 0
    changed: list[str] = []
    _push(
        session,
        strings.EDIT_BY_RULE_TITLE,
        lambda d: changed.extend(core.set_value(d, fids, param, value)),
    )
    report(strings.RULE_DONE.format(count=len(changed)))
    return len(changed)
