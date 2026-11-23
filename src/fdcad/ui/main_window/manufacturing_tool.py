"""Manufacturing Check on the Evaluate tab (TR295, TR296; DECISIONS D790).

Choose a process; its profile's rule values are listed and can be edited, saved
to a file and loaded from one. Check lists the findings for the part as last
rebuilt; clicking one highlights its faces and edges. Two findings offer a fix
button, which the user clicks (CLAUDE.md 5.12): Corner Relief adds a Corner
Relief feature on the sharp corner's edge, and Snap to Stock Size sets the hole
feature's diameter to the stock drill. Nothing else changes the part.
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
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.core.manufacturing import Finding
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


def ask_save_path(window: MainWindow) -> str:
    """Where to save a profile, or "" when cancelled (a seam for tests)."""
    from PySide6.QtWidgets import QFileDialog

    path, _f = QFileDialog.getSaveFileName(window, strings.MFG_SAVE, "", strings.MFG_FILE_FILTER)
    return path


def ask_open_path(window: MainWindow) -> str:
    """A profile to load, or "" when cancelled (a seam for tests)."""
    from PySide6.QtWidgets import QFileDialog

    path, _f = QFileDialog.getOpenFileName(window, strings.MFG_LOAD, "", strings.MFG_FILE_FILTER)
    return path


class ManufacturingTool(QObject):
    """The window, the profile being edited, and the check job."""

    def __init__(self, window: MainWindow) -> None:
        from fdcad.core.manufacturing import PROCESSES, default_profile

        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.findings: list[Finding] | None = None
        self.profiles: dict[str, dict[str, float | str]] = {
            p: default_profile(p) for p in PROCESSES
        }
        self._from_printer()
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("manufacturing_panel")
        self.panel.setWindowTitle(strings.MFG_TITLE)
        form = QFormLayout(self.panel)
        self.process = QComboBox()
        for p in PROCESSES:
            self.process.addItem(strings.MFG_PROCESSES[p], p)
        form.addRow(strings.MFG_PROCESS, self.process)
        self.rules = QTableWidget(0, 2)
        self.rules.setObjectName("manufacturing_rules")
        self.rules.setHorizontalHeaderLabels([strings.MFG_RULE, strings.MFG_VALUE])
        self.rules.verticalHeader().setVisible(False)
        # The rule names get the width the table has; they were cut off (D1034).
        from PySide6.QtWidgets import QHeaderView

        self.rules.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.rules.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        form.addRow(self.rules)
        files = QHBoxLayout()
        self.load_button = QPushButton(strings.MFG_LOAD)
        self.save_button = QPushButton(strings.MFG_SAVE)
        files.addWidget(self.load_button)
        files.addWidget(self.save_button)
        form.addRow(files)
        actions = QHBoxLayout()
        self.check_button = QPushButton(strings.HEALTH_CHECK)
        self.fix_button = QPushButton()
        self.fix_button.setEnabled(False)
        actions.addWidget(self.check_button)
        actions.addWidget(self.fix_button)
        form.addRow(actions)
        self.found = QListWidget()
        self.found.setObjectName("manufacturing_found")
        self.found.setWordWrap(True)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow(self.found)
        form.addRow(self.summary)
        self.process.currentIndexChanged.connect(lambda _i: self.fill_rules())
        self.rules.itemChanged.connect(self._rule_edited)
        self.load_button.clicked.connect(self.load)
        self.save_button.clicked.connect(self.save)
        self.check_button.clicked.connect(self.check)
        self.fix_button.clicked.connect(self.apply_fix)
        self.found.currentRowChanged.connect(self.select_row)
        self.fill_rules()

    def _from_printer(self) -> None:
        """The active printer's process starts from that printer's own limits (TR295 item 2,
        D801); the other print processes keep FDCAD's general values."""
        from fdcad.core.printing.profiles import manufacturing_values
        from fdcad.ui.preferences import print_settings

        try:
            printer = print_settings.active_profile(self.window.settings)
        except Exception:  # no preferences yet: keep the general values
            return
        if printer.process in self.profiles:
            self.profiles[printer.process].update(manufacturing_values(printer))

    @property
    def current_process(self) -> str:
        """The chosen process."""
        return str(self.process.currentData())

    def fill_rules(self) -> None:
        """List the chosen process's rule values."""
        values = self.profiles[self.current_process]
        self.rules.blockSignals(True)
        self.rules.setRowCount(len(values))
        for row, (key, value) in enumerate(values.items()):
            name = QTableWidgetItem(strings.MFG_RULES.get(key, key))
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name.setData(Qt.ItemDataRole.UserRole, key)
            self.rules.setItem(row, 0, name)
            self.rules.setItem(
                row, 1, QTableWidgetItem(f"{value:g}" if isinstance(value, float) else str(value))
            )
        self.rules.blockSignals(False)
        self.found.clear()
        self.findings = None
        self.summary.setText("")

    def _rule_edited(self, item: QTableWidgetItem) -> None:
        if item.column() != 1:
            return
        first = self.rules.item(item.row(), 0)
        if first is None:
            return
        key = first.data(Qt.ItemDataRole.UserRole)
        values = self.profiles[self.current_process]
        if isinstance(values.get(key), str):
            values[key] = item.text()
            return
        try:
            number = float(item.text())
            if number < 0:
                raise ValueError
        except ValueError:
            self.fill_rules()
            self.summary.setText(strings.MFG_BAD_VALUE)
            return
        values[key] = number

    def save(self) -> bool:
        """Save the chosen process's profile to a file."""
        from pathlib import Path

        from fdcad.core.manufacturing import profile_to_text

        path = ask_save_path(self.window)
        if not path:
            return False
        try:
            Path(path).write_text(
                profile_to_text(self.current_process, self.profiles[self.current_process]),
                encoding="utf-8",
            )
        except OSError as exc:
            self.summary.setText(strings.MFG_FILE_FAILED.format(reason=exc.strerror or exc))
            return False
        self.summary.setText(strings.MFG_SAVED.format(path=path))
        return True

    def load(self) -> bool:
        """Load a profile from a file; it becomes its process's profile."""
        from pathlib import Path

        from fdcad.core.manufacturing import profile_from_text

        path = ask_open_path(self.window)
        if not path:
            return False
        try:
            process, values = profile_from_text(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            reason = exc.strerror if isinstance(exc, OSError) else str(exc)
            self.summary.setText(strings.MFG_FILE_FAILED.format(reason=reason or exc))
            return False
        self.profiles[process] = values
        self.process.setCurrentIndex(self.process.findData(process))
        self.fill_rules()
        self.summary.setText(strings.MFG_LOADED.format(path=path))
        return True

    def set_on(self, on: bool) -> None:
        """Show or hide the window."""
        self.on = on
        self.panel.setVisible(on)
        if not on:
            self.generation += 1
            self.window.highlight_names([])

    def check(self) -> bool:
        """Work the findings out in the background. False when there is nothing to check."""
        from fdcad.core.manufacturing import check, has_checks

        tab = self.window.current
        built = tab.session.report if tab is not None else None
        if tab is None or built is None or built.body is None:
            self.summary.setText(strings.MASS_NO_BODY)
            return False
        process = self.current_process
        if not has_checks(process):
            self.summary.setText(strings.MFG_NOT_YET)
            return False
        doc, body, results = tab.session.document, built.body, dict(built.results)
        profile = dict(self.profiles[process])
        self.generation += 1
        generation = self.generation
        self.summary.setText(strings.HEALTH_RUNNING)
        jobs.start(
            lambda: check(process, doc, body, profile, results),
            lambda found: self._done(tab, generation, found),
            lambda message: self._failed(generation, message),
        )
        return True

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.summary.setText(strings.MFG_FAILED.format(reason=message))

    def _done(self, tab: DocumentTab, generation: int, found: list[Finding]) -> None:
        if generation != self.generation or not self.on:
            return
        self.findings = found
        self.found.clear()
        for item in found:
            self.found.addItem(item.message)
        self.summary.setText(
            strings.MFG_DONE.format(count=len(found)) if found else strings.MFG_NONE
        )
        self.fix_button.setEnabled(False)
        self.fix_button.setText("")

    def _selected(self) -> Finding | None:
        row = self.found.currentRow()
        if self.findings is None or not 0 <= row < len(self.findings):
            return None
        return self.findings[row]

    def select_row(self, row: int) -> None:
        """Highlight the finding's faces and edges, and offer its fix."""
        from fdcad.core.manufacturing import CORNER_RELIEF, SNAP_DRILL

        item = self._selected()
        if item is None:
            self.fix_button.setEnabled(False)
            return
        tab = self.window.current
        report = tab.session.report if tab is not None else None
        highlight = getattr(tab.viewport, "highlight", None) if tab is not None else None
        if highlight is not None and report is not None and report.body is not None:
            from fdcad.core.naming.select import shapes_for_names

            highlight(shapes_for_names(report.body, item.faces) + list(item.edges))
        if item.fid and self.window.tree is not None:
            self.window.tree.select(item.fid)
        label = {CORNER_RELIEF: strings.MFG_FIX_RELIEF, SNAP_DRILL: strings.MFG_FIX_SNAP}
        self.fix_button.setText(label.get(item.fix or "", ""))
        self.fix_button.setEnabled(item.fix in label and self._fix_possible(item))

    def _fix_possible(self, item: Finding) -> bool:
        from fdcad.core.manufacturing import SNAP_DRILL

        if item.fix != SNAP_DRILL:
            return True
        tab = self.window.current
        if tab is None or item.fid is None:
            return False
        try:
            feature = tab.session.document.feature(item.fid)
        except KeyError:
            return False
        return feature.type == "hole"

    def apply_fix(self) -> bool:
        """Run the selected finding's fix as one undo step."""
        from fdcad.core.document.model import Feature, Param
        from fdcad.core.manufacturing import CORNER_RELIEF, SNAP_DRILL
        from fdcad.core.naming.select import reference_for
        from fdcad.ui.commands.document import AddFeature, SetParam

        item = self._selected()
        tab = self.window.current
        report = tab.session.report if tab is not None else None
        if item is None or tab is None or report is None or report.body is None:
            return False
        doc = tab.session.document
        if item.fix == CORNER_RELIEF:
            refs = [r for e in item.edges if (r := reference_for(report.body, e)) is not None]
            if not refs:
                return False
            tool = self.profiles["milling"].get("tool_diameter", 6.0)
            size = float(tool) if isinstance(tool, (int, float)) else 6.0
            fid = doc.new_feature_id()
            feature = Feature(
                fid,
                "corner_relief",
                f"Corner Relief {fid}",
                params={"relief_type": "dogbone", "tool_diameter": Param(f"{size:g}", size)},
                refs={"edges": refs},
            )
            tab.session.undo.push(AddFeature(tab.session, feature))
        elif item.fix == SNAP_DRILL and item.fid is not None and self._fix_possible(item):
            value = float(item.extra.get("diameter", 0.0))
            text = f"{value / 25.4:g}in" if doc.units.value == "in" else f"{value:g}mm"
            tab.session.undo.push(SetParam(tab.session, item.fid, "diameter", Param(text, value)))
        else:
            return False
        self.window.status.setText(strings.MFG_FIXED)
        self.found.clear()
        self.findings = None
        self.fix_button.setEnabled(False)
        return True


def install(window: MainWindow) -> ManufacturingTool:
    """Create the controller and its checkable command."""
    tool = ManufacturingTool(window)
    action: Any = window.commands.add(
        "evaluate.manufacturing", lambda: tool.set_on(action.isChecked()), checkable=True
    )
    return tool
