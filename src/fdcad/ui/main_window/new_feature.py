"""Starting Extrude, Extruded Cut, Revolve and Revolved Cut (W2, feature first).

1. A finished sketch that no feature uses is selected: the property panel opens on it.
2. A plane or flat face is selected, or nothing is: a sketch starts for the
   feature (asking for a plane if needed). Exit Sketch opens the panel on it.
3. Nothing is selected and the part has exactly one unused sketch: it is used.

When the panel opens, the 3D view turns to a trimetric angle unless the user
moved the view since leaving the sketch (W2.4).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.sketch.model import Line, sketch_from_data
from fdcad.core.units import UnitSystem
from fdcad.ui import strings
from fdcad.ui.main_window.visibility import unused_sketches

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

#: Eye direction and up vector of the view used while a feature panel is open.
TRIMETRIC = ((0.56, 0.42, 0.72), (0.0, 1.0, 0.0))


def feature_name(doc: Document, ftype: str, operation: str) -> str:
    """Next free name such as "Extrude 1" or "Revolve Cut 2" (D11, D110)."""
    from fdcad.core.features.names import default_name

    return default_name(doc, ftype, operation)


def lone_centerline(sketch: Feature) -> str | None:
    """The sketch's only centerline, or None when it has none or several (W6.3)."""
    model = sketch_from_data(sketch.data)
    lines = [e.id for e in model.entities.values() if isinstance(e, Line) and e.construction]
    return lines[0] if len(lines) == 1 else None


def new_feature(doc: Document, sketch: Feature, ftype: str, operation: str) -> Feature:
    """A new extrude or revolve on ``sketch`` with default values."""
    inch = doc.units is UnitSystem.IN
    # An extruded cut from a sketch on a face goes into the part, against the face
    # normal. A revolve's Reverse only changes which way it turns (bug hunt E8).
    plane = sketch.refs.get("plane")
    on_face = isinstance(plane, dict) and "kind" in plane
    into = ftype == "extrude" and operation == "cut" and on_face
    params: dict[str, Any] = {"operation": operation, "reverse": into}
    refs: dict[str, Any] = {"sketch": {"feature": sketch.id}}
    if ftype == "extrude":
        params["end_condition"] = "blind"
        params["depth"] = Param("0.5", 12.7) if inch else Param("10", 10.0)
    else:
        params["direction"] = "one_direction"
        params["angle"] = Param("360", 2 * math.pi)
        axis = lone_centerline(sketch)
        if axis is not None:
            refs["axis"] = {"sketch_entity": axis}
    return Feature(
        doc.new_feature_id(), ftype, feature_name(doc, ftype, operation), params=params, refs=refs
    )


def _length(doc: Document, mm: float, inch: float) -> Param:
    return Param(f"{inch:g}", inch * 25.4) if doc.units is UnitSystem.IN else Param(f"{mm:g}", mm)


def phase2_feature(doc: Document, ftype: str, operation: str) -> Feature:
    """A new Phase 2 feature (fillet, chamfer, shell, draft, sweep, loft) with defaults.

    Settings kept from the last accepted feature of the type in this session come
    first (PHASE2_SPEC P2.4 item 1).
    """
    from fdcad.ui.property_panel.forms.base import remembered

    params: dict[str, Any] = {}
    if ftype in ("sweep", "loft"):
        params["operation"] = operation
    if ftype == "fillet":
        params.update({"fillet_type": "constant", "radius": _length(doc, 2.0, 0.1)})
    elif ftype == "draft":
        params["angle"] = Param("1", math.radians(1))
    elif ftype == "shell":
        params["thickness"] = _length(doc, 1.0, 0.05)
    elif ftype == "chamfer":
        params.update({"chamfer_type": "distance_distance", "distance": _length(doc, 1.0, 0.05)})
    from fdcad.ui.main_window.phase4_features import phase4_defaults

    params.update(phase4_defaults(doc, ftype))
    params.update(remembered(ftype))
    return Feature(doc.new_feature_id(), ftype, feature_name(doc, ftype, operation), params=params)


class FeatureFlow:
    """Runs the feature commands for the main window."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window

    def insert(self, ftype: str, operation: str) -> None:
        """Start a feature the way W2 describes."""
        w = self.window
        tab = w.current
        mode = w.sketch_mode
        if tab is None or w.tree is None or w.panel is None or mode is None:
            return
        if mode.picker.active:
            mode.picker.finish()
        if ftype not in ("extrude", "revolve"):
            self.open_direct(tab, ftype, operation)
            return
        if mode.is_open:
            # Pressing a feature while sketching exits the sketch and uses it.
            assert mode.canvas is not None
            sid = mode.canvas.edit.feature.id
            mode.after_accept = None
            if not mode.accept():
                return
            self.open_panel(tab, sid, ftype, operation)
            return
        doc = tab.session.document
        selected = w.tree.selected_id()
        # A selected sketch is used as it is, even one another feature already uses.
        if selected is not None and doc.feature(selected).type == "sketch":
            self.open_panel(tab, selected, ftype, operation)
            return
        if not self._plane_or_face_selected(tab, selected):
            unused = unused_sketches(doc)
            if len(unused) == 1:
                self.open_panel(tab, unused[0], ftype, operation)
                return
        w.status.setText(strings.SKETCH_FOR_FEATURE)

        def sketched(sid: str) -> None:
            self.open_panel(tab, sid, ftype, operation)

        mode.start(after_accept=sketched)

    @staticmethod
    def _plane_or_face_selected(tab: DocumentTab, selected: str | None) -> bool:
        from fdcad.ui.main_window.plane_pick import flat_face

        if selected is not None and tab.session.document.feature(selected).type in (
            "plane",
            "ref_plane",
        ):
            return True
        return flat_face(tab) is not None

    def open_panel(self, tab: DocumentTab, sketch_id: str, ftype: str, operation: str) -> None:
        """Open the property panel for a new feature on ``sketch_id``."""
        w = self.window
        if w.panel is None:
            return
        doc = tab.session.document
        feature = new_feature(doc, doc.feature(sketch_id), ftype, operation)
        w.panel.begin(tab.session, feature, is_new=True, preset=True)  # TR326
        w._left_tab(1)
        self.trimetric(tab)
        panel, tree = w.panel, w.tree

        def finished() -> None:
            panel.finished.disconnect(finished)
            # After OK the new feature is selected, so the next command starts fresh.
            if tree is not None and any(f.id == feature.id for f in doc.features):
                tree.select(feature.id)

        panel.finished.connect(finished)

    def open_direct(self, tab: DocumentTab, ftype: str, operation: str) -> None:
        """Open the panel for a Phase 2 feature; the current selection becomes its picks."""
        w = self.window
        mode = w.sketch_mode
        if w.panel is None:
            return
        if mode is not None and mode.is_open:
            assert mode.canvas is not None
            mode.after_accept = None
            if not mode.accept():
                return
        doc = tab.session.document
        selection = list(getattr(tab, "selection", []))
        feature = phase2_feature(doc, ftype, operation)
        w.panel.begin(tab.session, feature, is_new=True, preset=True)  # TR326
        w._left_tab(1)
        report = tab.session.report
        form = getattr(w.panel, "form", None)
        if form is not None and selection and report is not None and report.body is not None:
            form.take_shapes(report.body, selection)
        panel, tree = w.panel, w.tree

        def finished() -> None:
            panel.finished.disconnect(finished)
            if tree is not None and any(f.id == feature.id for f in doc.features):
                tree.select(feature.id)

        panel.finished.connect(finished)

    def trimetric(self, tab: DocumentTab) -> bool:
        """Turn the view so the depth shows, unless the user moved it since the sketch."""
        mode = self.window.sketch_mode
        viewport = tab.viewport
        look = getattr(viewport, "look", None)
        moved = mode is not None and getattr(viewport, "nav_count", 0) != mode.exit_nav
        if look is None or moved:
            return False
        look(*TRIMETRIC)
        if hasattr(viewport, "fit_next_preview"):
            viewport.fit_next_preview = True  # the preview grows off the sketch: frame it
        return True
