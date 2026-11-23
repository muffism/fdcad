"""Save screenshots of the main window widgets, light and dark, for UI review.

    uv run python tools/screenshot_tabs.py [--placeholders] [--scale 1.5] [--out screenshots]

Runs on Qt's offscreen platform by default and writes ``tabs_<tab>_<theme>.png`` plus the
feature tree, view strip, status bar and whole window with a sample part open
(``tree_``, ``viewbar_``, ``statusbar_``, ``window_<theme>.png``). On the
offscreen platform the 3D view shows as a placeholder. With a display (for
example ``QT_QPA_PLATFORM=xcb`` on Xvfb with software OpenGL) the window shot
is taken from the screen, so it includes the real 3D view. The ``screenshots``
folder is ignored by git. With
``--placeholders`` it draws simple stand in icons into a temporary folder
outside the repository (for when the real icon set is not there yet). The
placeholders are never saved in the repository.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

SHAPES = [
    '<rect x="4" y="4" width="16" height="16" rx="2" fill="none" stroke="currentColor" '
    'stroke-width="1.75"/><circle cx="12" cy="12" r="3.5" fill="#ACCENT"/>',
    '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.75"/>'
    '<path d="M8 16 L16 8" stroke="#ACCENT" stroke-width="2" stroke-linecap="round"/>',
    '<path d="M4 18 L12 5 L20 18 Z" fill="none" stroke="currentColor" stroke-width="1.75" '
    'stroke-linejoin="round"/><circle cx="12" cy="14" r="2.5" fill="#ACCENT"/>',
    '<path d="M5 19 L19 5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/>'
    '<circle cx="5" cy="19" r="2.2" fill="#ACCENT"/><circle cx="19" cy="5" r="2.2" '
    'fill="#ACCENT"/>',
]


def write_placeholders(folder: Path) -> None:
    """One simple SVG per command id, in the loader's format (24 by 24, theme colours)."""
    from fdcad.ui.input.commands import COMMANDS

    folder.mkdir(parents=True, exist_ok=True)
    for i, cmd in enumerate(COMMANDS):
        body = SHAPES[i % len(SHAPES)]
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body}</svg>'
        (folder / f"{cmd.id}.svg").write_text(svg, encoding="utf-8")


def _part_shots(app: Any, window: Any, out: Path, tag: str) -> None:
    """Open the first sample part and save the tree, view strip, status bar and window."""
    from fdcad.samples.location import sample_files

    samples = sample_files()
    if not samples:
        return
    window.open_sample(samples[0])
    tab = window.current
    tab.session.wait(20000)  # the rebuild runs in the background
    for _ in range(20):
        app.processEvents()
    window.sketch_status.setText("Under defined: 2 degrees of freedom left")
    window.coords.setText("X 12.50 mm  Y 4.00 mm")
    app.processEvents()
    shots = {
        "tree": window.left,
        "viewbar": tab.view_bar,
        "statusbar": window.statusBar(),
        "window": window,
    }
    for name, widget in shots.items():
        _save(widget, out / f"{name}_{tag}.png")
    if app.platformName() != "offscreen":
        # A widget grab leaves the OpenGL view out; the screen has it.
        import time

        time.sleep(1)
        app.processEvents()
        geometry = window.frameGeometry()
        shot = app.primaryScreen().grabWindow(
            0, geometry.x(), geometry.y(), geometry.width(), geometry.height()
        )
        shot.save(str(out / f"window_{tag}.png"))
    window.sketch_status.setText("")
    window.coords.setText("")
    _editing_shots(app, window, out, tag)


def _save(widget: Any, path: Path) -> None:
    widget.grab().save(str(path))
    print(path)


def _editing_shots(app: Any, window: Any, out: Path, tag: str) -> None:
    """The property panel, the sketch editor, the value box and the context toolbar."""
    from fdcad.ui import strings
    from fdcad.ui.sketch_tools.value_box import ValueBox

    tab = window.current
    features = tab.session.document.features
    solid = next((f for f in features if f.type == "extrude"), None)
    if solid is not None:
        window.edit_feature(solid.id)
        for _ in range(10):
            app.processEvents()
        _save(window.left, out / f"panel_{tag}.png")
        window.panel.cancel()
        app.processEvents()
    sketch = next((f for f in features if f.type == "sketch"), None)
    if sketch is not None:
        window.edit_feature(sketch.id)
        for _ in range(10):
            app.processEvents()
        if tab.sketch_canvas is not None:
            _save(window, out / f"sketch_{tag}.png")
        window.sketch_mode.cancel()
        app.processEvents()
    box = ValueBox("25 mm")
    box.show()
    app.processEvents()
    _save(box, out / f"valuebox_{tag}.png")
    box.close()
    bar = window.context_bar
    bar.offer(
        [
            ("sketch", strings.SKETCH, lambda: None),
            ("extrude", strings.EXTRUDED_BOSS, lambda: None),
            ("hide", strings.HIDE, lambda: None),
            ("normal_to", strings.NORMAL_TO, lambda: None),
        ]
    )
    bar.show()
    app.processEvents()
    _save(bar, out / f"contextbar_{tag}.png")
    bar.hide()


def main() -> int:
    """Open the main window offscreen and save the command tab screenshots."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="screenshots", help="folder for the PNG files")
    parser.add_argument("--placeholders", action="store_true", help="use stand in icons")
    parser.add_argument("--scale", type=float, default=1.0, help="display scale, e.g. 1.5")
    parser.add_argument("--width", type=int, default=1100, help="window width")
    parser.add_argument("--height", type=int, default=700, help="window height")
    parser.add_argument(
        "--contrast", action="store_true", help="also shoot the four contrast samples (TR378)"
    )
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if sys.platform == "win32":
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.expandvars(r"%WINDIR%\Fonts"))
    if args.scale != 1.0:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale)
    scratch = Path(tempfile.mkdtemp(prefix="fdcad_shots_"))
    os.environ.setdefault("FDCAD_CACHE_DIR", str(scratch / "cache"))
    os.environ.setdefault("FDCAD_DATA_DIR", str(scratch / "data"))

    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    import fdcad.ui.icons as icon_module
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.preferences.settings import Settings, Theme
    from fdcad.ui.themes import theme as theme_module
    from fdcad.ui.themes.system_contrast import SAMPLES
    from fdcad.ui.themes.theme import apply_theme

    if args.placeholders:
        write_placeholders(scratch / "icons")
        icon_module.ICON_DIR = scratch / "icons"

    app = QApplication(sys.argv)
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 9))  # the Windows UI font; offscreen has no default
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.scale == 1.0 else f"_{round(args.scale * 100)}"
    settings = Settings(QSettings(str(scratch / "prefs.ini"), QSettings.Format.IniFormat))
    runs: list[tuple[str, Theme, object | None]] = [
        ("light", Theme.LIGHT, None),
        ("dark", Theme.DARK, None),
    ]
    if args.contrast:
        runs += [(f"contrast_{name}", Theme.LIGHT, colors) for name, colors in SAMPLES.items()]
    for label, theme, colors in runs:
        theme_module.set_system_contrast(colors)
        apply_theme(app, theme)
        window = MainWindow(settings)
        window.resize(args.width, args.height)
        window.show()
        window.finish_setup()
        tabs = window.command_tabs
        tabs.theme_changed()
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            app.processEvents()
            path = out / f"tabs_{tabs.tabText(index).lower()}_{label}{suffix}.png"
            window.command_holder.grab().save(str(path))
            print(path)
        tabs.setCurrentIndex(0)  # the window shots show the Features tab
        _part_shots(app, window, out, f"{label}{suffix}")
        window.close()
        window.deleteLater()
        app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
