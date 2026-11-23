"""File, Export, DXF and SVG of a flat face or a sketch (PLAN Phase 2, DECISIONS D350).

The source is one flat face picked in the 3D view, else the sketch selected in
the feature tree. The kernel work (making and flattening the edges) and the
file writing run in the background.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QFileDialog

from fdcad.ui import strings_print as text
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


class FlatSource:
    """What to export: a face, or a built sketch (its model and plane)."""

    def __init__(self, name: str, face: Any = None, sketch: Any = None) -> None:
        self.name = name
        self.face = face
        self.sketch = sketch

    def edges_and_plane(self) -> tuple[list[Any], Any]:
        """The 3D edges and the plane to flatten them in (kernel work: run in the background)."""
        from fdcad.core.io import flat_export

        if self.face is not None:
            return flat_export.face_edges(self.face), flat_export.face_plane(self.face)
        return flat_export.sketch_items(self.sketch.model, self.sketch.plane)


def find_source(window: MainWindow, tab: DocumentTab) -> FlatSource | str:
    """The face picked in the view, else the sketch picked in the tree, else a message."""
    from OCP.TopAbs import TopAbs_FACE

    faces = [s for s in tab.selection if s.ShapeType() == TopAbs_FACE]
    if len(faces) == 1 and len(tab.selection) == 1:
        return FlatSource(tab.session.title.rstrip("*"), face=faces[0])
    tree = window.tree
    fid = tree.selected_id() if tree is not None else None
    doc = tab.session.document
    if fid is None or doc.feature(fid).type != "sketch":
        return text.FLAT_NOTHING
    name = doc.feature(fid).name
    report = tab.session.report
    result = report.results.get(fid) if report is not None else None
    if result is None or result.sketch is None:
        return text.FLAT_NOT_BUILT.format(name=name)
    return FlatSource(name, sketch=result.sketch)


def export(window: MainWindow, kind: str, path: str | None = None) -> jobs.Job | None:
    """Export as ``kind`` ("dxf" or "svg"). ``path`` skips the file dialog (tests)."""
    from fdcad.core.io import flat_export

    tab = window.current
    if tab is None:
        window.status.setText(text.FLAT_NOTHING)
        return None
    source = find_source(window, tab)
    if isinstance(source, str):
        window.status.setText(source)
        return None
    if path is None:
        filters = {"dxf": text.FILTER_DXF, "svg": text.FILTER_SVG}
        default = f"{source.name}.{kind}"
        path, _ = QFileDialog.getSaveFileName(window, kind.upper(), default, filters[kind])
        if not path:
            return None
        if not path.lower().endswith(f".{kind}"):
            path += f".{kind}"
    units = tab.session.document.units.value
    target = path

    def work() -> str:
        left = 0
        if source.sketch is not None:
            edges, plane, left = flat_export.sketch_items_left_out(
                source.sketch.model, source.sketch.plane
            )
        else:
            edges, plane = source.edges_and_plane()
        flat_export.export_flat(edges, plane, target, units)
        done = text.FLAT_DONE.format(name=Path(target).name, units=units)
        if left:
            done += " " + text.FLAT_LEFT_OUT.format(n=left, s="s" if left != 1 else "")
        return done

    return jobs.start(
        work,
        window.status.setText,
        lambda reason: window.status.setText(text.FLAT_FAILED.format(reason=reason)),
    )
