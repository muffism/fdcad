"""A face clicked in the view becomes the From pick of an open extrude (T5.1.2)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_clicking_a_face_sets_the_from_pick(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    boss = add_extrude(doc, sk, 5.0)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    panel = window.panel
    assert panel is not None
    window.edit_feature(boss)
    assert panel.start is not None
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ext}/cap/end")
    window._selection_changed(tab, [top])
    assert "start" not in (panel.current_feature() or doc.feature(boss)).refs  # Sketch Plane
    panel.start.condition.setCurrentIndex(panel.start.condition.findData("surface"))
    window._selection_changed(tab, [top])
    result = panel.current_feature()
    assert result is not None and result.refs["start"]["name"] == f"{ext}/cap/end"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.accept()
    assert tab.session.document.feature(boss).params["start_condition"] == "surface"
    report = tab.session.report
    assert report is not None and report.results[boss].state.value == "ok"
