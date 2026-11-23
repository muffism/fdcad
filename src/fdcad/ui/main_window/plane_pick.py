"""Pick where a new sketch goes (W1.2, C4).

With nothing selected, Sketch shows the planes in the 3D view and asks
"Select a plane or flat face". Clicking a plane in the view or the tree, or a
flat face of the part, picks it. Escape cancels.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QCursor, QKeySequence, QShortcut

from fdcad.ui import strings

if TYPE_CHECKING:
    from OCP.TopoDS import TopoDS_Shape

    from fdcad.core.sketch.profiles import SketchPlane
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

#: Called with the plane reference (``{"feature": id}`` or a face reference) and,
#: for a face, its placement.
PickHandler = Callable[[dict[str, Any], "SketchPlane | None"], None]


def plane_names(tab: DocumentTab) -> dict[str, str]:
    """The tree name of every plane, for the labels in the 3D view (T13)."""
    from fdcad.core.features.datum import PLANE_TYPES
    from fdcad.core.features.pattern_datums import DATUM_PATTERN_TYPES

    report = tab.session.report
    results = report.results if report is not None else {}
    return {
        f.id: f.name
        for f in tab.session.document.features
        if f.type in PLANE_TYPES
        or (f.type in DATUM_PATTERN_TYPES and getattr(results.get(f.id), "plane", None))
    }


def part_half_size(tab: DocumentTab) -> float:
    """Half the size planes and reference geometry are drawn at: 50 mm or 0.6 of the part."""
    half = 50.0
    report = tab.session.report
    if report is not None and report.body is not None:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        box = Bnd_Box()
        BRepBndLib.Add_s(report.body.shape, box)
        if not box.IsVoid():
            lo, hi = box.CornerMin(), box.CornerMax()
            values = (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z())
            half = max(half, 0.6 * max(abs(v) for v in values))
    return half


def plane_faces(tab: DocumentTab) -> dict[str, TopoDS_Shape]:
    """A square face for every plane of the part, sized to the part (tiny kernel work, D75)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Pln

    from fdcad.core.sketch.profiles import BASIS_PLANES

    half = part_half_size(tab)
    report = tab.session.report
    out: dict[str, TopoDS_Shape] = {}
    from fdcad.core.features.datum import PLANE_TYPES
    from fdcad.core.features.pattern_datums import DATUM_PATTERN_TYPES

    for feature in tab.session.document.features:
        copy = feature.type in DATUM_PATTERN_TYPES  # an exploded plane copy (TR142, D2402)
        if (feature.type not in PLANE_TYPES and not copy) or feature.suppressed:
            continue
        result = report.results.get(feature.id) if report is not None else None
        plane = result.plane if result is not None else None
        basis = feature.params.get("basis")
        if plane is None and isinstance(basis, str):
            plane = BASIS_PLANES.get(basis)
        if plane is None:
            continue
        maker = BRepBuilderAPI_MakeFace(gp_Pln(plane.ax3()), -half, half, -half, half)
        if maker.IsDone():
            out[feature.id] = maker.Face()
    return out


def picker_faces(tab: DocumentTab) -> dict[str, TopoDS_Shape]:
    """The planes drawn while picking (D1092): the three main planes and the planes shown
    in the view. Every plane drawn at the size of the part, each with its label, covered
    a bike frame with 17 construction planes and ignored Hide or Show Items. Any other
    plane is picked in the tree."""
    faces = plane_faces(tab)
    shown = set(getattr(tab, "visible_plane_ids", list)())
    main = {f.id for f in tab.session.document.features if isinstance(f.params.get("basis"), str)}
    return {fid: face for fid, face in faces.items() if fid in main or fid in shown}


class PlanePicker(QObject):
    """Waits for the user to pick a plane or a flat face."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.tab: DocumentTab | None = None
        self.handler: PickHandler | None = None
        self.on_cancel: Callable[[], None] | None = None
        self._escape: QShortcut | None = None

    @property
    def active(self) -> bool:
        """True while waiting for a pick."""
        return self.handler is not None

    def start(
        self,
        tab: DocumentTab,
        handler: PickHandler,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        """Show the planes and wait. ``handler`` runs once with the pick."""
        self.finish()
        w = self.window
        self.tab, self.handler, self.on_cancel = tab, handler, on_cancel
        w.status.setText(strings.SELECT_PLANE)
        viewport = tab.viewport
        show = getattr(viewport, "show_planes", None)
        if show is not None:
            show(picker_faces(tab), plane_names(tab))
            viewport.plane_picked.connect(self._plane_picked)
            viewport.selection_changed.connect(self._faces_picked)
            viewport.setCursor(self._cursor())
        if w.tree is not None:
            w.tree.currentItemChanged.connect(self._tree_picked)
        self._escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), w)
        self._escape.setContext(Qt.ShortcutContext.WindowShortcut)
        self._escape.activated.connect(self.cancel)

    @staticmethod
    def _cursor() -> QCursor:
        from fdcad.ui.icons import icon

        pixmap = icon("sketch.sketch").pixmap(20, 20)
        if pixmap.isNull():
            return QCursor(Qt.CursorShape.CrossCursor)
        return QCursor(pixmap, 0, 0)

    def pick(self, ref: dict[str, Any], placement: SketchPlane | None = None) -> None:
        """Finish with this plane reference."""
        handler = self.handler
        self.finish()
        if handler is not None:
            handler(ref, placement)

    def cancel(self) -> None:
        """Escape: stop without starting anything."""
        on_cancel = self.on_cancel
        if self.active:
            self.finish()
            self.window.status.setText(strings.READY)
            if on_cancel is not None:
                on_cancel()

    def finish(self) -> None:
        """Hide the planes and stop listening."""
        tab = self.tab
        if tab is not None:
            viewport = tab.viewport
            if hasattr(viewport, "hide_planes"):
                viewport.hide_planes()
                viewport.plane_picked.disconnect(self._plane_picked)
                viewport.selection_changed.disconnect(self._faces_picked)
                viewport.unsetCursor()
        if self.handler is not None and self.window.tree is not None:
            self.window.tree.currentItemChanged.disconnect(self._tree_picked)
        if self._escape is not None:
            self._escape.setEnabled(False)
            self._escape.deleteLater()
            self._escape = None
        self.tab, self.handler, self.on_cancel = None, None, None

    # Sources of a pick -----------------------------------------------------------------

    def _plane_picked(self, fid: str) -> None:
        self.pick({"feature": fid})

    def _tree_picked(self, *_args: object) -> None:
        tree, tab = self.window.tree, self.tab
        if tree is None or tab is None:
            return
        if tree.filling:
            return  # the tree is being rebuilt, not picked by the user (bug hunt B3)
        fid = tree.selected_id()
        feature = next((f for f in tab.session.document.features if f.id == fid), None)
        if feature is None:
            return  # the part row, the bodies or nothing (B3)
        if feature.type in ("plane", "ref_plane") and not feature.suppressed:
            self.pick({"feature": fid})

    def _faces_picked(self, shapes: list[TopoDS_Shape]) -> None:
        tab = self.tab
        if tab is None or not shapes:
            return
        tab.selection = list(shapes)
        face = flat_face(tab)
        if face is not None:
            self.pick(*face)


def flat_face(tab: DocumentTab) -> tuple[dict[str, Any], SketchPlane] | None:
    """Reference and placement of a selected flat face, if one is selected."""
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.sketch import face_plane
    from fdcad.core.naming.select import is_planar_face, reference_for

    report = tab.session.report
    if report is None or report.body is None:
        return None
    for shape in tab.selection:
        if is_planar_face(shape):
            ref = reference_for(report.body, shape)
            plane = face_plane(TopoDS.Face(shape))
            if ref is not None and plane is not None:
                return ref, plane
    return None
