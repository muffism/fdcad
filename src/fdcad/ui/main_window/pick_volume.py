"""Pick in Volume (TR329, D2208): pick the faces, edges or vertices inside, outside or
touching a box, cylinder or sphere. The sizes are typed, starting from the part's
box; the picking runs off the UI thread (CLAUDE.md rule 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.kernel import kernel_job
from fdcad.core.pick_volume import KINDS, MODES, SHAPES, PickVolume, PickVolumeError, pick_in_volume
from fdcad.ui import strings_extra as text
from fdcad.ui.background import start_job

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def _spin(value: float, low: float = -1e6) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(low, 1e6)
    box.setDecimals(3)
    box.setSuffix(" mm")
    box.setValue(value)
    return box


def _three(values: tuple[float, float, float], low: float = -1e6) -> tuple[QWidget, list[Any]]:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    boxes = [_spin(v, low) for v in values]
    for b in boxes:
        layout.addWidget(b)
    return row, boxes


class PickVolumeDialog(QDialog):
    """The volume, what to pick and how."""

    def __init__(
        self,
        centre: tuple[float, float, float],
        size: tuple[float, float, float],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(text.PICK_VOLUME_TITLE)
        self.shape = QComboBox()
        for key in SHAPES:
            self.shape.addItem(text.PICK_VOLUME_SHAPES[key], key)
        self.mode = QComboBox()
        for key in MODES:
            self.mode.addItem(text.PICK_VOLUME_MODES[key], key)
        self.kind = QComboBox()
        for key in KINDS:
            self.kind.addItem(text.PICK_VOLUME_KINDS[key], key)
        centre_row, self.centre = _three(centre)
        size_row, self.size_boxes = _three(size, 0.001)
        self.radius = _spin(max(min(size) / 2, 0.001), 0.001)
        self.axis = QComboBox()
        for key in AXES:
            self.axis.addItem(key.upper(), key)
        self.axis.setCurrentIndex(2)
        form = QFormLayout()
        form.addRow(text.PICK_VOLUME_SHAPE, self.shape)
        form.addRow(text.PICK_VOLUME_CENTRE, centre_row)
        form.addRow(text.PICK_VOLUME_SIZE, size_row)
        form.addRow(text.PICK_VOLUME_RADIUS, self.radius)
        form.addRow(text.PICK_VOLUME_AXIS, self.axis)
        form.addRow(text.PICK_VOLUME_MODE, self.mode)
        form.addRow(text.PICK_VOLUME_KIND, self.kind)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.shape.currentIndexChanged.connect(self._shape_changed)
        self._shape_changed()

    def _shape_changed(self) -> None:
        shape = self.shape.currentData()
        for i, box in enumerate(self.size_boxes):
            box.setEnabled(shape == "box" or (shape == "cylinder" and i == 2))
        self.radius.setEnabled(shape != "box")
        self.axis.setEnabled(shape == "cylinder")

    def volume(self) -> PickVolume:
        """The volume as typed."""
        centre = tuple(b.value() for b in self.centre)
        size = tuple(b.value() for b in self.size_boxes)
        return PickVolume(
            str(self.shape.currentData()),
            (centre[0], centre[1], centre[2]),
            (size[0], size[1], size[2]),
            self.radius.value(),
            AXES[str(self.axis.currentData())],
        )


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


class _Signals(QObject):
    done = Signal(object)


class PickVolumeJob(QRunnable):
    """Finds the picked items of the part."""

    def __init__(self, shape: Any, volume: PickVolume, mode: str, kind: str) -> None:
        super().__init__()
        self.shape, self.volume, self.mode, self.kind = shape, volume, mode, kind
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        try:
            self.signals.done.emit(pick_in_volume(self.shape, self.volume, self.mode, self.kind))
        except PickVolumeError as exc:
            self.signals.done.emit(str(exc))
        except Exception:  # a kernel failure picks nothing and says so
            self.signals.done.emit(text.PICK_VOLUME_FAILED)


_RUNNING: set[PickVolumeJob] = set()


def part_box(shape: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """The centre and size of the box round ``shape`` (the dialog's starting volume)."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        return (0.0, 0.0, 0.0), (10.0, 10.0, 10.0)
    lo, hi = box.CornerMin(), box.CornerMax()
    a, b = (lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z())
    centre = tuple((a[i] + b[i]) / 2 for i in range(3))
    size = tuple(max(b[i] - a[i], 0.001) for i in range(3))
    return (centre[0], centre[1], centre[2]), (size[0], size[1], size[2])


def open_pick_volume(window: MainWindow) -> PickVolumeJob | None:
    """Ask for the volume, then pick what it holds in the current part."""
    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.PICK_VOLUME_NO_BODY)
        return None
    shape = report.body.shape
    dialog = PickVolumeDialog(*part_box(shape), parent=window)
    accepted = run(dialog)
    volume = dialog.volume()
    mode, kind = str(dialog.mode.currentData()), str(dialog.kind.currentData())
    dialog.deleteLater()
    if not accepted:
        return None
    try:
        volume.check()
    except PickVolumeError as exc:
        window.status.setText(str(exc))
        return None
    job = PickVolumeJob(shape, volume, mode, kind)

    def done(result: Any) -> None:
        _RUNNING.discard(job)
        if isinstance(result, str):
            window.status.setText(result)
            return
        current = tab.session.report
        if current is None or current.body is None or current.body.shape is not shape:
            window.status.setText(text.PICK_VOLUME_CHANGED)
            return
        select = getattr(tab.viewport, "select_shapes", None)
        if select is not None:
            select(result)
            changed = getattr(tab.viewport, "selection_changed", None)
            selected = getattr(tab.viewport, "selected", None)
            if changed is not None and selected is not None:
                changed.emit(selected())
        window.status.setText(text.PICK_VOLUME_DONE.format(count=len(result)))

    job.signals.done.connect(done)
    _RUNNING.add(job)
    start_job(QThreadPool.globalInstance(), job)
    window.status.setText(text.PICK_VOLUME_WORKING)
    return job
