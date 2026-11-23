"""Renaming a feature in the tree rewrites the formulas that use it (D527)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, Variable
from fdcad.core.units import Kind
from fdcad.ui.main_window.window import MainWindow
from tests.core.equations.test_equations import _plate
from tests.ui.test_errors_panel import _folders, _open, window  # noqa: F401  (fixtures)


def test_tree_rename_rewrites_formulas_and_undo_restores(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    doc = _plate()
    ext = doc.features[-1].id
    doc.variables.append(Variable("Twice", Kind.LENGTH, '="depth@Extrude 1" * 2', 20.0))
    doc.variables.append(Variable("Other", Kind.LENGTH, '="depth@Extrude 10" + 1mm', 0.0))
    tab = _open(qtbot, window, doc)
    session = tab.session
    tree = window.tree
    assert tree is not None
    item = tree.item_for(ext)
    assert item is not None
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        item.setText(0, "Base")
    doc = session.document
    assert doc.feature(ext).name == "Base"
    assert [v.expr for v in doc.variables[1:]] == ['="depth@Base" * 2', '="depth@Extrude 10" + 1mm']
    assert session.undo.count() == 1
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    doc = session.document
    assert doc.feature(ext).name == "Extrude 1"
    assert doc.variables[1].expr == '="depth@Extrude 1" * 2'
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.redo()
    assert session.document.variables[1].expr == '="depth@Base" * 2'


def test_sketch_rename_rewrites_feature_values(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    doc = _plate()
    sid, ext = doc.features[-2].id, doc.features[-1].id
    doc.feature(ext).params["depth"] = Param('="d1@Sketch 1" / 6', 10.0)
    tab = _open(qtbot, window, doc)
    session = tab.session
    assert window.tree is not None
    item = window.tree.item_for(sid)
    assert item is not None
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        item.setText(0, "Outline")
    depth = session.document.feature(ext).params["depth"]
    assert isinstance(depth, Param) and depth.expr == '="d1@Outline" / 6'
    report = session.report
    assert report is not None and report.results[ext].issues == []
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    depth = session.document.feature(ext).params["depth"]
    assert isinstance(depth, Param) and depth.expr == '="d1@Sketch 1" / 6'


def test_tree_refuses_a_name_another_feature_has(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = _plate()
    sid, ext = doc.features[-2].id, doc.features[-1].id
    doc.variables.append(Variable("Twice", Kind.LENGTH, '="depth@Extrude 1" * 2', 20.0))
    tab = _open(qtbot, window, doc)
    session = tab.session
    tree = window.tree
    assert tree is not None
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, text: shown.append(text))
    for name in ("Sketch 1", 'Extrude "A"', "depth@Plate"):
        item = tree.item_for(ext)
        assert item is not None
        item.setText(0, name)
    assert session.undo.count() == 0
    assert session.document.feature(ext).name == "Extrude 1"
    assert session.document.feature(sid).name == "Sketch 1"
    assert len(shown) == 3 and all("Cannot rename Extrude 1" in s for s in shown)
    item = tree.item_for(ext)
    assert item is not None and item.text(0) == "Extrude 1"  # the old name is back
