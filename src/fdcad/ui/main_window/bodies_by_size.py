"""Select Bodies by Size (TR70, D894): a slider sets a size limit as a percent of the
largest body; the bodies below (or above) it can be selected, deleted or kept in one
step. Volumes are worked out in the background (CLAUDE.md rule 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.body_sizes import BodySize, pick
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


class BodiesBySizeDialog(QDialog):
    """The size limit, which side, and Select, Delete or Keep."""

    def __init__(self, window: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent or window)
        self.window_ = window
        self.bodies: list[BodySize] = []
        self.setWindowTitle(strings.BODY_SIZE_TITLE)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(10)
        self.side = QComboBox()
        self.side.addItem(strings.BODY_SIZE_SMALLER, False)
        self.side.addItem(strings.BODY_SIZE_LARGER, True)
        self.count = QLabel(strings.BODY_SIZE_WORKING)
        form = QFormLayout()
        form.addRow(strings.BODY_SIZE_LIMIT, self.slider)
        form.addRow(strings.BODY_SIZE_SIDE, self.side)
        form.addRow(self.count)
        self.buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout()
        for key, label in strings.BODY_SIZE_BUTTONS.items():
            button = QPushButton(label)
            button.setEnabled(False)
            button.clicked.connect(lambda _c=False, k=key: self.act(k))
            self.buttons[key] = button
            row.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(row)
        self.slider.valueChanged.connect(lambda _v: self.refresh())
        self.side.currentIndexChanged.connect(lambda _i: self.refresh())

    def set_bodies(self, bodies: list[BodySize]) -> None:
        """The part's bodies, once worked out."""
        self.bodies = bodies
        self.refresh()

    def chosen(self) -> list[BodySize]:
        """The bodies the limit picks now."""
        return pick(self.bodies, float(self.slider.value()), bool(self.side.currentData()))

    def refresh(self) -> None:
        """Count the picked bodies and enable the buttons."""
        found = self.chosen()
        self.count.setText(
            strings.BODY_SIZE_COUNT.format(
                n=len(found), total=len(self.bodies), percent=self.slider.value()
            )
        )
        for button in self.buttons.values():
            button.setEnabled(bool(found))

    def act(self, key: str) -> bool:
        """Select the picked bodies, or delete or keep them as one feature."""
        window = self.window_
        tab = window.current
        found = [b for b in self.chosen() if b.ref is not None]
        if tab is None or not found:
            return False
        if key == "select":
            report = tab.session.report
            if report is None or report.body is None:
                return False
            from fdcad.core.features.solids import solids

            shapes = [solids(report.body.shape)[b.index] for b in found]
            tab.selection = shapes
            select = getattr(tab.viewport, "select_shapes", None)
            if select is not None:
                select(shapes)
            return True
        from fdcad.core.document.model import Feature
        from fdcad.core.features.names import default_name
        from fdcad.ui.commands.document import AddFeature

        doc = tab.session.document
        feature = Feature(
            doc.new_feature_id(),
            "delete_body",
            default_name(doc, "delete_body"),
            params={"option": "delete" if key == "delete" else "keep"},
            refs={"bodies": [b.ref for b in found]},
        )
        tab.session.undo.push(AddFeature(tab.session, feature))
        self.accept()
        return True


def open_dialog(window: MainWindow) -> BodiesBySizeDialog | None:
    """Show the dialog and work out the body sizes in the background."""
    from fdcad.core.body_sizes import sizes
    from fdcad.ui.print_tools import jobs

    tab = window.current
    report = tab.session.report if tab is not None else None
    if report is None or report.body is None:
        window.status.setText(strings.BODY_SIZE_EMPTY)
        return None
    dialog = BodiesBySizeDialog(window)
    body = report.body

    def done(result: Any) -> None:
        dialog.set_bodies(list(result))

    def failed(message: str) -> None:
        dialog.count.setText(strings.BODY_SIZE_FAILED.format(reason=message))

    jobs.start(lambda: sizes(body), done, failed)
    dialog.show()
    return dialog
