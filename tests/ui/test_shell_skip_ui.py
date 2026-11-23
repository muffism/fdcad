"""Skip one face fix and Reset Skipped Faces (TR278, D1406)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.base import Fix
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.phase3_parts import add_feature, block_with_hole_and_boss
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_skip_fix_then_reset(qtbot: QtBot, window: MainWindow) -> None:
    doc, ids = block_with_hole_and_boss()
    fid = add_feature(doc, "shell", {"thickness": Param("1", 1.0)}, {})
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.add_session(session)
    ref = {"kind": "face", "name": f"{ids['boss']}/cap/end"}
    fix = Fix("Skip face", "add_refs", {"feature": fid, "key": "skipped_faces", "refs": [ref]})
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.apply_fix(fid, fix)
    assert session.document.feature(fid).refs["skipped_faces"] == [ref]
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.tree.reset_skipped(fid)
    assert "skipped_faces" not in session.document.feature(fid).refs


def test_both_sides_tick(qtbot: QtBot, window: MainWindow) -> None:
    """TR322 (D1411): Both sides is written and turns Shell outward off."""
    from tests.ui.test_body_tools import _open

    _open(qtbot, window)
    window.commands.actions["feature.shell"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "both")
    form.outward.setChecked(True)
    form.both.setChecked(True)
    assert not form.outward.isEnabled()
    made = window.panel.current_feature()
    assert made is not None and made.params["both_sides"] is True
    assert "outward" not in made.params
    window.panel.reject()


def test_draft_detailed_preview_flag_is_on_the_preview_copy_only(
    qtbot: QtBot, window: MainWindow
) -> None:
    """TR164 (D1417)."""
    from tests.ui.test_body_tools import _open

    _open(qtbot, window)
    window.commands.actions["feature.draft"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "detailed")
    form.detailed.setChecked(True)
    try:
        feature = window.panel.feature
        assert feature is not None
        assert form.for_preview(feature).data.get("preview_detailed") is True
        assert "preview_detailed" not in feature.data
    finally:
        form.detailed.setChecked(False)
    window.panel.reject()


def test_draft_angle_mode_and_split_are_written(qtbot: QtBot, window: MainWindow) -> None:
    """TR323 (D1419)."""
    from tests.ui.test_body_tools import _open

    _open(qtbot, window)
    window.commands.actions["feature.draft"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "split")
    form.faces.add({"kind": "face", "name": "f9/side/e5"})
    form.neutral.setCurrentIndex(max(form.neutral.findData({"feature": "f2"}), 1))
    form.angle_mode.setCurrentIndex(form.angle_mode.findData("relative"))
    form.split.setChecked(True)
    form.angle_below.edit.setText("7")
    made = window.panel.current_feature()
    assert made is not None, window.panel.message.text()
    assert made.params["angle_mode"] == "relative" and made.params["neutral_split"] is True
    assert abs(made.params["angle2"].value - 0.122173) < 1e-5
    window.panel.reject()
