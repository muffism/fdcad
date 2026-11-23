"""Extrude by dragging a sketch region without the panel (TOOL_SPEC T5.4, D525).

The 3D view needs a GPU, so the click is given as a view ray; everything after
it (worker, preview, bar, command) runs as in the app.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.ui.main_window.sketch_drag import (
    SketchDragTool,
    plane_hit,
    reverse_for,
    sketch_hits,
    start_depth,
)
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, rect, volume

FRONT = SketchPlane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))


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
    win.sketch_drag.cancel()
    win.sketch_drag.wait()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _part() -> tuple[Document, str, str]:
    """A 50 by 30 by 10 plate, a 10 mm square sketched on its top and one beside it."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    base = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, base, 10.0)
    on_top = Sketch()
    rect(on_top, 5, 5, 15, 15)
    top = add_sketch(doc, on_top, {"kind": "face", "name": f"{ext}/cap/end"})
    beside = Sketch()
    rect(beside, 60, 0, 70, 10)
    off = add_sketch(doc, beside, {"feature": "f2"})
    return doc, top, off


def _open(qtbot: QtBot, win: MainWindow, doc: Document) -> DocumentTab:
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _click(
    qtbot: QtBot, tool: SketchDragTool, tab: DocumentTab, sid: str, u: float, v: float
) -> None:
    """Click straight down onto sketch ``sid`` at its (u, v)."""
    report = tab.session.report
    assert report is not None
    out = report.results[sid].sketch
    assert out is not None
    p = out.plane.to_3d(u, v)
    point = (p.X(), p.Y(), p.Z())
    n = out.plane.normal
    start = (point[0] + n[0] * 100, point[1] + n[1] * 100, point[2] + n[2] * 100)
    with qtbot.waitSignal(tool.armed, timeout=20000):
        assert tool.start_at(tab, (start, (-n[0], -n[1], -n[2])), point)


# Pure helpers ------------------------------------------------------------------------------


def test_the_click_ray_meets_sketch_planes_in_front_of_the_part() -> None:
    u, v, p, t = plane_hit((3.0, 4.0, 50.0), (0.0, 0.0, -1.0), FRONT)
    assert (u, v, t) == pytest.approx((3, 4, 50)) and p == pytest.approx((3, 4, 0))
    raised = SketchPlane((0.0, 0.0, 20.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    ray = ((3.0, 4.0, 50.0), (0.0, 0.0, -1.0))
    hits = sketch_hits(ray, {"low": FRONT, "high": raised})
    assert [h.sketch_id for h in hits] == ["high", "low"]  # nearest first
    hidden = sketch_hits(ray, {"low": FRONT, "high": raised}, part_point=(3.0, 4.0, 10.0))
    assert [h.sketch_id for h in hidden] == ["high"]  # the part hides the lower one
    on_face = sketch_hits(ray, {"low": FRONT}, part_point=(3.0, 4.0, 0.0))
    assert [h.sketch_id for h in on_face] == ["low"]  # a sketch on the clicked face counts
    side = SketchPlane((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert sketch_hits(ray, {"side": side}) == []  # seen edge on


def test_cuts_go_into_the_part_and_bosses_away_from_it() -> None:
    assert reverse_for("cut", -1) and not reverse_for("cut", 1)
    assert reverse_for("boss", 1) and not reverse_for("boss", -1)
    assert not reverse_for("boss", 0) and not reverse_for("cut", 0)


# In the window ----------------------------------------------------------------------------


def test_region_on_the_part_starts_as_a_cut_and_ok_adds_it(
    qtbot: QtBot, window: MainWindow
) -> None:
    doc, top, _off = _part()
    tab = _open(qtbot, window, doc)
    tool = window.sketch_drag
    _click(qtbot, tool, tab, top, 10, 10)
    feature = tool.feature
    assert feature is not None and tool.start is not None
    assert feature.type == "extrude" and feature.params["operation"] == "cut"
    assert feature.params["reverse"] is True  # into the part
    assert feature.params["end_condition"] == "blind"
    assert feature.refs["sketch"] == {"feature": top}
    assert [r["kind"] for r in feature.refs["regions"]] == ["region"]
    assert feature.params["depth"].value == pytest.approx(start_depth(tool.start.region, False))
    with qtbot.waitSignal(tool.preview.ready, timeout=20000):
        tool.set_depth("depth", 4.0)
    assert feature.params["depth"].expr == "4"
    bar = tool.released(QPoint(40, 40))
    assert bar is not None and bar.isVisible() and bar.cut.isChecked()
    count = len(doc.features)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        bar.ok.click()
    assert not tool.is_active and tool.bar is None
    assert len(doc.features) == count + 1
    added = doc.features[-1]
    assert added.name == "Cut 1"  # as the panel names it
    report = tab.session.report
    assert report is not None
    result = report.results[added.id]
    assert result.state is FeatureState.OK and result.body is not None
    assert volume(result.body.shape) == pytest.approx(50 * 30 * 10 - 10 * 10 * 4, rel=1e-6)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()  # one undoable step
    assert len(doc.features) == count


def test_region_off_the_part_starts_as_a_boss_and_the_bar_swaps_it(
    qtbot: QtBot, window: MainWindow
) -> None:
    doc, _top, off = _part()
    tab = _open(qtbot, window, doc)
    tool = window.sketch_drag
    before = (len(doc.features), doc.next_id)
    _click(qtbot, tool, tab, off, 65, 5)
    feature = tool.feature
    assert feature is not None
    assert feature.params["operation"] == "boss" and feature.params["reverse"] is False
    bar = tool.released(QPoint(10, 10))
    assert bar is not None and bar.boss.isChecked()
    bar.cut.click()
    assert feature.params["operation"] == "cut" and "Cut" in feature.name
    assert bar.cut.isChecked() and not bar.boss.isChecked()
    bar.boss.click()
    assert feature.params["operation"] == "boss"
    tool.flip("depth")  # dragged past the start
    assert feature.params["reverse"] is True
    bar.cancel.click()
    assert not tool.is_active
    assert (len(doc.features), doc.next_id) == before  # nothing changed


def test_escape_cancels_and_edit_in_panel_opens_the_panel(qtbot: QtBot, window: MainWindow) -> None:
    doc, top, _off = _part()
    tab = _open(qtbot, window, doc)
    tool = window.sketch_drag
    _click(qtbot, tool, tab, top, 10, 10)
    bar = tool.released(QPoint(10, 10))
    assert bar is not None
    count = len(doc.features)
    qtbot.keyClick(bar, Qt.Key.Key_Escape)
    assert not tool.is_active and len(doc.features) == count
    _click(qtbot, tool, tab, top, 10, 10)
    feature = tool.feature
    assert feature is not None
    tool.released(QPoint(10, 10))
    assert tool.bar is not None
    tool.bar.panel.click()
    panel = window.panel
    assert panel is not None and panel.is_editing and not tool.is_active
    assert panel.feature is not None and panel.feature.refs.get("regions")
    assert len(doc.features) == count  # nothing added until the panel's OK
    panel.reject()


def test_no_region_under_the_click_and_nothing_while_editing(
    qtbot: QtBot, window: MainWindow
) -> None:
    doc, top, _off = _part()
    tab = _open(qtbot, window, doc)
    tool = window.sketch_drag
    ray = ((30.0, 25.0, 100.0), (0.0, 0.0, -1.0))  # over the plate, away from both squares
    assert tool.start_at(tab, ray, (30.0, 25.0, 10.0)) is True  # the top sketch's plane is hit
    tool.wait()
    qtbot.wait(50)
    assert not tool.is_active  # but no region holds the point
    window.reference_tool.start("ref_plane")  # another panel is open: no drag
    assert not tool.start_at(tab, ray, None)
    window.reference_tool.close()
    from fdcad.ui.main_window.new_feature import new_feature

    panel = window.panel
    assert panel is not None
    panel.begin(tab.session, new_feature(doc, doc.feature(top), "extrude", "boss"), is_new=True)
    assert window.editing == "feature"
    assert not tool.start_at(tab, ray, None)
    panel.reject()


def test_starting_another_tool_drops_the_arrow(qtbot: QtBot, window: MainWindow) -> None:
    doc, top, _off = _part()
    tab = _open(qtbot, window, doc)
    tool = window.sketch_drag
    count = len(doc.features)
    _click(qtbot, tool, tab, top, 10, 10)
    window.reference_tool.start("ref_plane")
    assert not tool.is_active
    window.reference_tool.close()
    _click(qtbot, tool, tab, top, 10, 10)
    from fdcad.ui.main_window.new_feature import new_feature

    panel = window.panel
    assert panel is not None
    panel.begin(tab.session, new_feature(doc, doc.feature(top), "extrude", "boss"), is_new=True)
    assert not tool.is_active
    panel.reject()
    assert len(doc.features) == count
