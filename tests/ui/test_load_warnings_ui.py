"""Opening a part shows what the reader left out or changed (audit D3 item 21, D2678)."""

from __future__ import annotations

import json
from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_a_damaged_configuration_entry_shows_a_warning_bar(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    data = fdef.to_json_data(new_document())
    data["schema"] = 2
    data["configurations"] = {
        "active": "Default",
        "items": [{"name": "Default", "overrides": {}}, {"overrides": {}}],
        "design_table": None,
    }
    path = tmp_path / "Damaged.fdprt"
    path.write_text(json.dumps(data), encoding="utf-8")
    window.open_path(path)
    tab = window.current
    assert isinstance(tab, DocumentTab)
    bar = tab.message_bars.bars["load_warnings"]
    text = bar.label.text()
    assert "Damaged opened" in text and "entry 2 of 2 has no name" in text
    assert not tab.message_bars.isHidden()
    assert tab.session.document.load_warnings == []  # shown once
    tab.session.wait()


def test_a_sound_part_shows_no_warning_bar(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    path = tmp_path / "Sound.fdprt"
    fdef.save(new_document(), path)
    window.open_path(path)
    tab = window.current
    assert isinstance(tab, DocumentTab)
    assert "load_warnings" not in tab.message_bars.bars
    tab.session.wait()
