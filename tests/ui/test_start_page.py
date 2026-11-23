"""The start page with recent parts, pins and pictures (TR218 item 2, D2504)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.core.io.thumbnail import set_thumbnail
from fdcad.ui.main_window import start_page
from fdcad.ui.main_window.start_page import PINNED_MARK, entries
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def _png() -> bytes:
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage

    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor("#3366cc"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data().data())


def test_entries_put_pins_first() -> None:
    assert entries(["a", "b", "c"], ["c", "z"]) == [
        ("c", True),
        ("z", True),
        ("a", False),
        ("b", False),
    ]


def test_shown_with_no_part_and_lists_pictures(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = window.start_page
    assert window.tabs.count() == 0 and page.isVisible()
    doc = new_document()
    set_thumbnail(doc, _png())
    first, second = tmp_path / "first.fdprt", tmp_path / "second.fdprt"
    fdef.save(doc, first)
    fdef.save(new_document(), second)
    window.settings.add_recent(str(second))
    window.settings.add_recent(str(first))
    page.refresh()
    names = [page.list.item(i).text() for i in range(page.list.count())]
    assert names == ["first", "second"]
    assert not page.list.item(0).icon().isNull()
    page.pin(str(second), True)
    assert page.list.item(0).text() == PINNED_MARK + "second"
    menu = page.menu_for(page.list.item(0))
    assert [a.text() for a in menu.actions()] == [
        "Open",
        "Unpin",
        "Remove from List",
        "Show in Folder",
    ]
    shown: list[Path] = []
    monkeypatch.setattr(start_page, "open_folder", lambda p: shown.append(p) or True)
    page.menu_for(page.list.item(0)).actions()[3].trigger()
    assert shown == [second]
    page.remove(str(second))
    assert page.list.count() == 1 and str(second) not in window.settings.recent_files
    page.open(str(tmp_path / "gone.fdprt"))
    assert "no longer on disk" in window.status.text()
    with qtbot.waitSignal(window.tabs.currentChanged, timeout=20000):
        page.list.itemActivated.emit(page.list.item(0))
    assert window.tabs.count() == 1 and not page.isVisible()
    tab = window.tabs.widget(0)
    assert isinstance(tab, DocumentTab)
    tab.session.wait()


def test_save_keeps_a_picture(window: MainWindow, tmp_path: Path) -> None:
    from fdcad.core.io.thumbnail import read_thumbnail
    from fdcad.ui.main_window.start_page import cache_folder, keep_thumbnail, saved

    class _View:
        def render_image(self, w: int, h: int):  # type: ignore[no-untyped-def]
            from PySide6.QtGui import QColor, QImage

            image = QImage(w, h, QImage.Format.Format_RGB32)
            image.fill(QColor("#cc6633"))
            return image

    class _Session:
        document = new_document()

    class _Tab:
        viewport = _View()
        session = _Session()

    path = tmp_path / "c.fdprt"
    png = keep_thumbnail(_Tab(), path)  # type: ignore[arg-type]
    assert png is not None and png.startswith(PNG_HEADER)
    assert "thumbnail" in _Session.document.extra
    saved(path, png)
    assert read_thumbnail(cache_folder(), path) == png


def test_the_list_leaves_file_drops_to_the_window(window: MainWindow) -> None:
    page = window.start_page
    assert not page.list.acceptDrops() and not page.list.viewport().acceptDrops()


def test_parts_with_the_same_name_show_their_folder(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    page = window.start_page
    for folder in ("jigs", "spares"):
        (tmp_path / folder).mkdir()
        fdef.save(new_document(), tmp_path / folder / "bracket.fdprt")
        window.settings.add_recent(str(tmp_path / folder / "bracket.fdprt"))
    fdef.save(new_document(), tmp_path / "plate.fdprt")
    window.settings.add_recent(str(tmp_path / "plate.fdprt"))
    page.refresh()
    names = [page.list.item(i).text() for i in range(page.list.count())]
    assert names == ["plate", "bracket (spares)", "bracket (jigs)"]
