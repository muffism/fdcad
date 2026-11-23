"""What lies under the cursor in the 3D view is the face, edge or vertex there, not
the whole part (IDEAS 83 F2, D2781).

The kernel's ``DetectedCurrentShape`` gives the whole shape of the shown item, and
for the part that is the part itself. Select Other, the view's right click menu,
Paste on a face, Select Through Faces, picking through see through bodies and the
handle snap read what lies under the cursor. These tests run on the offscreen
platform: the view gets a kernel view with no window, and the cursor is a ray, so
the kernel's own picking runs without a graphics card.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from OCP.AIS import AIS_ColoredShape, AIS_Shape
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopoDS import TopoDS_Shape
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import DocumentTab, MainWindow
from tests.ui.test_feature_paste import _open_bracket
from tests.ui.test_main_window import _folders, window
from tests.ui.test_workflow import face_with_normal

__all__ = ["_folders", "window"]

PARTS = (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX)


class _Aimed:
    """The view's interactive context, with ``MoveTo`` at a pixel turned into a ray.

    Picking at a pixel needs a window; picking along a ray does not.
    """

    def __init__(self, context: Any) -> None:
        self.context = context
        self.ray = gp_Ax1(gp_Pnt(0, 0, 100), gp_Dir(0, 0, -1))

    def MoveTo(self, *_args: Any) -> Any:  # noqa: N802 (the kernel's name)
        return self.context.MoveTo(self.ray, _args[2], False)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.context, name)


@pytest.fixture
def view(qapp: QApplication) -> Iterator[Any]:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    v = ViewportWidget()
    v._view = v._viewer.CreateView()  # no window: picking only
    v._context = _Aimed(v._context)
    yield v
    v.release()  # free the kernel view while the widget exists (D2780)
    v.deleteLater()


def _show(view: Any, shape: TopoDS_Shape) -> None:
    """Show ``shape`` as the part with faces, edges and vertices pickable."""
    part = AIS_ColoredShape(shape)
    view._context.Display(part, False)  # as show_part does
    view._part = part
    view._activate()


def _aim(view: Any, at: tuple[float, float, float], toward: tuple[float, float, float]) -> None:
    """Point the cursor's ray at ``at``, coming from 100 mm back along ``toward``."""
    start = gp_Pnt(*(a - 100.0 * t for a, t in zip(at, toward, strict=True)))
    view._context.ray = gp_Ax1(start, gp_Dir(*toward))


def _box() -> TopoDS_Shape:
    return BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()


def _top_face(box: TopoDS_Shape) -> TopoDS_Shape:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    explorer = TopExp_Explorer(box, TopAbs_FACE)
    while explorer.More():
        face = explorer.Current()
        if BRepAdaptor_Surface(TopoDS.Face(face)).Value(0.0, 0.0).Z() > 9.9:
            plane = BRepAdaptor_Surface(TopoDS.Face(face)).Plane()
            if abs(plane.Axis().Direction().Z()) > 0.99:
                return face
        explorer.Next()
    raise AssertionError("the box has no top face")


# detected_at --------------------------------------------------------------------------


def test_detected_at_gives_the_face_under_the_cursor(view: Any) -> None:
    box = _box()
    _show(view, box)
    _aim(view, (5.0, 5.0, 10.0), (0.0, 0.0, -1.0))  # the middle of the top face
    found = view.detected_at(QPointF(10, 10))
    assert found, "nothing under the cursor"
    assert all(s.ShapeType() in PARTS for s in found), [s.ShapeType() for s in found]
    assert found[0].IsSame(_top_face(box))
    assert not any(s.IsSame(box) for s in found)


def test_detected_at_gives_the_edge_under_the_cursor(view: Any) -> None:
    _show(view, _box())
    _aim(view, (5.0, 0.0, 10.0), (0.0, 0.0, -1.0))  # on the top face's front edge
    kinds = [s.ShapeType() for s in view.detected_at(QPointF(10, 10))]
    assert TopAbs_EDGE in kinds and TopAbs_FACE in kinds


def test_detected_at_leaves_out_a_face_hidden_for_now(view: Any) -> None:
    box = _box()
    _show(view, box)
    _aim(view, (5.0, 5.0, 10.0), (0.0, 0.0, -1.0))
    top = _top_face(box)
    view._hidden_faces = [top]
    assert not any(s.IsSame(top) for s in view.detected_at(QPointF(10, 10)))


def test_detected_at_leaves_out_items_that_are_not_the_part(view: Any) -> None:
    _show(view, _box())
    other = AIS_Shape(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 20), 10.0, 10.0, 10.0).Shape())
    view._context.Display(other, 1, 0, False)  # above the part, nearer the cursor
    _aim(view, (5.0, 5.0, 10.0), (0.0, 0.0, -1.0))
    found = view.detected_at(QPointF(10, 10))
    assert found and all(s.ShapeType() in PARTS for s in found)
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    mine = ShapeMap()
    TopExp.MapShapes_s(view._part.Shape(), mine)
    assert all(mine.Contains(s) for s in found)


# The other readers of what lies under the cursor --------------------------------------


def test_snap_finds_the_vertex_under_the_cursor(view: Any) -> None:
    """A drag handle snaps to a vertex of the part (T5.2.4); it never found one."""
    from fdcad.core.features.base import PreviewHandle

    _show(view, _box())
    _aim(view, (10.0, 10.0, 10.0), (-0.577, -0.577, -0.577))  # the corner nearest the eye
    handle = PreviewHandle("depth", (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 10.0, snaps=True)
    found = view._snap_target(handle, QPointF(10, 10))
    assert found is not None and found[1] == "vertex"
    assert found[0] == pytest.approx((10.0, 10.0, 10.0))


def test_select_through_faces_finds_the_edge_behind(view: Any) -> None:
    """Select Through Faces (TR64) takes the first edge under the cursor."""
    _show(view, _box())
    view.pick_through = True
    _aim(view, (5.0, 0.0, 10.0), (0.0, 0.0, -1.0))
    view._context.MoveTo(0, 0, view._view, False)
    edge = view._edge_through()
    assert edge is not None and edge.ShapeType() == TopAbs_EDGE


def test_pick_through_a_see_through_body_takes_the_face_behind(view: Any) -> None:
    """A click on a see through body picks what is behind it (TR224 item 1)."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    near = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 20), 10.0, 10.0, 10.0).Shape()
    far = _box()
    both = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(both)
    builder.Add(both, near)
    builder.Add(both, far)
    view._see_through = [near]
    _show(view, both)
    _aim(view, (5.0, 5.0, 10.0), (0.0, 0.0, -1.0))
    view._context.MoveTo(0, 0, view._view, False)
    picked = view._through_pick(Qt.KeyboardModifier.NoModifier)
    assert picked is not None and picked.IsSame(_top_face(far))


# The callers in the main window -------------------------------------------------------


def _bracket_in_view(qtbot: QtBot, window: MainWindow, tmp_path: Path, view: Any) -> DocumentTab:
    """The bracket sample, shown in ``view`` as its tab's 3D view."""
    tab = _open_bracket(qtbot, window, tmp_path)
    report = tab.session.report
    assert report is not None and report.body is not None
    _show(view, report.body.shape)
    tab.viewport = view
    return tab


def _centre(face: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """A point inside ``face`` and its outward normal."""
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_IN
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.sketch import face_plane

    f = TopoDS.Face(face)
    u0, u1, v0, v1 = BRepTools.UVBounds_s(f)
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    surface = BRepAdaptor_Surface(f)
    plane = face_plane(f)
    assert plane is not None
    for i in range(1, 10):
        for j in range(1, 10):
            u, v = u0 + (u1 - u0) * i / 10, v0 + (v1 - v0) * j / 10
            if BRepClass_FaceClassifier(f, gp_Pnt2d(u, v), 1e-6).State() == TopAbs_IN:
                p = surface.Value(u, v)
                return (p.X(), p.Y(), p.Z()), tuple(plane.normal)  # type: ignore[return-value]
    raise AssertionError("no point inside the face")


def test_paste_on_the_face_under_the_cursor(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, view: Any
) -> None:
    """Ctrl drag a feature onto a face: it was never found, the part is not a face."""
    tab = _bracket_in_view(qtbot, window, tmp_path, view)
    face = face_with_normal(tab, (-1.0, 0.0, 0.0))
    at, normal = _centre(face)
    _aim(view, at, tuple(-n for n in normal))  # type: ignore[arg-type]
    view.part_point_at = lambda pos: None
    window.feature_clipboard.ask_keep = lambda n: False
    count = len(tab.session.document.features)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert window.feature_clipboard.drop_at(QPointF(10, 10), "f8")
    assert len(tab.session.document.features) == count + 2


def test_right_click_selects_the_face_under_the_cursor(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, view: Any
) -> None:
    tab = _bracket_in_view(qtbot, window, tmp_path, view)
    face = face_with_normal(tab, (-1.0, 0.0, 0.0))
    at, normal = _centre(face)
    _aim(view, at, tuple(-n for n in normal))  # type: ignore[arg-type]
    window.context_menus.view_menu(tab, QPointF(10, 10))
    assert len(tab.selection) == 1 and tab.selection[0].IsSame(face)


def test_select_other_lists_faces_and_edges(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, view: Any
) -> None:
    from fdcad.ui.viewport.select_other import open_select_other

    tab = _bracket_in_view(qtbot, window, tmp_path, view)
    face = face_with_normal(tab, (-1.0, 0.0, 0.0))
    at, normal = _centre(face)
    _aim(view, at, tuple(-n for n in normal))  # type: ignore[arg-type]
    popup = open_select_other(window, tab, QPointF(10, 10))
    assert popup is not None
    rows = popup.candidates
    assert rows[0].kind == "face" and rows[0].payload.IsSame(face)
    assert all(r.payload.ShapeType() in PARTS for r in rows if r.kind != "plane")
