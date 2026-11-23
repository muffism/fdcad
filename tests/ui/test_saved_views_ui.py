"""Dimetric and Trimetric, Save View and saved views in the window (TR14, D690)."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.saved_views import ManageDialog
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.viewport.views import STANDARD_VIEWS, CameraPose
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


class _Camera:
    """Stands in for the 3D view's camera on the offscreen test platform."""

    def __init__(self) -> None:
        self.pose = CameraPose((0, 0, 0), (0, 0, -1), (0, 1, 0), 100.0, 50.0)

    def camera_pose(self) -> CameraPose:
        return self.pose

    def restore_pose(self, pose: CameraPose) -> None:
        self.pose = pose


def test_new_standard_views() -> None:
    for name in ("dimetric", "trimetric"):
        assert name in STANDARD_VIEWS
        assert BY_ID[f"view.{name}"].keys == ()
    eye = STANDARD_VIEWS["dimetric"][0]
    assert eye[0] == eye[2] != eye[1]
    assert len(set(STANDARD_VIEWS["trimetric"][0])) == 3


def test_save_go_update_rename_delete(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    camera = _Camera()
    tab.viewport = camera  # type: ignore[assignment]
    views = window.saved_views
    views.ask_name = lambda title, prompt, text: ("Side", True)
    assert window.commands.trigger("view.save_view")
    doc = tab.session.document
    assert [v["name"] for v in doc.views] == ["Side"]
    assert not tab.session.undo.isClean()
    saved = camera.pose
    camera.pose = CameraPose((5, 5, 5), (1, 0, 0), (0, 1, 0), 10.0, 20.0)
    assert views.go("Side") and camera.pose == saved
    camera.pose = CameraPose((5, 5, 5), (1, 0, 0), (0, 1, 0), 10.0, 20.0)
    assert views.update("Side")
    assert doc.views[0]["scale"] == 20.0
    assert not views.save("side")  # names are unique, whatever the case
    assert views.rename("Side", "Right Corner")
    assert views.delete("Right Corner") and doc.views == []
    tab.session.undo.undo()
    assert [v["name"] for v in doc.views] == ["Right Corner"]


def test_saved_views_are_listed_in_menus(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    tab.viewport = _Camera()  # type: ignore[assignment]
    assert window.saved_views.save("Side")
    menu = QMenu()
    window.saved_views.fill(menu)
    names = [a.text() for a in menu.actions()]
    assert "Side" in names and names[-1].startswith("Manage")
    parent = QMenu()
    orient = window.context_menus._orientations(parent)
    assert "Side" in [a.text() for a in orient.actions()]
    dialog = ManageDialog(window.saved_views)
    qtbot.addWidget(dialog)
    assert dialog.list.count() == 1 and dialog.buttons["Delete"].isEnabled()
    dialog.buttons["Delete"].click()
    assert dialog.list.count() == 0 and not dialog.buttons["Delete"].isEnabled()
