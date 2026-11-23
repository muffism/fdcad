"""Save as Library Feature and Insert Library Feature (TR72 item 1, D2115)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_design_table_ui import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_save_then_insert_on_a_plane(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    doc = tab.session.document
    ext = doc.features[-1]
    clip = window.feature_clipboard
    assert clip.save_library(ext.id, str(tmp_path / "plate.fdlib"))
    count = len(doc.features)
    window.tree.select("f3")  # the Top plane
    assert clip.insert_library(str(tmp_path / "plate.fdlib"))
    assert len(tab.session.document.features) == count + 2
    assert not clip.insert_library(str(tmp_path / "missing.fdlib"))
    assert "could not be read" in window.status.text()
