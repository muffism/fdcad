"""Save as Template and New Part from a template (TR217, D833)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Variable
from fdcad.core.units import Kind
from fdcad.ui.main_window import templates as tpl
from fdcad.ui.main_window.new_part_dialog import NewPartDialog
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_save_then_start_a_part_from_it(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tpl, "folder", lambda: tmp_path)
    tab, _ids = _open(qtbot, window)
    tab.session.document.variables.append(Variable("Wall", Kind.LENGTH, "2", 2.0))
    path = tpl.save_as_template(window, "Box")
    assert path is not None and path.exists()
    assert tpl.templates() == [("Box", path)]
    dialog = NewPartDialog(parent=window, templates=tpl.templates())
    qtbot.addWidget(dialog)
    dialog.template_box.setCurrentIndex(1)
    assert dialog.template() == path and not dialog.mm_button.isEnabled()
    before = window.tabs.count()
    assert tpl.new_from_template(window, path)
    assert window.tabs.count() == before + 1
    made = window.current
    assert made is not None and [v.name for v in made.session.document.variables][-1] == "Wall"
    assert made.session.path is None
    assert tpl.save_as_template(window, " / ") is None  # a name with nothing usable
