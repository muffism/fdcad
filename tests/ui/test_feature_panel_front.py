"""A feature that opens while a side panel is shown gets its own panel in front (D1040)."""

from __future__ import annotations

import pytest

from fdcad.samples.make import SAMPLE_DIR
from fdcad.ui.main_window.window import MainWindow
from tests.ui.sweep_support import idle, open_part, pump, settle, text_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]

PLATE = SAMPLE_DIR / "plate_with_holes.fdprt"


def _in_front(window: MainWindow) -> None:
    assert window.editing == "feature"
    assert window.properties is not None and window.panel is not None
    assert window.properties.currentWidget() is window.panel
    assert window.properties.count() == 1  # no side panel is left under it
    assert window.left.currentIndex() == 1
    assert window.panel.isVisible()


@pytest.mark.parametrize("opener", ["edit.appearance", "view.section", "feature.ref_plane"])
def test_feature_panel_comes_in_front_of_a_side_panel(window: MainWindow, opener: str) -> None:
    tab = open_part(window, PLATE)
    before = text_of(tab)  # the id counter may grow on Cancel (D490)
    window.commands.trigger(opener)
    pump(20)
    assert window.properties is not None
    assert window.properties.currentWidget() is not window.panel  # the side panel shows
    window.commands.trigger("feature.shell")
    pump(20)
    assert idle(tab)
    _in_front(window)
    # Each side tool has ended: Appearance closed, Section View as with its OK (the
    # section stays on), an unfinished reference plane as with its Cancel.
    assert window.appearance_tool.panel is None
    assert window.section_tool.panel is None
    assert window.reference_tool.panel is None
    if opener == "view.section":
        assert window.section_tool.state_of(tab) is not None
    settle(window, tab)
    assert text_of(tab) == before  # nothing was added to the part


def test_closing_a_side_panel_keeps_an_open_feature_in_front(window: MainWindow) -> None:
    tab = open_part(window, PLATE)
    window.commands.trigger("feature.shell")
    pump(20)
    assert idle(tab)
    _in_front(window)
    window.commands.trigger("view.section")  # look inside while the feature is open
    pump(20)
    assert window.section_tool.panel is not None
    window.section_tool.accept()
    pump(20)
    _in_front(window)  # not the tree tab: the feature is still open
    settle(window, tab)
    assert window.left.currentIndex() == 0  # with nothing open, back to the tree


def test_a_cancelled_features_note_does_not_show_in_the_next_panel(window: MainWindow) -> None:
    """D1042: the pre check box of each closed feature stayed in the panel, so its note
    ("Corner Relief 1: no edges are picked...") was listed in every panel opened after."""
    from PySide6.QtWidgets import QLabel, QWidget

    tab = open_part(window, PLATE)
    panel = window.panel
    assert panel is not None
    for command in ("feature.corner_relief", "feature.lip_groove", "feature.shell"):
        window.commands.trigger(command)
        pump(20)
        assert idle(tab)
        assert panel.form is not None
        boxes = [
            b for b in panel.groups_box.findChildren(QWidget, "check_box") if b.isVisibleTo(panel)
        ]
        assert boxes in ([], [panel.form.check])  # never another feature's box
        notes = [
            label.text()
            for label in panel.groups_box.findChildren(QLabel, "panel_message")
            if label.isVisibleTo(panel)
        ]
        assert not any("note of " in text for text in notes), notes
        panel.form.check.show_result(f"note of {command}", [])
        assert panel.form.check.isVisibleTo(panel)
        panel.reject()
        pump(20)
    settle(window, tab)
    assert len(panel.groups_box.findChildren(QWidget, "check_box")) == 0  # all were deleted
