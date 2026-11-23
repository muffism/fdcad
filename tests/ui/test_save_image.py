"""File, Save Image (TR24, D689)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtGui import QColor, QImage
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.save_image import ImageOptions, SaveImageDialog, save_view_image
from fdcad.ui.viewport.image_export import checked_size, qimage_rgb, rgba_image, without_background


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["file.save_image"].label == "Save Image"
    assert audit("file.save_image") == []


def test_background_comes_out_from_black_and_white_shots() -> None:
    black = np.zeros((2, 3, 3), dtype=np.uint8)
    white = np.full((2, 3, 3), 255, dtype=np.uint8)
    # Pixel (0, 0) is a solid red part; (0, 1) a half covered grey edge.
    black[0, 0] = white[0, 0] = (200, 10, 10)
    black[0, 1], white[0, 1] = (50, 50, 50), (178, 178, 178)
    out = without_background(black, white)
    assert tuple(out[0, 0]) == (200, 10, 10, 255)
    assert out[0, 1, 3] == 127 and abs(int(out[0, 1, 0]) - 100) <= 1
    assert out[1, 2, 3] == 0


def test_qimage_round_trip() -> None:
    image = QImage(5, 4, QImage.Format.Format_RGB32)
    image.fill(QColor(10, 20, 30))
    rgb = qimage_rgb(image)
    assert rgb.shape == (4, 5, 3) and tuple(rgb[3, 4]) == (10, 20, 30)
    rgba = np.zeros((4, 5, 4), dtype=np.uint8)
    rgba[..., 3] = 255
    back = rgba_image(rgba)
    assert back.width() == 5 and back.pixelColor(0, 0).alpha() == 255


def test_sizes_are_checked() -> None:
    assert checked_size(0, 10) and checked_size(10, 9000)
    assert checked_size(800, 600) == ""


def test_dialog_gives_view_or_chosen_size(qtbot: QtBot) -> None:
    dialog = SaveImageDialog((640, 480))
    qtbot.addWidget(dialog)
    assert dialog.options() == ImageOptions(640, 480, True)
    dialog.chosen.setChecked(True)
    dialog.width_box.setValue(1920)
    dialog.height_box.setValue(1080)
    dialog.background.setChecked(False)
    assert dialog.options() == ImageOptions(1920, 1080, False)


class _View:
    def render_image(self, width: int, height: int, background: bool = True) -> QImage:
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 255 if background else 0))
        return image


def test_saving_writes_the_png(tmp_path: Path) -> None:
    path = tmp_path / "view.png"
    assert save_view_image(_View(), str(path), ImageOptions(32, 16, False)) == ""
    image = QImage(str(path))
    assert (image.width(), image.height()) == (32, 16) and image.hasAlphaChannel()
    assert save_view_image(object(), str(path), ImageOptions(32, 16)) != ""
    assert save_view_image(_View(), str(path), ImageOptions(0, 16)) != ""
