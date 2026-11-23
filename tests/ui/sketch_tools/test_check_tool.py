"""Check Sketch for Feature and Use Only Fully Defined Sketches (TR36, D763)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.features.base import FeatureState
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from fdcad.ui.sketch_tools.check_tool import CheckSketchTool
from fdcad.ui.sketch_tools.registry import EXTRA_TOOL_NAMES
from tests.core.rebuild.test_full_sketches_only import _plate
from tests.ui.sketch_tools.p2_helpers import edit_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _open_square(edit) -> None:  # type: ignore[no-untyped-def]
    from tests.core.sketch.test_feature_check import SQUARE, _poly

    _poly(edit.sketch, [*SQUARE, (0.0, 2.0)], closed=False)


def test_command_icon_and_registry() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["sketch.check_sketch"].label == "Check Sketch"
    assert BY_ID["sketch.check_sketch"].keys == ()
    assert audit("sketch.check_sketch") == []
    assert "check_sketch" in EXTRA_TOOL_NAMES


def test_check_lists_problems_and_zooms_to_each() -> None:
    edit = edit_of()
    _open_square(edit)
    tool = CheckSketchTool(edit)
    assert "press Check" in tool.prompt
    tool.option_changed("check")
    assert tool.problems and "2 problems for Boss" in tool.prompt
    tool.option_changed("next")
    focus = tool.take_focus()
    assert focus is not None and focus[0] is not None and focus[1]
    assert "Problem 1 of 2" in tool.take_message()
    tool.option_changed("next")
    assert "Problem 2 of 2" in tool.take_message()
    tool.kind = "rib"
    tool.option_changed("kind")
    tool.option_changed("check")
    assert tool.prompt == "No problems found for Rib."
    assert edit.sketch.dimensions == []  # nothing in the sketch changed


def test_next_before_check_says_so() -> None:
    tool = CheckSketchTool(edit_of())
    tool.option_changed("next")
    assert "Press Check first" in tool.take_message()


def test_preference_is_off_by_default_and_refuses_when_on(
    qtbot: QtBot,
    window: MainWindow,
    tmp_path: Path,
) -> None:
    assert not Settings(
        QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    ).full_sketches_only
    session = DocumentSession(_plate(), None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    ext = next(f for f in session.document.features if f.type == "extrude")
    assert session.report is not None
    assert session.report.results[ext.id].state is not FeatureState.ERROR
    window.settings.full_sketches_only = True
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window._full_sketches_changed()
    assert session.report.results[ext.id].state is FeatureState.ERROR
    window.settings.full_sketches_only = False
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window._full_sketches_changed()
    assert session.report.results[ext.id].state is not FeatureState.ERROR


def test_preferences_dialog_has_the_box(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.preferences.dialog import PreferencesDialog

    dialog = PreferencesDialog(window.settings, window)
    qtbot.addWidget(dialog)
    assert not dialog.full_sketches_box.isChecked()
    dialog.full_sketches_box.setChecked(True)
    dialog.accept()
    assert window.settings.full_sketches_only
