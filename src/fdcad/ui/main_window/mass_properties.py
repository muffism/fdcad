"""Mass Properties on the Evaluate tab (TR79, DECISIONS D764).

A small window: the bodies (the whole part or the picked bodies, with or without
hidden ones), the material or a typed density, and the frame the inertia is
given about (the centre of mass, the part origin or a coordinate system).
Calculate runs ``core.mass`` in a kernel job; the values show in the part's
unit and Copy puts them on the clipboard. Nothing in the part changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.core.mass import MassProperties
    from fdcad.core.measure import Frame
    from fdcad.core.section_props import SectionProperties
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

TYPED = "__typed__"
CENTRE, ORIGIN = "__centre__", "__origin__"
SECTION = "section"


class MassPropertiesTool(QObject):
    """The window and its job."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.result: MassProperties | None = None
        self.section: SectionProperties | None = None
        self.rows: list[tuple[str, str]] = []
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("mass_panel")
        self.panel.setWindowTitle(strings.MASS_TITLE)
        form = QFormLayout(self.panel)
        self.scope = QComboBox()
        self.scope.addItem(strings.MASS_WHOLE_PART, "part")
        self.scope.addItem(strings.MASS_PICKED, "picked")
        self.scope.addItem(strings.MASS_SECTION, SECTION)  # TR81
        self.hidden = QCheckBox(strings.MASS_HIDDEN)
        self.material = QComboBox()
        self.density = QDoubleSpinBox()
        self.density.setRange(0.001, 30.0)
        self.density.setDecimals(4)
        self.density.setSuffix(" g/cm^3")
        self.about = QComboBox()
        self.values = QLabel()
        self.values.setObjectName("mass_values")
        self.values.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.run = QPushButton(strings.MASS_RUN)
        self.copy = QPushButton(strings.MASS_COPY)
        self.copy.setToolTip(strings.MASS_COPY_TIP)
        self.override = QPushButton(strings.MASS_OVERRIDE)  # TR80 (D1021)
        self.override.setToolTip(strings.MASS_OVERRIDE_TIP)
        buttons = QHBoxLayout()
        buttons.addWidget(self.run)
        buttons.addWidget(self.copy)
        buttons.addWidget(self.override)
        form.addRow(strings.MASS_USE, self.scope)
        form.addRow("", self.hidden)
        form.addRow(strings.MASS_MATERIAL, self.material)
        form.addRow(strings.MASS_DENSITY, self.density)
        form.addRow(strings.MASS_ABOUT, self.about)
        form.addRow(buttons)
        form.addRow(self.values)
        self.run.clicked.connect(self.calculate)
        self.copy.clicked.connect(self.copy_values)
        self.override.clicked.connect(self.edit_override)
        self.material.currentIndexChanged.connect(self._material_chosen)
        self.density.valueChanged.connect(lambda _v: self._density_typed())
        window.tabs.currentChanged.connect(self._tab_changed)

    # Choices -----------------------------------------------------------------------

    def _tab_changed(self, _index: int) -> None:
        """Another part's tab came forward: refresh while the tool is on."""
        if self.on:
            self.fill()

    def fill(self) -> None:
        """Materials from the print settings, and the frames of the current part."""
        from fdcad.core.materials import part_material
        from fdcad.ui.preferences.print_settings import densities, last_material

        found = densities(self.window.settings)
        tab = self.window.current
        own = part_material(tab.session.document) if tab is not None else None
        if own is not None:  # the part's material is the default (TR78, D803)
            found = {**found, own.name: own.density}
        self.material.blockSignals(True)
        self.material.clear()
        for name, value in found.items():
            self.material.addItem(f"{name} ({value:g} g/cm^3)", name)
        self.material.addItem(strings.MASS_TYPED, TYPED)
        start = own.name if own is not None else last_material(self.window.settings)
        index = self.material.findData(start)
        self.material.setCurrentIndex(max(index, 0))
        self.material.blockSignals(False)
        self._material_chosen(self.material.currentIndex())
        self.about.clear()
        self.about.addItem(strings.MASS_ABOUT_CENTRE, CENTRE)
        self.about.addItem(strings.MASS_ABOUT_ORIGIN, ORIGIN)
        tab = self.window.current
        if tab is not None:
            for f in tab.session.document.features:
                if f.type == "coord_system":
                    self.about.addItem(f.name, f.id)

    def _material_chosen(self, _index: int) -> None:
        from fdcad.core.materials import part_material
        from fdcad.ui.preferences.print_settings import densities

        name = self.material.currentData()
        tab = self.window.current
        own = part_material(tab.session.document) if tab is not None else None
        if own is not None and own.name == name:
            value: float | None = own.density
        else:
            value = densities(self.window.settings).get(str(name))
        if value is not None:
            self.density.blockSignals(True)
            self.density.setValue(value)
            self.density.blockSignals(False)

    def _density_typed(self) -> None:
        index = self.material.findData(TYPED)
        if index >= 0 and self.material.currentIndex() != index:
            self.material.blockSignals(True)
            self.material.setCurrentIndex(index)
            self.material.blockSignals(False)

    def set_on(self, on: bool) -> None:
        """Show or hide the window; showing it calculates at once."""
        self.on = on
        self.panel.setVisible(on)
        if on:
            self.fill()
            self.calculate()
        else:
            self.generation += 1

    # Calculating -------------------------------------------------------------------

    def _bodies(self, tab: DocumentTab) -> list[Any]:
        from fdcad.core.body_visibility import hidden_names, visible_indices
        from fdcad.core.features.solids import solids
        from fdcad.core.printing.estimate import bodies_for

        report = tab.session.report
        body = report.body if report is not None else None
        if body is None:
            return []
        every = solids(body.shape)
        if not self.hidden.isChecked():
            keep = visible_indices(body, hidden_names(tab.session.document))
            every = [every[i] for i in keep if i < len(every)]
        if self.scope.currentData() == "picked" and tab.selection:
            picked = bodies_for(body.shape, list(tab.selection))
            every = [b for b in every if any(b.IsSame(p) for p in picked)]
        return every

    def frame(self, tab: DocumentTab) -> tuple[Frame | None, str]:
        """The frame chosen in About, and its name (None: the centre of mass)."""
        from fdcad.core.features.datum import cross
        from fdcad.core.measure import Frame

        choice = self.about.currentData()
        if choice == ORIGIN:
            return Frame(), strings.MASS_ABOUT_ORIGIN.lower()
        report = tab.session.report
        if isinstance(choice, str) and choice != CENTRE and report is not None:
            datum = report.results[choice].datum if choice in report.results else None
            if datum is not None and datum.direction is not None and datum.x_dir is not None:
                z, x = datum.direction, datum.x_dir
                return Frame(datum.origin, x, cross(z, x), z), tab.session.document.feature(
                    choice
                ).name
        return None, ""

    def calculate(self) -> bool:
        """Work the values out in the background. False when there is nothing to measure."""
        from fdcad.core.mass import mass_properties

        tab = self.window.current
        if self.scope.currentData() == SECTION:
            return self._calculate_section(tab)
        bodies = self._bodies(tab) if tab is not None else []
        if tab is None or not bodies:
            self.values.setText(strings.MASS_NO_BODY)
            return False
        density = self.density.value()
        self.generation += 1
        generation = self.generation
        self.values.setText(strings.MASS_RUNNING)
        jobs.start(
            lambda: mass_properties(bodies, density),
            lambda result: self._done(tab, generation, result),
            lambda message: self._failed(generation, message),
        )
        return True

    def section_faces(self, tab: DocumentTab) -> tuple[list[Any], Any, Any]:
        """The faces to measure as a section (TR81, D1019) and the axes: the picked flat
        faces with their own plane's axes, or else the profile of the sketch selected in
        the tree with the sketch's axes."""
        from OCP.TopAbs import TopAbs_FACE

        faces = [s for s in tab.selection if s.ShapeType() == TopAbs_FACE]
        if faces:
            return faces, None, None
        report = tab.session.report
        tree = self.window.tree
        if report is None or tree is None:
            return [], None, None
        for fid in tree.selected_features():
            result = report.results.get(fid)
            out = result.sketch if result is not None else None
            if out is not None and out.profile is not None and out.profile.faces:
                return list(out.profile.faces), out.plane.x_dir, out.plane.normal
        return [], None, None

    def _calculate_section(self, tab: DocumentTab | None) -> bool:
        from fdcad.core.section_props import section_properties

        faces, x_dir, normal = self.section_faces(tab) if tab is not None else ([], None, None)
        if tab is None or not faces:
            self.values.setText(strings.MASS_NO_SECTION)
            return False
        self.generation += 1
        generation = self.generation
        self.values.setText(strings.MASS_RUNNING)
        jobs.start(
            lambda: section_properties(faces, x_dir, normal),
            lambda result: self._section_done(tab, generation, result),
            lambda message: self._failed(generation, message),
        )
        return True

    def _section_done(self, tab: DocumentTab, generation: int, result: Any) -> None:
        from fdcad.core.section_props import section_report

        if generation != self.generation:
            return
        self.section = result
        inch = tab.session.document.units.value == "in"
        self.rows = section_report(result, inch)
        self.values.setText("\n".join(f"{label}: {value}" for label, value in self.rows))

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.values.setText(strings.MASS_FAILED.format(reason=message))

    def _done(self, tab: DocumentTab, generation: int, result: MassProperties) -> None:
        from fdcad.core.mass import report

        if generation != self.generation:
            return
        from fdcad.core.mass import apply_override, part_override

        typed = part_override(tab.session.document)
        whole = self.scope.currentData() == "part"
        if typed is not None and whole:  # TR80 (D1021)
            result = apply_override(result, typed)
        self.result = result
        frame, name = self.frame(tab)
        inch = tab.session.document.units.value == "in"
        self.rows = report(result, inch, frame, name)
        if typed is not None and whole:
            mark = strings.MASS_OVERRIDE_MARK_TEXT.format(
                centre=", centre" if typed.centre is not None else "",
                inertia=", inertia" if typed.inertia is not None else "",
            )
            self.rows.insert(0, (strings.MASS_OVERRIDE_MARK, mark))
        text = "\n".join(f"{label}: {value}" for label, value in self.rows)
        failed = stale_name(tab)
        if failed:  # TR352: the part shown is not the one the tree describes
            text = strings.STALE_RESULTS.format(name=failed) + "\n\n" + text
        self.values.setText(text)

    def edit_override(self) -> bool:
        """Type or clear the part's mass properties (TR80); recalculates after a change."""
        from fdcad.ui.main_window.mass_override import edit_override

        tab = self.window.current
        if tab is None or not edit_override(tab.session, self.panel):
            return False
        self.calculate()
        return True

    def copy_values(self) -> None:
        """Copy the shown values as lines of label and value."""
        if self.rows:
            QGuiApplication.clipboard().setText(
                "\n".join(f"{label}\t{value}" for label, value in self.rows)
            )
            section = self.scope.currentData() == SECTION
            self.window.status.setText(
                strings.MASS_SECTION_COPIED if section else strings.MASS_COPIED
            )


def install(window: MainWindow) -> MassPropertiesTool:
    """Create the controller and its checkable command."""
    tool = MassPropertiesTool(window)
    action = window.commands.add(
        "evaluate.mass_properties", lambda: tool.set_on(action.isChecked()), checkable=True
    )
    return tool


def stale_name(tab: DocumentTab) -> str:
    """The name of the feature that failed when later ones built on an older part (TR352),
    or ""."""
    report = tab.session.report
    fid = getattr(report, "failed_at", None)
    if fid is None:
        return ""
    try:
        return tab.session.document.feature(fid).name
    except KeyError:
        return ""
