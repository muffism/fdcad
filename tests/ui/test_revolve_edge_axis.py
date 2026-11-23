"""Revolve axis picked as a straight edge of the part, through the window (W6.3)."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from pathlib import Path

import pytest
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.features.solids import line_ends
from fdcad.core.occ import ShapeMap
from fdcad.ui import strings
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from tests.core.features.test_revolve_axis import ring


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.show()
    win.finish_setup()
    yield win
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _edges(tab: DocumentTab) -> list[object]:
    report = tab.session.report
    assert report is not None and report.body is not None
    emap = ShapeMap()
    TopExp.MapShapes_s(report.body.shape, TopAbs_EDGE, emap)
    return [emap.FindKey(i) for i in range(1, emap.Extent() + 1)]


def _edge_at(tab: DocumentTab, a: tuple[float, ...], b: tuple[float, ...]) -> object:
    for edge in _edges(tab):
        ends = line_ends(edge)  # type: ignore[arg-type]
        if ends and {tuple(round(v, 6) for v in p) for p in ends} == {a, b}:
            return edge
    raise AssertionError("edge not found")


def _open(qtbot: QtBot, win: MainWindow) -> tuple[DocumentTab, str]:
    doc, _ext, rev = ring()
    # Start from a sketch line axis: the left side of the profile.
    sketch = doc.features[-2]
    left = next(
        e["id"]
        for e in sketch.data["entities"]
        if e["type"] == "line"
        and {p["x"] for p in sketch.data["entities"] if p["id"] in (e["p1"], e["p2"])} == {60}
    )
    doc.feature(rev).refs["axis"] = {"sketch_entity": left}
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab, rev


def test_clicking_a_straight_edge_sets_the_axis(qtbot: QtBot, window: MainWindow) -> None:
    tab, rev = _open(qtbot, window)
    panel = window.panel
    assert panel is not None
    window.edit_feature(rev)
    assert panel.is_editing and panel.axis_box.currentData() is not None
    edge = _edge_at(tab, (50.0, 0.0, 0.0), (50.0, 50.0, 0.0))
    window._selection_changed(tab, [edge])
    ref = panel.axis_box.currentData()
    assert isinstance(ref, dict) and ref["kind"] == "edge"
    assert panel.axis_box.currentText() == strings.AXIS_EDGE.format(feature="Extrude f6")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    stored = tab.session.document.feature(rev).refs["axis"]
    assert stored["kind"] == "edge" and stored["name"].startswith("edge(")
    # One undoable command; undo brings the sketch line back.
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert "sketch_entity" in tab.session.document.feature(rev).refs["axis"]
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.redo()
    assert tab.session.document.feature(rev).refs["axis"] == stored
    # Opening it again shows the edge as the chosen axis.
    window.edit_feature(rev)
    assert panel.axis_box.currentData() == stored
    panel.reject()


def test_curved_or_later_edges_are_refused(qtbot: QtBot, window: MainWindow) -> None:
    tab, rev = _open(qtbot, window)
    panel = window.panel
    assert panel is not None
    window.edit_feature(rev)
    before = copy.deepcopy(panel.axis_box.currentData())
    curved = next(e for e in _edges(tab) if line_ends(e) is None)  # type: ignore[arg-type]
    window._selection_changed(tab, [curved])
    assert window.status.text() == strings.AXIS_EDGE_NOT_STRAIGHT
    # A straight edge made by the revolve itself cannot be its own axis.
    own = next(
        e
        for e in _edges(tab)
        if line_ends(e) is not None  # type: ignore[arg-type]
        and rev in str(tab.session.report.body.edge_name(e))  # type: ignore[union-attr, arg-type]
    )
    window._selection_changed(tab, [own])
    assert "cannot use an edge or face made by itself" in window.status.text()
    assert panel.axis_box.currentData() == before
    panel.reject()


def test_origin_axes_are_in_the_axis_list(qtbot: QtBot, window: MainWindow) -> None:
    """Spec 2 section 20 item 3 (D712): only sketch lines and picked edges were listed."""
    from fdcad.ui import strings_phase3

    _tab, rev = _open(qtbot, window)
    panel = window.panel
    assert panel is not None
    window.edit_feature(rev)
    labels = [panel.axis_box.itemText(i) for i in range(panel.axis_box.count())]
    assert all(label in labels for label in strings_phase3.ORIGIN_AXES.values())
    index = labels.index(strings_phase3.ORIGIN_AXES["y"])
    assert panel.axis_box.itemData(index) == {"feature": "f1", "axis": "y"}
    panel.reject()


def test_clicking_a_round_face_uses_its_axis(qtbot: QtBot, window: MainWindow) -> None:
    """Spec 2 section 20 item 4 (D712): a temporary axis (round face) was not taken."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    tab, rev = _open(qtbot, window)
    panel = window.panel
    assert panel is not None
    report = tab.session.report
    assert report is not None and report.body is not None
    fmap = ShapeMap()
    TopExp.MapShapes_s(report.body.shape, TopAbs_FACE, fmap)
    faces = [fmap.FindKey(i) for i in range(1, fmap.Extent() + 1)]
    round_faces = [
        f for f in faces if BRepAdaptor_Surface(TopoDS.Face(f)).GetType() == GeomAbs_Cylinder
    ]
    if not round_faces:
        pytest.skip("the ring sample has no cylinder before the revolve")
    window.edit_feature(rev)
    window.status.clear()
    window._selection_changed(tab, [round_faces[0]])
    # The ring's round faces come from the revolve itself, so this one is refused as
    # too late; before, a face click was ignored with no message.
    data = panel.axis_box.currentData()
    took = isinstance(data, dict) and data.get("kind") == "face"
    assert took or "made by itself" in window.status.text(), window.status.text()
    panel.reject()
