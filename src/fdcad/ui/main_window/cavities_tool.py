"""Enclosed Cavities on the Evaluate tab (TR284, DECISIONS D772).

Find lists the closed voids in the part's bodies with their volume; clicking one
shows it in the view, and Add Drain Hole adds a small hole that drains it, as an
ordinary undoable Hole feature (a fix is offered, never applied by itself,
CLAUDE.md 5.12). Cup Volume gives the volume the picked faces hold below their
top, level with the Top Plane, or below a chosen plane.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.print_tools import jobs, overlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.core.cavities import Void
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

_LAYER = "cavities"
COLOUR = DATA["draft_straddle"]
TOP = "__top__"


def _volume(mm3: float, inch: bool) -> str:
    return f"{mm3 / 25.4**3:.4g} in^3" if inch else f"{mm3:.4g} mm^3"


class CavitiesTool(QObject):
    """The window, its jobs and the overlay."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.voids: list[Void] | None = None
        self.cup: float | None = None
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("cavities_panel")
        self.panel.setWindowTitle(strings.CAVITY_TITLE)
        form = QFormLayout(self.panel)
        self.find = QPushButton(strings.CAVITY_FIND)
        self.drain = QPushButton(strings.CAVITY_DRAIN)
        self.drain.setToolTip(strings.CAVITY_DRAIN_TIP)
        row = QHBoxLayout()
        row.addWidget(self.find)
        row.addWidget(self.drain)
        self.found = QListWidget()
        self.found.setObjectName("cavities_found")
        self.plane = QComboBox()
        self.cup_button = QPushButton(strings.CAVITY_CUP)
        self.cup_button.setToolTip(strings.CAVITY_CUP_TIP)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow(row)
        form.addRow(self.found)
        form.addRow(strings.CAVITY_OPENING, self.plane)
        form.addRow(self.cup_button)
        form.addRow(self.summary)
        self.find.clicked.connect(self.search)
        self.drain.clicked.connect(self.add_drain)
        self.cup_button.clicked.connect(self.measure_cup)
        self.found.currentRowChanged.connect(self.show_row)
        window.tabs.currentChanged.connect(self._tab_changed)

    def _tab_changed(self, _index: int) -> None:
        """Another part's tab came forward: refresh while the tool is on."""
        if self.on:
            self._reset()

    def _reset(self) -> None:
        self.clear()
        self.plane.clear()
        self.plane.addItem(strings.CAVITY_TOP, TOP)
        tab = self.window.current
        if tab is not None:
            for f in tab.session.document.features:
                if f.type in ("plane", "ref_plane"):
                    self.plane.addItem(f.name, f.id)

    def set_on(self, on: bool) -> None:
        """Show or hide the window; showing it looks for voids at once."""
        self.on = on
        self.panel.setVisible(on)
        if on:
            self._reset()
            self.search()
        else:
            self.generation += 1
            self.clear()

    def clear(self) -> None:
        """Empty the list and remove the overlay."""
        self.voids, self.cup = None, None
        self.found.clear()
        self.summary.setText("")
        for i in range(self.window.tabs.count()):
            viewport = getattr(self.window.tabs.widget(i), "viewport", None)
            if viewport is not None:
                overlay.show_layer(viewport, _LAYER, [], COLOUR)

    def _body(self, tab: DocumentTab | None) -> Any:
        report = tab.session.report if tab is not None else None
        return report.body if report is not None else None

    def search(self) -> bool:
        """Look for closed voids in the background. False when there is no body."""
        from fdcad.core.cavities import enclosed_voids

        tab = self.window.current
        body = self._body(tab)
        if tab is None or body is None:
            self.summary.setText(strings.MASS_NO_BODY)
            return False
        self.generation += 1
        generation = self.generation
        self.summary.setText(strings.CAVITY_RUNNING)
        shape = body.shape
        jobs.start(
            lambda: enclosed_voids(shape),
            lambda voids: self._found(tab, generation, voids),
            lambda message: self._failed(generation, message),
        )
        return True

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.summary.setText(strings.CAVITY_FAILED.format(reason=message))

    def _found(self, tab: DocumentTab, generation: int, voids: list[Void]) -> None:
        if generation != self.generation or not self.on:
            return
        self.voids = voids
        self.found.clear()
        inch = tab.session.document.units.value == "in"
        for v in voids:
            self.found.addItem(
                strings.CAVITY_ROW.format(body=v.body + 1, volume=_volume(v.volume, inch))
            )
        self.summary.setText(
            strings.CAVITY_DONE.format(count=len(voids)) if voids else strings.CAVITY_NONE
        )
        self.window.status.setText(self.summary.text())
        if voids:
            self.found.setCurrentRow(0)

    def show_row(self, row: int) -> None:
        """Show one void in the view."""
        tab = self.window.current
        if tab is None or self.voids is None or not 0 <= row < len(self.voids):
            return
        overlay.show_layer(tab.viewport, _LAYER, [self.voids[row].shell], COLOUR, shaded=True)

    def add_drain(self) -> bool:
        """Add a drain hole for the selected void, as one undo step."""
        from fdcad.core.cavities import drain_hole
        from fdcad.ui.commands.document import AddFeature

        tab = self.window.current
        row = self.found.currentRow()
        body = self._body(tab)
        if tab is None or body is None or self.voids is None or not 0 <= row < len(self.voids):
            self.summary.setText(strings.CAVITY_PICK)
            return False
        feature = drain_hole(tab.session.document, body, self.voids[row])
        if feature is None:
            self.summary.setText(strings.CAVITY_NO_FACE)
            return False
        tab.session.undo.push(AddFeature(tab.session, feature))
        self.summary.setText(strings.CAVITY_DRAINED.format(name=feature.name))
        self.voids = None
        self.found.clear()
        return True

    def measure_cup(self) -> bool:
        """The volume the picked faces hold below the opening plane, in the background."""
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopoDS import TopoDS

        from fdcad.core.cavities import cavity_volume

        tab = self.window.current
        body = self._body(tab)
        faces = [
            TopoDS.Face(s) for s in getattr(tab, "selection", []) if s.ShapeType() == TopAbs_FACE
        ]
        if tab is None or body is None or not faces:
            self.summary.setText(strings.CAVITY_CUP_PICK)
            return False
        origin, normal = self._opening(tab, faces)
        shape = body.shape
        self.generation += 1
        generation = self.generation
        jobs.start(
            lambda: cavity_volume(shape, faces, origin, normal),
            lambda result: self._cup_done(tab, generation, result),
            lambda message: self._failed(generation, message),
        )
        return True

    def _opening(
        self, tab: DocumentTab, faces: list[Any]
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """The opening plane: a chosen plane, or the top of the faces level with Top."""
        choice = self.plane.currentData()
        report = tab.session.report
        if isinstance(choice, str) and choice != TOP and report is not None:
            result = report.results.get(choice)
            plane = result.plane if result is not None else None
            if plane is None:
                from fdcad.core.sketch.profiles import BASIS_PLANES

                plane = BASIS_PLANES.get(
                    str(tab.session.document.feature(choice).params.get("basis"))
                )
            if plane is not None:
                return plane.origin, plane.normal
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        box = Bnd_Box()
        for face in faces:
            BRepBndLib.Add_s(face, box)
        top = box.CornerMax().Y()  # the Top Plane faces +Y (sketch plane "xz")
        return (0.0, top, 0.0), (0.0, 1.0, 0.0)

    def _cup_done(self, tab: DocumentTab, generation: int, result: tuple[float, Any]) -> None:
        if generation != self.generation:
            return
        volume, shape = result
        self.cup = volume
        inch = tab.session.document.units.value == "in"
        if shape is None:
            self.summary.setText(strings.CAVITY_CUP_EMPTY)
            return
        self.summary.setText(strings.CAVITY_CUP_DONE.format(volume=_volume(volume, inch)))
        overlay.show_layer(tab.viewport, _LAYER, [shape], COLOUR, shaded=True)


def install(window: MainWindow) -> CavitiesTool:
    """Create the controller and its checkable command."""
    tool = CavitiesTool(window)
    action = window.commands.add(
        "evaluate.cavities", lambda: tool.set_on(action.isChecked()), checkable=True
    )
    return tool
