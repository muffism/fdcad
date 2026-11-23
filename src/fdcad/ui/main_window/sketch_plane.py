"""Edit Sketch Plane (TOOL_SPEC T14.2): move a finished sketch to another plane or face.

A small panel in the left panel holds one pick box. Clicking a plane in the
view or the tree, or a flat face of the part, fills it; another pick replaces
it. OK moves the sketch there as one undoable command and the part rebuilds;
Cancel leaves the sketch where it was. A plane or face made after the sketch
in the feature tree is refused, since the sketch could not be built from it.
"""

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import icons, strings
from fdcad.ui.themes.style import unit

if TYPE_CHECKING:
    from fdcad.core.document.model import Document
    from fdcad.core.sketch.profiles import SketchPlane
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

_FEATURE_ID = re.compile(r"\bf\d+\b")


def plane_label(doc: Document, ref: dict[str, Any]) -> str:
    """The name shown in the pick box: the plane's tree name, or "Face of the part"."""
    fid = ref.get("feature")
    if isinstance(fid, str):
        try:
            return doc.feature(fid).name
        except KeyError:
            return fid
    return strings.SKETCH_PLANE_FACE


def ref_comes_first(doc: Document, sketch_id: str, ref: dict[str, Any]) -> bool:
    """True when every feature behind ``ref`` comes before sketch ``sketch_id``."""
    order = {f.id: i for i, f in enumerate(doc.features)}
    here = order.get(sketch_id)
    if here is None:
        return False
    fid = ref.get("feature")
    names = [fid] if isinstance(fid, str) else _FEATURE_ID.findall(str(ref.get("name", "")))
    return all(order.get(n, here) < here for n in names)


class SketchPlanePanel(QWidget):
    """Header with OK and Cancel, and the pick box."""

    accepted = Signal()
    rejected = Signal()

    def __init__(self, sketch_name: str, current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("property_panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        u = unit(self.font())
        header_box = QWidget()
        header_box.setObjectName("panel_header")
        header_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        # Two rows, like the property panel (D1034): OK and Cancel never get cut off.
        rows = QVBoxLayout(header_box)
        rows.setContentsMargins(2 * u, 2 * u, 2 * u, 2 * u)
        rows.setSpacing(2 * u)
        header = QHBoxLayout()
        rows.addLayout(header)
        mark = QLabel()
        size = self.style().pixelMetric(QStyle.PixelMetric.PM_LargeIconSize)
        mark.setPixmap(
            icons.icon("sketch.edit_plane").pixmap(QSize(size, size), self.devicePixelRatioF())
        )
        self.title = QLabel(f"<b>{strings.EDIT_SKETCH_PLANE}: {sketch_name}</b>")
        self.title.setObjectName("panel_title")
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accepted)
        self.buttons.rejected.connect(self.rejected)
        header.addWidget(mark)
        header.addWidget(self.title, 1)
        rows.addWidget(self.buttons)
        self.pick = QLabel(current)
        self.pick.setObjectName("plane_pick_box")
        self.pick.setFrameShape(QLabel.Shape.StyledPanel)
        self.hint = QLabel(strings.SKETCH_PLANE_HINT)
        self.hint.setWordWrap(True)
        body = QVBoxLayout()
        body.setContentsMargins(2 * u, 2 * u, 2 * u, 2 * u)
        form = QFormLayout()
        form.addRow(strings.SKETCH_PLANE_PICK, self.pick)
        body.addLayout(form)
        body.addWidget(self.hint)
        body.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(header_box)
        outer.addLayout(body, 1)


class EditSketchPlane:
    """Runs Edit Sketch Plane for one sketch of the active document."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.tab: DocumentTab | None = None
        self.sketch_id: str | None = None
        self.panel: SketchPlanePanel | None = None
        #: The new plane reference picked so far, or None.
        self.ref: dict[str, Any] | None = None

    @property
    def active(self) -> bool:
        """True while the panel is open."""
        return self.panel is not None

    def start(self, sketch_id: str) -> None:
        """Open the panel for ``sketch_id`` and wait for a pick."""
        w = self.window
        tab = w.current
        mode = w.sketch_mode
        if tab is None or mode is None:
            return
        if mode.is_open and not mode.accept():
            return
        self.finish()
        doc = tab.session.document
        feature = doc.feature(sketch_id)
        current = feature.refs.get("plane")
        label = plane_label(doc, current) if isinstance(current, dict) else ""
        self.tab, self.sketch_id, self.ref = tab, sketch_id, None
        panel = SketchPlanePanel(feature.name, label)
        panel.accepted.connect(self.accept)
        panel.rejected.connect(self.cancel)
        self.panel = panel
        w.show_side_panel(panel)
        self._wait()

    def _wait(self) -> None:
        mode = self.window.sketch_mode
        if self.tab is not None and mode is not None:
            mode.picker.start(self.tab, self.picked, self.cancel)
            self.window.status.setText(strings.SKETCH_PLANE_HINT)

    def picked(self, ref: dict[str, Any], _placement: SketchPlane | None = None) -> None:
        """A plane or face was picked: show it and wait for OK or another pick."""
        if self.tab is None or self.sketch_id is None or self.panel is None:
            return
        doc = self.tab.session.document
        name = doc.feature(self.sketch_id).name
        self._wait()
        if ref_comes_first(doc, self.sketch_id, ref):
            self.ref = ref
            self.panel.pick.setText(plane_label(doc, ref))
        else:
            self.window.status.setText(strings.SKETCH_PLANE_LATER.format(name=name))

    def accept(self) -> None:
        """Move the sketch to the picked plane as one undoable command."""
        from fdcad.ui.commands.document import ReplaceFeature

        tab, sid, ref = self.tab, self.sketch_id, self.ref
        self.finish()
        if tab is None or sid is None or ref is None:
            return
        doc = tab.session.document
        feature = doc.feature(sid)
        if feature.refs.get("plane") == ref:
            return
        edited = copy.deepcopy(feature)
        edited.refs["plane"] = copy.deepcopy(ref)
        text = f"{strings.EDIT_SKETCH_PLANE} {feature.name}"
        tab.session.undo.push(ReplaceFeature(tab.session, edited, text))

    def cancel(self) -> None:
        """Leave the sketch where it was."""
        self.finish()
        self.window.status.setText(strings.READY)

    def finish(self) -> None:
        """Close the panel and stop waiting for picks."""
        w = self.window
        panel = self.panel
        self.panel = None
        if w.sketch_mode is not None and w.sketch_mode.picker.active:
            w.sketch_mode.picker.on_cancel = None
            w.sketch_mode.picker.finish()
        if panel is not None:
            w.hide_side_panel()
            panel.deleteLater()
        self.tab, self.sketch_id = None, None
