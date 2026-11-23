"""Draw every icon at 16, 24 and 48 px for review, and audit the set (UI_POLISH_SPEC U5).

    uv run python tools/icon_sheet.py [--out docs/screenshots] [--audit]

Writes ``icons_light.png`` (Light theme) and ``icons_dark.png`` (Dark theme):
icons grouped by family, each at 16, 24 and 48 px, drawn the way the app draws
them (the 16 and 24 px images through the icon engine, so the pixel grid shows),
with the disabled look beside them. ``--audit`` also prints every rule an icon
breaks (``fdcad.ui.icons.audit``) and exits with 1 when any does.
Runs on Qt's offscreen platform.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    """Render the sheets, and audit when asked."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/screenshots", help="folder for the PNG files")
    parser.add_argument("--audit", action="store_true", help="check the icon rules too")
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if sys.platform == "win32":
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.expandvars(r"%WINDIR%\Fonts"))

    from PySide6.QtCore import QRectF, QSize, Qt
    from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.icons import _icon
    from fdcad.ui.icons.audit import audit_all, names
    from fdcad.ui.preferences.settings import Theme
    from fdcad.ui.themes.theme import SCHEMES

    app = QApplication(sys.argv)
    status = 0
    if args.audit:
        problems = audit_all()
        for name, found in problems.items():
            for problem in found:
                print(f"{name}: {problem}")
        print(f"audit: {len(names()) - len(problems)} of {len(names())} icons pass")
        status = 1 if problems else 0

    families: dict[str, list[str]] = {}
    for name in names():
        families.setdefault(name.split(".", 1)[0], []).append(name)
    sizes = (16, 24, 48)
    cell_w, cell_h, head_h, cols = 200, 76, 28, 6
    rows = sum(1 + (len(group) + cols - 1) // cols for group in families.values())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for theme, file_name in ((Theme.LIGHT, "icons_light.png"), (Theme.DARK, "icons_dark.png")):
        chrome = SCHEMES[theme][1]
        image = QImage(cols * cell_w, rows * cell_h, QImage.Format.Format_ARGB32)
        image.fill(QColor(chrome.surface))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        small, bold = QFont(app.font()), QFont(app.font())
        small.setPixelSize(10)
        bold.setPixelSize(13)
        bold.setBold(True)
        y = 0
        for family, group in families.items():
            painter.setFont(bold)
            painter.setPen(QColor(chrome.text))
            painter.drawText(
                QRectF(8, y, cols * cell_w, cell_h),
                Qt.AlignmentFlag.AlignBottom,
                f"{family} ({len(group)})",
            )
            y += cell_h
            for i, name in enumerate(group):
                col, row = i % cols, i // cols
                x0, y0 = col * cell_w, y + row * cell_h
                icon = _icon(name, theme)
                x = x0 + 8
                for size in sizes:
                    top = y0 + 4 + (48 - size)
                    painter.drawPixmap(x, top, icon.pixmap(QSize(size, size)))
                    x += size + 8
                painter.drawPixmap(x, y0 + 4 + 24, icon.pixmap(QSize(24, 24), QIcon.Mode.Disabled))
                painter.setFont(small)
                painter.setPen(QColor(chrome.muted))
                painter.drawText(
                    QRectF(x0 + 8, y0 + 4 + 48, cell_w - 12, cell_h - 52 - 4 + head_h),
                    Qt.AlignmentFlag.AlignTop,
                    name.split(".", 1)[1],
                )
            y += ((len(group) + cols - 1) // cols) * cell_h
        painter.end()
        path = out / file_name
        image.save(str(path))
        print(path, len(names()), "icons")
    del app
    return status


if __name__ == "__main__":
    raise SystemExit(main())
