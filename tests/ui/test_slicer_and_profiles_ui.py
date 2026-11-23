"""Open in Slicer and the Printing page of the preferences (PLAN Phase 2, D351, D352)."""

from __future__ import annotations

import math
import zipfile
from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.printing.profiles import GENERIC, PrinterProfile
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences import print_settings
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.printing_page import PrintingPage
from fdcad.ui.print_tools import slicer
from fdcad.ui.strings_print import SLICER_NOTHING
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]


def test_open_in_slicer_writes_3mf_and_starts_the_profile_slicer(
    qtbot: QtBot, window: MainWindow
) -> None:
    custom = PrinterProfile("Shop", slicer="/opt/slicer/run")
    print_settings.set_profiles(window.settings, [GENERIC, custom], "Shop")
    _tab, _ext = plate_tab(qtbot, window)
    started: list[tuple[Path, str]] = []
    job = slicer.open_in_slicer(window, launch=lambda p, s: started.append((p, s)))
    assert job is not None
    qtbot.waitUntil(lambda: "Opened" in window.status.text(), timeout=20000)
    assert len(started) == 1
    path, program = started[0]
    assert program == "/opt/slicer/run" and path.suffix == ".3mf"
    with zipfile.ZipFile(path) as zf:
        assert "<triangle " in zf.read("3D/3dmodel.model").decode("utf-8")
    assert "/opt/slicer/run" in window.status.text()


def test_open_in_slicer_reports_a_failed_start(qtbot: QtBot, window: MainWindow) -> None:
    plate_tab(qtbot, window)

    def fail(_p: Path, _s: str) -> None:
        raise RuntimeError("no slicer here")

    slicer.open_in_slicer(window, launch=fail)
    qtbot.waitUntil(lambda: "no slicer here" in window.status.text(), timeout=20000)


def test_open_in_slicer_needs_a_part(window: MainWindow) -> None:
    assert slicer.open_in_slicer(window) is None
    assert window.status.text() == SLICER_NOTHING


def test_open_in_slicer_is_a_command_in_the_print_tab(window: MainWindow) -> None:
    assert "print.open_slicer" in window.commands.actions
    tabs = window.command_tabs
    panel = tabs.widget(tabs.index_of("print"))  # the 3D Print tab (D435)
    texts = [a.text() for b in panel.buttons() for a in b.group_actions]
    assert "Open in Slicer" in texts
    file_menu = window.menuBar().actions()[0].menu()
    assert window.commands.actions["print.open_slicer"] in file_menu.actions()


def test_printing_page_edits_adds_and_removes_profiles(qtbot: QtBot, window: MainWindow) -> None:
    settings = window.settings
    page = PrintingPage(settings)
    qtbot.addWidget(page)
    assert page.profile_box.count() == 1
    page.add_profile()
    assert page.profile_box.count() == 2 and page.name_edit.text() == "New printer"
    page.name_edit.setText("Delta")
    page.fields["bed_x"].setValue(180)
    page.overhang_box.setValue(55)
    page.slicer_edit.setText("/usr/bin/slicer")
    page.apply(settings)
    active = print_settings.active_profile(settings)
    assert active.name == "Delta" and active.bed_x == 180
    assert math.degrees(active.overhang_angle) == 55 and active.slicer == "/usr/bin/slicer"
    page.remove_profile()
    assert page.profile_box.count() == 1
    page.remove_profile()  # the last one stays
    assert page.profile_box.count() == 1


def test_printing_page_keeps_names_unique_and_densities(qtbot: QtBot, window: MainWindow) -> None:
    settings = window.settings
    page = PrintingPage(settings)
    qtbot.addWidget(page)
    page.add_profile()
    page.name_edit.setText(GENERIC.name)
    page.apply(settings)
    names = [p.name for p in print_settings.profiles(settings)]
    assert names == [GENERIC.name, f"{GENERIC.name} 2"]
    item = page.material_table.item(0, 1)
    assert item is not None
    item.setText("1.30")
    page.apply(settings)
    assert print_settings.densities(settings)["PLA"] == 1.3


def test_preferences_dialog_has_a_printing_page(qtbot: QtBot, window: MainWindow) -> None:
    dialog = PreferencesDialog(window.settings)
    qtbot.addWidget(dialog)
    titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert "Printing" in titles
    dialog.printing.fields["height"].setValue(300)
    dialog.accept()
    assert print_settings.active_profile(window.settings).height == 300


def test_open_in_slicer_keeps_face_colours(qtbot: QtBot, window: MainWindow) -> None:
    """Spec 2 section 20 item 12 (D714): the slicer file never had colours."""
    tab, ext = plate_tab(qtbot, window)
    tab.session.document.appearance["faces"] = {f"{ext}/cap/end": "#FF0000"}
    started: list[Path] = []
    slicer.open_in_slicer(window, launch=lambda p, s: started.append(p))
    qtbot.waitUntil(lambda: bool(started), timeout=20000)
    with zipfile.ZipFile(started[0]) as zf:
        model = zf.read("3D/3dmodel.model").decode("utf-8")
    assert "#FF0000" in model and 'p1="1"' in model


def test_export_bodies_writes_one_file_per_body(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: object
) -> None:
    """Spec 2 section 20 item 13 (D714): split pieces could only be saved from the body
    Split panel, and STL export wrote every piece into one file."""
    import pytest
    from PySide6.QtWidgets import QFileDialog, QInputDialog

    from fdcad.core.io import fdef
    from fdcad.samples.make import SAMPLE_DIR
    from fdcad.ui.print_tools.export_bodies import export_bodies
    from fdcad.ui.session import DocumentSession

    mp: pytest.MonkeyPatch = monkeypatch  # type: ignore[assignment]
    doc = fdef.load(SAMPLE_DIR / "split_with_pins.fdprt")
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        window.add_session(session)
    mp.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
    mp.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("STL", True)))
    assert export_bodies(window) is not None
    qtbot.waitUntil(lambda: "Saved" in window.status.text(), timeout=30000)
    assert len(list(tmp_path.glob("*.stl"))) == 4
    assert "file.export_bodies" in window.commands.actions
