"""Render the app icon at every size the installers need (D557).

Reads ``src/fdcad/ui/app_icon.svg`` (and ``app_icon_small.svg``, the bolder
drawing used at 32 px and below, D672) and writes, under ``packaging/icons``:
PNGs at 16 to 1024 px, ``fdcad.ico`` for Windows (16 to 256 px) and
``fdcad.icns`` for macOS (16 to 1024 px, with the Retina sizes). Run it after
changing the SVG and commit the results:

    QT_QPA_PLATFORM=offscreen uv run python tools/make_app_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "src" / "fdcad" / "ui" / "app_icon.svg"
SMALL_SVG = ROOT / "src" / "fdcad" / "ui" / "app_icon_small.svg"
#: Sizes drawn from the small drawing, so the block reads on a taskbar.
SMALL_SIZES = (16, 24, 32)
OUT = ROOT / "packaging" / "icons"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
#: ICNS entry types and the PNG size each holds (Apple's icon family types).
ICNS_TYPES = (
    (b"icp4", 16),
    (b"icp5", 32),
    (b"icp6", 64),
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic09", 512),
    (b"ic10", 1024),
    (b"ic11", 32),
    (b"ic12", 64),
    (b"ic13", 256),
    (b"ic14", 512),
)


def render(renderer: QSvgRenderer, size: int) -> bytes:
    """The icon as PNG bytes at ``size`` by ``size`` pixels."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data.data())


def ico(pngs: dict[int, bytes]) -> bytes:
    """A Windows .ico file holding PNG images."""
    sizes = [s for s in ICO_SIZES if s in pngs]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, blobs = b"", b""
    for size in sizes:
        blob = pngs[size]
        side = 0 if size >= 256 else size  # 0 means 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(blob), offset)
        blobs += blob
        offset += len(blob)
    return header + entries + blobs


def icns(pngs: dict[int, bytes]) -> bytes:
    """A macOS .icns file holding PNG images."""
    body = b""
    for kind, size in ICNS_TYPES:
        blob = pngs[size]
        body += kind + struct.pack(">I", 8 + len(blob)) + blob
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def main() -> int:
    """Write every icon file."""
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(SVG))
    small = QSvgRenderer(str(SMALL_SVG))
    for path, check in ((SVG, renderer), (SMALL_SVG, small)):
        if not check.isValid():
            print(f"cannot read {path}", file=sys.stderr)
            return 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "png").mkdir(exist_ok=True)
    pngs = {size: render(small if size in SMALL_SIZES else renderer, size) for size in SIZES}
    for size, blob in pngs.items():
        (OUT / "png" / f"fdcad_{size}.png").write_bytes(blob)
    (OUT / "fdcad.ico").write_bytes(ico(pngs))
    (OUT / "fdcad.icns").write_bytes(icns(pngs))
    print(f"wrote {len(pngs)} PNGs, fdcad.ico and fdcad.icns to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
