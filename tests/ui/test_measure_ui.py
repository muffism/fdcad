"""Measure box: picks, results, options, history, copy and the status bar (P2.12, D252)."""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from OCP.BRep import BRep_Tool
from OCP.TopAbs import TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QToolButton
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, Feature, new_document
from fdcad.core.measure import Value
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.measure.box import format_value
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, rect


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
    win.measure_tool.close()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _plate() -> Document:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 10.0)
    doc.features.append(
        Feature("f7", "coord_system", "Coordinate System 1", params={"method": "directions"})
    )
    doc.next_id = 8
    return doc


def _open(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    session = DocumentSession(_plate(), None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _shapes(tab: DocumentTab, kind: object) -> list[object]:
    report = tab.session.report
    assert report is not None and report.body is not None
    out = []
    exp = TopExp_Explorer(report.body.shape, kind)  # type: ignore[arg-type]
    while exp.More():
        out.append(exp.Current())
        exp.Next()
    return out


def _vertex(tab: DocumentTab, at: tuple[float, float, float]) -> object:
    for v in _shapes(tab, TopAbs_VERTEX):
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(v))  # type: ignore[call-overload]
        if math.dist((p.X(), p.Y(), p.Z()), at) < 1e-9:
            return v
    raise AssertionError


def _rows(window: MainWindow) -> dict[str, str]:
    box = window.measure_tool.box
    assert box is not None
    out = {}
    for i in range(box.results.rowCount()):
        label = box.results.cellWidget(i, 0)
        value = box.results.cellWidget(i, 1)
        assert isinstance(label, QLabel) and isinstance(value, QLabel)
        out[label.text()] = value.text()
    return out


def test_format_values() -> None:
    assert format_value(Value("length", "length", 25.4), UnitSystem.IN, 3) == "1.000 in"
    assert format_value(Value("area", "area", 100.0), UnitSystem.MM, 1) == "100.0 mm^2"
    assert format_value(Value("angle", "angle", math.pi / 2), UnitSystem.MM, 0) == "90 deg"
    assert format_value(Value("point", "point", (1, 2, 3)), UnitSystem.MM, 1) == "1.0, 2.0, 3.0 mm"


def test_measure_box_picks_results_history_and_copy(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window)
    assert "evaluate.measure" in BY_ID
    assert window.commands.trigger("evaluate.measure")
    tool = window.measure_tool
    box = tool.box
    assert box is not None and box.isVisible()
    a, b = _vertex(tab, (0, 0, 0)), _vertex(tab, (50, 30, 10))
    tool.pick_shapes([a])
    qtbot.waitUntil(lambda: "Point" in _rows(window), timeout=10000)
    assert _rows(window)["Point"] == "0.00, 0.00, 0.00 mm"
    tool.pick_shapes([b])
    qtbot.waitUntil(lambda: "Distance" in _rows(window), timeout=10000)
    assert _rows(window)["Distance"] == f"{math.sqrt(50**2 + 30**2 + 10**2):.2f} mm"
    assert box.picks.count() == 2 and box.history.count() >= 2
    copy = box.results.findChild(QToolButton, "measure_copy_distance")
    assert copy is not None
    copy.click()
    assert QGuiApplication.clipboard().text() == _rows(window)["Distance"]
    # Units and precision for the box only.
    box.units.setCurrentIndex(box.units.findData(UnitSystem.IN))
    box.decimals.setValue(3)
    qtbot.waitUntil(lambda: _rows(window).get("Distance", "").endswith(" in"), timeout=10000)
    assert tab.session.document.units is UnitSystem.MM
    # Hide dX, dY, dZ.
    assert "dX, dY, dZ" in _rows(window)
    box.show_xyz.setChecked(False)
    qtbot.waitUntil(lambda: "dX, dY, dZ" not in _rows(window), timeout=10000)
    # Clicking a picked item again removes it; an empty click clears.
    tool.pick_shapes([a])
    assert len(tool.picks) == 1
    tool.pick_shapes([])
    assert tool.picks == [] and box.picks.count() == 0


def test_six_picks_at_most_pause_and_projection(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window)
    tool = window.measure_tool
    tool.open()
    box = tool.box
    assert box is not None
    faces = _shapes(tab, TopAbs_FACE)
    for f in faces:
        tool.pick_shapes([f])
    assert len(tool.picks) == 6
    box.pause.setChecked(True)
    tool.pick_shapes([])
    assert len(tool.picks) == 6  # paused: clicks select as usual
    box.pause.setChecked(False)
    tool.pick_shapes([])
    a, b = _vertex(tab, (0, 0, 0)), _vertex(tab, (50, 30, 10))
    tool.pick_shapes([a])
    tool.pick_shapes([b])
    box.project.setCurrentIndex(box.project.findData("f2"))  # Front plane: normal Z
    qtbot.waitUntil(lambda: "Normal distance" in _rows(window), timeout=10000)
    assert _rows(window)["Normal distance"] == "10.00 mm"
    assert _rows(window)["Projected distance"] == f"{math.hypot(50, 30):.2f} mm"
    assert box.frame.findData("f7") > 0  # coordinate systems can be chosen for XYZ


def test_closing_the_box_ends_the_tool(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    tool = window.measure_tool
    tool.toggle()
    assert tool.is_open
    assert tool.box is not None
    tool.box.close()
    assert not tool.is_open
    tool.toggle()
    tool.toggle()
    assert not tool.is_open


def test_status_bar_shows_selection_values(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window)
    top = next(
        f
        for f in _shapes(tab, TopAbs_FACE)
        if abs(
            __import__("fdcad.core.measure", fromlist=["measure"]).measure([f]).get("area") - 1500
        )
        < 1e-6
    )
    window._selection_changed(tab, [top])
    qtbot.waitUntil(lambda: "Area" in window.status.text(), timeout=10000)
    assert "1500.00 mm^2" in window.status.text()


def test_units_and_decimals_do_not_add_history(qtbot: QtBot, window: MainWindow) -> None:
    """Round 10c: each units, decimals or Show XYZ change measured again and added the
    same result to the history once more."""
    tab = _open(qtbot, window)
    tool = window.measure_tool
    tool.open()
    box = tool.box
    assert box is not None
    tool.pick_shapes([_vertex(tab, (0, 0, 0))])
    tool.pick_shapes([_vertex(tab, (50, 30, 10))])
    qtbot.waitUntil(lambda: "Distance" in _rows(window), timeout=10000)
    count = box.history.count()
    box.units.setCurrentIndex(box.units.findData(UnitSystem.IN))
    for places in (3, 4, 5):
        box.decimals.setValue(places)
    box.show_xyz.setChecked(False)
    tool.wait()
    qtbot.wait(50)
    assert _rows(window)["Distance"] == f"{math.sqrt(50**2 + 30**2 + 10**2) / 25.4:.5f} in"
    assert box.history.count() == count


def test_format_with_a_second_unit() -> None:
    """TR26 (D748): the value in a second unit, in brackets after the first."""
    from fdcad.ui.measure.box import format_both

    inch = UnitSystem.IN
    length = Value("length", "length", 25.4)
    assert format_both(length, UnitSystem.MM, inch, 2) == "25.40 mm (1.00 in)"
    assert format_both(length, UnitSystem.MM, None, 2) == "25.40 mm"
    assert format_both(length, inch, inch, 3) == "1.000 in"  # the same unit once
    area = Value("area", "area", 645.16)
    assert format_both(area, inch, UnitSystem.MM, 1) == "1.0 in^2 (645.2 mm^2)"
    point = Value("point", "point", (25.4, 0.0, 50.8))
    assert format_both(point, UnitSystem.MM, inch, 1) == "25.4, 0.0, 50.8 mm (1.0, 0.0, 2.0 in)"
    # Angles and counts have no unit to change.
    assert format_both(Value("angle", "angle", math.pi), UnitSystem.MM, inch, 0) == "180 deg"
    assert format_both(Value("count", "count", 12), UnitSystem.MM, inch, 0) == "12"


def test_second_unit_option(qtbot: QtBot, window: MainWindow) -> None:
    """TR26 (D748): the Measure box can show a second unit; Copy copies the first."""
    tab = _open(qtbot, window)
    tool = window.measure_tool
    tool.open()
    box = tool.box
    assert box is not None
    assert box.second_units.currentData() is None  # off until chosen
    tool.pick_shapes([_vertex(tab, (0, 0, 0))])
    tool.pick_shapes([_vertex(tab, (50, 30, 10))])
    qtbot.waitUntil(lambda: "Distance" in _rows(window), timeout=10000)
    count = box.history.count()
    box.second_units.setCurrentIndex(box.second_units.findData(UnitSystem.IN))
    d = math.sqrt(50**2 + 30**2 + 10**2)
    assert _rows(window)["Distance"] == f"{d:.2f} mm ({d / 25.4:.2f} in)"
    assert box.history.count() == count  # only how it reads changed
    copy = box.results.findChild(QToolButton, "measure_copy_distance")
    assert copy is not None
    copy.click()
    assert QGuiApplication.clipboard().text() == f"{d:.2f} mm"


def test_thickness_where_a_face_is_clicked(qtbot: QtBot, window: MainWindow) -> None:
    """TR349, D876: the spot under the cursor when a face is picked gives its wall."""
    from OCP.TopAbs import TopAbs_FACE

    from fdcad.core.naming.names import centroid

    tab = _open(qtbot, window)
    assert window.commands.trigger("evaluate.measure")
    tool = window.measure_tool
    top = next(f for f in _shapes(tab, TopAbs_FACE) if abs(centroid(f)[2] - 10) < 1e-9)  # type: ignore[arg-type]
    tool._cursor_moved((25.0, 15.0, 10.0))
    tool.pick_shapes([top])
    qtbot.waitUntil(lambda: "Thickness here" in _rows(window), timeout=10000)
    assert _rows(window)["Thickness here"] == "10.00 mm"
    assert not tab.session.undo.canUndo()  # measuring never changes the part


def test_free_points_on_faces(qtbot: QtBot, window: MainWindow) -> None:
    """TR192, D925: with Points on faces, clicks measure between the clicked spots."""
    from OCP.TopAbs import TopAbs_FACE

    from fdcad.core.naming.names import centroid

    tab = _open(qtbot, window)
    assert window.commands.trigger("evaluate.measure")
    tool = window.measure_tool
    assert tool.box is not None
    tool.box.free_points.setChecked(True)
    top = next(f for f in _shapes(tab, TopAbs_FACE) if abs(centroid(f)[2] - 10) < 1e-9)  # type: ignore[arg-type]
    tool._cursor_moved((5.0, 5.0, 10.0))
    tool.pick_shapes([top])
    assert tool.box.picks.item(0).text() == "Point 1"
    tool._cursor_moved((8.0, 9.0, 10.0))
    tool.pick_shapes([top])
    qtbot.waitUntil(lambda: "Distance" in _rows(window), timeout=10000)
    assert _rows(window)["Distance"] == "5.00 mm"
    assert not tool.keep()  # free points are not items of the part
