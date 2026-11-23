"""Live feature preview (C2, L7, W6.4): built off the UI thread, cleared after use."""

import copy
import math
from collections.abc import Callable
from typing import Any

import pytest
from OCP.BRepCheck import BRepCheck_Analyzer
from PySide6.QtCore import QObject, Signal
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import PreviewHandle
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from fdcad.ui.viewport.preview import (
    FeaturePreview,
    PreviewData,
    arrow_shape,
    drag_angle,
    drag_distance,
    value_limits,
)
from tests.core.features.test_features import bounds, plate, shaft, volume


class FakeView(QObject):
    """Stands in for the 3D view, which needs a GPU."""

    handle_dragged = Signal(str, float)

    def __init__(self) -> None:
        super().__init__()
        self.shown: list[tuple[PreviewData, str]] = []
        self.cleared = 0
        self.label: Callable[[str, float], str] | None = None

    def show_preview(self, data: PreviewData, active: str, label: Any) -> None:
        self.shown.append((data, active))
        self.label = label

    def clear_preview(self) -> None:
        self.cleared += 1


def _setup(qtbot: QtBot, doc: Document) -> tuple[DocumentSession, PropertyPanel, FeaturePreview]:
    session = DocumentSession(doc)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    preview = FeaturePreview()
    return session, panel, preview


@pytest.fixture
def view() -> FakeView:
    return FakeView()


def test_preview_follows_panel_values(qtbot: QtBot, view: FakeView) -> None:
    doc, _ext = plate(10.0)
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    feature = session.document.features.pop()  # new feature, added only on OK
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, feature, is_new=True)
    data, active = view.shown[-1]
    assert active == "depth"
    assert data.geometry.shape is not None
    assert volume(data.geometry.shape) == pytest.approx(50 * 50 * 10)
    assert len(data.arrows) == 1 and data.arrow_size > 0
    assert view.label is not None and view.label("depth", 10.0) == "10.00 mm"
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.values["depth"].edit.setText("30")
    data, _ = view.shown[-1]
    assert data.geometry.shape is not None
    assert volume(data.geometry.shape) == pytest.approx(50 * 50 * 30)
    assert data.handles[0].tip[2] == pytest.approx(30.0)
    assert len(session.document.features) == len(doc.features)  # nothing committed yet


def test_rapid_changes_build_once_and_stale_results_are_dropped(
    qtbot: QtBot, view: FakeView
) -> None:
    doc, ext = plate(10.0)
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, doc.feature(ext), is_new=False)
    before = len(view.shown)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        for text in ("11", "12", "13", "14", "15"):
            panel.values["depth"].edit.setText(text)
    preview.wait()
    qtbot.wait(100)
    assert len(view.shown) == before + 1  # debounced into one build
    data, _ = view.shown[-1]
    assert data.geometry.shape is not None
    assert volume(data.geometry.shape) == pytest.approx(50 * 50 * 15)


def test_cancel_removes_preview_and_forgets_shapes(qtbot: QtBot, view: FakeView) -> None:
    doc, ext = plate(10.0)
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, doc.feature(ext), is_new=False)
    panel.values["depth"].edit.setText("40")  # a build is now waiting
    panel.reject()
    assert view.cleared >= 1
    assert preview.data is None and not preview.is_active
    shown = len(view.shown)
    preview.wait()
    qtbot.wait(100)
    assert len(view.shown) == shown  # nothing reached the view after Cancel


def test_ok_commits_through_undo_and_clears_preview(qtbot: QtBot, view: FakeView) -> None:
    doc, ext = plate(10.0)
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, doc.feature(ext), is_new=False)
    panel.values["depth"].edit.setText("20")
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    assert preview.data is None and not preview.is_active
    assert session.undo.count() == 1
    assert session.document.feature(ext).params["depth"].value == 20.0  # type: ignore[union-attr]


def test_dragged_handle_updates_the_typed_value(qtbot: QtBot, view: FakeView) -> None:
    doc, ext = plate(10.0)
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, doc.feature(ext), is_new=False)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        view.handle_dragged.emit("depth", 22.5)
    assert panel.values["depth"].edit.text() == "22.5"
    assert view.shown[-1][0].handles[0].value == pytest.approx(22.5)


def test_wrong_value_hides_preview_and_cut_shows_tool(qtbot: QtBot, view: FakeView) -> None:
    doc, ext = plate(10.0)
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    cut = copy.deepcopy(doc.feature(ext))
    cut.id, cut.name = "new", "Cut 1"
    cut.params["operation"] = "cut"
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, cut, is_new=True)
    assert view.shown[-1][0].geometry.shape is not None
    cleared = view.cleared
    panel.values["depth"].edit.setText("nonsense")
    assert view.cleared == cleared + 1 and preview.data is None


def test_preview_without_a_view_still_builds(qtbot: QtBot) -> None:
    doc, ext = plate(10.0)
    session, _panel, preview = _setup(qtbot, doc)
    preview.start(session, None)
    feature: Feature = doc.feature(ext)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        preview.show(feature)
    assert preview.data is not None
    preview.clear()
    assert preview.data is None


def test_drag_distance() -> None:
    # Axis drawn left to right, 10 px per 5 mm.
    assert drag_distance((0, 0), (10, 0), (20, 7), 5.0) == pytest.approx(10.0)
    assert drag_distance((0, 0), (10, 0), (-4, 0), 5.0) == pytest.approx(-2.0)
    assert drag_distance((3, 3), (3, 4), (9, 9), 5.0) is None  # axis points at the viewer


# Revolve handle (W6.4) ------------------------------------------------------------------


def test_revolve_preview_has_a_curved_angle_handle(qtbot: QtBot, view: FakeView) -> None:
    doc, rev = shaft(90)
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, doc.feature(rev), is_new=False)
    data, active = view.shown[-1]
    assert active == "angle"
    [handle] = data.handles
    assert handle.is_angle and handle.value == pytest.approx(math.pi / 2)
    assert len(data.arrows) == 1 and data.arrow_size > 0
    assert view.label is not None and view.label("angle", math.pi / 2) == "90.00 deg"
    assert view.label("depth", 10.0) == "10.00 mm"
    # Typed and dragged values stay in sync, both ways.
    with qtbot.waitSignal(preview.ready, timeout=20000):
        view.handle_dragged.emit("angle", math.radians(135))
    assert panel.values["angle"].edit.text() == "135"
    data, _ = view.shown[-1]
    assert data.handles[0].value == pytest.approx(math.radians(135))
    assert data.geometry.shape is not None
    assert volume(data.geometry.shape) == pytest.approx(math.pi * 100 * 40 * 135 / 360, rel=1e-6)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.values["angle"].edit.setText("200")
    assert view.shown[-1][0].handles[0].value == pytest.approx(math.radians(200))


def test_two_direction_revolve_handles_follow_the_active_field(
    qtbot: QtBot, view: FakeView
) -> None:
    doc, rev = shaft(90, direction="two_directions", angle2=Param("30", math.radians(30)))
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, doc.feature(rev), is_new=False)
    data, active = view.shown[-1]
    assert [h.param for h in data.handles] == ["angle", "angle2"]
    assert active == "angle"
    with qtbot.waitSignal(preview.ready, timeout=20000):
        view.handle_dragged.emit("angle2", math.radians(45))
    assert panel.active_param == "angle2"
    assert panel.values["angle2"].edit.text() == "45"
    assert view.shown[-1][1] == "angle2"  # the dragged handle is now the accent one


def test_curved_arrow_shape_is_a_valid_solid() -> None:
    handle = PreviewHandle("angle", (10, 0, 0), (0, 1, 0), math.pi / 2, 1.0, (0, 0, 0))
    shape = arrow_shape(handle, 2.0)
    assert BRepCheck_Analyzer(shape).IsValid()
    lo_x, _ly, lo_z, hi_x, _hy, _hz = bounds(shape)
    # The arc runs along the circle of radius 10 towards the tip at (0, 0, -10).
    assert lo_z == pytest.approx(-10.7, abs=0.5) and hi_x > 3.0 and lo_x < 0.5


def test_drag_angle_picks_the_nearest_arc_point_and_unwraps() -> None:
    # A circle of radius 100 px drawn around (0, 0): angle t at (100 cos t, 100 sin t).
    samples = [
        (i * math.pi / 90, (100 * math.cos(i * math.pi / 90), 100 * math.sin(i * math.pi / 90)))
        for i in range(180)
    ]
    assert drag_angle(samples, (0, 120), 1.0) == pytest.approx(math.pi / 2)
    # Just past the start, while the drag was near a full turn: keeps going past 360.
    near_start = drag_angle(samples, (100, 3), 6.2)
    assert near_start is not None and near_start == pytest.approx(2 * math.pi, abs=0.05)
    edge_on = [(t, (5.0, 5.0)) for t, _p in samples]
    assert drag_angle(edge_on, (0, 0), 1.0) is None

    low, high = value_limits(PreviewHandle("angle", (1, 0, 0), (0, 0, 1), 1.0, 1.0, (0, 0, 0)))
    assert 0 < low < 0.01 and high == pytest.approx(2 * math.pi)


def test_preview_is_drawn_in_front_of_the_part_it_covers() -> None:
    """Owner report 2026-11-01: a fillet preview on a big tube showed stripes and
    blotches, because the preview lies on the part's own faces (z-fighting)."""
    from OCP.AIS import AIS_Shape
    from OCP.Aspect import Aspect_POM_Fill
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.Quantity import Quantity_Color, Quantity_NOC_BLUE

    from fdcad.ui.viewport.widget import preview_solid

    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    solid = preview_solid(box, Quantity_Color(Quantity_NOC_BLUE))
    offset = solid.Attributes().ShadingAspect().Aspect().PolygonOffset()
    assert offset.Mode == Aspect_POM_Fill
    assert offset.Factor < 0 and offset.Units < 0
    # Only the preview moves: a plain part keeps no offset.
    plain = AIS_Shape(box).Attributes().ShadingAspect()
    assert plain is None or plain.Aspect().PolygonOffset().Units >= 0


def test_overlay_is_see_through_accent_in_the_topmost_layer() -> None:
    """D1032, PV8: faces over the unchanged part, drawn so the part cannot hide them."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.Graphic3d import Graphic3d_ZLayerId_Topmost
    from OCP.Quantity import Quantity_Color, Quantity_NOC_BLUE
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.ui.viewport.preview import PREVIEW_TRANSPARENCY
    from fdcad.ui.viewport.widget import ViewportWidget, overlay_solid

    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    faces = []
    explorer = TopExp_Explorer(box, TopAbs_FACE)
    while explorer.More():
        faces.append(explorer.Current())
        explorer.Next()
    item = overlay_solid(faces[:2], Quantity_Color(Quantity_NOC_BLUE))
    assert item.Transparency() == pytest.approx(PREVIEW_TRANSPARENCY)
    assert item.ZLayer() == Graphic3d_ZLayerId_Topmost
    offset = item.Attributes().ShadingAspect().Aspect().PolygonOffset()
    assert offset.Factor < 0 and offset.Units < 0
    assert not hasattr(ViewportWidget, "_ghost_part")  # the part is never ghosted


def test_extrude_cut_preview_solid_is_in_the_topmost_layer(qtbot: QtBot, view: FakeView) -> None:
    """PV2.3: the removed volume lies inside the part, so it must not be hidden by it."""
    from OCP.Graphic3d import Graphic3d_ZLayerId_Topmost
    from OCP.Quantity import Quantity_Color, Quantity_NOC_BLUE

    from fdcad.ui.viewport.widget import preview_solid

    doc, ext = plate(10.0)
    session, panel, preview = _setup(qtbot, doc)
    preview.bind(panel, lambda: view)
    cut = copy.deepcopy(doc.feature(ext))
    cut.id, cut.name = "new", "Cut 1"
    cut.params["operation"] = "cut"
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, cut, is_new=True)
    shape = view.shown[-1][0].geometry.shape
    assert shape is not None
    solid = preview_solid(shape, Quantity_Color(Quantity_NOC_BLUE))
    assert solid.ZLayer() == Graphic3d_ZLayerId_Topmost
