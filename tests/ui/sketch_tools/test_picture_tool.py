"""Sketch Picture tool, panel, drawing and saving (PHASE2_SPEC P2.9)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QImage
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.core.sketch.model import sketch_from_data
from fdcad.core.sketch.picture import block_bytes
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from fdcad.ui.sketch_tools.picture_tool import PictureTool
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of, free, ui_drag


def _png(tmp_path: Path, w: int = 40, h: int = 20) -> Path:
    image = QImage(w, h, QImage.Format.Format_ARGB32)
    image.fill(QColor("#3070c0"))
    path = tmp_path / "plan.png"
    assert image.save(str(path))
    return path


def _tool_with_picture(tmp_path: Path) -> PictureTool:
    edit = edit_of()
    tool = make_tool("picture", edit)
    assert isinstance(tool, PictureTool)
    data = _png(tmp_path).read_bytes()
    assert tool.insert(data, "plan.png", "png", 40, 20)
    return tool


def test_command() -> None:
    assert BY_ID["sketch.picture"].label == "Sketch Picture"


def test_insert_is_one_undo_step(qapp: object, tmp_path: Path) -> None:
    tool = _tool_with_picture(tmp_path)
    edit = tool.edit
    (pic,) = edit.sketch.pictures
    assert (pic.width, pic.height) == (40, 20) and pic.origin == (0, 0)
    assert block_bytes(edit.blocks[pic.block]).startswith(b"\x89PNG")
    edit.undo()
    assert not edit.sketch.pictures


def test_drag_moves_and_corner_resizes_with_locked_aspect(qapp: object, tmp_path: Path) -> None:
    tool = _tool_with_picture(tmp_path)
    tool.tolerance = 0.5
    pic = tool.picture
    assert pic is not None
    tool.click(free(10, 10))
    tool.hover(free(15, 12))
    assert tool.release(free(15, 12), True)
    assert pic.origin == pytest.approx((5, 2))
    # Upper right corner from (45, 22) out to (85, 22): width doubles, height follows.
    tool.click(free(45, 22))
    tool.hover(free(85, 22))
    assert tool.release(free(85, 22), True)
    assert (pic.width, pic.height) == pytest.approx((80, 40))
    assert pic.origin == pytest.approx((5, 2))


def test_panel_values(qapp: object, tmp_path: Path) -> None:
    tool = _tool_with_picture(tmp_path)
    pic = tool.picture
    assert pic is not None
    tool.width = 80.0
    assert tool.option_changed("width")
    assert pic.height == pytest.approx(40)
    tool.lock_aspect = False
    tool.height = 10.0
    assert (pic.width, pic.height) == (80, 10)
    tool.transparency = 60
    assert pic.transparency == pytest.approx(0.6)
    tool.flip_h = True
    tool.x = 3.0
    assert pic.flip_h and pic.origin[0] == 3.0


def test_scale_tool_sets_a_true_length(qapp: object, tmp_path: Path) -> None:
    tool = _tool_with_picture(tmp_path)
    tool.scale_tool = True
    tool.option_changed("scale_tool")
    assert len(tool.handles) == 2
    tool.tolerance = 0.5
    # Drag the handles onto two known points of the image, 30 mm apart in pixels.
    for i, target in enumerate([(5.0, 10.0), (35.0, 10.0)]):
        h = tool.handles[i]
        tool.click(free(*h))
        tool.hover(free(*target))
        tool.release(free(*target), True)
    assert tool.scale_length == pytest.approx(30)
    tool.scale_length = 60.0  # the true length is twice the drawn one
    pic = tool.picture
    assert pic is not None
    assert (pic.width, pic.height) == pytest.approx((80, 40))
    assert pic.origin == pytest.approx((-5, -10))
    assert tool.scale_length == pytest.approx(60)


def test_delete_picture(qapp: object, tmp_path: Path) -> None:
    tool = _tool_with_picture(tmp_path)
    assert tool.option_changed("delete")
    assert not tool.edit.sketch.pictures and tool.picture is None


def test_panel_inserts_a_file_and_canvas_draws_it(qtbot: QtBot, tmp_path: Path) -> None:
    canvas, panel = canvas_of(qtbot)
    canvas.set_tool("picture")
    assert "insert" in panel.pick_panel.fields
    assert panel.pick_panel.insert_image(str(_png(tmp_path)))
    assert canvas.edit.sketch.pictures
    image = canvas.grab().toImage()
    p = canvas.to_screen((20, 10))
    color = image.pixelColor(round(p.x()), round(p.y()))
    assert color.blue() > color.red()  # the picture shows under the grid
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    messages: list[str] = []
    canvas.status_message.connect(messages.append)
    assert not panel.pick_panel.insert_image(str(bad))
    assert "not a PNG" in messages[-1]
    # Dragging in the canvas moves the picture.
    ui_drag(qtbot, canvas, [(10, 10), (14, 10), (20, 10)])
    assert canvas.edit.sketch.pictures[0].origin == pytest.approx((10, 0), abs=0.5)


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1200, 800)
    win.show()
    win.finish_setup()
    yield win
    if win.sketch_mode is not None and win.sketch_mode.is_open:
        win.sketch_mode._close()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def test_ok_embeds_the_image_and_undo_removes_it(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    session = DocumentSession(new_document(), None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    mode = window.sketch_mode
    assert mode is not None
    front = next(f for f in tab.session.document.features if f.name == "Front Plane")
    mode.start(plane_id=front.id)
    assert mode.canvas is not None and mode.panel is not None
    mode.canvas.set_tool("picture")
    assert mode.panel.pick_panel.insert_image(str(_png(tmp_path)))
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert mode.accept()
    doc = tab.session.document
    images = [k for k, v in doc.embedded.items() if v.get("type") == "image"]
    assert len(images) == 1
    sketch = doc.features[-1]
    assert sketch_from_data(sketch.data).pictures[0].block == images[0]
    # Saved and opened again, the picture and its image are there.
    path = tmp_path / "part.fdef"
    fdef.save(doc, path)
    again = fdef.load(path)
    assert block_bytes(again.embedded[images[0]]).startswith(b"\x89PNG")
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert not any(v.get("type") == "image" for v in doc.embedded.values())
