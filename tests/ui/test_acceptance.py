"""The Block, Turned and Box tests of docs/WORKFLOW_SPEC.md, driven through the
window's commands and mouse clicks on the sketch canvas (offscreen).

The 3D view does not exist offscreen, so picking a face in it is done by
setting the tab's selection, the same thing a click in the view does.
"""

from __future__ import annotations

import math

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.model import Line
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    click,
    face_with_normal,
    new_part,
    plane_id,
    window,
)


def view(qtbot: QtBot, win: MainWindow, center: tuple[float, float], scale: float) -> SketchCanvas:
    canvas = canvas_of(win)
    qtbot.wait(30)
    canvas.scale, canvas.center = scale, center
    return canvas


def dimension(
    qtbot: QtBot,
    canvas: SketchCanvas,
    picks: list[tuple[float, float]],
    place: tuple[float, float],
    value: str,
) -> None:
    """Smart Dimension: click the items, click where the text goes, type the value."""
    canvas.set_tool("dimension")
    for p in picks:
        click(qtbot, canvas, *p)
    click(qtbot, canvas, *place)
    box = canvas.value_box
    assert box is not None, f"no value box for {picks}"
    box.edit.setText(value)
    box.ok.click()
    assert canvas.value_box is None
    canvas.set_tool(None)


def exit_sketch(qtbot: QtBot, tab: DocumentTab) -> None:
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.corner_ok.click()


def ok_feature(qtbot: QtBot, win: MainWindow, tab: DocumentTab) -> None:
    assert win.panel is not None and win.panel.is_editing
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.corner_ok.click()
    report = tab.session.report
    assert report is not None
    last = tab.session.document.features[-1]
    assert report.results[last.id].state is FeatureState.OK, report.results[last.id].issues


def volume(tab: DocumentTab) -> float:
    report = tab.session.report
    assert report is not None and report.body is not None
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(report.body.shape, props)
    return props.Mass()


def test_block(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    tree, mode, panel = window.tree, window.sketch_mode, window.panel
    assert tree is not None and mode is not None and panel is not None

    # Corner rectangle on Top from the origin, dimensioned 30 x 90, extruded 30.
    tree.select(plane_id(tab, "Top Plane"))
    window.commands.trigger("sketch.sketch")
    canvas = view(qtbot, window, (20.0, 45.0), 4.0)
    canvas.set_tool("corner_rectangle")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 25, 80)
    dimension(qtbot, canvas, [(12, 0)], (12, -8), "30")
    dimension(qtbot, canvas, [(30, 40)], (40, 40), "90")
    assert canvas.edit.status().state.value == "full"
    exit_sketch(qtbot, tab)
    window.commands.trigger("feature.extrude")  # uses the only unused sketch
    panel.values["depth"].edit.setText("30")
    ok_feature(qtbot, window, tab)
    assert volume(tab) == pytest.approx(30 * 30 * 90, rel=1e-6)

    # Preselect the top face, Extrude: two circles of diameter 20 placed by dimensions.
    tab.selection = [face_with_normal(tab, (0.0, 1.0, 0.0))]
    window.commands.trigger("feature.extrude")
    assert mode.is_open
    canvas = view(qtbot, window, (15.0, 45.0), 4.0)
    canvas.set_tool("circle")
    for cy in (25.0, 65.0):
        click(qtbot, canvas, 14, cy)
        click(qtbot, canvas, 20, cy)
    dimension(qtbot, canvas, [(14 + 6 * 0.7071, 25 + 6 * 0.7071)], (25, 35), "20")
    dimension(qtbot, canvas, [(14 + 6 * 0.7071, 65 + 6 * 0.7071)], (25, 75), "20")
    for cy, gap in ((25.0, "22.5"), (65.0, "67.5")):
        dimension(qtbot, canvas, [(0, 0), (14, cy)], (7, -6), "15")
        dimension(qtbot, canvas, [(0, 0), (14, cy)], (-6, cy / 2), gap)
    assert canvas.edit.status().state.value == "full"
    exit_sketch(qtbot, tab)  # the panel opens on the sketch
    assert panel.feature is not None and panel.feature.name == "Extrude 2"
    panel.values["depth"].edit.setText("10")
    ok_feature(qtbot, window, tab)
    studs = 2 * math.pi * 10**2 * 10
    assert volume(tab) == pytest.approx(81000 + studs, rel=1e-6)

    # Extruded Cut, pick a stud's top face, circle snapped to the stud centre, diameter 16.
    window.commands.trigger("feature.extruded_cut")
    assert mode.picker.active
    mode.picker._faces_picked([face_with_normal(tab, (0.0, 1.0, 0.0))])
    assert mode.is_open
    canvas = canvas_of(window)
    qtbot.waitUntil(lambda: bool(canvas.reference_circles), timeout=20000)
    (cx, cy), r = canvas.reference_circles[0]
    canvas = view(qtbot, window, (cx, cy), 6.0)
    canvas.set_tool("circle")
    qtbot.mouseMove(canvas, canvas.to_screen((cx + r, cy)).toPoint())  # reveal the centre
    click(qtbot, canvas, cx + 0.4, cy + 0.3)
    click(qtbot, canvas, cx + 6, cy)
    circle = canvas.edit.sketch.curves()[0]
    assert canvas.edit.sketch.xy(circle.center) == pytest.approx((cx, cy))
    dimension(qtbot, canvas, [(cx + 6 * 0.7071, cy + 6 * 0.7071)], (cx + 12, cy + 12), "16")
    exit_sketch(qtbot, tab)
    assert panel.feature is not None and panel.feature.name == "Cut 1"
    panel.values["depth"].edit.setText("10")
    ok_feature(qtbot, window, tab)
    cut = math.pi * 8**2 * 10
    assert volume(tab) == pytest.approx(81000 + studs - cut, rel=1e-6)

    # Extruded Cut on the bottom face, circle diameter 10, Through All.
    tab.selection = [face_with_normal(tab, (0.0, -1.0, 0.0))]
    window.commands.trigger("feature.extruded_cut")
    assert mode.is_open
    canvas = view(qtbot, window, (15.0, -45.0), 4.0)
    canvas.set_tool("circle")
    click(qtbot, canvas, 15, -45)
    click(qtbot, canvas, 19, -45)
    dimension(qtbot, canvas, [(15 + 4 * 0.7071, -45 + 4 * 0.7071)], (25, -35), "10")
    exit_sketch(qtbot, tab)
    box = panel.choices["end_condition"]
    box.setCurrentIndex(box.findData("through_all"))
    ok_feature(qtbot, window, tab)
    hole = math.pi * 5**2 * 30
    assert volume(tab) == pytest.approx(81000 + studs - cut - hole, rel=1e-6)
    # Every sketch sits under its feature in the tree and is hidden in the view.
    assert tab.visible_sketch_ids() == []
    assert [f.name for f in tab.session.document.features if f.type != "sketch"][4:] == [
        "Extrude 1",
        "Extrude 2",
        "Cut 1",
        "Cut 2",
    ]


def test_turned(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    tree, mode, panel = window.tree, window.sketch_mode, window.panel
    assert tree is not None and mode is not None and panel is not None

    # Revolve with nothing selected: pick Front.
    window.commands.trigger("feature.revolve")
    assert mode.picker.active
    tree.select(plane_id(tab, "Front Plane"))
    assert mode.is_open
    canvas = view(qtbot, window, (22.0, 125.0), 2.5)

    def chain(points: list[tuple[float, float]]) -> None:
        canvas.set_tool("line")
        for p in points:
            click(qtbot, canvas, *p)
        canvas.set_tool(None)

    chain([(0, 0), (0, 250), (15, 250)])  # the vertical 250 line from the origin first
    canvas.set_tool("three_point_arc")
    for p in ((15, 250), (25, 200), (24, 230)):
        click(qtbot, canvas, *p)
    chain([(25, 200), (25, 60)])
    canvas.set_tool("center_arc")
    for p in ((26, 40), (25, 60), (45, 40)):
        click(qtbot, canvas, *p)
    chain([(45, 40), (45, 0), (0, 0)])
    sk = canvas.edit.sketch
    assert not canvas.edit.status().issues, canvas.edit.status().issues

    # Vertical relation between the arc centre and its start, by Ctrl click and the panel.
    click(qtbot, canvas, 26, 40, ctrl=True)
    click(qtbot, canvas, 25, 60, ctrl=True)
    assert mode.panel is not None
    mode.panel.relation_buttons["vertical"].click()
    a, b = (sk.xy(i) for i in canvas.selection)
    assert a[0] == pytest.approx(b[0], abs=1e-6) and abs(a[1] - b[1]) > 10
    axis = next(
        e.id
        for e in sk.curves()
        if isinstance(e, Line)
        and max(abs(sk.xy(e.p1)[0]), abs(sk.xy(e.p2)[0])) < 1e-6
        and abs(sk.xy(e.p1)[1] - sk.xy(e.p2)[1])
        == pytest.approx(250.0, abs=0.5)  # clicks land on whole pixels
    )

    exit_sketch(qtbot, tab)
    assert panel.feature is not None and panel.feature.name == "Revolve 1"
    panel.axis_box.setCurrentIndex(panel.axis_box.findData(axis))  # the 250 line
    assert panel.values["angle"].edit.text() == "360"
    ok_feature(qtbot, window, tab)
    assert volume(tab) > math.pi * 15**2 * 200  # at least the thin part of the body


def test_box(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    tree, mode, panel, preview = window.tree, window.sketch_mode, window.panel, window.preview
    assert tree is not None and mode is not None and panel is not None and preview is not None

    # Sketch on a preselected Front plane: rectangle 120 x 70.
    tree.select(plane_id(tab, "Front Plane"))
    window.commands.trigger("sketch.sketch")
    assert mode.is_open
    canvas = view(qtbot, window, (60.0, 35.0), 4.0)
    canvas.set_tool("corner_rectangle")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 110, 60)
    dimension(qtbot, canvas, [(55, 0)], (55, -10), "120")
    dimension(qtbot, canvas, [(120, 30)], (135, 30), "70")
    assert canvas.edit.status().state.value == "full"

    # Double click the 70 and change it to 75.
    canvas.update()
    qtbot.wait(30)
    seventy = next(d for d in canvas.edit.sketch.dimensions if d.param.value == 70.0)
    label = canvas._labels[seventy.id].center().toPoint()
    qtbot.mouseDClick(canvas, Qt.MouseButton.LeftButton, pos=label)
    box = canvas.value_box
    assert box is not None and box.edit.text() == seventy.param.expr
    box.edit.setText("75")
    box.ok.click()
    sk = canvas.edit.sketch
    heights = {abs(sk.xy(e.p1)[1] - sk.xy(e.p2)[1]) for e in sk.curves() if isinstance(e, Line)}
    assert max(heights) == pytest.approx(75.0)
    exit_sketch(qtbot, tab)

    # Extrude 40 by dragging the handle, then by typing.
    with qtbot.waitSignal(preview.ready, timeout=20000):
        window.commands.trigger("feature.extrude")  # uses the only unused sketch
    assert panel.feature is not None and panel.feature.name == "Extrude 1"
    data = preview.data
    assert data is not None and [h.param for h in data.handles] == ["depth"]
    with qtbot.waitSignal(preview.ready, timeout=20000):
        preview.drag_to("depth", 37.5)  # the handle API the view drives
    assert panel.values["depth"].edit.text() == "37.5"
    assert preview.data is not None and preview.data.handles[0].value == pytest.approx(37.5)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        preview.drag_to("depth", 40.0)
    assert panel.values["depth"].edit.text() == "40"
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.values["depth"].edit.setText("40 mm")
    assert preview.data is not None and preview.data.handles[0].value == pytest.approx(40.0)
    ok_feature(qtbot, window, tab)
    assert volume(tab) == pytest.approx(120 * 75 * 40, rel=1e-6)

    # Sketch a circle on the front face, dimension it to two edges, Extruded Cut Through All.
    tab.selection = [face_with_normal(tab, (0.0, 0.0, 1.0))]
    window.commands.trigger("sketch.sketch")
    assert mode.is_open
    canvas = canvas_of(window)
    qtbot.waitUntil(lambda: bool(canvas.reference), timeout=20000)
    canvas = view(qtbot, window, (60.0, 37.5), 4.0)
    canvas.set_tool("circle")
    click(qtbot, canvas, 32, 41)
    click(qtbot, canvas, 40, 41)
    circle = canvas.edit.sketch.curves()[0]
    rim = (32 + 8 * 0.7071, 41 + 8 * 0.7071)
    dimension(qtbot, canvas, [rim], (50, 55), "16")
    dimension(qtbot, canvas, [rim, (0, 20)], (16, 60), "30")  # to the left edge
    dimension(qtbot, canvas, [rim, (90, 0)], (95, 20), "25")  # to the bottom edge
    sk = canvas.edit.sketch
    assert sk.xy(circle.center) == pytest.approx((30.0, 25.0))
    assert canvas.edit.status().state.value == "full"
    exit_sketch(qtbot, tab)
    window.commands.trigger("feature.extruded_cut")
    assert panel.feature is not None and panel.feature.name == "Cut 1"
    box = panel.choices["end_condition"]
    box.setCurrentIndex(box.findData("through_all"))
    ok_feature(qtbot, window, tab)
    assert volume(tab) == pytest.approx(120 * 75 * 40 - math.pi * 8**2 * 40, rel=1e-6)
