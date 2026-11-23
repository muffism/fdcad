"""WP8: Dimension panel, value preview, reference dimensions, over define prompt and
dragged labels (TOOL_SPEC T1.4.4, T4.2.1, T4.2.5, T4.4.2, T7.4, owner note 3)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Line, sketch_from_data, sketch_to_data
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, label_position, new_sketch_data
from fdcad.ui.sketch_tools.panel import SketchPanel

Vec = tuple[float, float]


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (20.0, 10.0)
    yield canvas


@pytest.fixture
def panel(qtbot: QtBot, canvas: SketchCanvas) -> SketchPanel:
    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    panel.show()
    return panel


def _pos(canvas: SketchCanvas, at: Vec) -> QPoint:
    p = canvas.to_screen(at)
    return QPoint(round(p.x()), round(p.y()))


def _move(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    qtbot.mouseMove(canvas, _pos(canvas, at))


def _click(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    _move(qtbot, canvas, at)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_pos(canvas, at))


def _drag_screen(qtbot: QtBot, canvas: SketchCanvas, a: QPointF, b: QPointF) -> None:
    pa, pb = QPoint(round(a.x()), round(a.y())), QPoint(round(b.x()), round(b.y()))
    qtbot.mouseMove(canvas, pa)
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=pa)
    qtbot.mouseMove(canvas, (pa + pb) / 2)
    qtbot.mouseMove(canvas, pb)
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=pb)


def _line(canvas: SketchCanvas, length: float = 30.0) -> Line:
    lid = canvas.edit.sketch.add_line(0, 0, length, 0)
    canvas.changed()
    line = canvas.edit.sketch.entities[lid]
    assert isinstance(line, Line)
    return line


def _length_dimension(qtbot: QtBot, canvas: SketchCanvas, place: Vec = (15, -8)) -> str:
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (15, 0))
    _click(qtbot, canvas, place)
    dim = canvas.edit.sketch.dimensions[-1]
    if canvas.value_box is not None:
        canvas.value_box.ok.click()
    return dim.id


def test_panel_shows_when_smart_dimension_starts(canvas: SketchCanvas, panel: SketchPanel) -> None:
    dims = panel.dimension_panel
    assert not dims.isVisibleTo(panel)
    canvas.set_tool("dimension")
    assert dims.isVisibleTo(panel)
    assert dims.hint.isVisibleTo(panel) and not dims.value.isVisibleTo(panel)
    canvas.set_tool(None)
    assert not dims.isVisibleTo(panel)


def test_panel_shows_for_a_selected_dimension(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    _line(canvas)
    did = _length_dimension(qtbot, canvas)
    canvas.set_tool(None)
    assert not panel.dimension_panel.isVisibleTo(panel)
    canvas.selection = [did]
    canvas.selection_changed.emit()
    dims = panel.dimension_panel
    assert dims.isVisibleTo(panel)
    assert dims.kind.text() == "Distance"
    assert dims.value.text() == "30mm" and not dims.value.isReadOnly()
    assert dims.driving.isChecked()


def test_value_preview_follows_the_cursor_before_placement(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    _line(canvas)
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (15, 0))
    assert canvas.dim_preview is None  # the cursor is still on the line
    _move(qtbot, canvas, (15, -9))
    preview = canvas.dim_preview
    assert preview is not None and preview.type == "distance"
    assert preview.param.value == pytest.approx(30.0)
    assert canvas.edit.sketch.dimensions == []  # nothing placed yet
    dims = panel.dimension_panel
    assert dims.value.text() == "30.00mm" and dims.value.isReadOnly()
    canvas.repaint()  # draws the preview half transparent
    _move(qtbot, canvas, (15, -12))
    assert canvas.label_at("preview") is not None
    _click(qtbot, canvas, (15, -12))
    (dim,) = canvas.edit.sketch.dimensions
    assert canvas.dim_preview is None
    placed = label_position(canvas.edit.sketch, dim)
    assert placed is not None and placed == pytest.approx((15.0, -12.0), abs=0.3)
    # The value box opens beside the placed text, not at an automatic place.
    assert canvas.value_box is not None
    rect = canvas.label_rect(dim.id)
    assert abs(rect.center().y() - canvas.to_screen((15, -12)).y()) < 3


def test_panel_value_changes_the_dimension(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    line = _line(canvas)
    did = _length_dimension(qtbot, canvas)
    canvas.set_tool(None)
    canvas.selection = [did]
    canvas.selection_changed.emit()
    field = panel.dimension_panel.value
    field.setText("=20+5")
    field.returnPressed.emit()
    sk = canvas.edit.sketch
    assert sk.xy(line.p2)[0] - sk.xy(line.p1)[0] == pytest.approx(25.0)
    assert sk.dimensions[0].param.expr == "=20+5"
    field.setText("-4")
    field.returnPressed.emit()
    assert field.property("error") is True
    assert sk.dimensions[0].param.value == pytest.approx(25.0)
    canvas.undo()
    assert canvas.edit.sketch.dimensions[0].param.value == pytest.approx(30.0)


def test_reference_toggle_follows_geometry(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    line = _line(canvas)
    did = _length_dimension(qtbot, canvas)
    canvas.set_tool(None)
    canvas.selection = [did]
    canvas.selection_changed.emit()
    dims = panel.dimension_panel
    dims.reference.click()
    dim = canvas.edit.sketch.dimensions[0]
    assert not dim.driving and dims.value.isReadOnly()
    assert canvas._dimension_text(dim).startswith("(")
    # A reference dimension only measures: the line can be dragged and it follows.
    assert canvas.edit.drag_to({line.p2: (40.0, 0.0)})
    canvas.changed()
    assert canvas.edit.sketch.dimensions[0].param.value == pytest.approx(40.0)
    assert dims.value.text() == "40.00mm"
    dims.driving.click()
    assert canvas.edit.sketch.dimensions[0].driving
    canvas.undo()
    assert not canvas.edit.sketch.dimensions[0].driving


def test_driving_is_refused_when_it_would_over_define(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    _line(canvas)
    first = _length_dimension(qtbot, canvas)
    _click(qtbot, canvas, (15, 0))
    _click(qtbot, canvas, (15, 8))
    assert canvas.over_prompt is not None
    canvas.over_prompt.reference.click()
    second = canvas.edit.sketch.dimensions[1]
    assert not second.driving
    canvas.set_tool(None)
    canvas.selection = [second.id]
    canvas.selection_changed.emit()
    messages: list[str] = []
    canvas.status_message.connect(messages.append)
    panel.dimension_panel.driving.click()
    assert not canvas.edit.sketch.dimensions[1].driving
    assert panel.dimension_panel.reference.isChecked()
    assert messages and "reference" in messages[-1]
    assert canvas.edit.dimension(first) is not None


def test_over_define_prompt_make_reference(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _line(canvas)
    _length_dimension(qtbot, canvas)
    _click(qtbot, canvas, (15, 0))
    _click(qtbot, canvas, (15, 8))
    prompt = canvas.over_prompt
    assert prompt is not None and prompt.isVisible()
    assert canvas.value_box is None
    assert "over defines the sketch" in prompt.question.text()
    assert prompt.reference.text() == "Make Reference"
    assert prompt.driving.text() == "Keep Driving"
    prompt.reference.click()
    first, second = canvas.edit.sketch.dimensions
    assert first.driving and not second.driving
    assert canvas.over_prompt is None and canvas.value_box is None
    assert canvas.edit.status().state.value == "full" or canvas.edit.result is not None


def test_over_define_prompt_keep_driving_and_escape(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _line(canvas)
    _length_dimension(qtbot, canvas)
    _click(qtbot, canvas, (15, 0))
    _click(qtbot, canvas, (15, 8))
    assert canvas.over_prompt is not None
    canvas.over_prompt.driving.click()
    assert canvas.over_prompt is None
    assert canvas.value_box is not None  # type the value of the driving dimension
    assert all(d.driving for d in canvas.edit.sketch.dimensions)
    canvas.value_box.cancel.click()  # cancelling a new dimension removes it
    assert len(canvas.edit.sketch.dimensions) == 1
    _click(qtbot, canvas, (15, 0))
    _click(qtbot, canvas, (15, 8))
    assert canvas.over_prompt is not None
    qtbot.keyClick(canvas.over_prompt, Qt.Key.Key_Escape)
    assert canvas.over_prompt is None
    assert len(canvas.edit.sketch.dimensions) == 1


def test_always_reference_preference_skips_the_prompt(qtbot: QtBot, canvas: SketchCanvas) -> None:
    from dataclasses import replace

    from fdcad.ui.sketch_tools.options import OverDefine, SketchOptions

    canvas.set_options(replace(SketchOptions(), over_define=OverDefine.REFERENCE))
    _line(canvas)
    _length_dimension(qtbot, canvas)
    _click(qtbot, canvas, (15, 0))
    _click(qtbot, canvas, (15, 8))
    assert canvas.over_prompt is None
    assert not canvas.edit.sketch.dimensions[1].driving


def test_drag_a_label_stores_its_place(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _line(canvas)
    did = _length_dimension(qtbot, canvas, place=(15, -8))
    canvas.set_tool(None)
    canvas.repaint()
    start = canvas.label_at(did)
    target = canvas.to_screen((22.0, 10.0))  # across the line: the other side
    _drag_screen(qtbot, canvas, start, target)
    dim = canvas.edit.dimension(did)
    assert dim is not None
    assert dim.param.value == pytest.approx(30.0)  # the value never changes
    placed = label_position(canvas.edit.sketch, dim)
    assert placed is not None and placed == pytest.approx((22.0, 10.0), abs=0.4)
    assert (canvas.label_at(did) - target).manhattanLength() < 4
    canvas.repaint()  # draws the dimension line above the line now
    data = sketch_to_data(canvas.edit.sketch)
    assert data["dimensions"][0]["label"] == pytest.approx([7.0, 10.0], abs=0.4)
    assert canvas.value_box is None  # a drag does not open the value box
    canvas.undo()
    back = label_position(canvas.edit.sketch, canvas.edit.sketch.dimensions[0])
    assert back == pytest.approx((15.0, -8.0), abs=0.4)


def test_drag_a_label_in_smart_dimension_and_click_to_type(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    _line(canvas)
    did = _length_dimension(qtbot, canvas)
    canvas.repaint()
    start = canvas.label_at(did)
    _drag_screen(qtbot, canvas, start, start + QPointF(0, 40))
    assert canvas.value_box is None
    assert canvas.tool_name == "dimension"
    dim = canvas.edit.dimension(did)
    assert dim is not None and dim.label is not None
    canvas.repaint()
    at = canvas.label_at(did)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(at.x()), round(at.y())))
    assert canvas.value_box is not None  # a plain click on the text opens the box


def test_place_text_automatically_again(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    _line(canvas)
    did = _length_dimension(qtbot, canvas)
    canvas.set_tool(None)
    canvas.selection = [did]
    canvas.selection_changed.emit()
    dims = panel.dimension_panel
    assert dims.reset_label.isVisibleTo(panel)
    dims.reset_label.click()
    dim = canvas.edit.dimension(did)
    assert dim is not None and dim.label is None
    canvas.repaint()  # automatic placement still draws


def test_doubled_distance_from_a_point_to_a_centerline() -> None:
    from fdcad.ui.sketch_tools.edit import centres_for_distance, smart_dimension

    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    edit = SketchEdit(feature)
    sk = edit.sketch
    axis = sk.add_line(0, -10, 0, 30, construction=True)
    pid = sk.add_point(12, 5)
    ids = centres_for_distance(sk, [pid, axis])
    assert smart_dimension(sk, ids, (-6, 5)) == "doubled_distance"
    assert smart_dimension(sk, ids, (6, 5)) == "distance"  # same side: a radius
    dim = edit.add_dimension("doubled_distance", ids, None, (-6, 5))
    assert dim.entities == [pid, axis]
    assert dim.param.value == pytest.approx(24.0)
    plain = sk.add_line(20, -10, 20, 30)  # not a centerline: never doubled
    assert smart_dimension(sk, [pid, plain], (30, 5)) == "distance"


def test_label_survives_save_and_old_dimensions_place_automatically() -> None:
    data = new_sketch_data()
    sketch = sketch_from_data(data)
    lid = sketch.add_line(0, 0, 30, 0)
    from fdcad.core.document.model import Param

    old = sketch.dimension("distance", [lid], Param("30", 30.0))
    placed = sketch.dimension("distance", [lid], Param("30", 30.0), driving=False)
    placed.label = (1.5, -8.0)
    out = sketch_to_data(sketch)
    assert "label" not in out["dimensions"][0]
    assert out["dimensions"][1]["label"] == [1.5, -8.0]
    back = sketch_from_data(out)
    assert back.dimensions[0].label is None and old.label is None
    assert back.dimensions[1].label == (1.5, -8.0)
    assert sketch_to_data(back) == out


def test_leaving_the_value_field_applies_the_typed_value(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    # Round 10a: Tab away from the field used to drop the typed text (D593).
    line = _line(canvas)
    did = _length_dimension(qtbot, canvas)
    canvas.set_tool(None)
    canvas.selection = [did]
    canvas.selection_changed.emit()
    field = panel.dimension_panel.value
    field.setText("12")
    field.editingFinished.emit()
    sk = canvas.edit.sketch
    assert sk.xy(line.p2)[0] - sk.xy(line.p1)[0] == pytest.approx(12.0)
    depth = canvas.edit.undo_depth
    field.editingFinished.emit()  # unchanged text adds no second undo step
    assert canvas.edit.undo_depth == depth
