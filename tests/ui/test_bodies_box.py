"""The Bodies box of cuts and bosses in a multibody part (TR33, D697)."""

from __future__ import annotations

from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from pytestqt.qtbot import QtBot

from fdcad.core.features.solids import solids
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_bodies_scope import _cut_across, _split
from tests.ui.test_property_panel import _session


def test_box_shows_in_multibody_parts_and_picks_a_body_per_face(qtbot: QtBot) -> None:
    doc = _split()
    fid = _cut_across(doc, "all", [])
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, session.document.feature(fid), is_new=False)
    box = panel.bodies_box
    assert box is not None and not box.selected() and not panel.bodies_want_pick()
    box.scope.setCurrentIndex(1)
    assert panel.bodies_want_pick()
    assert panel.current_feature() is None  # Selected with nothing picked
    report = session.report
    assert report is not None and report.body is not None
    # The part before the cut: two bodies. Pick two faces of the first one.
    from fdcad.core.features.preview import body_before

    before = body_before(session.document, session.document.feature(fid), report.results)
    assert before is not None
    first = solids(before.shape)[0]
    explorer = TopExp_Explorer(first, TopAbs_FACE)
    a = explorer.Current()
    explorer.Next()
    b = explorer.Current()
    assert box.take(before, [a, b]) is None
    assert len(box.picks.refs()) == 1  # one body, however many of its faces
    edited = panel.current_feature()
    assert edited is not None
    assert edited.params["bodies_scope"] == "selected" and len(edited.refs["bodies"]) == 1


def test_single_body_parts_get_no_box(qtbot: QtBot) -> None:
    from tests.ui.test_extrude_phase2_panel import _second

    session, _ext, fid = _second(qtbot)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, session.document.feature(fid), is_new=False)
    assert panel.bodies_box is None
