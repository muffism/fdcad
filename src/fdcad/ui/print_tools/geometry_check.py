"""Geometry Check in the Evaluate tab (PLAN section 5A item 10, DECISIONS D356).

A tool window lists the problems found on every body; clicking one highlights
it in the 3D view. The check runs in the background and changes nothing.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings_print as text
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.core.geometry_check import GeometryIssue
    from fdcad.ui.main_window.window import MainWindow

_ROLE = Qt.ItemDataRole.UserRole


def _limit_box(value: float) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(0.0001, 10.0)
    box.setDecimals(4)
    box.setSingleStep(0.001)
    box.setSuffix(" mm")
    box.setValue(value)
    return box


def _angle_box(value: float) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(0.01, 45.0)
    box.setDecimals(2)
    box.setSuffix(" deg")
    box.setValue(value)
    return box


class GeometryCheck(QObject):
    """The Geometry Check tool window."""

    def __init__(self, window: MainWindow) -> None:
        from fdcad.core.geometry_check import SLIVER_WIDTH, TINY_EDGE

        super().__init__(window)
        self.window = window
        self.issues: list[GeometryIssue] = []
        self.generation = 0
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("geometry_check")
        self.panel.setWindowTitle(text.CHECK_TITLE)
        layout = QVBoxLayout(self.panel)
        form = QFormLayout()
        self.sliver_box = _limit_box(SLIVER_WIDTH)
        self.edge_box = _limit_box(TINY_EDGE)
        form.addRow(text.CHECK_SLIVER_LABEL, self.sliver_box)
        form.addRow(text.CHECK_EDGE_LABEL, self.edge_box)
        # TR87 and TR262 (D1416): more classes with typed limits.
        from fdcad.core.geometry_check import KNIFE_ANGLE, NEAR_SMOOTH
        from fdcad.ui import strings

        self.curve_check = QCheckBox(strings.CHECK_CURVE_LABEL)
        self.curve_box = _limit_box(1.0)
        form.addRow(self.curve_check, self.curve_box)
        self.knife_box = _angle_box(math.degrees(KNIFE_ANGLE))
        form.addRow(strings.CHECK_KNIFE_LABEL, self.knife_box)
        self.smooth_box = _angle_box(math.degrees(NEAR_SMOOTH))
        form.addRow(strings.CHECK_SMOOTH_LABEL, self.smooth_box)
        from fdcad.core.geometry_check import NEAR_SQUARE

        self.square_box = _angle_box(math.degrees(NEAR_SQUARE))  # TR262 (D2303)
        form.addRow(strings.CHECK_SQUARE_LABEL, self.square_box)
        layout.addLayout(form)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.currentItemChanged.connect(self._picked)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.back_button = QPushButton(strings.CHECK_BACK)
        self.back_button.clicked.connect(lambda: self.step(-1))
        self.next_button = QPushButton(strings.CHECK_NEXT)
        self.next_button.clicked.connect(lambda: self.step(1))
        self.fix_button = QPushButton(strings.CHECK_FIX)
        self.fix_button.setToolTip(strings.CHECK_FIX_TIP)
        self.fix_button.clicked.connect(self.fix)
        self.ignore_button = QPushButton(strings.CHECK_IGNORE)
        self.ignore_button.setToolTip(strings.CHECK_IGNORE_TIP)
        self.ignore_button.clicked.connect(self.ignore)
        for button in (self.back_button, self.next_button, self.fix_button, self.ignore_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.clip_check = QCheckBox(strings.CHECK_CLIP)  # TR262 (D2303)
        self.clip_check.setToolTip(strings.CHECK_CLIP_TIP)
        self.clip_check.toggled.connect(self._clip_toggled)
        layout.addWidget(self.clip_check)
        #: The section the view had before the tour clipped it, put back after.
        self._saved_clip: object | None = None
        self._clipping = False
        self.panel.installEventFilter(self)
        #: Findings marked Ignore, by kind and message, for this session.
        self.ignored: set[tuple[str, str]] = set()
        self.run_button = QPushButton(text.CHECK_RUN)
        self.run_button.clicked.connect(self.run)
        layout.addWidget(self.run_button)
        self.symmetry_button = QPushButton(strings.CHECK_SYMMETRY)
        self.symmetry_button.setToolTip(strings.CHECK_SYMMETRY_TIP)
        self.symmetry_button.clicked.connect(self.check_symmetry)
        layout.addWidget(self.symmetry_button)
        self.panel.resize(420, 360)

    def open(self) -> None:
        """Show the window and check the part."""
        self.panel.show()
        self.panel.raise_()
        self.run()

    def run(self) -> None:
        """Check every body of the current part in the background."""
        from fdcad.core.geometry_check import check

        self.generation += 1
        self.list.clear()
        self.issues = []
        tab = self.window.current
        report = tab.session.report if tab is not None else None
        if tab is None or report is None or report.body is None:
            self.summary.setText(text.CHECK_NOTHING)
            return
        shape = report.body.shape
        sliver, tiny = self.sliver_box.value(), self.edge_box.value()
        from fdcad.core.geometry_check import Limits

        limits = Limits(
            curvature=self.curve_box.value() if self.curve_check.isChecked() else None,
            knife=math.radians(self.knife_box.value()),
            near_smooth=math.radians(self.smooth_box.value()),
            near_square=math.radians(self.square_box.value()),
        )
        generation = self.generation
        self.summary.setText(text.CHECK_WORKING)

        def done(result: tuple[list[GeometryIssue], int]) -> None:
            if generation == self.generation:
                self._show(*result)

        def failed(message: str) -> None:
            if generation == self.generation:
                self.summary.setText(text.CHECK_FAILED.format(reason=message))

        jobs.start(lambda: check(shape, sliver=sliver, tiny=tiny, limits=limits), done, failed)

    def _show(self, issues: list[GeometryIssue], bodies: int) -> None:
        issues = [i for i in issues if (i.kind, i.message) not in self.ignored]
        self.issues = issues
        if not issues:
            noun = "the body" if bodies == 1 else f"{bodies} bodies"
            message = text.CHECK_CLEAN.format(bodies=noun)
        else:
            message = text.CHECK_FOUND.format(count=len(issues))
        self.summary.setText(message)
        self.window.status.setText(message)
        for index, issue in enumerate(issues):
            item = QListWidgetItem(issue.message)
            item.setData(_ROLE, index)
            self.list.addItem(item)

    def _picked(self, item: QListWidgetItem | None, _old: Any = None) -> None:
        tab = self.window.current
        if tab is None:
            return
        shapes = [] if item is None else [self.issues[int(item.data(_ROLE))].shape]
        tab.viewport.check_highlight = shapes
        highlight = getattr(tab.viewport, "highlight", None)
        if highlight is not None:
            highlight(shapes)

    # TR262 (D1416): tour, Fix and Ignore ---------------------------------------------

    def step(self, delta: int) -> None:
        """Next or Back through the findings; the view zooms to each."""
        count = self.list.count()
        if not count:
            return
        row = (self.list.currentRow() + delta) % count
        self.list.setCurrentRow(row)
        tab = self.window.current
        item = self.list.item(row)
        if tab is not None and item is not None:
            zoom = getattr(tab.viewport, "zoom_to", None)
            if zoom is not None:
                zoom([self.issues[int(item.data(_ROLE))].shape])
            if self.clip_check.isChecked():
                self._clip_to(self.issues[int(item.data(_ROLE))].shape)

    # TR262 (D2303): the clip box of the tour ---------------------------------------

    def _clip_to(self, shape: Any) -> None:
        """Clip the view to a box round ``shape`` (display only, the part is not cut)."""
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        from fdcad.core.geometry_check import clip_box
        from fdcad.ui.viewport.section_view import clip_chains

        tab = self.window.current
        setter = getattr(tab.viewport, "set_section", None) if tab is not None else None
        if tab is None or setter is None:
            return
        box = Bnd_Box()
        BRepBndLib.Add_s(shape, box)
        if box.IsVoid():
            return
        lo, hi = box.CornerMin(), box.CornerMax()
        planes = clip_box((lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z()))
        if not self._clipping:
            self._saved_clip = getattr(tab.viewport, "_section_clip", None)
            self._clipping = True
        setter(clip_chains([[p] for p in planes], False))  # type: ignore[list-item]

    def unclip(self) -> None:
        """Put back the view's own section, if the tour clipped it."""
        if not self._clipping:
            return
        self._clipping = False
        tab = self.window.current
        setter = getattr(tab.viewport, "set_section", None) if tab is not None else None
        if setter is not None:
            setter(self._saved_clip)
        self._saved_clip = None

    def _clip_toggled(self, on: bool) -> None:
        if not on:
            self.unclip()
            return
        issue = self.current_issue()
        if issue is not None:
            self._clip_to(issue.shape)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt name)
        """Put the view back when the window is closed."""
        if watched is self.panel and event.type() == QEvent.Type.Hide:
            self.unclip()
        return False

    def current_issue(self) -> GeometryIssue | None:
        """The selected finding."""
        item = self.list.currentItem()
        return None if item is None else self.issues[int(item.data(_ROLE))]

    def fix(self) -> bool:
        """Fix the selected finding where a fix exists: a sliver or duplicate face is
        removed by a new Delete Face feature (one undo step). Nothing changes until
        the user clicks (CLAUDE.md 5.12)."""
        from fdcad.core.document.model import Feature
        from fdcad.core.features.names import default_name
        from fdcad.core.naming.select import reference_for
        from fdcad.ui import strings
        from fdcad.ui.commands.document import AddFeature

        issue = self.current_issue()
        tab = self.window.current
        report = tab.session.report if tab is not None else None
        if issue is None or tab is None or report is None or report.body is None:
            return False
        if issue.kind in ("gap", "inexact") and "open edge" not in issue.message:
            return self._heal(issue)  # TR262 (D1807)
        if issue.kind in ("not_smooth", "not_square") and issue.turn is not None:
            return self._turn(issue, report.body)  # TR262 (D2303)
        if issue.kind not in ("sliver", "duplicate"):
            self.summary.setText(strings.CHECK_NO_FIX)
            return False
        ref = reference_for(report.body, issue.shape)
        if ref is None:
            self.summary.setText(strings.CHECK_NO_FIX)
            return False
        doc = tab.session.document
        feature = Feature(
            doc.new_feature_id(),
            "delete_face",
            default_name(doc, "delete_face"),
            params={"option": "patch"},
            refs={"faces": [ref]},
        )
        tab.session.undo.push(AddFeature(tab.session, feature))
        self.summary.setText(strings.CHECK_FIXED.format(name=feature.name))
        return True

    def _heal(self, issue: GeometryIssue) -> bool:
        """Add a Heal Edges feature whose tolerance covers the edge's gap (TR262, D1807)."""
        import math

        from OCP.BRep import BRep_Tool
        from OCP.TopoDS import TopoDS

        from fdcad.core.document.model import Feature, Param
        from fdcad.core.features.heal_edges import DEFAULT_TOLERANCE
        from fdcad.core.features.names import default_name
        from fdcad.ui import strings_finish as finish
        from fdcad.ui.commands.document import AddFeature

        tab = self.window.current
        if tab is None:
            return False
        gap = BRep_Tool.Tolerance_s(TopoDS.Edge(issue.shape))
        # A little over the gap, rounded up to two significant digits.
        wanted = max(DEFAULT_TOLERANCE, gap * 1.1)
        step = 10 ** (math.floor(math.log10(wanted)) - 1)
        value = round(math.ceil(round(wanted / step, 6)) * step, 9)
        doc = tab.session.document
        feature = Feature(
            doc.new_feature_id(),
            "heal_edges",
            default_name(doc, "heal_edges"),
            params={"tolerance": Param(f"{value:g}", value)},
        )
        tab.session.undo.push(AddFeature(tab.session, feature))
        self.summary.setText(finish.CHECK_HEALED.format(name=feature.name))
        return True

    def _turn(self, issue: GeometryIssue, body: Any) -> bool:
        """Add a Move Face that turns one flat face about the edge, so the edge becomes
        exactly smooth or exactly square (TR262, D2303). Only on click (CLAUDE.md 5.12)."""
        from fdcad.core.document.model import Feature, Param
        from fdcad.core.features.names import default_name
        from fdcad.core.naming.select import reference_for
        from fdcad.ui import strings
        from fdcad.ui.commands.document import AddFeature

        tab = self.window.current
        if tab is None or issue.turn is None:
            return False
        face, angle = issue.turn
        face_ref, edge_ref = reference_for(body, face), reference_for(body, issue.shape)
        if face_ref is None or edge_ref is None:
            self.summary.setText(strings.CHECK_NO_FIX)
            return False
        doc = tab.session.document
        feature = Feature(
            doc.new_feature_id(),
            "move_face",
            default_name(doc, "move_face"),
            params={
                "mode": "rotate",
                "angle": Param(f"{math.degrees(angle):.10g} deg", angle),
            },
            refs={"faces": [face_ref], "axis": edge_ref},
        )
        tab.session.undo.push(AddFeature(tab.session, feature))
        self.summary.setText(strings.CHECK_TURNED.format(name=feature.name))
        return True

    def ignore(self) -> None:
        """Mark the selected finding Ignore: it is not listed again in this session."""
        issue = self.current_issue()
        row = self.list.currentRow()
        if issue is None:
            return
        self.ignored.add((issue.kind, issue.message))
        self.list.takeItem(row)

    def check_symmetry(self) -> str | None:
        """Symmetry Check about the selected flat face's plane (TR87 item 3, D1416)."""
        from fdcad.core.geometry_check import GeometryIssue, symmetry
        from fdcad.core.naming.select import is_planar_face
        from fdcad.core.plane_normal import plane_normal
        from fdcad.ui import strings

        tab = self.window.current
        report = tab.session.report if tab is not None else None
        selection = list(getattr(tab, "selection", [])) if tab is not None else []
        planes = [s for s in selection if is_planar_face(s)]
        if tab is None or report is None or report.body is None or not planes:
            self.summary.setText(strings.CHECK_SYMMETRY_PICK)
            return strings.CHECK_SYMMETRY_PICK
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        face = planes[0]
        normal = plane_normal(face)
        assert normal is not None
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        c = props.CentreOfMass()
        shape = report.body.shape
        self.generation += 1
        generation = self.generation
        self.summary.setText(text.CHECK_WORKING)

        def done(result: tuple[bool, list[Any]]) -> None:
            if generation != self.generation:
                return
            same, differ = result
            self.list.clear()
            self.issues = [
                GeometryIssue("differs", f, 1, strings.CHECK_SYMMETRY_FACE.format(k=k))
                for k, f in enumerate(differ, start=1)
            ]
            for index, issue in enumerate(self.issues):
                item = QListWidgetItem(issue.message)
                item.setData(_ROLE, index)
                self.list.addItem(item)
            message = (
                strings.CHECK_SYMMETRIC
                if same
                else strings.CHECK_NOT_SYMMETRIC.format(count=len(differ))
            )
            self.summary.setText(message)
            self.window.status.setText(message)

        def failed(message: str) -> None:
            if generation == self.generation:
                self.summary.setText(text.CHECK_FAILED.format(reason=message))

        point = (c.X(), c.Y(), c.Z())
        jobs.start(lambda: symmetry(shape, point, normal), done, failed)
        return None
