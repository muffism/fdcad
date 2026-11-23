"""Display quality (TR214, D1605)."""

from __future__ import annotations

import pytest
from OCP.BRep import BRep_Tool
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.viewport import display_quality as dq
from fdcad.ui.viewport.meshing import deviation_for, mesh_for_display
from tests.ui.test_section_view import _folders, _open, window  # noqa: F401


def _triangles(shape: object) -> int:
    total = 0
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        tri = BRep_Tool.Triangulation_s(TopoDS.Face(explorer.Current()), TopLoc_Location())
        total += tri.NbTriangles() if tri is not None else 0
        explorer.Next()
    return total


def test_quality_scales_the_deviation() -> None:
    assert deviation_for(100.0) == pytest.approx(0.05)
    assert deviation_for(100.0, 10) < deviation_for(100.0, 5) / 9
    assert deviation_for(100.0, 1) > deviation_for(100.0, 5) * 6
    assert deviation_for(0.0, 10) == 0.001


def test_finer_quality_makes_more_triangles_and_coarser_cleans() -> None:
    shape = BRepPrimAPI_MakeCylinder(20, 10).Shape()
    mesh_for_display(shape, 5)
    normal = _triangles(shape)
    mesh_for_display(shape, 10)
    fine = _triangles(shape)
    assert fine > normal
    mesh_for_display(shape, 1, coarser=True)
    assert _triangles(shape) < normal


def test_quality_is_stored_only_when_not_the_default() -> None:
    doc = new_document()
    assert dq.quality_of(doc) == 5
    dq.set_quality(doc, 8)
    assert dq.quality_of(fdef.loads(fdef.dumps(doc))) == 8
    dq.set_quality(doc, 5)
    assert dq.KEY not in doc.appearance
    doc.appearance[dq.KEY] = "high"
    assert dq.quality_of(doc) == 5


def test_dialog_shows_the_deviation(qtbot: QtBot) -> None:
    dialog = dq.DisplayQualityDialog(5, 100.0)
    qtbot.addWidget(dialog)
    assert "0.05 mm" in dialog.deviation.text()
    dialog.slider.setValue(10)
    assert dialog.quality() == 10 and "Quality 10 of 10" in dialog.deviation.text()


def test_is_large() -> None:
    assert not dq.is_large(BRepPrimAPI_MakeCylinder(1, 1).Shape())
    assert not dq.is_large(None)


def test_command_is_one_undo_step(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _open(qtbot, window)
    monkeypatch.setattr(dq.DisplayQualityDialog, "exec", lambda self: 1)
    monkeypatch.setattr(dq.DisplayQualityDialog, "quality", lambda self: 9)
    count = tab.session.undo.count()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert window.display_quality()
    assert dq.quality_of(tab.session.document) == 9
    assert tab.session.undo.count() == count + 1
    assert not window.display_quality()  # the same value again changes nothing
