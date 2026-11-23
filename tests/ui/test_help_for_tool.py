"""Help for This Tool (TR380 item 2, D1002)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.ui.help.paths import guide_dir
from fdcad.ui.help.topics import find_topic
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_help import _folders, settings, window

__all__ = ["_folders", "settings", "window"]


def test_headings_win_over_bold_mentions(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A\n\nUse **Shell** after fillets.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n\n## Shell\n\nHollows the part.\n", encoding="utf-8")
    assert find_topic(tmp_path, ["Shell"]) == (tmp_path / "b.md", "Shell")
    assert find_topic(tmp_path, ["Nothing Like It", "fillets"]) is None
    assert find_topic(tmp_path, ["Nothing Like It", "Shell"]) == (tmp_path / "b.md", "Shell")


def test_the_real_guide_has_the_common_tools() -> None:
    for label in ("Shell", "Scale", "Fillet"):
        assert find_topic(guide_dir(), [label]) is not None, label


def test_help_for_the_last_command(qtbot: QtBot, window: MainWindow) -> None:
    window.commands.last = "feature.scale"
    assert "Scale" in window.help.tool_labels()
    guide = window.help.help_for_tool()
    page = guide.page()
    assert guide.isVisible() and page is not None and page.name.endswith(".md")
    assert window.commands.trigger("help.tool")
    guide.close()
