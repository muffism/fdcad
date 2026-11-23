"""File, Save Image: the 3D view as a PNG (TUTORIAL_REVIEW_SPEC TR24, D689)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui.viewport.image_export import MAX_SIDE, checked_size

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

TITLE = "Save Image"
WINDOW_SIZE = "Size of the view ({w} x {h} pixels)"
CHOSEN_SIZE = "Chosen size"
WIDTH = "Width (pixels)"
HEIGHT = "Height (pixels)"
BACKGROUND = "Include the background"
BACKGROUND_TIP = "Off saves a PNG that is see through where the background was."
FILTER = "PNG image (*.png)"
SAVED = "Saved the view as {name}."
NO_VIEW = "Save Image needs an open part with a 3D view. Open a part and try again."
FAILED = "The view could not be saved as {name}. Choose another folder or a smaller size."


@dataclass
class ImageOptions:
    """What the dialog asks for."""

    width: int
    height: int
    background: bool = True


class SaveImageDialog(QDialog):
    """Size (the view's, or chosen) and whether to keep the background."""

    def __init__(self, view_size: tuple[int, int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.view_size = view_size
        layout = QVBoxLayout(self)
        self.window_size = QRadioButton(WINDOW_SIZE.format(w=view_size[0], h=view_size[1]))
        self.window_size.setChecked(True)
        self.chosen = QRadioButton(CHOSEN_SIZE)
        layout.addWidget(self.window_size)
        layout.addWidget(self.chosen)
        form = QFormLayout()
        self.width_box, self.height_box = QSpinBox(), QSpinBox()
        for box, value in ((self.width_box, view_size[0]), (self.height_box, view_size[1])):
            box.setRange(1, MAX_SIDE)
            box.setValue(max(1, value))
            box.setEnabled(False)
        form.addRow(WIDTH, self.width_box)
        form.addRow(HEIGHT, self.height_box)
        layout.addLayout(form)
        self.chosen.toggled.connect(self.width_box.setEnabled)
        self.chosen.toggled.connect(self.height_box.setEnabled)
        self.background = QCheckBox(BACKGROUND)
        self.background.setChecked(True)
        self.background.setToolTip(BACKGROUND_TIP)
        layout.addWidget(self.background)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> ImageOptions:
        """The chosen size and background."""
        if self.chosen.isChecked():
            w, h = self.width_box.value(), self.height_box.value()
        else:
            w, h = self.view_size
        return ImageOptions(w, h, self.background.isChecked())


def save_view_image(viewport: object, path: str, options: ImageOptions) -> str:
    """Render and write the PNG. Returns "" on success, else the message to show."""
    problem = checked_size(options.width, options.height)
    if problem:
        return problem
    render = getattr(viewport, "render_image", None)
    if render is None:
        return NO_VIEW
    image = render(options.width, options.height, options.background)
    name = Path(path).name
    if image is None or not image.save(path, "PNG"):
        return FAILED.format(name=name)
    return ""


def save_image(window: MainWindow) -> bool:
    """Ask for the size and a file, then save the active part's view."""
    tab = window.current
    viewport = getattr(tab, "viewport", None)
    size = getattr(viewport, "view_pixels", None)
    if tab is None or size is None:
        window.status.setText(NO_VIEW)
        return False
    dialog = SaveImageDialog(size(), window)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    options = dialog.options()
    dialog.deleteLater()  # closed dialogs stayed alive (D637, audit D8 item 2)
    if not accepted:
        return False
    start = str(Path(tab.session.path).with_suffix(".png")) if tab.session.path else ""
    path, _filter = QFileDialog.getSaveFileName(window, TITLE, start, FILTER)
    if not path:
        return False
    if not path.lower().endswith(".png"):
        path += ".png"
    problem = save_view_image(viewport, path, options)
    window.status.setText(problem or SAVED.format(name=Path(path).name))
    return not problem
