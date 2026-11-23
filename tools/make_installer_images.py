"""Render the Windows installer's wizard pictures from the app icon (D588).

Writes BMP files under ``packaging/windows/images``: the tall picture on the
welcome and finish pages (``wizard_*.bmp``) and the small picture at the top
right of the other pages (``small_*.bmp``), each at the sizes Inno Setup picks
from for the screen scale. Run it after changing the app icon and commit the
results:

    uv run python tools/make_installer_images.py

Run it with a normal Qt platform (not offscreen), which has no fonts for the name.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "src" / "fdcad" / "ui" / "app_icon.svg"
SMALL_ICON = ROOT / "src" / "fdcad" / "ui" / "app_icon_small.svg"
OUT = ROOT / "packaging" / "windows" / "images"
#: Inno Setup's wizard picture sizes, 100% to 250% scale.
WIZARD_SIZES = ((164, 314), (192, 386), (246, 459), (273, 556), (328, 604), (355, 700), (410, 797))
SMALL_SIZES = (55, 64, 69, 83, 92, 110, 138)
TOP, BOTTOM = QColor("#24388F"), QColor("#0A1030")
TEXT = QColor("#FFFFFF")


def wizard(width: int, height: int, renderer: QSvgRenderer) -> QImage:
    """The tall picture: the icon on the app's midnight blue, with the name under it."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    fill = QLinearGradient(QPointF(0, 0), QPointF(0, height))
    fill.setColorAt(0, TOP)
    fill.setColorAt(1, BOTTOM)
    painter.fillRect(image.rect(), fill)
    side = width * 0.78
    top = height * 0.30 - side / 2
    renderer.render(painter, QRectF((width - side) / 2, top, side, side))
    font = QFont("Segoe UI", 1, QFont.Weight.DemiBold)
    font.setPixelSize(round(width * 0.16))
    painter.setFont(font)
    painter.setPen(TEXT)
    words = QRectF(0, top + side + height * 0.02, width, width * 0.25)
    painter.drawText(words, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "FDCAD")
    painter.end()
    return image


def small(size: int, renderer: QSvgRenderer) -> QImage:
    """The small picture: the icon on white, the page header's colour."""
    image = QImage(size, size, QImage.Format.Format_RGB32)
    image.fill(QColor("#FFFFFF"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def boot_picture() -> QImage:
    """The start picture as a plain image, for the single file build to show while it
    unpacks (``packaging/splash.png``, D1034). No clear corners: the boot loader's
    window cannot show them, so the tile is drawn square."""
    from PySide6.QtGui import QIcon, QPixmap

    from fdcad.ui.splash import HEIGHT, WIDTH, splash_pixmap

    mark = QImage(256, 256, QImage.Format.Format_ARGB32)
    mark.fill(Qt.GlobalColor.transparent)
    painter = QPainter(mark)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(str(ICON)).render(painter, QRectF(0, 0, 256, 256))
    painter.end()
    rounded = splash_pixmap(QIcon(QPixmap.fromImage(mark)), 1.0).toImage()
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    fill = QLinearGradient(QPointF(0, 0), QPointF(WIDTH, HEIGHT))
    fill.setColorAt(0, TOP)
    fill.setColorAt(1, BOTTOM)
    painter.fillRect(image.rect(), fill)
    painter.drawImage(0, 0, rounded)
    painter.end()
    return image


def main() -> None:
    """Write every picture."""
    app = QGuiApplication.instance() or QGuiApplication([])
    OUT.mkdir(parents=True, exist_ok=True)
    big, little = QSvgRenderer(str(ICON)), QSvgRenderer(str(SMALL_ICON))
    for width, height in WIZARD_SIZES:
        wizard(width, height, big).save(str(OUT / f"wizard_{width}x{height}.bmp"), "BMP")
    for size in SMALL_SIZES:
        small(size, little if size < 64 else big).save(str(OUT / f"small_{size}.bmp"), "BMP")
    print(f"wrote {len(WIZARD_SIZES) + len(SMALL_SIZES)} pictures to {OUT}")
    boot = ROOT / "packaging" / "splash.png"
    boot_picture().save(str(boot), "PNG")
    print(f"wrote {boot}")
    del app


if __name__ == "__main__":
    main()
