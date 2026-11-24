"""Main window flow for Phase 2 features: the command opens the panel with the selection
as picks, view picks go to the panel, OK adds an undoable feature, and fix buttons
in the errors list change the feature only when clicked (CLAUDE.md rules 3 and 12)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.modify import edges_of
from fdcad.ui.commands.document import AddFeature
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))
    REMEMBERED.clear()


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1200, 800)
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


def plate_tab(qtbot: QtBot, win: MainWindow) -> tuple[DocumentTab, str]:
    doc, ext = plate()
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab, ext


def top_edges(tab: DocumentTab, ext: str) -> list:
    report = tab.session.report
    assert report is not None and report.body is not None
    face = report.body.face(f"{ext}/cap/end")
    assert face is not None
    return edges_of(face)


def test_fillet_from_selection_view_picks_and_ok(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = plate_tab(qtbot, window)
    edges = top_edges(tab, ext)
    tab.selection = [edges[0]]
    window.insert_feature("fillet", "boss")
    panel = window.panel
    assert panel is not None and panel.form is not None
    assert len(panel.form.items.refs()) == 1
    window._selection_changed(tab, [edges[1]])  # a click in the view adds an edge
    assert len(panel.form.items.refs()) == 2
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    doc = tab.session.document
    fillet = doc.features[-1]
    assert fillet.type == "fillet" and len(fillet.refs["edges"]) == 2
    report = tab.session.report
    assert report is not None and report.results[fillet.id].state is FeatureState.OK
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert doc.features[-1].type == "extrude"


def test_fix_buttons_change_the_feature_only_when_clicked(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = plate_tab(qtbot, window)
    edges = top_edges(tab, ext)
    window.insert_feature("fillet", "boss")
    panel = window.panel
    assert panel is not None and panel.form is not None
    report = tab.session.report
    assert report is not None and report.body is not None
    panel.form.take_shapes(report.body, edges[:1])
    panel.form.fields["radius"].edit.setText("60")  # larger than the 50 mm plate allows
    # OK takes a failing feature back to the panel (D2876). A feature in the tree still
    # fails when a change before it breaks it, so add this one as such a change would.
    failing = panel.current_feature()
    assert failing is not None
    panel.reject()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.push(AddFeature(tab.session, failing))
    report = tab.session.report
    assert report is not None
    fillet = tab.session.document.features[-1]
    issue = report.results[fillet.id].issues[0]
    assert report.results[fillet.id].state is FeatureState.ERROR
    reduce = next(f for f in issue.fixes if f.action == "set_param")
    assert fillet.params["radius"] == Param("60", 60.0)  # nothing changed by itself
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.apply_fix(fillet.id, reduce)
    fixed = tab.session.document.feature(fillet.id)
    radius = fixed.params["radius"]
    assert isinstance(radius, Param) and radius.value < 60
    report = tab.session.report
    assert report is not None and report.results[fillet.id].state is FeatureState.OK
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()  # the fix is one undoable step
    assert tab.session.document.feature(fillet.id).params["radius"] == Param("60", 60.0)


def test_edit_feature_opens_the_fillet_form(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = plate_tab(qtbot, window)
    window.insert_feature("fillet", "boss")
    panel = window.panel
    assert panel is not None and panel.form is not None
    report = tab.session.report
    assert report is not None and report.body is not None
    panel.form.take_shapes(report.body, top_edges(tab, ext)[:1])
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    fid = tab.session.document.features[-1].id
    window.edit_feature(fid)
    assert panel.form is not None and panel.form.items.names()
    panel.reject()


def _settled(qtbot: QtBot, tab: DocumentTab) -> None:
    """Wait until the part is rebuilt and nothing is left to build."""
    qtbot.waitUntil(lambda: not tab.session.is_rebuilding, timeout=20000)
    qtbot.wait(50)
    qtbot.waitUntil(lambda: not tab.session.is_rebuilding, timeout=20000)


def test_ok_on_a_fillet_that_fails_keeps_the_panel_open(qtbot: QtBot, window: MainWindow) -> None:
    """D2876, the owner: a fillet that does not work out must not finish its command."""
    tab, ext = plate_tab(qtbot, window)
    session = tab.session
    count = len(session.document.features)
    window.insert_feature("fillet", "boss")
    panel = window.panel
    assert panel is not None and panel.form is not None
    report = session.report
    assert report is not None and report.body is not None
    panel.form.take_shapes(report.body, top_edges(tab, ext)[:1])
    panel.form.fields["radius"].edit.setText("60")  # larger than the 50 mm plate allows
    panel.accept()
    qtbot.waitUntil(lambda: panel.is_editing, timeout=20000)
    _settled(qtbot, tab)
    assert len(session.document.features) == count  # not applied
    assert panel.is_new and panel.feature is not None and panel.feature.type == "fillet"
    assert panel.form is not None and panel.form.fields["radius"].edit.text() == "60"
    assert "was not applied because it failed" in panel.message.text()
    assert not panel.message.isHidden()
    panel.reject()
    assert not panel.is_editing and len(session.document.features) == count


def test_ok_on_an_edit_that_fails_keeps_the_old_values(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = plate_tab(qtbot, window)
    session = tab.session
    window.insert_feature("fillet", "boss")
    panel = window.panel
    assert panel is not None and panel.form is not None
    report = session.report
    assert report is not None and report.body is not None
    panel.form.take_shapes(report.body, top_edges(tab, ext)[:1])
    panel.form.fields["radius"].edit.setText("5")
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        panel.accept()
    _settled(qtbot, tab)
    fid = session.document.features[-1].id
    assert session.report is not None
    assert session.report.results[fid].state is FeatureState.OK
    assert not panel.is_editing  # a feature that builds closes as before
    window.edit_feature(fid)
    assert panel.form is not None
    panel.form.fields["radius"].edit.setText("60")
    panel.accept()
    qtbot.waitUntil(lambda: panel.is_editing, timeout=20000)
    _settled(qtbot, tab)
    assert session.document.feature(fid).params["radius"] == Param("5", 5.0)
    assert not panel.is_new and panel.form is not None
    assert panel.form.fields["radius"].edit.text() == "60"
    assert session.report is not None
    assert session.report.results[fid].state is FeatureState.OK
