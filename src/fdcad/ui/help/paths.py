"""Where the user guide and the license texts are, in the source tree and in a build (D551).

A PyInstaller build puts its data files under ``sys._MEIPASS``: the guide at
``docs/user_guide``, the license texts at ``LICENSE``, ``THIRD_PARTY_NOTICES.txt``,
``SOURCE_OFFER.md`` and ``licenses/`` (see ``packaging/fdcad.spec``). From the source tree the same
files are found from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon

#: The repository root when running from the source tree (src/fdcad/ui/help/paths.py).
_SOURCE_ROOT = Path(__file__).resolve().parents[4]


def frozen_root() -> Path | None:
    """The data folder of a PyInstaller build, or None when running from source."""
    root = getattr(sys, "_MEIPASS", None)
    return Path(root) if isinstance(root, str) else None


def guide_dir(root: Path | None = None) -> Path:
    """The folder that holds the user guide's ``README.md``."""
    base = root or frozen_root() or _SOURCE_ROOT
    return base / "docs" / "user_guide"


def changelog_path(root: Path | None = None) -> Path:
    """The change log What's New reads (TR291, D2018)."""
    return (root or frozen_root() or _SOURCE_ROOT) / "CHANGELOG.md"


def license_files(root: Path | None = None) -> dict[str, Path]:
    """The license texts shown in the About box, by key of ``LICENSE_DOCS``."""
    frozen = root or frozen_root()
    base = frozen or _SOURCE_ROOT
    folder = base / "licenses" if frozen else base / "packaging" / "licenses"
    return {
        "license": base / "LICENSE",
        "notices": base / "THIRD_PARTY_NOTICES.txt",
        "offer": base / "SOURCE_OFFER.md",
        "lgpl21": folder / "LGPL-2.1.txt",
        "lgpl3": folder / "LGPL-3.0.txt",
    }


def app_icon_path() -> Path:
    """The app icon SVG, next to the ``fdcad.ui`` package in source and in a build (D557)."""
    return Path(__file__).resolve().parents[1] / "app_icon.svg"


def app_icon_small_path() -> Path:
    """The bolder app icon drawing for 16 to 32 px (D672), next to ``app_icon.svg``."""
    return app_icon_path().with_name("app_icon_small.svg")


def app_icon() -> QIcon:
    """The app icon: the small drawing at 16 to 32 px, the full one above (U5.5).

    Drawn into one pixmap per size, because Qt's SVG icon engine keeps a single
    drawing per icon. Needs a running QGuiApplication.
    """
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    result = QIcon()
    small = QSvgRenderer(str(app_icon_small_path()))
    full = QSvgRenderer(str(app_icon_path()))
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        (small if size <= 32 else full).render(painter, QRectF(0, 0, size, size))
        painter.end()
        result.addPixmap(pixmap)
    return result
