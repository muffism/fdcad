"""Slice Body (TR151 item 1, D1718): parallel planes, or planes round an axis (D2204),
cut the part into section sketches in a tree folder, one undo step. The cuts are
worked out off the UI thread (CLAUDE.md rule 2)."""

from __future__ import annotations

import copy
import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Feature
from fdcad.core.kernel import kernel_job
from fdcad.core.slices import (
    MAX_SLICES,
    SliceError,
    SlicePlan,
    sections,
    slice_features,
    slice_planes,
)
from fdcad.ui import strings
from fdcad.ui.background import start_job
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.session import DocumentSession


class SliceDialog(QDialog):
    """Base plane, count, spacing and start offset."""

    def __init__(
        self,
        planes: list[tuple[str, str]],
        parent: QWidget | None = None,
        axes: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.SLICE_TITLE)
        self.base = QComboBox()
        for fid, name in planes:
            self.base.addItem(name, fid)
        self.count = QSpinBox()
        self.count.setRange(1, MAX_SLICES)
        self.count.setValue(5)
        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(0.01, 10000.0)
        self.spacing.setDecimals(3)
        self.spacing.setSuffix(" mm")
        self.spacing.setValue(3.0)
        self.start = QDoubleSpinBox()
        self.start.setRange(-10000.0, 10000.0)
        self.start.setDecimals(3)
        self.start.setSuffix(" mm")
        # TR151 item 1 (D2204): planes round an axis in the base plane.
        self.axis = QComboBox()
        self.axis.addItem(strings.SLICE_PARALLEL, "")
        for fid, name in axes or []:
            self.axis.addItem(name, fid)
        self.angle_step = QDoubleSpinBox()
        self.angle_step.setRange(0.01, 360.0)
        self.angle_step.setDecimals(3)
        self.angle_step.setSuffix(" deg")
        self.angle_step.setValue(30.0)
        self.start_angle = QDoubleSpinBox()
        self.start_angle.setRange(-360.0, 360.0)
        self.start_angle.setDecimals(3)
        self.start_angle.setSuffix(" deg")
        form = QFormLayout()
        form.addRow(strings.SLICE_BASE, self.base)
        form.addRow(strings.SLICE_AXIS, self.axis)
        form.addRow(strings.SLICE_COUNT, self.count)
        form.addRow(strings.SLICE_SPACING, self.spacing)
        form.addRow(strings.SLICE_START, self.start)
        form.addRow(strings.SLICE_ANGLE_STEP, self.angle_step)
        form.addRow(strings.SLICE_START_ANGLE, self.start_angle)
        self.axis.currentIndexChanged.connect(self._axis_changed)
        self._axis_changed()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _axis_changed(self) -> None:
        around = bool(self.axis.currentData())
        for box in (self.spacing, self.start):
            box.setEnabled(not around)
        for box in (self.angle_step, self.start_angle):
            box.setEnabled(around)

    def plan(self) -> SlicePlan:
        """The slices as chosen."""
        axis = str(self.axis.currentData() or "")
        if axis:
            return SlicePlan(
                str(self.base.currentData()),
                self.count.value(),
                math.radians(self.angle_step.value()),
                math.radians(self.start_angle.value()),
                axis,
            )
        return SlicePlan(
            str(self.base.currentData()),
            self.count.value(),
            self.spacing.value(),
            self.start.value(),
        )


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


class AddSlices(DocumentCommand):
    """Add the slice planes and sketches at the end of the tree, in one new folder."""

    def __init__(self, session: DocumentSession, features: list[Feature], folder: str) -> None:
        super().__init__(session, strings.SLICE_TITLE)
        self.features = copy.deepcopy(features)
        self.tree_before = copy.deepcopy(session.document.tree)
        self.folder = folder

    def apply(self) -> None:
        """Append the features and put them in the folder."""
        from fdcad.core.document.tree_info import add_folder

        doc = self.session.document
        doc.features.extend(copy.deepcopy(self.features))
        top = [f.id for f in doc.features]
        doc.tree = add_folder(doc.tree, self.folder, [f.id for f in self.features], top)

    def revert(self) -> None:
        """Take them out again."""
        doc = self.session.document
        ids = {f.id for f in self.features}
        doc.features = [f for f in doc.features if f.id not in ids]
        doc.tree = copy.deepcopy(self.tree_before)


class _Signals(QObject):
    done = Signal(object)


class SliceJob(QRunnable):
    """Cuts the part with each slice plane."""

    def __init__(self, shape: Any, base: Any, plan: SlicePlan, axis: Any = None) -> None:
        super().__init__()
        self.shape, self.base, self.plan, self.axis = shape, base, plan, axis
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        try:
            self.signals.done.emit(sections(self.shape, self.base, self.plan, self.axis))
        except Exception:  # a kernel failure gives no slices and a message
            self.signals.done.emit(None)


_RUNNING: set[SliceJob] = set()


def planes_of(window: MainWindow) -> list[tuple[str, str]]:
    """The part's planes as (feature id, name)."""
    from fdcad.core.features.datum import PLANE_TYPES

    tab = window.current
    if tab is None:
        return []
    return [(f.id, f.name) for f in tab.session.document.features if f.type in PLANE_TYPES]


def axes_of(window: MainWindow) -> list[tuple[str, str]]:
    """The part's reference axes as (feature id, name) (TR151, D2204)."""
    tab = window.current
    if tab is None:
        return []
    return [(f.id, f.name) for f in tab.session.document.features if f.type == "ref_axis"]


def open_slices(window: MainWindow) -> SliceJob | None:
    """Ask for the slices, then work them out and add them (one undo step)."""
    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(strings.SLICE_NO_BODY)
        return None
    dialog = SliceDialog(planes_of(window), window, axes_of(window))
    accepted = run(dialog)
    plan = dialog.plan()
    dialog.deleteLater()
    if not accepted:
        return None
    result = report.results.get(plan.base)
    base = result.plane if result is not None else None
    if base is None:
        window.status.setText(strings.SLICE_NO_PLANE)
        return None
    axis = None
    if plan.axis:  # TR151 (D2204)
        found = report.results.get(plan.axis)
        datum = found.datum if found is not None else None
        if datum is None or datum.direction is None:
            window.status.setText(strings.SLICE_NO_AXIS_BUILT)
            return None
        axis = (datum.origin, datum.direction)
    try:
        slice_planes(base, plan, axis)
    except SliceError as exc:
        window.status.setText(str(exc))
        return None
    session = tab.session
    job = SliceJob(report.body.shape, base, plan, axis)

    def done(cuts: Any) -> None:
        _RUNNING.discard(job)
        if cuts is None:
            window.status.setText(strings.SLICE_FAILED)
            return
        from fdcad.core.document.tree_info import name_problem

        folder, n = "Slices", 1
        while name_problem(session.document.tree, folder):
            n += 1
            folder = f"Slices {n}"
        try:
            made = slice_features(session.document, plan, cuts)
        except SliceError as exc:
            window.status.setText(str(exc))
            return
        session.undo.push(AddSlices(session, made, folder))
        window.status.setText(strings.SLICE_DONE.format(count=len(made) // 2))

    job.signals.done.connect(done)
    _RUNNING.add(job)
    start_job(QThreadPool.globalInstance(), job)
    window.status.setText(strings.SLICE_WORKING)
    return job
