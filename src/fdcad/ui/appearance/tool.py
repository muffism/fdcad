"""Appearance, Copy Appearance and Paste Appearance commands (P2.11, D254)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from fdcad.core.appearance import Target, face_colors, part_color
from fdcad.ui import strings
from fdcad.ui.appearance.commands import SetAppearance

if TYPE_CHECKING:
    from OCP.TopoDS import TopoDS_Face

    from fdcad.ui.appearance.panel import AppearancePanel
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


def selected_faces(tab: DocumentTab) -> list[str]:
    """Names of the faces selected in the 3D view."""
    from OCP.TopAbs import TopAbs_FACE

    report = tab.session.report
    if report is None or report.body is None:
        return []
    names = []
    for shape in tab.selection:
        if shape.ShapeType() == TopAbs_FACE:
            name = report.body.primary_name(shape)
            if name is not None and name not in names:
                names.append(name)
    return names


def part_display(tab: DocumentTab) -> tuple[str, list[tuple[TopoDS_Face, str]]]:
    """The part colour and the faces in other colours, for the 3D view and export."""
    app = tab.session.document.appearance
    report = tab.session.report
    body = report.body if report is not None else None
    from fdcad.core.appearance import propagating

    doc = tab.session.document
    faces = face_colors(body, app, propagating(doc)) if body is not None else []
    return part_color(app), faces


class AppearanceTool(QObject):
    """Owns the Appearance panel and the copied colour."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.panel: AppearancePanel | None = None
        #: The colour Copy Appearance took, for Paste Appearance.
        self.copied: str | None = None

    def _targets(self, tab: DocumentTab) -> list[tuple[str, list[Target]]]:
        from fdcad.core.features import REGISTRY
        from fdcad.ui.appearance.panel import targets_for

        feature = self.window.tree.selected_id() if self.window.tree is not None else None
        if feature is not None:
            ftype = REGISTRY.get(tab.session.document.feature(feature).type)
            if ftype is None or not ftype.makes_solid:
                feature = None
        return targets_for(tab.session, selected_faces(tab), feature)

    def open(self) -> None:
        """Show the Appearance panel for the selection (faces, a feature, or the part)."""
        from fdcad.ui.appearance.panel import AppearancePanel

        tab = self.window.current
        if tab is None:
            return
        self.close()
        panel = AppearancePanel(tab.session, self._targets(tab))
        panel.closed.connect(self.close)
        self.panel = panel
        self.window.show_side_panel(panel)

    def close(self) -> None:
        """Close the panel."""
        if self.panel is not None:
            self.window.hide_side_panel()
            self.panel.deleteLater()
            self.panel = None

    def tab_changed(self) -> None:
        """Close the panel when another part is shown, so it never colours a hidden part."""
        tab = self.window.current
        if self.panel is not None and (tab is None or self.panel.session is not tab.session):
            self.close()

    def copy(self) -> None:
        """Copy Appearance: remember the colour of the selection (or the part)."""
        from fdcad.ui.appearance.panel import effective_color

        tab = self.window.current
        if tab is None:
            return
        targets = self._targets(tab)[0][1]
        self.copied = effective_color(tab.session, targets)
        self.window.status.setText(strings.APPEARANCE_COPIED.format(color=self.copied))

    def paste(self) -> None:
        """Paste Appearance: give the selection the copied colour, as one undoable step."""
        tab = self.window.current
        if tab is None or self.copied is None:
            self.window.status.setText(strings.APPEARANCE_NOTHING_COPIED)
            return
        label, targets = self._targets(tab)[0]
        text = strings.APPEARANCE_SET.format(item=label)
        tab.session.undo.push(SetAppearance(tab.session, targets, self.copied, text))
