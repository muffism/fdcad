"""Selection sets in the window (TR94, D944).

Save Selection Set keeps the current picks under a name. Selection Sets lists the
part's sets: pick one again, make a set by a rule (the faces of a feature or of a
colour, or the edges over a length), combine two sets, or delete one. A set is
resolved in a background job (CLAUDE.md rule 2), since rules measure the part.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import selection_sets as core
from fdcad.core.kernel import kernel_job
from fdcad.ui import strings_extra as text
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.session import DocumentSession


class SetSelectionSets(DocumentCommand):
    """Replace the part's selection sets as one undo step. Nothing to rebuild."""

    def __init__(self, session: DocumentSession, sets: list[dict[str, Any]], label: str) -> None:
        super().__init__(session, label)
        self.before = core.sets_of(session.document)
        self.after = copy.deepcopy(sets)

    def _put(self, sets: list[dict[str, Any]]) -> None:
        if sets:
            self.session.document.extra[core.KEY] = copy.deepcopy(sets)
        else:
            self.session.document.extra.pop(core.KEY, None)

    def apply(self) -> None:
        """Store the new sets."""
        self._put(self.after)

    def revert(self) -> None:
        """Put the old sets back."""
        self._put(self.before)

    def redo(self) -> None:
        """Store only; the solid does not change."""
        self.apply()

    def undo(self) -> None:
        """Restore only; the solid does not change."""
        self.revert()


class _Signals(QObject):
    done = Signal(object)


class ResolveJob(QRunnable):
    """Resolves one set off the UI thread; never raises (CLAUDE.md rule 7)."""

    def __init__(self, doc: Any, named: Any, name: str) -> None:
        super().__init__()
        self.doc, self.named, self.name = doc, named, name
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        """Emit the Resolved result, or the error text."""
        try:
            result: object = core.resolve(self.doc, self.named, self.name)
        except core.SelectionSetError as exc:
            result = str(exc)
        except Exception:
            result = text.SETS_FAILED
        self.signals.done.emit(result)


def describe(entry: dict[str, Any], names: dict[str, str]) -> str:
    """One line for the list: the name and what the set holds."""
    if isinstance(entry.get("items"), list):
        detail = text.SETS_ITEMS.format(count=len(entry["items"]))
    elif isinstance(entry.get("rule"), dict):
        rule = entry["rule"]
        kind = rule.get("kind")
        if kind == "feature":
            detail = text.SETS_RULE_FEATURE.format(name=names.get(rule.get("feature"), "?"))
        elif kind == "colour":
            detail = text.SETS_RULE_COLOUR.format(colour=rule.get("colour"))
        else:
            detail = text.SETS_RULE_LENGTH.format(mm=rule.get("min"))
    else:
        combine = entry.get("combine", {})
        detail = text.SETS_COMBINE.format(
            op=text.SETS_OPS.get(combine.get("op"), "?"), names=", ".join(combine.get("of", []))
        )
    return f"{entry['name']}: {detail}"


class SelectionSets:
    """The selection set commands of the main window."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self._jobs: set[ResolveJob] = set()

    def _tab(self) -> Any:
        tab = self.window.current
        if tab is None or self.window.editing == "sketch":
            return None
        return tab

    def _push(self, sets: list[dict[str, Any]], label: str) -> None:
        tab = self._tab()
        if tab is not None:
            tab.session.undo.push(SetSelectionSets(tab.session, sets, label))

    def sets(self) -> list[dict[str, Any]]:
        """The active part's sets."""
        tab = self._tab()
        return core.sets_of(tab.session.document) if tab is not None else []

    def save_picks(self, name: str | None = None) -> bool:
        """Save Selection Set: keep the current picks under a name (asked when None)."""
        tab = self._tab()
        report = tab.session.report if tab is not None else None
        view = tab.viewport if tab is not None else None
        if report is None or report.body is None or not hasattr(view, "selected"):
            return False
        picks = view.selected() if view is not None else []
        if not picks:
            self.window.status.setText(text.CONVERT_NOTHING)
            return False
        if name is None:
            name, ok = QInputDialog.getText(self.window, text.SETS_SAVE, text.SETS_NAME)
            if not ok:
                return False
        names = core.names_for(report.body, picks)
        if not names:
            self.window.status.setText(text.SETS_NO_NAMES)
            return False
        return self._add({"name": name, "items": names})

    def add_rule(self, name: str, rule: dict[str, Any]) -> bool:
        """Make a set that picks by a rule each time it is used."""
        return self._add({"name": name, "rule": rule})

    def combine(self, name: str, op: str, of: list[str]) -> bool:
        """Make a set from other sets: union, subtract or intersect."""
        if name in of:
            self.window.status.setText(text.SETS_SELF)
            return False
        return self._add({"name": name, "combine": {"op": op, "of": list(of)}})

    def _add(self, entry: dict[str, Any]) -> bool:
        try:
            sets = core.with_set(self.sets(), entry)
        except core.SelectionSetError as exc:
            self.window.status.setText(str(exc))
            return False
        self._push(sets, text.SETS_UNDO)
        self.window.status.setText(text.SETS_SAVED.format(name=entry["name"].strip()))
        return True

    def delete(self, name: str) -> bool:
        """Delete a set, unless a combined set uses it."""
        sets = self.sets()
        users = core.users_of(sets, name)
        if users:
            self.window.status.setText(text.SETS_IN_USE.format(name=name, users=", ".join(users)))
            return False
        self._push([s for s in sets if s["name"] != name], text.SETS_DELETE_UNDO)
        return True

    def use(self, name: str) -> bool:
        """Pick what set ``name`` holds now (in a background job)."""
        tab = self._tab()
        report = tab.session.report if tab is not None else None
        if report is None or report.body is None or not hasattr(tab.viewport, "select_shapes"):
            return False
        doc = copy.copy(tab.session.document)
        doc.extra = copy.deepcopy(doc.extra)
        doc.appearance = copy.deepcopy(doc.appearance)
        named = report.body
        job = ResolveJob(doc, named, name)
        self._jobs.add(job)
        job.signals.done.connect(lambda result, j=job, t=tab: self._resolved(j, t, named, result))
        QThreadPool.globalInstance().start(job)
        return True

    def _resolved(self, job: ResolveJob, tab: Any, named: Any, result: object) -> None:
        self._jobs.discard(job)
        if isinstance(result, str):
            self.window.status.setText(result)
            return
        report = tab.session.report
        if report is None or report.body is not named:
            return  # the part rebuilt meanwhile: run the set again
        assert isinstance(result, core.Resolved)
        tab.viewport.select_shapes(result.shapes)
        message = text.INVERTED.format(count=len(result.shapes))
        if result.missing:
            message += " " + text.SETS_MISSING.format(count=result.missing)
        self.window.status.setText(message)

    def wait(self, timeout_ms: int = 20000) -> bool:
        """Wait for running jobs (tests)."""
        return QThreadPool.globalInstance().waitForDone(timeout_ms)

    def show(self) -> None:
        """Selection Sets: the list and its buttons."""
        if self._tab() is None:
            return
        dialog = SetsDialog(self, self.window)
        dialog.exec()
        dialog.deleteLater()


class RuleDialog(QDialog):
    """A new rule set: its name and rule."""

    def __init__(
        self, features: list[tuple[str, str]], colours: list[str], parent: QWidget | None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(text.SETS_NEW_RULE)
        self.name = QLineEdit()
        self.kind = QComboBox()
        for key in core.RULE_KINDS:
            self.kind.addItem(text.SETS_RULE_KINDS[key], key)
        self.feature = QComboBox()
        for fid, label in features:
            self.feature.addItem(label, fid)
        self.colour = QComboBox()
        self.colour.addItems(colours)
        self.length = QDoubleSpinBox()
        self.length.setRange(0.0, 100000.0)
        self.length.setSuffix(" mm")
        self.length.setValue(10.0)
        form = QFormLayout()
        form.addRow(text.SETS_NAME, self.name)
        form.addRow(text.SETS_RULE, self.kind)
        form.addRow(text.SETS_RULE_KINDS["feature"], self.feature)
        form.addRow(text.SETS_RULE_KINDS["colour"], self.colour)
        form.addRow(text.SETS_RULE_KINDS["edge_length"], self.length)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def rule(self) -> dict[str, Any]:
        """The chosen rule."""
        kind = self.kind.currentData()
        if kind == "feature":
            return {"kind": kind, "feature": self.feature.currentData()}
        if kind == "colour":
            return {"kind": kind, "colour": self.colour.currentText()}
        return {"kind": kind, "min": self.length.value()}


class CombineDialog(QDialog):
    """A new set made of two others."""

    def __init__(self, names: list[str], parent: QWidget | None) -> None:
        super().__init__(parent)
        self.setWindowTitle(text.SETS_COMBINE_TITLE)
        self.name = QLineEdit()
        self.first, self.second = QComboBox(), QComboBox()
        self.first.addItems(names)
        self.second.addItems(names)
        self.op = QComboBox()
        for key in core.OPS:
            self.op.addItem(text.SETS_OPS[key], key)
        form = QFormLayout()
        form.addRow(text.SETS_NAME, self.name)
        form.addRow(text.SETS_FIRST, self.first)
        form.addRow(text.SETS_OP, self.op)
        form.addRow(text.SETS_SECOND, self.second)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)


class SetsDialog(QDialog):
    """The part's selection sets with Pick, New Rule, Combine and Delete."""

    def __init__(self, owner: SelectionSets, parent: QWidget | None) -> None:
        super().__init__(parent)
        self.owner = owner
        self.setObjectName("selection_sets")
        self.setWindowTitle(text.SETS_TITLE)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self._pick())
        row = QHBoxLayout()
        for label, slot in (
            (text.SETS_PICK, self._pick),
            (text.SETS_NEW_RULE, self._new_rule),
            (text.SETS_COMBINE_TITLE, self._combine),
            (text.SETS_DELETE, self._delete),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            row.addWidget(button)
        self.note = QLabel(text.SETS_HINT)
        self.note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.note)
        layout.addWidget(self.list)
        layout.addLayout(row)
        layout.addWidget(buttons)
        self.fill()

    def fill(self) -> None:
        """List the sets."""
        tab = self.owner._tab()
        names = {f.id: f.name for f in tab.session.document.features} if tab is not None else {}
        self.list.clear()
        for entry in self.owner.sets():
            self.list.addItem(describe(entry, names))

    def _chosen(self) -> str | None:
        row = self.list.currentRow()
        sets = self.owner.sets()
        return sets[row]["name"] if 0 <= row < len(sets) else None

    def _pick(self) -> None:
        name = self._chosen()
        if name is not None:
            self.owner.use(name)

    def _delete(self) -> None:
        name = self._chosen()
        if name is not None and self.owner.delete(name):
            self.fill()

    def _new_rule(self) -> None:
        from fdcad.core.appearance import colors_in_use, part_color
        from fdcad.core.features import REGISTRY

        tab = self.owner._tab()
        if tab is None:
            return
        doc = tab.session.document
        features = [
            (f.id, f.name)
            for f in doc.features
            if (ftype := REGISTRY.get(f.type)) is not None and ftype.makes_solid
        ]
        names = {f.id: f.name for f in doc.features}
        colours = [part_color(doc.appearance)] + [
            c for c, _t in colors_in_use(doc.appearance, names)
        ]
        dialog = RuleDialog(features, list(dict.fromkeys(colours)), self)
        if dialog.exec() and self.owner.add_rule(dialog.name.text(), dialog.rule()):
            self.fill()
        dialog.deleteLater()

    def _combine(self) -> None:
        names = [s["name"] for s in self.owner.sets()]
        if len(names) < 2:
            self.note.setText(text.SETS_NEED_TWO)
            return
        dialog = CombineDialog(names, self)
        if dialog.exec() and self.owner.combine(
            dialog.name.text(),
            str(dialog.op.currentData()),
            [dialog.first.currentText(), dialog.second.currentText()],
        ):
            self.fill()
        dialog.deleteLater()
