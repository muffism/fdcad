"""The Bend Table window and the bend order (TR282, D1110)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.sheetmetal.export import dxf_text, flat_drawing
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sheet_metal import flow
from fdcad.ui.sheet_metal.bend_table_dialog import BendTableDialog
from tests.core.features.sheetmetal.parts import add, edge_ref, flat_pattern, on, plate, sheet_doc
from tests.ui.test_revolve_edge_axis import _folders, window
from tests.ui.test_sheet_metal_ui import _open

__all__ = ["_folders", "window"]


def _two_flanges():  # type: ignore[no-untyped-def]
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60, z=2))]}, length=Param("20", 20.0))
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=0, z=2))]}, length=Param("20", 20.0))
    flat_pattern(doc, flattened=False)
    return doc


def test_edits_become_edit_bends_and_the_order(qtbot: QtBot, window: MainWindow) -> None:
    tab = _open(qtbot, window, _two_flanges())
    seen: list[str] = []

    def fill(dialog: BendTableDialog) -> bool:
        assert dialog.table.rowCount() == 2
        dialog.picked.connect(seen.append)
        dialog.table.setCurrentCell(1, 0)
        dialog.table.item(0, 4).setText("3")  # radius of bend 1
        dialog.table.item(0, 6).setText("2")  # bend 1 second
        dialog.table.item(1, 6).setText("1")
        return True

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.bend_table(window, fill)
    doc = tab.session.document
    edits = [f for f in doc.features if f.type == "edit_bends"]
    assert len(edits) == 1 and edits[0].params["radius"].value == 3.0
    flat = flow.flat_of(doc)
    assert flat is not None and flat.params["bend_order"] == "2, 1"
    assert seen and doc.features.index(edits[0]) < doc.features.index(flat)
    result = flow.flat_result(tab.session.report, doc)
    assert result is not None and sorted(result.order.values()) == [1, 2]
    assert "BEND_ORDER" in dxf_text(flat_drawing(result))
    tab.session.undo.undo()
    assert not any(f.type == "edit_bends" for f in doc.features)


def test_bad_values_keep_the_window_open(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window, _two_flanges())

    def fill(dialog: BendTableDialog) -> bool:
        dialog.table.item(0, 5).setText("zero")
        assert dialog.problem()
        return False

    assert not flow.bend_table(window, fill)


def test_rips_are_listed_and_their_gap_can_be_typed(qtbot: QtBot, window: MainWindow) -> None:
    """TR282 (D2310)."""
    from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref

    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60, z=2))]}, length=Param("20", 20.0))
    from fdcad.core.naming.names import centroid

    top, _p = face_ref(doc, (0.0, 0.0, 1.0), lambda f: abs(centroid(f)[2] - 2.0) < 1e-6)
    sk = SketchBuilder()
    sk.sk.add_line(50, 0, 50, 30)
    sid = add_sketch(doc, sk, top, "Rip Line")
    rid = add(doc, "rip", {"sketch": {"feature": sid}}, gap=Param("0.2", 0.2))
    flat_pattern(doc, flattened=False)
    tab = _open(qtbot, window, doc)
    seen: list[str] = []

    def fill(dialog: BendTableDialog) -> bool:
        assert dialog.rip_table.rowCount() == 1
        assert dialog.rip_table.item(0, 0).text() == "R1"
        dialog.rip_picked.connect(seen.append)
        dialog.rip_table.setCurrentCell(0, 0)
        dialog.rip_table.item(0, 3).setText("0.5")
        assert not dialog.problem()
        return True

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert flow.bend_table(window, fill)
    rip = tab.session.document.feature(rid)
    assert rip.params["gap"].value == 0.5 and seen == [rid]
    tab.session.undo.undo()
    assert tab.session.document.feature(rid).params["gap"].value == 0.2
