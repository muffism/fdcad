"""Copy a sketch or a feature in the tree and paste it on a plane or face (TR3.2, TR9, D685)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.samples.make import SAMPLE_DIR, measure
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.ui.test_main_window import _folders, window
from tests.ui.test_workflow import face_with_normal

__all__ = ["_folders", "window"]


def _open_bracket(qtbot: QtBot, win: MainWindow, tmp_path: Path) -> DocumentTab:
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _volume(tab: DocumentTab) -> float:
    report = tab.session.report
    assert report is not None and report.body is not None
    return float(measure(report.body.shape)["volume"])


def test_copy_a_sketch_and_paste_it_on_a_plane(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    tab = _open_bracket(qtbot, window, tmp_path)
    assert window.tree is not None
    window.tree.select("f5")
    assert window.feature_clipboard.copy()
    window.tree.select("f3")  # Top Plane
    count = len(tab.session.document.features)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert window.feature_clipboard.paste()
    doc = tab.session.document
    assert len(doc.features) == count + 1
    new = doc.features[-1]
    assert new.type == "sketch" and new.refs["plane"] == {"feature": "f3"}
    tab.session.undo.undo()
    assert len(doc.features) == count


def test_copy_a_cut_and_paste_it_on_a_face(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    tab = _open_bracket(qtbot, window, tmp_path)
    before = _volume(tab)
    assert window.tree is not None
    window.tree.select("f8")  # the base holes cut
    assert window.feature_clipboard.copy()
    tab.selection = [face_with_normal(tab, (-1.0, 0.0, 0.0))]  # the leg's outer face
    window.feature_clipboard.ask_keep = lambda n: False
    count = len(tab.session.document.features)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert window.feature_clipboard.paste()
    doc = tab.session.document
    assert len(doc.features) == count + 2
    sketch, cut = doc.features[-2:]
    assert cut.refs["sketch"] == {"feature": sketch.id}
    assert _volume(tab) < before - 50  # the holes cut the leg
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()  # one step takes both away
    assert len(doc.features) == count


def test_copy_refuses_features_without_a_sketch(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    _open_bracket(qtbot, window, tmp_path)
    assert window.tree is not None
    window.tree.select("f2")
    assert not window.feature_clipboard.copy()
    assert "Ctrl+C" in window.status.text()


def test_drop_with_ctrl_pastes_on_the_face_under_the_cursor(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    tab = _open_bracket(qtbot, window, tmp_path)
    if not hasattr(tab.viewport, "detected_at"):
        return  # no 3D view on this platform
    face = face_with_normal(tab, (-1.0, 0.0, 0.0))
    tab.viewport.detected_at = lambda pos: [face]  # type: ignore[method-assign]
    tab.viewport.part_point_at = lambda pos: None  # type: ignore[method-assign]
    window.feature_clipboard.ask_keep = lambda n: False
    count = len(tab.session.document.features)
    from PySide6.QtCore import QPointF

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert window.feature_clipboard.drop_at(QPointF(10, 10), "f8")
    assert len(tab.session.document.features) == count + 2


def test_paste_with_an_empty_clipboard_says_so(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    from PySide6.QtGui import QGuiApplication

    _open_bracket(qtbot, window, tmp_path)
    QGuiApplication.clipboard().clear()
    assert not window.feature_clipboard.paste()
    assert "Nothing to paste" in window.status.text()


def test_paste_with_no_part_open_says_so(window: MainWindow) -> None:
    """Audit D3 item 22 (D744): Paste with no part open did nothing without a word."""
    from fdcad.ui.main_window.feature_clipboard import PASTE_NO_PART

    while window.tabs.count():
        window.close_tab(0, ask=False)
    assert not window.feature_clipboard.paste()
    assert window.status.text() == PASTE_NO_PART


def test_paste_into_another_part_says_its_picks_were_cleared(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    """Audit D3 item 3 (D708): the pasted cut kept a face of the first part."""
    first = _open_bracket(qtbot, window, tmp_path)
    cut = first.session.document.feature("f8")
    cut.refs["end_face"] = {"kind": "face", "name": "f6/cap/end"}
    assert window.tree is not None
    window.tree.select("f8")
    assert window.feature_clipboard.copy()
    second = _open_bracket(qtbot, window, tmp_path)
    assert window.current is second
    window.tree.select("f2")  # Front Plane
    with qtbot.waitSignal(second.session.rebuilt, timeout=20000):
        assert window.feature_clipboard.paste()
    new = second.session.document.features[-1]
    assert "end_face" not in new.refs
    assert "another part" in window.status.text() and "pick them again" in window.status.text()
