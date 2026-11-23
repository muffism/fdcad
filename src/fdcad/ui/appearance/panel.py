"""Appearance panel (PHASE2_SPEC P2.11, D254).

Choose what to colour (the part, a body, a feature or the selected faces),
pick a colour from the swatches or the colour dialog, or remove a colour so
the next less specific one shows. Below, every colour in use is listed. Each
change is one undoable command and needs no rebuild.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.appearance import Target, appearance_entries, color_of, part_color
from fdcad.ui import strings
from fdcad.ui.appearance.commands import SetAppearance
from fdcad.ui.appearance.entries import (
    LABEL_ROLE,
    TARGETS_ROLE,
    DeleteKeyFilter,
    change_color,
    entry_menu,
    row_targets,
    set_color,
)
from fdcad.ui.appearance.tree_rows import swatch
from fdcad.ui.icons import icon

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

#: Quick colours, chosen for FDCAD (not taken from any other program).
SWATCHES = (
    "#B4BCC4",
    "#5B6770",
    "#2F3439",
    "#E8E4DC",
    "#C8553D",
    "#E59A2F",
    "#E8C547",
    "#6BA368",
    "#3E8E8A",
    "#3A6EA5",
    "#6C5B9E",
    "#B85C8A",
)


class AppearancePanel(QWidget):
    """Edits the colours of the open part."""

    closed = Signal()

    def __init__(
        self,
        session: DocumentSession,
        targets: list[tuple[str, list[Target]]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("appearance_panel")
        self.session = session
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{strings.APPEARANCE_TITLE}</b>"), 1)
        self.close_button = QPushButton(icon("corner.ok"), strings.APPEARANCE_DONE)
        self.close_button.clicked.connect(self.closed.emit)
        header.addWidget(self.close_button)
        layout.addLayout(header)
        layout.addWidget(QLabel(strings.APPEARANCE_TARGET))
        self.target = QComboBox()
        self.targets = targets
        for label, _t in targets:
            self.target.addItem(label)
        self.target.currentIndexChanged.connect(lambda _i: self.refresh())
        layout.addWidget(self.target)
        self.current = QLabel()
        layout.addWidget(self.current)
        grid = QGridLayout()
        self.swatches: list[QPushButton] = []
        for i, color in enumerate(SWATCHES):
            b = QPushButton()
            b.setFixedSize(28, 22)
            b.setToolTip(color)
            b.setStyleSheet(f"QPushButton {{ background: {color}; }}")
            b.clicked.connect(lambda _c=False, c=color: self.apply(c))
            grid.addWidget(b, i // 6, i % 6)
            self.swatches.append(b)
        layout.addLayout(grid)
        buttons = QHBoxLayout()
        self.more = QPushButton(strings.APPEARANCE_MORE)
        self.more.clicked.connect(self._dialog)
        self.remove = QPushButton(strings.APPEARANCE_REMOVE)
        self.remove.setToolTip(strings.APPEARANCE_REMOVE_TIP)
        self.remove.clicked.connect(lambda: self.apply(None))
        buttons.addWidget(self.more)
        buttons.addWidget(self.remove)
        layout.addLayout(buttons)
        layout.addWidget(QLabel(strings.APPEARANCE_IN_USE))
        self.in_use = QListWidget()
        self.in_use.setToolTip(strings.APPEARANCE_IN_USE_TIP)
        self.in_use.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.in_use.customContextMenuRequested.connect(self._row_menu)
        self.in_use.itemDoubleClicked.connect(self._row_change)
        self._delete_filter = DeleteKeyFilter(self.remove_selected_row, self)
        self.in_use.installEventFilter(self._delete_filter)
        layout.addWidget(self.in_use)
        layout.addStretch(1)
        session.display_changed.connect(self.refresh)
        self.refresh()

    @property
    def chosen(self) -> list[Target]:
        """The targets of the current choice."""
        index = self.target.currentIndex()
        return self.targets[index][1] if 0 <= index < len(self.targets) else []

    def select_kind(self, kind: str) -> None:
        """Choose the first target of ``kind`` (part, body, feature or face)."""
        for i, (_label, targets) in enumerate(self.targets):
            if targets and targets[0].kind == kind:
                self.target.setCurrentIndex(i)
                return

    def apply(self, color: str | None) -> None:
        """Set ``color`` (None removes it) on the chosen targets, as one undoable step."""
        targets = self.chosen
        if not targets:
            return
        app = self.session.document.appearance
        if all(color_of(app, t) == color for t in targets):
            return
        label = self.target.currentText()
        word = strings.APPEARANCE_SET if color else strings.APPEARANCE_CLEARED
        self.session.undo.push(SetAppearance(self.session, targets, color, word.format(item=label)))

    def _row(self, item: QListWidgetItem | None) -> tuple[list[Target], str]:
        if item is None:
            return [], ""
        return row_targets(item.data(TARGETS_ROLE)), str(item.data(LABEL_ROLE) or "")

    def remove_selected_row(self) -> None:
        """Remove the colour of the selected row of the colours in use (Delete key)."""
        targets, label = self._row(self.in_use.currentItem())
        set_color(self.session, targets, None, label)

    def _row_change(self, item: QListWidgetItem) -> None:
        targets, label = self._row(item)
        change_color(self.session, targets, label, self)

    def row_menu(self, item: QListWidgetItem | None) -> QMenu | None:
        """The right click menu of a row of the colours in use (tests use this)."""
        targets, label = self._row(item)
        return entry_menu(self, self.session, targets, label) if targets else None

    def _row_menu(self, pos: QPoint) -> None:
        menu = self.row_menu(self.in_use.itemAt(pos))
        if menu is not None:
            menu.exec(self.in_use.viewport().mapToGlobal(pos))

    def _dialog(self) -> None:
        start = QColor(self._shown_color())
        chosen = QColorDialog.getColor(start, self, strings.APPEARANCE_TITLE)
        if chosen.isValid():
            self.apply(chosen.name().upper())

    def _shown_color(self) -> str:
        app = self.session.document.appearance
        targets = self.chosen
        own = color_of(app, targets[0]) if targets else None
        return own or part_color(app)

    def refresh(self) -> None:
        """Show the chosen target's colour and the colours in use."""
        app = self.session.document.appearance
        targets = self.chosen
        own = color_of(app, targets[0]) if targets else None
        text = own if own else strings.APPEARANCE_INHERITED
        self.current.setText(strings.APPEARANCE_CURRENT.format(color=text))
        self.remove.setEnabled(bool(own) and bool(targets) and targets[0].kind != "part")
        names = {f.id: f.name for f in self.session.document.features}
        row = self.in_use.currentRow()
        self.in_use.clear()
        for color, label, carriers in appearance_entries(app, names):
            item = QListWidgetItem(swatch(color), f"{label}: {color}")
            item.setData(TARGETS_ROLE, carriers)
            item.setData(LABEL_ROLE, label)
            self.in_use.addItem(item)
        if 0 <= row < self.in_use.count():
            self.in_use.setCurrentRow(row)


def targets_for(
    session: DocumentSession, faces: list[str], feature: str | None
) -> list[tuple[str, list[Target]]]:
    """The target list: selected faces, the selected feature, each body, then the part."""
    out: list[tuple[str, list[Target]]] = []
    if faces:
        label = strings.APPEARANCE_FACES.format(count=len(faces))
        out.append((label, [Target("face", n) for n in faces]))
    doc = session.document
    if feature is not None:
        out.append((doc.feature(feature).name, [Target("feature", feature)]))
    report = session.report
    count = report.body_count if report is not None else 0
    for i in range(count if count > 1 else 0):
        out.append((strings.BODY.format(index=i + 1), [Target("body", str(i + 1))]))
    out.append((strings.APPEARANCE_PART, [Target("part")]))
    return out


def effective_color(session: DocumentSession, targets: list[Target]) -> str:
    """The colour shown for the first target, for Copy Appearance."""
    app: dict[str, Any] = session.document.appearance
    for t in targets[:1]:
        own = color_of(app, t)
        if own:
            return own
        if t.kind == "face":
            # A face shows its feature's or its body's colour when it has none of its own.
            shown = _shown_face_color(session, t.key)
            if shown:
                return shown
    return part_color(app)


def _shown_face_color(session: DocumentSession, name: str) -> str | None:
    """The colour drawn on face ``name`` (face, feature or body colour), or None."""
    from fdcad.core.appearance import face_colors

    report = session.report
    body = report.body if report is not None else None
    face = body.face(name) if body is not None else None
    if body is None or face is None:
        return None
    from fdcad.core.appearance import propagating

    doc = session.document
    for shape, color in face_colors(body, doc.appearance, propagating(doc)):
        if shape.IsSame(face):
            return color
    return None
