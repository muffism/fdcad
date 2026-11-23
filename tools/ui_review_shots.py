"""Save screenshots of the whole UI for a design review, in every theme.

    uv run python tools/ui_review_shots.py --out .shots/before [--themes light,dark]
        [--scale 1.5] [--width 1440] [--height 900] [--only panels,sketch]

Runs on Qt's offscreen platform, so the 3D view is blank: the review is of the
chrome around it. Each theme writes the start page, the left panel with no
part open, the main window with a sample part, sketch mode, three property
panels (Extrude, Fillet, Hole Tool), the panel header with Pin off and on, the
Plane and Section View panels, one group each of Split, the Hole Tool, Draft and
Fillet side by side, the right click menus, a message bar with a
button, the Variables and Errors tabs, the Preferences window, the node editor
(docked, its title bar, and floating), a sheet of every control state and a
sheet of every text colour on every row fill. A shot that fails is reported
and the run goes on. The folder is not for git.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _spin(app: Any, turns: int = 12) -> None:
    """Run the event loop a few turns, and delete what ``deleteLater`` queued: a bare
    ``processEvents`` leaves those widgets on screen, under the ones that replaced them."""
    from PySide6.QtCore import QCoreApplication, QEvent

    for _ in range(turns):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class Shots:
    """Takes the shots of one theme."""

    def __init__(self, app: Any, window: Any, out: Path, tag: str) -> None:
        self.app, self.window, self.out, self.tag = app, window, out, tag
        self.failed: list[str] = []

    def save(self, name: str, widget: Any) -> None:
        """Grab ``widget`` into ``<name>_<theme>.png``."""
        path = self.out / f"{name}_{self.tag}.png"
        widget.grab().save(str(path))
        print(path)

    def step(self, name: str, work: Callable[[], None]) -> None:
        """Run one shot; a failure is printed and the others still run."""
        try:
            work()
        except Exception:
            self.failed.append(name)
            print(f"FAILED {name}_{self.tag}")
            traceback.print_exc()
        _spin(self.app)

    def open(self, sample: str) -> Any:
        """Open a sample part and wait for its rebuild."""
        self.window.open_path(ROOT / "samples" / sample)
        tab = self.window.current
        tab.session.wait(60000)
        _spin(self.app, 30)
        return tab

    def close_parts(self) -> None:
        """Close every part without asking."""
        w = self.window
        if w.sketch_mode is not None and w.editing == "sketch":
            w.sketch_mode.cancel()
        if w.panel is not None and w.editing == "feature":
            w.panel.cancel()
        _spin(self.app)
        while w.tabs.count():
            w.close_tab(0, ask=False)
            _spin(self.app)

    # The shots ---------------------------------------------------------------------

    def start_page(self) -> None:
        w = self.window
        recent = [str(ROOT / "samples" / f"{n}.fdprt") for n in ("bracket", "enclosure", "gearbox")]
        w.settings.store.setValue("files/recent", recent)
        w.start_page.refresh()
        _spin(self.app)
        self.save("start_page", w)
        w.settings.store.setValue("files/recent", [])
        w.start_page.refresh()
        _spin(self.app)
        self.save("start_page_empty", w)
        self.save("left_no_part", w.left)

    def main_window(self) -> None:
        w = self.window
        tab = self.open("enclosure.fdprt")
        w.coords.setText("X 12.50 mm  Y 4.00 mm  Z 0.00 mm")
        _spin(self.app)  # the status bar lays out again for the new text
        self.save("main", w)
        self.save("tree", w.left)
        self.save("statusbar", w.statusBar())
        self.save("viewbar", tab.view_bar)
        tabs = w.command_tabs
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            _spin(self.app, 4)
            self.save(f"tabs_{tabs.tabText(index).lower().replace(' ', '_')}", w.command_holder)
        tabs.setCurrentIndex(0)
        w.coords.setText("")

    def message_bar(self) -> None:
        tab = self.window.current
        tab.message_bars.show_message(
            "review_warning",
            "Fillet 2 was left out so this part could open. It stopped FDCAD the last time.",
            "warning",
            ("Suppress", lambda: None),
        )
        tab.message_bars.show_message(
            "review_info", "This part was opened to look at. Edit it to make changes.", "info"
        )
        _spin(self.app)
        self.save("message_bars", tab.message_bars)
        self.save("main_message_bars", self.window)
        tab.message_bars.close_message("review_warning")
        tab.message_bars.close_message("review_info")

    def menus(self) -> None:
        w = self.window
        tab = w.current
        tree = w.tree
        item = None
        for fid in [f.id for f in tab.session.document.features if f.type == "fillet"]:
            item = tree.item_for(fid) if hasattr(tree, "item_for") else None
            break
        if item is None:
            item = tree.topLevelItem(tree.topLevelItemCount() - 1)
        tree.setCurrentItem(item)
        menu = tree._context_menu(tab.session, item)
        if menu is not None:
            self.save("menu_tree", menu)
        menu = w.context_menus.build_view_menu(tab, [])
        self.save("menu_view", menu)
        bar = w.menuBar()
        for action in bar.actions()[:3]:
            sub = action.menu()
            if sub is not None:
                sub.aboutToShow.emit()
                name = action.text().replace("&", "").lower()
                self.save(f"menubar_{name}", sub)

    def panels(self) -> None:
        w = self.window
        features = w.current.session.document.features
        for kind in ("extrude", "fillet"):
            feature = next(f for f in features if f.type == kind)
            w.edit_feature(feature.id)
            _spin(self.app, 30)
            self.save(f"panel_{kind}", w.left)
            if kind == "extrude":
                self.save("main_panel", w)
                header = w.panel.pin_button.parentWidget()
                self.save("panel_header", header)
                w.panel.pin_button.setChecked(True)  # the pinned look (D2701)
                _spin(self.app)
                self.save("panel_header_pinned", header)
                w.panel.pin_button.setChecked(False)
            w.panel.cancel()
            _spin(self.app)
        w.left.setCurrentIndex(2)
        _spin(self.app)
        self.save("tab_variables", w.left)
        w.left.setCurrentIndex(3)
        _spin(self.app)
        self.save("tab_errors_empty", w.left)
        w.left.setCurrentIndex(0)

    def side_panels(self) -> None:
        """The Plane panel and the Section View panel, which open in the same place."""
        w = self.window
        w.reference_tool.start("ref_plane")
        _spin(self.app, 30)
        self.save("panel_reference", w.left)
        w.reference_tool.close()
        _spin(self.app)
        w.section_tool.open(w.current)
        _spin(self.app, 30)
        self.save("panel_section", w.left)
        w.section_tool.turn_off(w.current)

    def group_of(self, title: str) -> Any:
        """A picture of the open panel's group with this title, on its tab."""
        from fdcad.ui.property_panel.groups import Group

        panel = self.window.panel
        tabs = getattr(panel, "page_tabs", None)
        for key in tabs.keys if tabs is not None else [""]:
            if tabs is not None:
                tabs.show_tab(key)
                _spin(self.app, 10)
            for group in panel.groups_box.findChildren(Group):
                if group.title_text == title and group.isVisibleTo(panel):
                    group.set_checked(True)
                    group.set_expanded(True)
                    _spin(self.app, 20)
                    return group.grab()
        raise LookupError(title)

    def leftovers(self) -> None:
        """Four groups in one picture: Split's list of bodies, the Hole Tool's Options,
        Draft's faces and Fillet's Variable Radii with one control point."""
        w = self.window
        found: list[tuple[str, Any]] = []
        for command, name, title in (
            ("feature.split", "Split", "Resulting Bodies"),
            ("feature.hole", "Hole Tool", "Options"),
            ("feature.draft", "Draft", "Faces to Draft"),
        ):
            w.commands.trigger(command)
            _spin(self.app, 30)
            found.append((name, self.group_of(title)))
            w.panel.cancel()
            _spin(self.app)
        fillet = next(f for f in w.current.session.document.features if f.type == "fillet")
        w.edit_feature(fillet.id)
        _spin(self.app, 30)
        form = w.panel.form
        form.kind.setCurrentIndex(form.kind.findData("variable"))
        form.controls.setValue(1)
        _spin(self.app, 30)
        found.append(("Fillet, Variable Size", self.group_of("Variable Radii")))
        w.panel.cancel()
        _spin(self.app)
        path = self.out / f"leftovers_{self.tag}.png"
        side_by_side(found).save(str(path))
        print(path)

    def sketch(self) -> None:
        w = self.window
        feature = next(f for f in w.current.session.document.features if f.type == "sketch")
        w.edit_feature(feature.id)
        _spin(self.app, 30)
        self.save("sketch", w)
        self.save("sketch_panel", w.left)
        self.save("sketch_tabs", w.command_holder)
        canvas = w.current.sketch_canvas
        if canvas is not None:
            self.save("menu_sketch", w.context_menus.build_sketch_menu(canvas))
        w.sketch_mode.cancel()

    def hole(self) -> None:
        w = self.window
        self.open("tapped_housing.fdprt")
        feature = next(f for f in w.current.session.document.features if f.type == "hole")
        w.edit_feature(feature.id)
        _spin(self.app, 30)
        self.save("panel_hole", w.left)
        w.panel.cancel()

    def errors(self) -> None:
        import json

        w = self.window
        # A copy of the sample whose first fillet cannot be built, so it has an error.
        data = json.loads((ROOT / "samples" / "enclosure.fdprt").read_text(encoding="utf-8"))
        fillet = next(f for f in data["features"] if f["type"] == "fillet")
        fillet["params"]["radius"] = {"expr": "500", "value": 500}
        broken = Path(tempfile.mkdtemp(prefix="fdcad_review_")) / "enclosure.fdprt"
        broken.write_text(json.dumps(data), encoding="utf-8")
        w.open_path(broken)
        w.current.session.wait(60000)
        _spin(self.app, 30)
        w.left.setCurrentIndex(3)
        _spin(self.app)
        self.save("tab_errors", w.left)
        self.save("main_errors", w)
        w.left.setCurrentIndex(0)
        _spin(self.app)
        self.save("tree_error", w.left)

    def preferences(self) -> None:
        from fdcad.ui.preferences.dialog import PreferencesDialog

        dialog = PreferencesDialog(self.window.settings, self.window)
        dialog.show()
        _spin(self.app)
        self.save("preferences", dialog)
        tabs = dialog.findChild(type(self.window.tabs))
        if tabs is not None:
            for index in range(1, tabs.count()):
                tabs.setCurrentIndex(index)
                _spin(self.app)
                self.save(f"preferences_{index}", dialog)
        dialog.close()
        dialog.deleteLater()

    def node_editor(self) -> None:
        from fdcad.ui.node_editor import install

        self.open("graphs/slider_bracket.fdprt")
        install.show(self.window, True)
        _spin(self.app, 30)
        panel = install.panel_of(self.window)
        panel.fit()
        _spin(self.app, 10)
        self.save("node_editor", self.window)
        self.save("node_editor_panel", panel)
        dock = self.window.node_editor_dock
        title = dock.grab().copy(0, 0, dock.width(), panel.mapTo(dock, panel.rect().topLeft()).y())
        path = self.out / f"node_editor_title_{self.tag}.png"
        title.save(str(path))
        print(path)
        dock.setFloating(True)
        dock.resize(640, 420)
        _spin(self.app, 10)
        self.save("node_editor_floating", dock)
        dock.setFloating(False)
        _spin(self.app, 10)
        install.show(self.window, False)

    def dialogs(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("FDCAD")
        box.setText("Save changes to enclosure before closing?")
        box.setInformativeText("Your changes since the last save will be lost.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        box.show()
        _spin(self.app)
        self.save("dialog_unsaved", box)
        box.close()
        box.deleteLater()

    def controls(self) -> None:
        sheet = control_sheet()
        sheet.show()
        _spin(self.app)
        self.save("controls", sheet)
        sheet.close()
        sheet.deleteLater()

    def rows(self) -> None:
        sheet = row_sheet()
        sheet.show()
        _spin(self.app)
        self.save("rows", sheet)
        sheet.close()
        sheet.deleteLater()


def side_by_side(found: list[tuple[str, Any]]) -> Any:
    """One picture of the named pictures in a row, each under its name, on the panel
    colour."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap

    from fdcad.ui.themes import theme

    c = theme.chrome()
    gap, top = 12, 28
    ratio = found[0][1].devicePixelRatio()
    sizes = [picture.deviceIndependentSize().toSize() for _name, picture in found]
    width = sum(size.width() for size in sizes) + gap * (len(found) + 1)
    height = max(size.height() for size in sizes) + top + gap
    sheet = QPixmap(round(width * ratio), round(height * ratio))
    sheet.setDevicePixelRatio(ratio)
    sheet.fill(QColor(c.surface))
    painter = QPainter(sheet)
    painter.setPen(QColor(c.text))
    x = gap
    flags = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
    for (name, picture), size in zip(found, sizes, strict=True):
        painter.drawText(QRect(x, 0, size.width(), top), flags, name)
        painter.drawPixmap(x, top, picture)
        x += size.width() + gap
    painter.end()
    return sheet


def control_sheet() -> Any:
    """One widget with every control in its normal, disabled, checked and focused look."""
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QGridLayout,
        QGroupBox,
        QLabel,
        QLineEdit,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QSlider,
        QToolButton,
        QWidget,
    )

    from fdcad.ui.icons import icon

    sheet = QWidget()
    sheet.setObjectName("property_panel")
    sheet.resize(760, 420)
    grid = QGridLayout(sheet)
    for column, title in enumerate(("Normal", "Disabled", "Checked or main", "Keyboard focus")):
        grid.addWidget(QLabel(title), 0, column + 1)

    def row(index: int, name: str, make: Callable[[], Any], third: Callable[[Any], None]) -> None:
        grid.addWidget(QLabel(name), index, 0)
        for column in range(4):
            widget = make()
            if column == 1:
                widget.setEnabled(False)
            elif column == 2:
                third(widget)
            elif column == 3:
                widget.setProperty("keyfocus", True)
            grid.addWidget(widget, index, column + 1)

    def tool() -> Any:
        button = QToolButton()
        button.setIcon(icon("feature.fillet"))
        button.setCheckable(True)
        return button

    def combo() -> Any:
        box = QComboBox()
        box.addItems(["Blind", "Through All", "Up to Surface"])
        return box

    def spin() -> Any:
        box = QDoubleSpinBox()
        box.setValue(12.5)
        box.setSuffix(" mm")
        return box

    def slider() -> Any:
        from PySide6.QtCore import Qt

        s = QSlider(Qt.Orientation.Horizontal)
        s.setValue(40)
        return s

    row(1, "Button", lambda: QPushButton("Apply"), lambda b: b.setProperty("main", True))
    row(2, "Tool button", tool, lambda b: b.setChecked(True))
    row(3, "Text field", lambda: QLineEdit("25 mm"), lambda f: f.setProperty("invalid", True))
    row(4, "Drop down", combo, lambda b: None)
    row(5, "Spin box", spin, lambda b: None)
    row(6, "Check box", lambda: QCheckBox("Merge result"), lambda b: b.setChecked(True))
    row(7, "Radio button", lambda: QRadioButton("Constant size"), lambda b: b.setChecked(True))
    row(8, "Slider", slider, lambda b: None)
    group = QGroupBox("Group box")
    inner = QGridLayout(group)
    inner.addWidget(QLabel("Depth"), 0, 0)
    inner.addWidget(QLineEdit("10 mm"), 0, 1)
    bar = QProgressBar()
    bar.setValue(60)
    inner.addWidget(bar, 1, 0, 1, 2)
    grid.addWidget(group, 9, 0, 1, 5)
    return sheet


def row_sheet() -> Any:
    """Every text colour of a row on every fill a row can have, with its contrast: the
    panel, a row under the pointer, a selected row, and a selected row under the
    pointer. The same pairs ``themes.contrast`` measures."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtWidgets import QWidget

    from fdcad.ui.themes import contrast, theme

    c, p = theme.chrome(), theme.palette()
    fills = [
        ("Panel", c.surface),
        ("Under the pointer", c.hover),
        ("Selected", c.selected),
        ("Selected, under the pointer", c.pressed),
    ]
    texts = [
        ("Text", c.text),
        ("Muted", c.muted),
        ("Accent", c.accent),
        ("Danger", c.danger),
        ("Ok", p.state_ok),
        ("Warning", p.state_warning),
        ("Error", p.state_error),
    ]
    row, label, column, top = 28, 80, 190, 28

    class Sheet(QWidget):
        def paintEvent(self, _event: Any) -> None:  # noqa: N802  (Qt override)
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(c.window))
            flags = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            painter.setPen(QColor(c.text))
            for x, (name, _fill) in enumerate(fills):
                painter.drawText(QRect(label + x * column + 8, 0, column, top), flags, name)
            for y, (name, colour) in enumerate(texts):
                painter.setPen(QColor(c.text))
                painter.drawText(QRect(8, top + y * row, label, row), flags, name)
                for x, (_n, fill) in enumerate(fills):
                    cell = QRect(label + x * column + 2, top + y * row + 2, column - 4, row - 4)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(fill))
                    painter.drawRoundedRect(cell, 6, 6)
                    painter.setPen(QColor(colour))
                    text = f"Fillet 2    {contrast.ratio(colour, fill):.2f}"
                    painter.drawText(cell.adjusted(8, 0, 0, 0), flags, text)

    sheet = Sheet()
    sheet.resize(label + len(fills) * column + 8, top + len(texts) * row + 8)
    return sheet


def run_theme(
    app: Any, settings: Any, theme: Any, tag: str, out: Path, size: Any, only: set[str]
) -> list[str]:
    """Every shot of one theme. Returns the names of the shots that failed."""
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.themes.theme import apply_theme

    apply_theme(app, theme)
    window = MainWindow(settings)
    window.resize(*size)
    window.show()
    window.finish_setup()
    window.command_tabs.theme_changed()
    _spin(app, 20)
    shots = Shots(app, window, out, tag)
    steps: list[tuple[str, Callable[[], None]]] = [
        ("start_page", shots.start_page),
        ("main", shots.main_window),
        ("message_bar", shots.message_bar),
        ("menus", shots.menus),
        ("panels", shots.panels),
        ("side_panels", shots.side_panels),
        ("leftovers", shots.leftovers),
        ("sketch", shots.sketch),
        ("close", shots.close_parts),
        ("hole", shots.hole),
        ("close", shots.close_parts),
        ("errors", shots.errors),
        ("preferences", shots.preferences),
        ("dialogs", shots.dialogs),
        ("close", shots.close_parts),
        ("node_editor", shots.node_editor),
        ("close", shots.close_parts),
        ("controls", shots.controls),
        ("rows", shots.rows),
    ]
    for name, work in steps:
        # The shots after "main" need its part open, so it always runs.
        if not only or name in only or name in ("close", "main"):
            shots.step(name, work)
    window.close()
    window.deleteLater()
    _spin(app)
    return shots.failed


def main() -> int:
    """Open the main window offscreen and save the review screenshots."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=".shots/review", help="folder for the PNG files")
    parser.add_argument("--themes", default="light,beige,dark,stealth")
    parser.add_argument("--scale", type=float, default=1.0, help="display scale, e.g. 1.5")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--only", default="", help="shots to take, e.g. panels,sketch")
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if sys.platform == "win32":
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.expandvars(r"%WINDIR%\Fonts"))
    if args.scale != 1.0:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale)
    scratch = Path(tempfile.mkdtemp(prefix="fdcad_review_"))
    os.environ.setdefault("FDCAD_CACHE_DIR", str(scratch / "cache"))
    os.environ.setdefault("FDCAD_DATA_DIR", str(scratch / "data"))

    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.preferences.settings import Settings, Theme

    app = QApplication(sys.argv)
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 9))  # the Windows UI font; offscreen has no default
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.scale == 1.0 else f"_{round(args.scale * 100)}"
    themes = {
        "light": Theme.LIGHT,
        "beige": Theme.BEIGE,
        "dark": Theme.DARK,
        "stealth": Theme.STEALTH,
    }
    failed: list[str] = []
    size = (args.width, args.height)
    only = {n.strip() for n in args.only.split(",") if n.strip()}
    for name in [n.strip() for n in args.themes.split(",") if n.strip()]:
        settings = Settings(
            QSettings(str(scratch / f"prefs_{name}.ini"), QSettings.Format.IniFormat)
        )
        settings.theme = themes[name]
        tag = f"{name}{suffix}"
        failed += [
            f"{shot}_{tag}" for shot in run_theme(app, settings, themes[name], tag, out, size, only)
        ]
    if failed:
        print("Failed shots: " + ", ".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
