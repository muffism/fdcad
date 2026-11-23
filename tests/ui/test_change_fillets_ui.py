"""Change Fillet Edge, Change Fillets and Change Drafts dialogs (TR132, D1404)."""

from __future__ import annotations

import math

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, Param
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from fdcad.ui.tree.change_fillets import DraftsDialog, EdgeDialog, FilletsDialog
from tests.core.features.test_features import body, plate
from tests.core.features.test_fillet import add_fillet, top_edges
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _session(qtbot: QtBot, window: MainWindow) -> tuple[DocumentSession, str, list[str]]:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in top_edges(b, ext)[:2]]
    fid = add_fillet(doc, 2.0, edges=refs)
    add_fillet(doc, 3.0, edges=[reference_for(b, top_edges(b, ext)[2])])
    doc.features.append(
        Feature(
            doc.new_feature_id(),
            "draft",
            "Draft 1",
            params={"angle": Param("3", math.radians(3))},
            refs={"neutral": {"feature": "f3"}, "faces": []},
        )
    )
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    return session, fid, [str(r["name"]) for r in refs if r is not None]


def test_edge_dialog_sets_a_radius_and_removes_an_edge(qtbot: QtBot, window: MainWindow) -> None:
    session, fid, names = _session(qtbot, window)
    dialog = EdgeDialog(session, fid, names[1])
    dialog.radius.edit.setText("1")
    dialog.set_radius()
    feature = session.document.feature(fid)
    assert feature.params["radius_2"].value == 1.0
    dialog = EdgeDialog(session, fid, names[0])
    dialog.remove_edge()
    feature = session.document.feature(fid)
    assert [r["name"] for r in feature.refs["edges"]] == [names[1]]
    assert feature.params["radius_1"].value == 1.0  # moved up with its edge
    session.undo.undo()
    assert len(session.document.feature(fid).refs["edges"]) == 2


def test_fillets_dialog_filters_and_changes_together(qtbot: QtBot, window: MainWindow) -> None:
    session, fid, _names = _session(qtbot, window)
    dialog = FilletsDialog(session)
    assert len(dialog.listed()) == 2
    dialog.low.edit.setText("2.5")
    assert len(dialog.listed()) == 1 and fid not in dialog.listed()
    dialog.low.edit.setText("0")
    dialog.new.edit.setText("1.5")
    dialog.apply()
    radii = [f.params["radius"].value for f in session.document.features if f.type == "fillet"]
    assert radii == [1.5, 1.5]
    session.undo.undo()
    radii = [f.params["radius"].value for f in session.document.features if f.type == "fillet"]
    assert radii == [2.0, 3.0]


def test_drafts_dialog_sets_angle_and_removes(qtbot: QtBot, window: MainWindow) -> None:
    session, _fid, _names = _session(qtbot, window)
    dialog = DraftsDialog(session)
    assert dialog.table.rowCount() == 1
    dialog.apply_angle()
    assert "Select drafts" in dialog.message.text()
    dialog.table.selectRow(0)
    dialog.angle.edit.setText("5")
    dialog.apply_angle()
    draft = next(f for f in session.document.features if f.type == "draft")
    assert draft.params["angle"].value == math.radians(5)
    dialog.table.selectRow(0)
    dialog.remove_selected()
    assert not any(f.type == "draft" for f in session.document.features)


def test_split_fix_adds_fillets_in_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:
    """TR346 (D1405): the split fix from the errors panel."""
    from fdcad.core.features.base import Fix

    session, fid, names = _session(qtbot, window)
    count = len(session.document.features)
    fix = Fix("One fillet per edge (2 fillets)", "split_fillet", {"feature": fid,
              "groups": [[names[0]], [names[1]]]})  # fmt: skip
    window.apply_fix(fid, fix)
    doc = session.document
    assert len(doc.features) == count + 1
    index = next(i for i, f in enumerate(doc.features) if f.id == fid)
    assert doc.features[index + 1].type == "fillet"
    assert [r["name"] for r in doc.features[index + 1].refs["edges"]] == [names[1]]
    session.undo.undo()
    assert len(session.document.features) == count


def test_remove_fillets_feature_from_the_dialog(qtbot: QtBot, window: MainWindow) -> None:
    """TR260 (D1410): count rounds in the range and add a Remove Fillets feature."""
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    add_fillet(doc, 2.0, edges=[reference_for(b, top_edges(b, ext)[0])])
    add_fillet(doc, 3.0, edges=[reference_for(b, top_edges(b, ext)[2])])
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    dialog = FilletsDialog(session)
    assert dialog.count_rounds() == 2
    dialog.low.edit.setText("2.5")
    assert dialog.count_rounds() == 1
    dialog.new.edit.setText("1")
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        dialog.add_remove_fillets()
    made = session.document.features[-1]
    assert made.type == "remove_fillets" and made.params["min_radius"].value == 2.5
    assert session.report is not None
    res = session.report.results[made.id]
    assert res.state.value != "error", [i.message for i in res.issues]
    window.edit_feature(made.id)
    form = window.panel.form
    assert form is not None and type(form).__name__ == "RemoveFilletsForm"
    window.panel.reject()
