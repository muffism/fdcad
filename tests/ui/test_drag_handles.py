"""Drag handle ruler, tick snapping, flip past the start and the clickable value
(owner note 7, TOOL_SPEC T5.2.2, T5.2.3, T5.2.5, T6.3.1, T6.3.2).

No GPU in CI: the logic is tested without drawing. The view's part is plain
arithmetic in ``ui/viewport/handles.py`` and signals, both tested here.
"""

import math

import pytest
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.base import ANGLE_RULER_STEP, PreviewHandle, ruler_step
from fdcad.core.features.preview import build_preview
from fdcad.core.rebuild.runner import rebuild
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from fdcad.ui.viewport.handles import (
    MIN_LENGTH,
    HandleDrag,
    label_box,
    label_hit,
    polyline_distance,
    ruler_span,
    ruler_ticks,
    segment_distance,
    snap,
    snap_point,
    travel_to,
)
from fdcad.ui.viewport.preview import FeaturePreview, PreviewData, ruler_shape
from tests.core.features.test_features import plate, shaft

LENGTH = PreviewHandle("depth", (0, 0, 0), (0, 0, 1), 20.0, step=5.0, flips=True)
ANGLE = PreviewHandle("angle", (10, 0, 0), (0, 0, 1), math.pi / 2, 1.0, (0, 0, 0), ANGLE_RULER_STEP)


def _edges(shape: object) -> int:
    count = 0
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)  # type: ignore[arg-type]
    while explorer.More():
        count += 1
        explorer.Next()
    return count


# Ruler step and ticks -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("size", "inch", "step"),
    [(50.0, False, 5.0), (8.0, False, 1.0), (0.3, False, 0.05), (130.0, False, 20.0),
     (254.0, True, 25.4), (60.0, True, 0.5 * 25.4), (0.0, False, 1.0)],
)  # fmt: skip
def test_ruler_step_is_a_round_value_in_the_part_unit(size: float, inch: bool, step: float) -> None:
    assert ruler_step(size, inch) == pytest.approx(step)


def test_length_ruler_reaches_past_the_tip_and_behind_the_start() -> None:
    assert ruler_span(LENGTH) == (-10.0, 50.0)  # at least ten ticks, two behind
    ticks = ruler_ticks(LENGTH)
    assert [t for t, _major in ticks] == [-10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    assert [t for t, major in ticks if major] == [0, 25, 50]
    far = PreviewHandle("depth", (0, 0, 0), (0, 0, 1), 80.0, step=5.0)
    assert ruler_span(far) == (0.0, 160.0)  # twice the travel
    fixed = PreviewHandle("depth2", (0, 0, 0), (0, 0, -1), 2.0, step=1.0)
    assert ruler_span(fixed) == (0.0, 10.0)  # no flip: nothing behind the start


def test_angle_ruler_has_ticks_every_five_degrees() -> None:
    ticks = ruler_ticks(ANGLE)
    assert len(ticks) == 72
    assert [round(math.degrees(t)) for t, major in ticks if major] == [
        0, 45, 90, 135, 180, 225, 270, 315,
    ]  # fmt: skip


def test_ruler_shapes_are_built() -> None:
    length = ruler_shape(LENGTH, 4.0)
    assert length is not None and _edges(length) == 1 + 13
    angle = ruler_shape(ANGLE, 4.0)
    assert angle is not None and _edges(angle) == 1 + 72
    assert ruler_shape(PreviewHandle("depth", (0, 0, 0), (0, 0, 1), 1.0), 4.0) is None


# Snapping and flipping --------------------------------------------------------------------


def test_snap_rounds_to_whole_steps() -> None:
    assert snap(12.4, 5.0) == 10.0
    assert snap(12.6, 5.0) == 15.0
    assert snap(1.0, 5.0) == 5.0  # never below one step
    assert snap(3.3, 0.0) == 3.3


def test_value_is_free_off_the_ruler_and_snaps_on_it() -> None:
    drag = HandleDrag(LENGTH)
    assert drag.update(12.3, on_ruler=False) == pytest.approx(12.3)
    assert drag.update(12.3, on_ruler=True) == pytest.approx(10.0)
    mid = HandleDrag(PreviewHandle("depth", (0, 0, 0), (0, 0, 1), 20.0, 2.0, step=5.0))
    assert mid.update(6.0, on_ruler=True) == pytest.approx(10.0)  # 2 x 5 mm travel


def test_dragging_past_the_start_flips() -> None:
    drag = HandleDrag(LENGTH, offset=0.0)
    assert drag.update(-7.0, on_ruler=False) == pytest.approx(7.0)
    assert drag.flipped
    assert drag.travel(7.0) == pytest.approx(-7.0)
    assert drag.update(-7.0, on_ruler=True) == pytest.approx(5.0)
    assert drag.update(4.0, on_ruler=False) == pytest.approx(4.0)
    assert not drag.flipped


def test_handles_that_do_not_flip_stop_at_the_start() -> None:
    drag = HandleDrag(PreviewHandle("depth2", (0, 0, 0), (0, 0, -1), 2.0, step=1.0))
    assert drag.update(-5.0, on_ruler=False) == MIN_LENGTH
    assert not drag.flipped


def test_angle_drag_snaps_to_five_degrees_and_stays_in_range() -> None:
    drag = HandleDrag(ANGLE)
    assert math.degrees(drag.update(math.radians(47.4), True)) == pytest.approx(45.0)
    assert math.degrees(drag.update(math.radians(47.4), False)) == pytest.approx(47.4)
    assert drag.update(-1.0, False) == pytest.approx(math.radians(0.1))
    assert drag.update(10.0, False) == pytest.approx(2 * math.pi)


def test_distances_on_screen() -> None:
    assert segment_distance((5, 3), (0, 0), (10, 0)) == pytest.approx(3)
    assert segment_distance((-4, 3), (0, 0), (10, 0)) == pytest.approx(5)
    assert polyline_distance((5, 5), [(0, 0), (10, 0), (10, 10)]) == pytest.approx(5)


def test_value_label_hit_box() -> None:
    left, top, right, bottom = label_box((100, 50), "10.00 mm", 14)
    assert left < 100 < right and top < 50 - 14 and bottom > 50
    assert label_hit((100, 50), "10.00 mm", 14, (120, 44))
    assert not label_hit((100, 50), "10.00 mm", 14, (100, 90))


# Handles from the features ---------------------------------------------------------------


def test_extrude_handles_carry_step_and_flip_rules() -> None:
    doc, ext = plate()
    one = build_preview(doc, doc.feature(ext), rebuild(doc)).handles
    # The 50 mm square profile is 70.7 mm across: a tenth rounds to 10 mm ticks.
    assert [(h.param, h.flips, h.step) for h in one] == [("depth", True, 10.0)]
    doc.feature(ext).params["end_condition"] = "mid_plane"
    mid = build_preview(doc, doc.feature(ext), rebuild(doc)).handles
    assert [(h.param, h.flips, h.scale) for h in mid] == [("depth", False, 2.0)]


def test_revolve_handles_have_the_angle_ruler() -> None:
    doc, rev = shaft(90)
    handles = build_preview(doc, doc.feature(rev), rebuild(doc)).handles
    assert handles and all(h.step == pytest.approx(math.radians(5)) for h in handles)
    assert not any(h.flips for h in handles)


# Panel and preview wiring ----------------------------------------------------------------


class WidgetView(QWidget):
    """A plain widget with the 3D view's signals (the real view needs a GPU)."""

    handle_dragged = Signal(str, float)
    handle_flipped = Signal(str)
    value_clicked = Signal(str, QPoint)

    def __init__(self) -> None:
        super().__init__()
        self.shown: list[tuple[PreviewData, str]] = []

    def show_preview(self, data: PreviewData, active: str, _label: object) -> None:
        self.shown.append((data, active))

    def clear_preview(self) -> None:
        pass


def _open(qtbot: QtBot) -> tuple[DocumentSession, PropertyPanel, FeaturePreview, WidgetView]:
    doc, ext = plate()
    session = DocumentSession(doc)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    view = WidgetView()
    qtbot.addWidget(view)
    view.show()
    preview = FeaturePreview()
    preview.bind(panel, lambda: view)
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, doc.feature(ext), is_new=False)
    return session, panel, preview, view


def test_preview_has_one_ruler_per_handle(qtbot: QtBot) -> None:
    _session, _panel, _preview, view = _open(qtbot)
    data, _active = view.shown[-1]
    assert len(data.rulers) == len(data.handles) == 1
    assert data.rulers[0] is not None


def test_flip_signal_reverses_the_direction(qtbot: QtBot) -> None:
    _session, panel, preview, view = _open(qtbot)
    reverse = panel.flags["reverse"]
    assert not reverse.isChecked()
    with qtbot.waitSignal(preview.ready, timeout=20000):
        view.handle_flipped.emit("depth")
    assert reverse.isChecked()
    data, _active = view.shown[-1]
    assert data.handles[0].direction[2] == pytest.approx(-1.0)
    view.handle_flipped.emit("depth2")  # only the first direction flips
    assert reverse.isChecked()


def test_clicking_the_value_opens_the_value_box(qtbot: QtBot) -> None:
    _session, panel, preview, view = _open(qtbot)
    view.value_clicked.emit("depth", QPoint(30, 40))
    editor = preview._editor
    assert editor is not None and editor.box is not None
    box = editor.box
    assert box.text() == panel.values["depth"].edit.text()
    assert box.isVisible()
    assert (box.x(), box.y()) == (30, 40)  # opened where the value was clicked
    box.edit.setText("=2*12 mm")
    with qtbot.waitSignal(preview.ready, timeout=20000):
        qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert editor.box is None  # Enter applies and closes
    assert panel.values["depth"].edit.text() == "=2*12 mm"
    data, _active = view.shown[-1]
    assert data.handles[0].value == pytest.approx(24.0)


def test_wrong_value_keeps_the_box_open(qtbot: QtBot) -> None:
    _session, panel, preview, view = _open(qtbot)
    before = panel.values["depth"].edit.text()
    view.value_clicked.emit("depth", QPoint(5, 5))
    editor = preview._editor
    assert editor is not None and editor.box is not None
    editor.box.edit.setText("=nonsense +")
    qtbot.keyClick(editor.box.edit, Qt.Key.Key_Return)
    assert editor.box is not None and editor.box.edit.property("error") is True
    assert panel.values["depth"].edit.text() == before
    qtbot.keyClick(editor.box, Qt.Key.Key_Escape)
    assert editor.box is None


def test_value_box_steps_with_the_arrows(qtbot: QtBot) -> None:
    _session, _panel, preview, view = _open(qtbot)
    view.value_clicked.emit("depth", QPoint(5, 5))
    editor = preview._editor
    assert editor is not None and editor.box is not None
    editor.box.edit.setText("10")
    qtbot.keyClick(editor.box.edit, Qt.Key.Key_Up)
    assert editor.box.text() == "11"


def test_closing_the_panel_closes_the_value_box(qtbot: QtBot) -> None:
    _session, panel, preview, view = _open(qtbot)
    view.value_clicked.emit("depth", QPoint(5, 5))
    assert preview._editor is not None and preview._editor.box is not None
    panel.reject()
    assert preview._editor.box is None


def test_the_3d_view_has_the_handle_signals() -> None:
    from fdcad.ui.viewport.widget import ViewportWidget

    for name in ("handle_dragged", "handle_flipped", "value_clicked", "handle_released"):
        assert hasattr(ViewportWidget, name)


# Alt snap to a part vertex or face (T5.2.4, D525) -----------------------------------------


def test_alt_snap_travel_is_measured_along_the_handle() -> None:
    handle = PreviewHandle("depth", (0, 0, 5), (0, 0, 1), 10.0, step=5.0, snaps=True)
    assert travel_to(handle, (7, -3, 25)) == pytest.approx(20.0)
    back = PreviewHandle("depth2", (0, 0, 5), (0, 0, -1), 10.0, snaps=True)
    assert travel_to(back, (0, 0, -5)) == pytest.approx(10.0)


def test_alt_snap_point_on_flat_parallel_faces_and_others() -> None:
    handle = PreviewHandle("depth", (0, 0, 0), (0, 0, 1), 10.0, snaps=True)
    picked = (3.0, 4.0, 12.3)  # the cursor point, slightly off on the triangles
    flat = ((50.0, 50.0, 12.0), (0.0, 0.0, -1.0))  # parallel to the sketch plane
    assert snap_point(handle, picked, flat) == (50.0, 50.0, 12.0)
    assert travel_to(handle, snap_point(handle, picked, flat)) == pytest.approx(12.0)
    slanted = ((0.0, 0.0, 0.0), (0.0, 0.6, 0.8))
    assert snap_point(handle, picked, slanted) == picked
    assert snap_point(handle, picked, None) == picked  # a curved face


def test_alt_snap_value_flips_or_stops_like_a_drag() -> None:
    drag = HandleDrag(LENGTH, offset=3.0)  # the grab offset does not move a snapped end
    assert drag.snap_to(12.0) == pytest.approx(12.0) and not drag.flipped
    assert drag.snap_to(-8.0) == pytest.approx(8.0) and drag.flipped
    assert drag.travel(8.0) == pytest.approx(-8.0)
    mid = HandleDrag(PreviewHandle("depth", (0, 0, 0), (0, 0, 1), 20.0, 2.0, snaps=True))
    assert mid.snap_to(7.0) == pytest.approx(14.0)  # Mid Plane: the end lands on the point
    second = HandleDrag(PreviewHandle("depth2", (0, 0, 0), (0, 0, -1), 5.0, snaps=True))
    assert second.snap_to(-4.0) == MIN_LENGTH and not second.flipped


def test_only_extrude_depth_arrows_snap() -> None:
    doc, ext = plate()
    feature = doc.feature(ext)
    feature.params["depth2"] = Param("4", 4.0)
    feature.params["end_condition2"] = "blind"
    handles = build_preview(doc, feature, rebuild(doc)).handles
    assert [(h.param, h.snaps) for h in handles] == [("depth", True), ("depth2", True)]
    doc2, rev = shaft(90)
    assert not any(h.snaps for h in build_preview(doc2, doc2.feature(rev), rebuild(doc2)).handles)


def test_the_3d_view_drag_takes_the_alt_snap() -> None:
    import inspect

    from fdcad.ui.viewport.widget import SNAP_NOTES, ViewportWidget

    assert "snap" in inspect.signature(ViewportWidget._drag_handle).parameters
    assert set(SNAP_NOTES) == {"vertex", "face"}


def test_edges_pick_within_a_few_pixels(qtbot: QtBot) -> None:
    # The kernel's default of 2 pixels made edges hard to hit for Fillet (owner report).
    from OCP.Aspect import Aspect_DisplayConnection

    from fdcad.ui.viewport.widget import PICK_TOLERANCE_PX, ViewportWidget

    try:
        Aspect_DisplayConnection()
    except Exception:  # Linux with no X display: the kernel's view cannot start (D630)
        pytest.skip("no display for the kernel's OpenGL view")
    view = ViewportWidget()
    qtbot.addWidget(view)
    assert PICK_TOLERANCE_PX >= 5
    # PixelTolerance() reads 2 until shapes are shown; the custom value is what was set.
    assert view._context.MainSelector().CustomPixelTolerance() == PICK_TOLERANCE_PX
