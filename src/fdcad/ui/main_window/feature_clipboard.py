"""Copy a sketch or a sketch based feature from the tree and paste it onto a plane or a
flat face (TUTORIAL_REVIEW_SPEC TR3.2, TR9, DECISIONS D685).

Ctrl+C with a tree row selected copies it to the system clipboard as feature data.
Ctrl+V pastes onto the selected plane or flat face, or asks for one. Ctrl and drag
of a tree row onto a face of the part does the same as copy and paste there. The
clipboard is read as data only: nothing in it is run (CLAUDE.md rule 10).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QMimeData, QObject, QPointF, Qt
from PySide6.QtGui import QDropEvent, QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from fdcad.core.document.model import Feature
from fdcad.core.document.paste import (
    PasteError,
    face_centre,
    link_count,
    paste_feature,
    paste_sketch,
    sketch_of,
)
from fdcad.core.io.fdef import feature_from_json_data, feature_to_json_data
from fdcad.core.io.migrations import FileFormatError
from fdcad.ui import clipboard

if TYPE_CHECKING:
    from fdcad.core.sketch.profiles import SketchPlane
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

#: Format of copied features on the system clipboard.
FEATURE_FORMAT = "application/x-fdcad-features"
#: Asks what to do with relations to part edges: True keeps them, False removes them,
#: None cancels. Tests replace it.
AskKeep = Callable[[int], "bool | None"]

COPY_WHAT = "Select a sketch, or a feature made from a sketch, in the tree, then press Ctrl+C."
COPIED = "Copied {name}. Select a plane or flat face and press Ctrl+V to paste it."
NOTHING = "Nothing to paste. Select a sketch or a feature made from a sketch and press Ctrl+C."
PASTE_NO_PART = "Open or start a part, then paste."
DAMAGED = "The clipboard does not hold a copied feature. Copy it again."
PICK = "Select a plane or flat face to paste {name} on. Press Escape to cancel."
PICK_FACE = "Pick a flat face or a plane to paste on."
PASTED = "Pasted {names}."
DROPPED = " {n} relation{s} or dimension{s} to the part dropped."
#: Pasted from another part (D708): picks named faces of that part.
CLEARED = (
    " It came from another part, so its picks ({keys}) were cleared."
    " Edit the feature and pick them again."
)
FROZEN = " {n} formula{s} became plain value{s}, since names differ between parts."


def part_token(doc: object) -> str:
    """Which open part a copy came from, for this run of FDCAD."""
    import os

    return f"{os.getpid()}:{id(doc)}"


KEEP_TITLE = "Paste"
KEEP_TEXT = (
    "The copied sketch has {n} relation{s} or dimension{s} to edges of the part. "
    "Keep them to place the copy where the original was, as fixed geometry. "
    "Remove them to center the copy on the picked face, free to move and dimension."
)


def ask_keep_dialog(parent: Any) -> AskKeep:
    """The Keep or Remove question as a message box."""

    def ask(n: int) -> bool | None:
        box = QMessageBox(parent)
        box.setWindowTitle(KEEP_TITLE)
        box.setText(KEEP_TEXT.format(n=n, s="s" if n != 1 else ""))
        keep = box.addButton("Keep", QMessageBox.ButtonRole.AcceptRole)
        remove = box.addButton("Remove", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(remove)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()  # closed boxes stayed alive (D637, audit D8 item 2)
        if clicked is keep:
            return True
        if clicked is remove:
            return False
        return None

    return ask


class FeatureClipboard(QObject):
    """Copy and paste of tree features for one window."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.ask_keep: AskKeep = ask_keep_dialog(window)
        self._watched: set[int] = set()
        #: The part the clipboard's copy came from (D708).
        self.source: str | None = None

    # Commands ------------------------------------------------------------------------

    def _in_node_editor(self) -> bool:
        dock = getattr(self.window, "node_editor_dock", None)
        focus = QApplication.focusWidget()
        return dock is not None and focus is not None and dock.isAncestorOf(focus)

    def copy_command(self) -> None:
        """Edit, Copy (Ctrl+C): nodes in the node editor, else the selected tree row."""
        if self._in_node_editor():
            from fdcad.ui.node_editor.install import panel_of

            panel_of(self.window).copy_selected()
            return
        self.copy()

    def paste_command(self) -> None:
        """Edit, Paste (Ctrl+V): nodes in the node editor, else a copied feature."""
        if self._in_node_editor():
            from fdcad.ui.node_editor.install import panel_of

            panel_of(self.window).paste()
            return
        self.paste()

    # Copy ----------------------------------------------------------------------------

    def copy(self, fid: str | None = None) -> bool:
        """Copy the selected tree row (or ``fid``). False, with a status note, when it
        is not a sketch or a feature made from one."""
        w, tab = self.window, self.window.current
        if tab is None:
            return False
        if fid is None:
            fid = w.tree.selected_id() if w.tree is not None else None
        doc = tab.session.document
        try:
            feature = doc.feature(fid) if fid else None
        except KeyError:
            feature = None
        sketch = None
        if feature is not None and feature.type != "sketch":
            sketch = sketch_of(doc, feature)
        if feature is None or (feature.type != "sketch" and sketch is None):
            w.status.setText(COPY_WHAT)
            return False
        payload = {
            "feature": feature_to_json_data(feature),
            "sketch": feature_to_json_data(sketch) if sketch is not None else None,
            "source": part_token(doc),
        }
        mime = QMimeData()
        mime.setData(FEATURE_FORMAT, json.dumps(payload).encode("utf-8"))
        clipboard.put(mime)
        w.status.setText(COPIED.format(name=feature.name))
        return True

    def copied(self) -> tuple[Feature, Feature | None] | None:
        """The copied feature and its sketch, read as data only, or None."""
        mime = QGuiApplication.clipboard().mimeData()
        if mime is None or not mime.hasFormat(FEATURE_FORMAT):
            return None
        try:
            raw = json.loads(bytes(mime.data(FEATURE_FORMAT).data()).decode("utf-8"))
            feature = feature_from_json_data(raw["feature"])
            sketch = feature_from_json_data(raw["sketch"]) if raw.get("sketch") else None
            source = raw.get("source")
            self.source = source if isinstance(source, str) else None
        except (ValueError, KeyError, TypeError, FileFormatError):
            self.window.status.setText(DAMAGED)
            return None
        if feature.type != "sketch" and (sketch is None or sketch.type != "sketch"):
            self.window.status.setText(DAMAGED)
            return None
        return feature, sketch

    # Paste ---------------------------------------------------------------------------

    def paste(self) -> bool:
        """Paste onto the selected plane or flat face, or ask for one."""
        w, tab = self.window, self.window.current
        if tab is None:
            w.status.setText(PASTE_NO_PART)  # was silent (audit D3 item 22, D744)
            return False
        clip = self.copied()
        if clip is None:
            mime = QGuiApplication.clipboard().mimeData()
            if mime is None or not mime.hasFormat(FEATURE_FORMAT):
                w.status.setText(NOTHING)  # an empty clipboard has no data at all
            return False
        return self.paste_clip(tab, clip)

    def paste_clip(self, tab: DocumentTab, clip: tuple[Feature, Feature | None]) -> bool:
        """Paste ``clip`` onto the selected plane or flat face, or ask for one."""
        from fdcad.ui.main_window.plane_pick import flat_face

        w = self.window
        face = flat_face(tab)
        if face is not None:
            return self.paste_on(tab, clip, face[0], face[1])
        selected = w.tree.selected_id() if w.tree is not None else None
        doc = tab.session.document
        if selected is not None and any(
            f.id == selected and f.type in ("plane", "ref_plane") for f in doc.features
        ):
            return self.paste_on(tab, clip, {"feature": selected}, None)
        if w.sketch_mode is None:
            return False

        def picked(ref: dict[str, Any], plane: SketchPlane | None) -> None:
            self.paste_on(tab, clip, ref, plane)

        w.sketch_mode.picker.start(tab, picked)
        w.status.setText(PICK.format(name=clip[0].name))
        return True

    def paste_on(
        self,
        tab: DocumentTab,
        clip: tuple[Feature, Feature | None],
        target: dict[str, Any],
        plane: SketchPlane | None,
        at: tuple[float, float, float] | None = None,
    ) -> bool:
        """Paste the clip onto ``target`` as one undo step. ``at`` is a model point on
        the face to center a pasted feature on (a drop point); the face's middle is
        used otherwise."""
        from fdcad.ui.commands.document import AddFeature

        w = self.window
        session = tab.session
        doc = session.document
        feature, sketch = clip
        other_part = getattr(self, "source", None) != part_token(doc)
        keep = False
        links = link_count(sketch if sketch is not None else feature)
        if feature.type != "sketch" and links and not other_part:
            answer = self.ask_keep(links)
            if answer is None:
                return False
            keep = answer
        centre = None
        middle = at or face_centre(target)
        if plane is not None and middle is not None:
            u, v, _w = plane.to_2d(*middle)
            centre = (u, v)
        try:
            if feature.type == "sketch":
                pasted = paste_sketch(doc, feature, target, other_part=other_part)
            else:
                assert sketch is not None
                pasted = paste_feature(
                    doc, feature, sketch, target, keep, centre, other_part=other_part
                )
        except PasteError as exc:
            w.status.setText(str(exc))
            return False
        names = ", ".join(f.name for f in pasted.features)
        session.undo.beginMacro(f"Paste {feature.name}")
        for new in pasted.features:
            session.undo.push(AddFeature(session, new))
        session.undo.endMacro()
        note = PASTED.format(names=names)
        if pasted.removed:
            n = pasted.removed
            note += DROPPED.format(n=n, s="s" if n != 1 else "")
        if pasted.cleared:
            note += CLEARED.format(keys=", ".join(pasted.cleared))
        if pasted.frozen:
            n = pasted.frozen
            note += FROZEN.format(n=n, s="s" if n != 1 else "")
        w.status.setText(note)
        if pasted.cleared or pasted.frozen:
            w.note_after_rebuild = note  # the rebuild must not hide what to do next
        if w.tree is not None:
            w.tree.select(pasted.features[-1].id)
        return True

    # Library feature files (TR72, D2115) --------------------------------------------------

    def save_library(self, fid: str, path: str | None = None) -> bool:
        """Save a sketch, or a feature with its sketch, to a library feature file."""
        from PySide6.QtWidgets import QFileDialog

        from fdcad.core.io import library
        from fdcad.ui import strings_config as text
        from fdcad.ui.strings import clause

        w, tab = self.window, self.window.current
        if tab is None:
            return False
        doc = tab.session.document
        feature = doc.feature(fid)
        sketch = sketch_of(doc, feature) if feature.type != "sketch" else None
        if feature.type != "sketch" and sketch is None:
            w.status.setText(text.LIBRARY_WHAT)
            return False
        if path is None:
            path, _f = QFileDialog.getSaveFileName(
                w, text.LIBRARY_SAVE, f"{feature.name}{library.SUFFIX}", text.LIBRARY_FILTER
            )
            if not path:
                return False
        try:
            written = library.save(path, feature, sketch)
        except OSError as exc:
            w.status.setText(text.LIBRARY_SAVE_FAILED.format(reason=clause(exc)))
            return False
        w.status.setText(text.LIBRARY_SAVED.format(name=written.name))
        return True

    def insert_library(self, path: str | None = None) -> bool:
        """Insert a library feature file onto the selected plane or flat face, or ask
        for one, as a paste from another part."""
        from PySide6.QtWidgets import QFileDialog

        from fdcad.core.io import library
        from fdcad.ui import strings_config as text
        from fdcad.ui.strings import clause

        w, tab = self.window, self.window.current
        if tab is None:
            w.status.setText(PASTE_NO_PART)
            return False
        if path is None:
            path, _f = QFileDialog.getOpenFileName(w, text.LIBRARY_INSERT, "", text.LIBRARY_FILTER)
            if not path:
                return False
        try:
            clip = library.load(path)
        except library.LibraryError as exc:
            w.status.setText(str(exc))
            return False
        except OSError as exc:
            w.status.setText(text.LIBRARY_READ_FAILED.format(reason=clause(exc)))
            return False
        self.source = "library"  # from outside this part: picks cleared, formulas frozen
        return self.paste_clip(tab, clip)

    # Ctrl and drag from the tree onto a face (TR9.3) -------------------------------------

    def watch(self, viewport: Any) -> None:
        """Let a tab's 3D view take tree rows dropped on it with Ctrl held."""
        if id(viewport) in self._watched or not hasattr(viewport, "setAcceptDrops"):
            return
        self._watched.add(id(viewport))
        viewport.setAcceptDrops(True)
        viewport.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Accept tree rows dragged over the view, and paste them where they drop."""
        kind = event.type()
        if kind in (QEvent.Type.DragEnter, QEvent.Type.DragMove) and self._from_tree(event):
            event.acceptProposedAction()  # type: ignore[attr-defined]
            return True
        if kind == QEvent.Type.Drop and self._from_tree(event):
            assert isinstance(event, QDropEvent)
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            event.acceptProposedAction()
            if ctrl:
                self.drop_at(event.position())
            else:
                self.window.status.setText("Hold Ctrl while dragging to paste a copy on a face.")
            return True
        return False

    def _from_tree(self, event: QEvent) -> bool:
        source = getattr(event, "source", None)
        return callable(source) and source() is self.window.tree

    def drop_at(self, pos: QPointF, fid: str | None = None) -> bool:
        """Paste the tree's selected row (or ``fid``) on the flat face under ``pos``."""
        from OCP.TopoDS import TopoDS

        from fdcad.core.features.sketch import face_plane
        from fdcad.core.naming.select import is_planar_face, reference_for

        w, tab = self.window, self.window.current
        if tab is None:
            return False
        report = tab.session.report
        viewport = tab.viewport
        if report is None or report.body is None or not hasattr(viewport, "detected_at"):
            return False
        face = next((s for s in viewport.detected_at(pos) if is_planar_face(s)), None)
        if face is None:
            w.status.setText(PICK_FACE)
            return False
        ref = reference_for(report.body, face)
        plane = face_plane(TopoDS.Face(face))
        if ref is None or plane is None:
            w.status.setText(PICK_FACE)
            return False
        if not self.copy(fid):
            return False
        clip = self.copied()
        if clip is None:
            return False
        at = viewport.part_point_at(pos) if hasattr(viewport, "part_point_at") else None
        return self.paste_on(tab, clip, ref, plane, at)
