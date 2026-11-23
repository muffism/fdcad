"""Normal To rules, view menu items and the view selector (TOOL_SPEC T14.4).

The 3D view needs a GPU, so a small stand in records what the window asks of it.
"""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.viewport import view_selector as vs
from fdcad.ui.viewport.views import (
    STANDARD_VIEWS,
    axis_view,
    flipped,
    nearest_standard,
    same_direction,
    two_face_view,
    view_name,
)
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    draw_rectangle,
    face_with_normal,
    new_part,
    plane_id,
    rectangle_sketch,
    window,
)

# Pure rules ---------------------------------------------------------------------------------


def test_nearest_standard_flip_axis_and_two_faces() -> None:
    assert nearest_standard((0.2, 0.9, 0.1)) == STANDARD_VIEWS["top"]
    assert nearest_standard((-0.8, 0.3, 0.2)) == STANDARD_VIEWS["left"]
    assert flipped((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)) == ((-0.0, -0.0, -1.0), (0.0, 1.0, 0.0))
    eye, _up = axis_view((0.0, 0.0, 1.0), (0.1, 0.2, -0.9), (0.0, 1.0, 0.0))
    assert eye == pytest.approx((0.0, 0.0, -1.0))  # from the end nearer the eye
    eye, up = two_face_view((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))  # type: ignore[misc]
    assert eye == pytest.approx((0.0, 0.0, 1.0)) and up == pytest.approx((0.0, 1.0, 0.0))
    eye, up = two_face_view((1.0, 0.0, 0.0), (0.6, 0.0, 0.8))  # type: ignore[misc]
    assert up == pytest.approx((0.0, 0.0, 1.0))
    assert two_face_view((0.0, 0.0, 1.0), (0.0, 0.0, -1.0)) is None
    assert same_direction((0.0, 0.0, 2.0), (0.0, 0.0, 1.0))
    assert not same_direction((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))


def test_view_names() -> None:
    assert view_name((0.0, 0.0, 1.0)) == "Front"
    assert view_name((0.0, -1.0, 0.0)) == "Bottom"
    assert view_name((1.0, 0.0, 1.0)) == "Front Right"
    assert view_name((-1.0, 1.0, -1.0)) == "Back Left Top"
    assert view_name((1.0, 1.0, 1.0)) == "Isometric"


def test_back_faces_pushed_out_and_alt() -> None:
    for axis in range(3):
        sx, sy = vs.back_face_centre(axis)
        assert vs.direction_at(sx, sy) is None  # outside the cube's outline
        expected = [0.0, 0.0, 0.0]
        expected[axis] = -1.0
        assert vs.pick_at(sx, sy) == tuple(expected)
    front = vs.project((0.0, 0.0, 1.0))
    assert vs.pick_at(*front) == (0.0, 0.0, 1.0)
    assert vs.pick_at(*front, back=True) == (0.0, 0.0, -1.0)
    corner = vs.project((0.9, 0.9, 1.0))
    assert vs.pick_at(*corner, back=True) == (-1.0, -1.0, -1.0)


def test_preview_looks_from_the_direction() -> None:
    pts = vs.preview_points((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
    # Looking from the front: corner (1, 1, 1) is right, up and nearest.
    x, y, depth = pts[7]
    assert x == pytest.approx(1.0) and y == pytest.approx(-1.0) and depth == pytest.approx(1.0)


def _mouse(widget: object, kind: QEvent.Type, pos: QPointF, mods: Qt.KeyboardModifier) -> None:
    button = (
        Qt.MouseButton.LeftButton
        if kind == QEvent.Type.MouseButtonRelease
        else (Qt.MouseButton.NoButton)
    )
    event = QMouseEvent(kind, pos, widget.mapToGlobal(pos), button, button, mods)  # type: ignore[attr-defined]
    QApplication.sendEvent(widget, event)  # type: ignore[arg-type]


def test_view_selector_preview_alt_and_back_faces(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    looks: list[tuple[object, object]] = []
    tab.viewport.look = lambda eye, up: looks.append((eye, up))  # type: ignore[attr-defined]
    selector = window.show_view_selector()
    assert isinstance(selector, vs.ViewSelector) and selector.isVisible()
    cube = selector.cube
    front = cube.to_widget((0.0, 0.0, 1.0))
    none = Qt.KeyboardModifier.NoModifier
    _mouse(cube, QEvent.Type.MouseMove, front, none)
    assert selector.preview.name == "Front"
    _mouse(cube, QEvent.Type.MouseMove, front, Qt.KeyboardModifier.AltModifier)
    assert cube.back and selector.preview.name == "Back"
    _mouse(cube, QEvent.Type.MouseButtonRelease, front, Qt.KeyboardModifier.AltModifier)
    assert looks[-1] == STANDARD_VIEWS["back"]
    selector = window.show_view_selector()
    cube = selector.cube
    tab_point = cube.back_face_point(1)  # the bottom face, pushed out
    _mouse(cube, QEvent.Type.MouseMove, tab_point, none)
    assert selector.preview.name == "Bottom"
    _mouse(cube, QEvent.Type.MouseButtonRelease, tab_point, none)
    assert looks[-1] == STANDARD_VIEWS["bottom"]
    assert len(looks) == 2


# Normal To in the window ----------------------------------------------------------------------


class _View:
    """Records the camera the window asks for."""

    def __init__(self, eye: tuple[float, float, float]) -> None:
        self.eye, self.up = eye, (0.0, 1.0, 0.0)
        self.looks: list[tuple[object, object]] = []
        self.zoomed: list[object] = []

    def eye_up(self) -> tuple[object, object]:
        return self.eye, self.up

    def look(self, eye: tuple[float, float, float], up: tuple[float, float, float]) -> None:
        self.looks.append((eye, up))
        self.eye, self.up = eye, up

    def zoom_to(self, shapes: list[object]) -> bool:
        self.zoomed = list(shapes)
        return True


def _with_view(tab: DocumentTab, eye: tuple[float, float, float]) -> _View:
    view = _View(eye)
    tab.viewport = view
    return view


def test_normal_to_rules(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    assert window.tree is not None and window.panel is not None
    window.tree.select(sid)
    window.insert_feature("extrude", "boss")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.panel.accept()
    fid = tab.session.document.features[-1].id
    real = tab.viewport
    view = _with_view(tab, (0.3, 0.4, 0.8))
    try:
        tree = window.tree
        # A plane in the tree, then the same plane again: turned round.
        tree.select(plane_id(tab, "Front Plane"))
        window.normal_to()
        assert view.looks[-1][0] == pytest.approx((0.0, 0.0, 1.0))
        window.normal_to()
        assert view.looks[-1][0] == pytest.approx((0.0, 0.0, -1.0))
        # A feature looks at its sketch.
        tree.select(fid)
        window.normal_to()
        assert view.looks[-1][0] == pytest.approx((0.0, 0.0, 1.0))
        # Two flat faces: the first toward the screen, the second at the top.
        top = face_with_normal(tab, (0.0, 1.0, 0.0))
        front = face_with_normal(tab, (0.0, 0.0, 1.0))
        tab.selection = [front, top]
        window.normal_to()
        eye, up = view.looks[-1]
        assert eye == pytest.approx((0.0, 0.0, 1.0)) and up == pytest.approx((0.0, 1.0, 0.0))
        tab.selection = [top, front]
        window.normal_to()
        eye, up = view.looks[-1]
        assert eye == pytest.approx((0.0, 1.0, 0.0)) and up == pytest.approx((0.0, 0.0, 1.0))
        # Nothing selected: the nearest standard direction.
        tab.selection = []
        tree.setCurrentItem(None)  # type: ignore[arg-type]
        view.eye = (0.9, 0.2, 0.3)
        window.normal_to()
        assert view.looks[-1] == STANDARD_VIEWS["right"]
    finally:
        tab.viewport = real


def test_normal_to_a_round_face_looks_along_its_axis(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    tab = new_part(qtbot, window)
    side = TopExp_Explorer(BRepPrimAPI_MakeCylinder(5, 10).Shape(), TopAbs_FACE).Current()
    real = tab.viewport
    view = _with_view(tab, (0.2, 0.1, -0.9))
    try:
        tab.selection = [side]
        window.normal_to()
        assert view.looks[-1][0] == pytest.approx((0.0, 0.0, -1.0))
    finally:
        tab.viewport = real


def test_zoom_to_selection(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    rectangle_sketch(qtbot, window, tab)
    real = tab.viewport
    view = _with_view(tab, (0.0, 0.0, 1.0))
    try:
        tab.selection = []
        assert window.commands.trigger("view.zoom_selection")
        assert "Zoom to Selection" in window.status.text() and view.zoomed == []
        tab.selection = ["shape"]
        window.zoom_to_selection()
        assert view.zoomed == ["shape"]
    finally:
        tab.viewport = real
    assert window.sketch_mode is not None
    window.sketch_mode.edit(tab.session.document.features[-1].id)
    canvas = canvas_of(window)
    first = next(iter(canvas.edit.sketch.entities))
    canvas.selection = [e for e in canvas.edit.sketch.entities if e != first][:1]
    before = canvas.scale
    window.zoom_to_selection()
    assert canvas.scale != before
    assert math.isfinite(canvas.center[0])


def test_view_menu_items_and_show_toggles(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    view_menu = next(a.menu() for a in window.menuBar().actions() if a.text() == "&View")
    assert view_menu is not None
    texts = [a.text() for a in view_menu.actions()]
    for label in ("Zoom to Fit", "Zoom to Area", "Zoom to Selection", "Previous View"):
        assert label in texts
    subs = {a.menu().title(): a.menu() for a in view_menu.actions() if a.menu() is not None}
    assert [a.text() for a in subs["Display Style"].actions()] == [
        "Shaded With Edges",
        "Shaded",
        "Hidden Lines Removed",
        "Hidden Lines Visible",
        "Wireframe",
    ]
    assert [a.text() for a in subs["Hide or Show"].actions()] == [
        "Planes",
        "Origins",
        "Sketches",
        "Sketch Relations",
        "Curvature Combs",  # D514
    ]
    window.show_sketches_action.trigger()
    assert tab.sketches_hidden
    window.show_sketches_action.trigger()
    assert not tab.sketches_hidden
    window.show_planes_action.trigger()
    assert tab.reference_hidden and not window.show_planes_action.isChecked()
    window.toggle_reference_geometry()  # Ctrl+H keeps the menu in step
    assert not tab.reference_hidden and window.show_planes_action.isChecked()
    window.show_origins_action.trigger()
    assert tab.origin_shown
