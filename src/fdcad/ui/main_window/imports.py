"""Import commands of the main window: open a STEP or mesh file as a new part, and
insert one into the open part (PHASE3_SPEC P3.5 and P3.9, DECISIONS D290, D305).

Only the file bytes are read here. Reading the geometry is kernel work, so it
happens in the rebuild worker (CLAUDE.md rule 2); the import report is shown in
the status bar when that rebuild finishes.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from fdcad.ui import strings, strings_import
from fdcad.ui.input.commands import BY_ID

if TYPE_CHECKING:
    from fdcad.core.document.model import Document, Feature
    from fdcad.core.rebuild.engine import RebuildReport
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.session import DocumentSession

STEP_SUFFIXES = (".step", ".stp", ".igs", ".iges")  # IGES reads like STEP (TR31)
MESH_SUFFIXES = (".stl", ".3mf", ".obj")


def is_import(path: Path) -> bool:
    """True for a file that opens as a new part with an import feature."""
    return path.suffix.lower() in STEP_SUFFIXES + MESH_SUFFIXES


def _new_import(doc: Document, path: Path, data: bytes) -> tuple[str, dict[str, Any], Feature]:
    if path.suffix.lower() in STEP_SUFFIXES:
        from fdcad.core.features.import_step import new_step_import

        return new_step_import(doc, path.name, data)
    from fdcad.core.features.import_mesh import new_mesh_import

    return new_mesh_import(doc, path.name, data)


def report_text(report: RebuildReport, fid: str, filename: str, name: str) -> str:
    """Status bar text after an import: what healing fixed, or why it failed."""
    result = report.results.get(fid)
    if result is None:
        return ""
    errors = [i.message for i in result.issues if i.state.value == "error"]
    if errors:
        return errors[0]
    lines = [str(line) for line in result.extras.get("report", [])]
    lines += [i.message for i in result.issues if i.state.value == "warning"]
    if lines:
        return strings_import.IMPORTED_REPORT.format(
            feature=name, name=filename, report=" ".join(lines)
        )
    return strings_import.IMPORTED.format(feature=name, name=filename)


class ImportFlow:
    """Runs the import commands for the main window."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window

    def _read(self, path: Path) -> bytes | None:
        try:
            return path.read_bytes()
        except OSError as exc:
            from fdcad.ui import strings_feedback
            from fdcad.ui.errors.message import show_error

            show_error(
                self.window,
                strings_import.READ_FAILED.format(name=path.name, reason=strings.clause(exc)),
                exc,
                strings_feedback.READ_FAILED_CONTEXT.format(path=path),
            )
            return None

    def open_file(self, path: Path) -> DocumentSession | None:
        """Open a STEP or mesh file as a new, unsaved part."""
        from fdcad.core.document.model import new_document
        from fdcad.ui.session import DocumentSession

        data = self._read(path)
        if data is None:
            return None
        doc = new_document(self.window.settings.default_units)
        bid, block, feature = _new_import(doc, path, data)
        doc.embedded[bid] = block
        doc.features.append(feature)
        session = DocumentSession(doc, None, self.window)
        session.name = path.stem
        session.opened_from = path
        self._when_built(session, feature.id, path.name, feature.name)
        self.window.add_session(session)
        return session

    def insert_dialog(self, kind: str) -> None:
        """Choose a STEP (``kind`` "step") or mesh file and add it to the open part."""
        title, filters = (
            (strings_import.IMPORT_STEP_TITLE, strings_import.FILTER_STEP_IGES)
            if kind == "step"
            else (strings_import.IMPORT_MESH_TITLE, strings_import.FILTER_MESH)
        )
        name, _ = QFileDialog.getOpenFileName(self.window, title, "", filters)
        if name:
            fid = self.insert(Path(name))
            tab = self.window.current
            if fid is not None and kind == "step" and tab is not None:
                self._then_pick(tab.session, fid)  # TR302: tick the bodies that come in

    def _then_pick(self, session: DocumentSession, fid: str) -> None:
        """After the import's first build, offer Pick Bodies when it has several."""

        def done(report: RebuildReport) -> None:
            if report.cancelled or fid not in report.results:
                return
            session.rebuilt.disconnect(slot)
            QTimer.singleShot(0, lambda: self.pick_dialog(fid, quiet=True))

        slot: Callable[[RebuildReport], None] = done
        session.rebuilt.connect(slot)

    def insert(self, path: Path) -> str | None:
        """Add the file at ``path`` to the open part as one undoable step.

        Returns the new feature id, or None when nothing was added.
        """
        from fdcad.ui.commands.imports import AddImport

        tab = self.window.current
        if tab is None:
            return None
        data = self._read(path)
        if data is None:
            return None
        session = tab.session
        bid, block, feature = _new_import(session.document, path, data)
        self._when_built(session, feature.id, path.name, feature.name)
        session.undo.push(AddImport(session, feature, bid, block))
        return feature.id

    def replace_dialog(self, fid: str) -> None:
        """Replace From File (TR11): choose a file of the same kind for an import."""
        tab = self.window.current
        if tab is None:
            return
        feature = tab.session.document.feature(fid)
        filters = (
            strings_import.FILTER_STEP_IGES
            if feature.type == "import_step"
            else strings_import.FILTER_MESH
        )
        name, _ = QFileDialog.getOpenFileName(
            self.window, strings_import.REPLACE_TITLE.format(name=feature.name), "", filters
        )
        if name:
            self.replace(fid, Path(name))

    def replace(self, fid: str, path: Path) -> bool:
        """Make import ``fid`` read the file at ``path`` instead, as one undo step."""
        from fdcad.core.features.import_replace import ReplaceError, new_source
        from fdcad.ui.commands.imports import ReplaceImport

        tab = self.window.current
        if tab is None:
            return False
        data = self._read(path)
        if data is None:
            return False
        session = tab.session
        feature = session.document.feature(fid)
        try:
            bid, block = new_source(session.document, feature, path.name, data)
        except ReplaceError as exc:
            self.window.status.setText(str(exc))
            return False
        self._when_built(session, fid, path.name, feature.name)
        session.undo.push(ReplaceImport(session, fid, bid, block))
        return True

    def heal_dialog(self, fid: str) -> None:
        """Heal (TR31): ask for the largest gap to close, then rebuild the import."""
        from PySide6.QtWidgets import QInputDialog

        from fdcad.core.features.import_step import heal_gap
        from fdcad.core.io.iges_import import MAX_GAP

        tab = self.window.current
        if tab is None:
            return
        feature = tab.session.document.feature(fid)
        start = min((heal_gap(feature) or 0.01) * 10, MAX_GAP)
        gap, ok = QInputDialog.getDouble(
            self.window,
            strings_import.HEAL_TITLE.format(name=feature.name),
            strings_import.HEAL_PROMPT.format(most=f"{MAX_GAP:g}"),
            start,
            0.001,
            MAX_GAP,
            3,
        )
        if ok:
            self.heal(fid, gap)

    def heal(self, fid: str, gap_mm: float) -> bool:
        """Read the import again closing gaps up to ``gap_mm``, as one undo step."""
        from fdcad.core.document.model import Param
        from fdcad.ui.commands.document import SetParam

        tab = self.window.current
        if tab is None:
            return False
        session = tab.session
        feature = session.document.feature(fid)
        source = feature.refs.get("source")
        block = (
            session.document.embedded.get(source.get("embedded", ""))
            if isinstance(source, dict)
            else None
        )
        filename = str(block.get("filename", "")) if isinstance(block, dict) else ""
        self._when_built(session, fid, filename, feature.name)
        session.undo.push(SetParam(session, fid, "heal_gap", Param(f"{gap_mm:g}mm", gap_mm)))
        return True

    def pick_dialog(self, fid: str, quiet: bool = False) -> None:
        """Pick Bodies (TR302, D1203): read the import's file in the background, then
        list its bodies to tick. ``quiet`` says nothing for a file of one body."""
        from fdcad.core.features.import_step import keep_list, read_import
        from fdcad.core.features.solids import solids
        from fdcad.ui.print_tools import jobs

        tab = self.window.current
        if tab is None:
            return
        session = tab.session
        feature = session.document.feature(fid)
        name = feature.name
        status = self.window.status
        if not quiet:
            status.setText(strings_import.PICK_BODIES_READING.format(name=name))

        def read() -> list[Any]:
            return solids(read_import(session.document, feature).shape)

        def shown(bodies: list[Any]) -> None:
            if self.window.current is not tab:
                return
            if len(bodies) < 2:
                if not quiet:
                    status.setText(strings_import.PICK_BODIES_ONE.format(name=name))
                return
            text = feature.params.get("keep_bodies")
            try:
                keep = keep_list(text, len(bodies)) if isinstance(text, str) and text else None
            except ValueError:
                keep = None
            self.pick(fid, bodies, keep)

        def failed(reason: str) -> None:
            status.setText(strings_import.PICK_BODIES_FAILED.format(name=name, reason=reason))

        jobs.start(read, shown, failed)

    def pick(self, fid: str, bodies: list[Any], keep: list[int] | None) -> bool:
        """Show the tick list for ``bodies`` and store the pick as one undo step."""
        from fdcad.ui.commands.document import SetParam
        from fdcad.ui.main_window import body_pick_dialog

        tab = self.window.current
        if tab is None:
            return False
        session = tab.session
        feature = session.document.feature(fid)
        dialog = body_pick_dialog.BodyPickDialog(
            feature.name, bodies, keep, self.window, viewport=tab.viewport
        )
        accepted = body_pick_dialog.run(dialog)
        dialog.clear_preview()
        text = dialog.keep
        dialog.deleteLater()
        now = feature.params.get("keep_bodies")
        if not accepted or text == (now if isinstance(now, str) else ""):
            return False
        session.undo.push(SetParam(session, fid, "keep_bodies", text))
        return True

    def _when_built(self, session: DocumentSession, fid: str, filename: str, name: str) -> None:
        """Show the import report once the next rebuild finishes."""
        status = self.window.status

        def done(report: RebuildReport) -> None:
            if report.cancelled or fid not in report.results:
                return
            session.rebuilt.disconnect(slot)
            text = report_text(report, fid, filename, name)
            if text:
                # After the window's own "Rebuilt" message for this rebuild.
                QTimer.singleShot(0, lambda: status.setText(text))

        slot: Callable[[RebuildReport], None] = done
        session.rebuilt.connect(slot)


#: Phase 3 feature commands in the Insert menu's Curves submenu: command id, type.
CURVE_INSERTS = (
    ("feature.helix", "helix"),
    ("feature.projected_curve", "projected_curve"),
    ("feature.composite_curve", "composite_curve"),
    ("feature.point_curve", "point_curve"),
    ("feature.sketch3d", "sketch3d"),  # TR7 (D1719)
    ("feature.pipe", "pipe"),
    ("feature.curve_array", "curve_array"),
    ("feature.contour", "contour"),
)


def install(window: MainWindow, menu: Any) -> None:
    """Add the import and curve commands to the Insert menu."""
    a = window.commands
    curves = menu.addMenu(strings_import.MENU_CURVES)
    for cid, ftype in CURVE_INSERTS:
        if cid not in BY_ID:
            continue
        action = a.actions.get(cid) or a.add(
            cid, partial(window.insert_feature, ftype, "boss"), repeatable=True
        )
        curves.addAction(action)
    from fdcad.ui.main_window import curvature_graph

    window.curvature_graph = curvature_graph.install(window)
    flow = ImportFlow(window)
    window.import_flow = flow
    tree = getattr(window, "tree", None)
    if tree is not None:
        tree.replace_requested.connect(flow.replace_dialog)  # TR11
        tree.heal_requested.connect(flow.heal_dialog)  # TR31
        tree.pick_requested.connect(flow.pick_dialog)  # TR302
    menu.addSeparator()
    if "feature.split_for_print" in BY_ID:
        menu.addAction(
            a.actions.get("feature.split_for_print")
            or a.add(
                "feature.split_for_print",
                partial(window.insert_feature, "split_for_print", "boss"),
                repeatable=True,
            )
        )
    for cid, kind in (("feature.import_step", "step"), ("feature.import_mesh", "mesh")):
        if cid not in BY_ID:
            continue
        action = a.actions.get(cid) or a.add(cid, partial(flow.insert_dialog, kind))
        menu.addAction(action)
