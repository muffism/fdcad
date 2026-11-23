"""Which configurations a value edit applies to (PHASE4_SPEC P4.10 item 2, D391).

Every value field gets a Configurations entry in its right click menu while the
part has more than one configuration: This Configuration, All Configurations or
Chosen Configurations. The choice is kept on the field until the panel's OK,
where ``push_edit`` applies the edit and then the scope, as one undo step.
Fields without a choice follow the default rule in ``core/configurations``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import configurations as configs
from fdcad.core.document.model import Feature
from fdcad.ui import strings_config as text

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

SCOPE_PROPERTY = "config_scope"
CHOSEN_PROPERTY = "config_chosen"


def _session_of(widget: QWidget) -> DocumentSession | None:
    window = widget.window()
    tab = getattr(window, "current", None)
    return getattr(tab, "session", None)


def scope_of(field: QWidget) -> tuple[str, list[str]] | None:
    """The scope chosen on a field, or None for the default rule."""
    scope = field.property(SCOPE_PROPERTY)
    if scope not in configs.SCOPES:
        return None
    chosen = field.property(CHOSEN_PROPERTY)
    return str(scope), [str(c) for c in chosen] if isinstance(chosen, list) else []


def set_scope(field: QWidget, scope: str | None, chosen: list[str] | None = None) -> None:
    """Choose the scope of a field (None goes back to the default rule)."""
    field.setProperty(SCOPE_PROPERTY, scope)
    field.setProperty(CHOSEN_PROPERTY, list(chosen or []))
    info = getattr(field, "info", None)
    if scope is not None and info is not None:
        label = text.CONFIG_SCOPE[scope].rstrip(".")
        if scope == "chosen" and chosen:
            label = ", ".join(chosen)
        info.setText(text.CONFIG_SCOPE_TIP.format(scope=label))


class ChooseConfigurations(QDialog):
    """Tick the configurations an edit applies to."""

    def __init__(self, names: list[str], ticked: list[str], parent: QWidget | None) -> None:
        super().__init__(parent)
        self.setObjectName("choose_configurations")
        self.setWindowTitle(text.CONFIG_CHOOSE_TITLE)
        layout = QVBoxLayout(self)
        self.boxes: dict[str, QCheckBox] = {}
        for name in names:
            box = QCheckBox(name)
            box.setChecked(name in ticked)
            layout.addWidget(box)
            self.boxes[name] = box
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen(self) -> list[str]:
        """The ticked names, in order."""
        return [n for n, box in self.boxes.items() if box.isChecked()]


def add_scope_menu(menu: QMenu, field: QWidget) -> QMenu | None:
    """Add the Configurations submenu to a value field's menu (two or more configurations)."""
    session = _session_of(field)
    if session is None:
        return None
    doc = session.document
    names = configs.names(doc)
    if len(names) < 2:
        return None
    sub = menu.addMenu(text.CONFIG_SCOPE_MENU)
    sub.setObjectName("config_scope_menu")
    current = scope_of(field)
    for scope, label in text.CONFIG_SCOPE.items():
        action = sub.addAction(label)
        action.setObjectName(f"config_scope_{scope}")
        action.setCheckable(True)
        action.setChecked(current is not None and current[0] == scope)

        def choose(_c: bool = False, s: str = scope) -> None:
            if s != "chosen":
                set_scope(field, s)
                return
            dialog = ChooseConfigurations(names, [configs.active_name(doc)], field)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                set_scope(field, "chosen", dialog.chosen())
            dialog.deleteLater()  # closed dialogs stayed alive (D637)

        action.triggered.connect(choose)
    return sub


def _value(feature: Feature, path: str) -> Any:
    tail = path.partition(".")[2]
    if tail == configs.SUPPRESSED:
        return feature.suppressed
    return feature.params.get(tail)


def push_edit(session: DocumentSession, edited: Feature, fields: dict[str, QWidget]) -> None:
    """Apply a property panel edit, then any chosen scopes, as one undo step."""
    import copy

    from fdcad.ui.commands.document import ReplaceFeature
    from fdcad.ui.equations.commands import DocumentChange

    doc = session.document
    before = copy.deepcopy(doc.feature(edited.id))
    scoped: dict[str, tuple[str, list[str]]] = {}
    for name, field in fields.items():
        chosen = scope_of(field)
        if chosen is not None:
            scoped[f"{edited.id}.{name}"] = chosen
    paths = [p for p in configs.changed_paths(before, edited) if p in scoped]
    if len(configs.names(doc)) < 2 or not paths:
        session.undo.push(ReplaceFeature(session, edited))
        return

    def change(work: Any) -> None:
        for path in paths:
            scope, names = scoped[path]
            configs.set_scoped(
                work, path, _value(edited, path), scope, names, old=_value(before, path)
            )

    session.undo.beginMacro(f"Edit {edited.name}")
    session.undo.push(ReplaceFeature(session, edited))
    session.undo.push(DocumentChange(session, f"Edit {edited.name}", change))
    session.undo.endMacro()


def add_suppress_items(menu: QMenu, session: DocumentSession, feature: Feature) -> None:
    """Suppress or unsuppress in the active configuration only (tree menu, two or more)."""
    from fdcad.ui.equations.commands import DocumentChange

    doc = session.document
    if len(configs.names(doc)) < 2:
        return
    label = text.CONFIG_UNSUPPRESS_THIS if feature.suppressed else text.CONFIG_SUPPRESS_THIS
    action = menu.addAction(label)
    action.setObjectName("suppress_this_configuration")
    path = f"{feature.id}.{configs.SUPPRESSED}"
    wanted = not feature.suppressed

    def run(_c: bool = False) -> None:
        session.undo.push(
            DocumentChange(
                session,
                f"{label} ({feature.name})",
                lambda work: configs.set_scoped(work, path, wanted, "this"),
            )
        )

    action.triggered.connect(run)
