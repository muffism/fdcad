"""WP14 in the main window: projection off the UI thread, the stale copy warning and
Update (sketch bar and the errors panel fix), all undoable (D250, CLAUDE.md rules 2, 3, 12)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.window import DocumentTab, MainWindow
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


def _part() -> tuple[Document, str, str, str]:
    """A 50 by 30 plate with a sketch on its top face holding a copy of its corner."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    sk1 = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk1, 10.0)
    s2 = Sketch()
    origin = s2.add_point(0, 0, True)
    s2.relate("fixed", origin)
    corner = s2.add_point(50, 30, True)
    s2.entities[corner].source = {  # type: ignore[union-attr]
        "kind": "vertex",
        "name": f"vertex({ext}/cap/end|{ext}/side/e6|{ext}/side/e7)",
    }
    s2.relate("fixed", corner)
    q = s2.add_point(40, 30)
    s2.relate("coincident", q, corner)
    sk2 = add_sketch(doc, s2, {"kind": "face", "name": f"{ext}/cap/end"})
    return doc, sk1, sk2, corner


def _open(qtbot: QtBot, win: MainWindow, doc: Document) -> DocumentTab:
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _widen(tab: DocumentTab, qtbot: QtBot, sk1: str) -> None:
    """Make the plate 60 wide, so the corner copy no longer matches."""
    from fdcad.ui.commands.document import ReplaceFeature

    session = tab.session
    import copy

    feature = copy.deepcopy(session.document.feature(sk1))
    for e in feature.data["entities"]:
        if e["type"] == "point" and e["x"] == 50:
            e["x"] = 60.0
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.push(ReplaceFeature(session, feature))


def test_copy_matches_then_warns_after_the_part_changes(qtbot: QtBot, window: MainWindow) -> None:
    doc, sk1, sk2, corner = _part()
    tab = _open(qtbot, window, doc)
    report = tab.session.report
    assert report is not None and report.results[sk2].state is FeatureState.OK
    _widen(tab, qtbot, sk1)
    report = tab.session.report
    assert report is not None
    res = report.results[sk2]
    assert res.state is FeatureState.WARNING
    assert any(i.code == "stale_links" for i in res.issues)
    # The copy never moves on its own (rule 12).
    entities = tab.session.document.feature(sk2).data["entities"]
    assert next(e for e in entities if e["id"] == corner)["x"] == 50


def test_sketch_bar_update_and_projection(qtbot: QtBot, window: MainWindow) -> None:
    doc, sk1, sk2, corner = _part()
    tab = _open(qtbot, window, doc)
    _widen(tab, qtbot, sk1)
    mode = window.sketch_mode
    assert mode is not None
    mode.edit(sk2)
    canvas = mode.canvas
    assert canvas is not None and mode.link_bar is not None
    assert not mode.link_bar.isHidden()
    # The projection arrives from a worker thread, once.
    qtbot.waitUntil(lambda: canvas.model_index is not None, timeout=20000)
    index = canvas.model_index
    assert index is not None
    assert any(p.xy == pytest.approx((60.0, 30.0)) for p in index.points)
    mode.link_bar.button.click()
    sk = canvas.edit.sketch
    assert sk.xy(corner) == pytest.approx((60.0, 30.0))
    assert mode.link_bar.isHidden()
    canvas.undo()
    assert canvas.edit.sketch.xy(corner) == (50.0, 30.0)
    canvas.redo()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert mode.accept()
    report = tab.session.report
    assert report is not None and report.results[sk2].state is FeatureState.OK


def test_errors_panel_fix_updates_and_undoes(qtbot: QtBot, window: MainWindow) -> None:
    doc, sk1, sk2, corner = _part()
    tab = _open(qtbot, window, doc)
    _widen(tab, qtbot, sk1)
    report = tab.session.report
    assert report is not None
    issue = next(i for i in report.results[sk2].issues if i.code == "stale_links")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.apply_fix(sk2, issue.fixes[0])
    entities = tab.session.document.feature(sk2).data["entities"]
    assert next(e for e in entities if e["id"] == corner)["x"] == pytest.approx(60.0)
    report = tab.session.report
    assert report is not None and report.results[sk2].state is FeatureState.OK
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    entities = tab.session.document.feature(sk2).data["entities"]
    assert next(e for e in entities if e["id"] == corner)["x"] == 50
