"""Convert Entities on curve features (IDEAS.md item 2, DECISIONS D517)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.curve_convert import CurvePiece, ProjectedCurve
from fdcad.core.sketch.model import Line, Sketch, Spline
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from fdcad.ui.sketch_tools.tools import make_tool
from tests.core.features.test_curves import add
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, free, ui_click


def _square(fid: str = "f9", name: str = "Contour 1", skipped: int = 0) -> ProjectedCurve:
    pts = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    pieces = [CurvePiece("line", (pts[i], pts[(i + 1) % 4])) for i in range(4)]
    return ProjectedCurve(fid, name, pieces, skipped)


def _wave() -> ProjectedCurve:
    pts = tuple((float(x), float(x % 3)) for x in range(30, 41))
    return ProjectedCurve("f8", "Helix 1", [CurvePiece("spline", pts)])


def test_click_a_curve_feature_converts_all_its_edges_once() -> None:
    edit = edit_of()
    tool = make_tool("convert", edit)
    tool.curve_sources = [_square(skipped=2), _wave()]  # type: ignore[attr-defined]
    tool.construction = True
    assert click(edit, tool, 10, 0.05)
    lines = [e for e in edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 4 and all(line.construction for line in lines)
    note = tool.take_message()  # type: ignore[attr-defined]
    assert note == (
        "Converted Contour 1: 4 curves. 2 edges were skipped because they project to a point."
    )
    assert not click(edit, tool, 10, 0.05)
    assert tool.take_message() == "Contour 1 is already in the sketch."  # type: ignore[attr-defined]
    # One undo step for the whole curve.
    edit.undo()
    assert not any(isinstance(e, Line) for e in edit.sketch.entities.values())


def test_hover_highlights_the_whole_feature_and_part_edges_come_first() -> None:
    edit = edit_of()
    tool = make_tool("convert", edit)
    tool.curve_sources = [_square()]  # type: ignore[attr-defined]
    tool.model_lines = [[(0.0, 0.0), (20.0, 0.0)]]  # type: ignore[attr-defined]
    tool.hover(free(10, 20))
    assert len(tool.preview().lines) == 4
    click(edit, tool, 10, 0)  # the part edge wins where both lie
    assert sum(isinstance(e, Line) for e in edit.sketch.entities.values()) == 1


def test_canvas_tree_pick_and_drawing(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_curve_sources([_square(), _wave()])
    canvas.set_tool("convert")
    canvas.grab()  # the dotted curve features draw
    messages: list[str] = []
    canvas.status_message.connect(messages.append)
    assert canvas.pick_feature("f8", "Helix 1")
    assert any(isinstance(e, Spline) for e in canvas.edit.sketch.entities.values())
    assert messages[-1] == "Converted Helix 1: 1 curve."
    assert not canvas.pick_feature("f2", "Front Plane")
    assert "Front Plane is not a curve feature" in messages[-1]
    # In the view: a click on the dotted square converts it.
    ui_click(qtbot, canvas, (20, 10))
    assert sum(isinstance(e, Line) for e in canvas.edit.sketch.entities.values()) == 4
    canvas.set_tool("line")
    assert not canvas.pick_feature("f9")


def test_empty_curve_says_why() -> None:
    edit = edit_of()
    tool = make_tool("convert", edit)
    tool.curve_sources = [ProjectedCurve("f7", "Contour 2", [], 4)]  # type: ignore[attr-defined]
    assert not tool.pick_feature("f7")  # type: ignore[attr-defined]
    assert "project to a point" in tool.take_message()  # type: ignore[attr-defined]


# In the main window ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1200, 800)
    win.show()
    win.finish_setup()
    yield win
    if win.sketch_mode is not None and win.sketch_mode.is_open:
        win.sketch_mode._close()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def test_tree_click_converts_a_contour_into_a_new_sketch(qtbot: QtBot, window: MainWindow) -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    contour = add(doc, "contour", {"direction": {"feature": "f2"}}, spacing=Param("2.5", 2.5))
    del ext
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    mode = window.sketch_mode
    tree = window.tree
    assert mode is not None and tree is not None
    mode.start(plane_id="f2", then_tool="convert")
    canvas = mode.canvas
    assert canvas is not None
    qtbot.waitUntil(lambda: bool(canvas.curve_sources), timeout=20000)
    assert [c.feature for c in canvas.curve_sources] == [contour]
    tree.select(contour)
    item = tree.currentItem()
    assert item is not None
    tree.itemClicked.emit(item, 0)
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 4  # three stacked loops seen from the front, copied once
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert mode.accept()
    report = tab.session.report
    assert report is not None
    new = tab.session.document.features[-1]
    assert new.type == "sketch" and report.results[new.id].state is FeatureState.OK
