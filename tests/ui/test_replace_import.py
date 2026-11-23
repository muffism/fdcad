"""Replace an imported body with a new file (TR11, D694)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document
from fdcad.core.features.import_replace import ReplaceError, block_users, can_replace, new_source
from fdcad.core.io import fdef
from fdcad.core.io.export import export_step
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR, measure
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _bracket_step(tmp_path: Path) -> tuple[Path, float]:
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    path = tmp_path / "bracket.step"
    export_step(report.body.shape, path)
    return path, float(measure(report.body.shape)["volume"])


def _imported() -> Document:
    return fdef.loads(
        (SAMPLE_DIR / "imported_step_with_features.fdprt").read_text(encoding="utf-8")
    )


def test_core_checks_the_kind_of_file(tmp_path: Path) -> None:
    doc = _imported()
    feature = next(f for f in doc.features if f.type == "import_step")
    assert can_replace(feature)
    with pytest.raises(ReplaceError):
        new_source(doc, feature, "part.stl", b"solid")
    with pytest.raises(ReplaceError):
        new_source(doc, feature, "part.step", b"")
    bid, block = new_source(doc, feature, "part.step", b"ISO-10303-21;")
    assert bid not in doc.embedded and block
    assert block_users(doc, feature.refs["source"]["embedded"]) == [feature.id]


def test_replace_from_file_rebuilds_on_the_new_body_and_undoes(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    step, bracket_volume = _bracket_step(tmp_path)
    doc = _imported()
    fid = next(f.id for f in doc.features if f.type == "import_step")
    old_block = doc.feature(fid).refs["source"]["embedded"]
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert window.import_flow.replace(fid, step)
    feature = session.document.feature(fid)
    new_block = feature.refs["source"]["embedded"]
    assert new_block != old_block and old_block not in session.document.embedded
    result = session.report.results[fid] if session.report else None
    assert result is not None and result.body is not None
    assert float(measure(result.body.shape)["volume"]) == pytest.approx(bracket_volume, rel=1e-6)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert session.document.feature(fid).refs["source"]["embedded"] == old_block
    assert old_block in session.document.embedded and new_block not in session.document.embedded


def test_tree_menu_offers_replace(qtbot: QtBot, window: MainWindow) -> None:
    doc = _imported()
    fid = next(f.id for f in doc.features if f.type == "import_step")
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    assert window.tree is not None
    item = window.tree.item_for(fid)
    assert item is not None
    menu = window.tree._context_menu(session, item)
    assert menu is not None and "Replace From File..." in [a.text() for a in menu.actions()]
