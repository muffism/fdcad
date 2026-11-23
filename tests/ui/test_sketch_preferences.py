"""Sketch preferences (TOOL_SPEC T11, T1.2.7, T1.2.8, T1.3.3)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Circle, Line
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.options import OverDefine, SketchOptions
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    new_part,
    plane_id,
    window,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (0.0, 0.0)
    yield canvas


def _screen(canvas: SketchCanvas, x: float, y: float) -> QPoint:
    p = canvas.to_screen((x, y))
    return QPoint(round(p.x()), round(p.y()))


def _move(canvas: SketchCanvas, x: float, y: float, ctrl: bool = False) -> None:
    mods = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    pos = QPointF(_screen(canvas, x, y))
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        pos,
        canvas.mapToGlobal(pos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        mods,
    )
    QApplication.sendEvent(canvas, event)


def _click(qtbot: QtBot, canvas: SketchCanvas, x: float, y: float, ctrl: bool = False) -> None:
    mods = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    _move(canvas, x, y, ctrl)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, mods, pos=_screen(canvas, x, y))


def test_settings_round_trip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert settings.sketch_options == SketchOptions()  # everything on but the grid, ask
    changed = SketchOptions(
        normal_to_on_open=False,
        show_centres=False,
        end_point_dots=False,
        snapping=False,
        model_snaps=False,
        auto_relations=False,
        show_grid=True,
        over_define=OverDefine.REFERENCE,
    )
    settings.sketch_options = changed
    assert _settings(tmp_path).sketch_options == changed  # read back from the file
    settings.store.setValue("sketch/over_define", "nonsense")
    assert settings.sketch_options.over_define is OverDefine.ASK


def test_preferences_dialog_sketch_page(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    names = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert names[0] == "General" and "Sketch" in names  # View sits between them (TR212)
    off = (
        "show_grid",
        "value_input",
        "keep_proportions",
        "double_click_exit",
        "escape_exit",
        "dimension_middles",  # TR418: off by default
        "lock_changed_dimensions",  # TR238 (D1706): off by default
        "drag_changes_dimensions",  # TR112 (D1716): off by default
    )
    assert all(box.isChecked() for k, box in dialog.sketch_boxes.items() if k not in off)
    assert not dialog.sketch_boxes["show_grid"].isChecked()  # grid off by default (D434)
    assert not dialog.sketch_boxes["value_input"].isChecked()  # off by default (D513)
    dialog.sketch_boxes["auto_relations"].setChecked(False)
    dialog.sketch_boxes["snapping"].setChecked(False)
    dialog.over_define_box.setCurrentIndex(dialog.over_define_box.findData(OverDefine.REFERENCE))
    dialog.accept()
    options = settings.sketch_options
    assert not options.auto_relations and not options.snapping and options.show_centres
    assert options.over_define is OverDefine.REFERENCE


def test_ctrl_turns_snapping_off_for_the_move(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.edit.sketch.add_point(10, 10)
    canvas.set_tool("line")
    _move(canvas, 10.5, 10.5)
    assert canvas.snap is not None and canvas.snap.kind == "point"
    _move(canvas, 10.5, 10.5, ctrl=True)
    assert canvas.snap is not None and canvas.snap.kind == "free"
    assert canvas.snap.xy == pytest.approx(canvas.to_sketch(QPointF(_screen(canvas, 10.5, 10.5))))
    # A Ctrl click places the point where the cursor is, with no relation.
    before = len(canvas.edit.sketch.relations)
    _click(qtbot, canvas, 10.5, 10.5, ctrl=True)
    _click(qtbot, canvas, 40, 30.4, ctrl=True)  # near horizontal: no direction snap either
    line = next(e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line))
    assert canvas.edit.sketch.xy(line.p1) != pytest.approx((10, 10))
    assert canvas.edit.sketch.xy(line.p2)[1] == pytest.approx(30.4, abs=0.3)
    assert len(canvas.edit.sketch.relations) == before


def test_snapping_preference_off(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.edit.sketch.add_point(10, 10)
    canvas.set_options(replace(SketchOptions(), snapping=False))
    canvas.set_tool("point")
    _move(canvas, 10.5, 10.5)
    assert canvas.snap is not None and canvas.snap.kind == "free"


def test_automatic_relations_off(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_options(replace(SketchOptions(), auto_relations=False))
    sk = canvas.edit.sketch
    rels_before = list(sk.relations)
    canvas.set_tool("line")
    _click(qtbot, canvas, 0, 0)  # on the origin: still snaps there
    _click(qtbot, canvas, 30, 0.2)  # near horizontal: snaps, but no Horizontal
    _click(qtbot, canvas, 30, 20)
    lines = [e for e in sk.entities.values() if isinstance(e, Line)]
    assert len(lines) == 2
    assert sk.xy(lines[0].p1) == pytest.approx((0, 0))
    assert sk.xy(lines[0].p2)[1] == pytest.approx(0.0)
    new = [r for r in sk.relations if r not in rels_before]
    # Only the chain join between the two segments is kept.
    assert [r.type for r in new] == ["coincident"]
    assert set(new[0].entities) == {lines[0].p2, lines[1].p1}


def test_automatic_relations_on_by_default(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    canvas.set_tool("line")
    _click(qtbot, canvas, 0, 0)
    _click(qtbot, canvas, 30, 0.2)
    types = [r.type for r in sk.relations]
    assert "horizontal" in types and types.count("coincident") >= 1


def test_model_snaps_off(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_reference([], [((20.0, 20.0), 10.0)])
    canvas.set_tool("point")
    _move(canvas, 30, 20)  # on the edge: reveals the centre
    _move(canvas, 20.5, 20)
    assert canvas.snap is not None and canvas.snap.kind == "center"
    canvas.set_options(replace(SketchOptions(), model_snaps=False))
    assert canvas.revealed == []
    _move(canvas, 30, 20)
    _move(canvas, 20.5, 20)
    assert canvas.snap is not None and canvas.snap.kind != "center"


def test_centre_and_end_point_display(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    cid = sk.add_circle(10, 10, 5)
    lid = sk.add_line(0, 0, 20, 0)
    circle, line = sk.entities[cid], sk.entities[lid]
    assert isinstance(circle, Circle) and isinstance(line, Line)
    assert canvas._hidden_points() == set()
    canvas.set_options(replace(SketchOptions(), show_centres=False))
    assert canvas._hidden_points() == {circle.center}
    canvas.set_options(replace(SketchOptions(), end_point_dots=False))
    assert canvas._hidden_points() == {line.p1, line.p2}
    canvas.selection = [line.p1]  # selected points always show
    assert canvas._hidden_points() == {line.p2}
    canvas.repaint()


def test_over_defining_dimension_becomes_reference(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_options(replace(SketchOptions(), over_define=OverDefine.REFERENCE))
    canvas.set_tool("line")
    _click(qtbot, canvas, 0, 0)
    _click(qtbot, canvas, 30, 0)
    canvas.set_tool("dimension")
    _click(qtbot, canvas, 15, 0)
    _click(qtbot, canvas, 15, -6)
    assert canvas.value_box is not None
    canvas.value_box.ok.click()
    # The same length again would over define the sketch.
    _click(qtbot, canvas, 15, 0)
    _click(qtbot, canvas, 15, 6)
    first, second = canvas.edit.sketch.dimensions
    assert first.driving and not second.driving
    assert canvas.value_box is None  # nothing to type for a reference dimension
    assert second.param.value == pytest.approx(first.param.value)


def test_make_reference_only_when_over(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.edit.sketch.add_line(0, 0, 30, 0)
    lid = next(e.id for e in canvas.edit.sketch.entities.values() if isinstance(e, Line))
    first = canvas.edit.add_dimension("distance", [lid], None)
    assert not canvas.edit.make_reference_if_over(first.id) and first.driving
    dim = canvas.edit.add_dimension("distance", [lid], None)
    assert dim.driving
    assert canvas.edit.make_reference_if_over(dim.id)
    assert not dim.driving


def test_settings_reach_an_open_sketch(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = new_part(qtbot, window)
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas = canvas_of(window)
    assert canvas.options == SketchOptions() and canvas.edit.auto_relations

    def run(dialog: PreferencesDialog) -> int:
        dialog.sketch_boxes["auto_relations"].setChecked(False)
        dialog.sketch_boxes["show_centres"].setChecked(False)
        dialog.accept()
        return 1

    monkeypatch.setattr(PreferencesDialog, "exec", run)
    window.preferences()
    assert not canvas.options.auto_relations and not canvas.options.show_centres
    assert not canvas.edit.auto_relations


def test_normal_to_on_open_preference(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = new_part(qtbot, window)
    calls: list[object] = []
    tab.viewport.animate_normal_to = lambda *args: calls.append(args)  # type: ignore[method-assign]
    window.settings.sketch_options = replace(SketchOptions(), normal_to_on_open=False)
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    assert calls == []
    assert canvas_of(window).isVisible() or tab.findChild(SketchCanvas) is not None
    window.sketch_mode._close()
    window.settings.sketch_options = SketchOptions()
    window.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    assert len(calls) == 1
