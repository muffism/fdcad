"""Coating Allowance kept in the part and taken off STL exports (TR307, D1214)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.io.mesh_import import read_stl
from fdcad.ui import strings_print
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools.coating_tool import set_coating
from tests.core.features.test_mesh_split import mesh_volume
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_coating_shrinks_the_exported_mesh(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    plain = tmp_path / "plain.stl"
    window.export("stl", plain)
    qtbot.waitUntil(lambda: plain.exists() and not window.feedback.running("export"), timeout=30000)
    set_coating(window, 0.3)
    assert tab.session.document.print_setup["coating"] == pytest.approx(0.3)
    assert tab.session.undo.undoText() == strings_print.COATING_UNDO
    coated = tmp_path / "coated.stl"
    window.export("stl", coated)
    qtbot.waitUntil(
        lambda: coated.exists() and not window.feedback.running("export"), timeout=30000
    )
    before = mesh_volume(read_stl(plain.read_bytes()))
    after = mesh_volume(read_stl(coated.read_bytes()))
    assert after < before * 0.99
    set_coating(window, 0.0)
    assert "coating" not in tab.session.document.print_setup
