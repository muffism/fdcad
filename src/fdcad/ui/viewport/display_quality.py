"""Display quality of a part (TR214, D1605).

A per part value from 1 (coarse, fast) to 10 (fine), saved in the part file
under ``appearance.display_quality`` (5, the old fineness, is not stored). The
dialog shows the chord deviation each step gives for this part. Large parts are
also drawn with less smoothing while the view turns (see the 3D view).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QSlider, QVBoxLayout, QWidget

from fdcad.core.document.model import Document
from fdcad.ui.commands.document import DocumentCommand
from fdcad.ui.viewport.meshing import QUALITY_DEFAULT, QUALITY_MAX, QUALITY_MIN, deviation_for

KEY = "display_quality"
TITLE = "Display Quality"
INTRO = "Drag to the right to draw curved faces more finely. Finer drawing is slower."
DEVIATION = "Quality {quality} of 10: faces stay within {deviation} of the true shape."
UNDO = "Display Quality"
CHANGED = "Display quality set to {quality}. The part is drawn again."
#: Parts with more faces than this draw with less smoothing while the view turns.
LARGE_FACES = 1500


def quality_of(doc: Document) -> int:
    """The part's display quality, 1 to 10."""
    value = doc.appearance.get(KEY, QUALITY_DEFAULT)
    if isinstance(value, bool) or not isinstance(value, int):
        return QUALITY_DEFAULT
    return max(QUALITY_MIN, min(QUALITY_MAX, value))


def set_quality(doc: Document, quality: int) -> None:
    """Store a display quality; the default is not stored."""
    if quality == QUALITY_DEFAULT:
        doc.appearance.pop(KEY, None)
    else:
        doc.appearance[KEY] = int(quality)


class SetDisplayQuality(DocumentCommand):
    """Change the part's display quality: one undo step that draws the part again."""

    def __init__(self, session: Any, quality: int) -> None:
        super().__init__(session, UNDO)
        self.before = quality_of(session.document)
        self.after = quality

    def apply(self) -> None:
        """Store the new quality."""
        set_quality(self.session.document, self.after)

    def revert(self) -> None:
        """Store the old quality."""
        set_quality(self.session.document, self.before)

    def redo(self) -> None:
        """Mesh the part again at the new quality."""
        self.apply()
        self.session.request_rebuild()

    def undo(self) -> None:
        """Mesh the part again at the old quality."""
        self.revert()
        self.session.request_rebuild()


def deviation_text(size: float, quality: int, unit: str = "mm", scale: float = 1.0) -> str:
    """The deviation line for a part of box diagonal ``size`` (mm), in the part's unit
    (``scale`` mm per unit)."""
    value = deviation_for(size, quality) / scale
    return DEVIATION.format(quality=quality, deviation=f"{value:.3g} {unit}")


class DisplayQualityDialog(QDialog):
    """A slider from 1 to 10 with the deviation it gives for this part."""

    def __init__(
        self,
        quality: int,
        size: float,
        unit: str = "mm",
        scale: float = 1.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.part_size, self.unit, self.scale = size, unit, scale
        layout = QVBoxLayout(self)
        intro = QLabel(INTRO)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("display_quality")
        self.slider.setRange(QUALITY_MIN, QUALITY_MAX)
        self.slider.setValue(quality)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        layout.addWidget(self.slider)
        self.deviation = QLabel()
        self.deviation.setObjectName("display_quality_deviation")
        layout.addWidget(self.deviation)
        self.slider.valueChanged.connect(self._show)
        self._show(quality)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _show(self, quality: int) -> None:
        self.deviation.setText(deviation_text(self.part_size, quality, self.unit, self.scale))

    def quality(self) -> int:
        """The chosen quality."""
        return int(self.slider.value())


def run(window: Any) -> bool:
    """Display Quality for the active part. True when it changed."""
    from fdcad.core.features.solids import bounding_size

    tab = window.current
    if tab is None:
        return False
    doc = tab.session.document
    report = tab.session.report
    size = bounding_size(report.body.shape) if report is not None and report.body else 0.0
    unit = doc.units.value if hasattr(doc.units, "value") else "mm"
    scale = 25.4 if unit == "in" else 1.0
    dialog = DisplayQualityDialog(quality_of(doc), size, unit, scale, window)
    try:
        if not dialog.exec():
            return False
        quality = dialog.quality()
    finally:
        dialog.deleteLater()
    if quality == quality_of(doc):
        return False
    tab.session.undo.push(SetDisplayQuality(tab.session, quality))
    window.status.setText(CHANGED.format(quality=quality))
    return True


def is_large(shape: Any) -> bool:
    """True when ``shape`` has more than ``LARGE_FACES`` faces."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    if shape is None:
        return False
    faces = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, faces)
    return bool(faces.Extent() > LARGE_FACES)
