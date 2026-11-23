"""The application shell on the Qt offscreen platform (PLAN section 10 item 6)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QMessageBox
from pytestqt.qtbot import QtBot

from fdcad import __version__
from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.units import UnitSystem
from fdcad.ui import strings
from fdcad.ui.main_window import recovery
from fdcad.ui.main_window.window import DocumentTab, MainWindow, viewport_supported
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from fdcad.ui.tree.feature_tree import FID_ROLE
from tests.core.features.test_features import _hole, plate


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)  # not given to qtbot: it would close it before the cleanup below
    win.show()
    win.finish_setup()
    yield win
    # Close quietly: no "save changes?" prompt can be answered in a test.
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _open_plate(qtbot: QtBot, win: MainWindow) -> tuple[DocumentTab, str]:
    doc, ext = plate()
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab, ext


def _tree_names(win: MainWindow) -> list[str]:
    assert win.tree is not None
    # Top level rows, plus sketches nested under their features (W5.3).
    return [
        item.text(0)
        for item in win.tree.all_items()
        if item.parent() is None or item.data(0, FID_ROLE) is not None
    ]


def test_window_starts_with_version_and_no_gpu(window: MainWindow) -> None:
    assert __version__ in window.windowTitle()
    assert viewport_supported() is False  # CI has no GPU; the real view is checked by hand
    assert window.ready


def test_open_part_fills_tree_and_status(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = _open_plate(qtbot, window)
    names = _tree_names(window)
    assert names[:8] == [
        tab.session.title.rstrip("*"),
        "Solid Bodies (1)",
        "Appearances (1)",  # P2.11 item 1 (D254)
        "Material: none",  # TR78 (D803)
        "Front Plane",
        "Top Plane",
        "Right Plane",
        "Origin",
    ]
    # Part, folder, Appearances and Material rows.
    assert len(names) == len(tab.session.document.features) + 4
    assert window.tree is not None
    for i in range(window.tree.topLevelItemCount()):
        assert not window.tree.topLevelItem(i).icon(0).isNull()  # every row has a type icon
    assert window.status.text().startswith("Rebuilt in")
    assert window.unit_button.text() == "mm"
    assert tab.session.report is not None
    assert tab.session.report.results[ext].state is FeatureState.OK


def test_insert_extruded_cut_through_panel_and_undo(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = _open_plate(qtbot, window)
    session = tab.session
    _hole(session.document, f"{ext}/cap/end")  # adds a hole sketch and a cut
    hole_sketch = session.document.features[-2]
    session.document.features.pop()  # keep only the sketch, the panel adds the cut
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    assert window.tree is not None and window.panel is not None
    window.tree.select(hole_sketch.id)
    window.insert_feature("extrude", "cut")
    assert window.panel.is_editing
    assert window.panel.title.text() == "Cut 1"
    assert window.preview is not None and window.preview.is_active  # live preview follows
    window.panel.choices["end_condition"].setCurrentIndex(
        window.panel.choices["end_condition"].findData("through_all")
    )
    window.panel.flags["reverse"].setChecked(True)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.panel.accept()
    cut: Feature = session.document.features[-1]
    assert cut.type == "extrude" and cut.refs["sketch"] == {"feature": hole_sketch.id}
    assert cut.name == "Cut 1" and not window.preview.is_active
    assert session.report is not None
    assert session.report.results[cut.id].state is FeatureState.OK
    assert window.undo_group.canUndo()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.undo_group.undo()
    assert session.document.features[-1].id == hole_sketch.id


def test_panel_rejects_bad_values(qtbot: QtBot, window: MainWindow) -> None:
    tab, ext = _open_plate(qtbot, window)
    assert window.panel is not None
    window.edit_feature(ext)
    window.panel.values["depth"].edit.setText("20 furlongs")
    assert "Unknown unit" in window.panel.values["depth"].info.text()
    window.panel.accept()
    assert window.panel.is_editing  # stays open until the value is fixed
    window.panel.values["depth"].edit.setText("1in")
    assert window.panel.values["depth"].info.text() == "= 25.40 mm"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.panel.accept()
    assert tab.session.document.feature(ext).params["depth"].value == pytest.approx(25.4)  # type: ignore[union-attr]


def test_save_and_reopen(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ = _open_plate(qtbot, window)
    target = tmp_path / "plate.fdprt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    assert window.save()
    assert target.exists() and tab.session.path == target
    assert window.settings.recent_files == [str(target)]
    assert window.close_tab(window.tabs.currentIndex())
    window.open_path(target)
    reopened = window.current
    assert reopened is not None and reopened.session.path == target
    window.open_path(target)  # opening again switches to the tab
    assert window.tabs.count() == 1


def test_unsaved_prompt_can_cancel_close(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, ext = _open_plate(qtbot, window)
    from fdcad.ui.commands.document import RenameFeature

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.push(RenameFeature(tab.session, ext, "Base"))
    assert window.tabs.tabText(0).endswith("*")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert not window.close_tab(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Discard)
    assert window.close_tab(0)
    assert window.tabs.count() == 0


def test_units_toggle_keeps_bare_numbers_and_undo_restores_them(
    qtbot: QtBot, window: MainWindow
) -> None:
    """Audit D3 item 1 (D702): a bare "10" depth stays 10 mm in an inch part."""
    tab, ext = _open_plate(qtbot, window)
    doc = tab.session.document
    depth = doc.feature(ext).params["depth"]
    assert not any(c.isalpha() for c in depth.expr)  # typed as a bare number
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.toggle_units()
    assert doc.units is UnitSystem.IN
    assert doc.feature(ext).params["depth"].expr == f"{depth.expr.strip()}mm"
    assert doc.feature(ext).params["depth"].value == depth.value
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.undo_group.undo()
    assert doc.units is UnitSystem.MM
    assert doc.feature(ext).params["depth"].expr == depth.expr


def test_units_toggle_is_undoable(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ = _open_plate(qtbot, window)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.toggle_units()
    assert tab.session.document.units is UnitSystem.IN and window.unit_button.text() == "in"
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.undo_group.undo()
    assert tab.session.document.units is UnitSystem.MM


def test_variables_tab_drives_the_part(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    assert window.variables is not None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.variables.add_row()
    assert tab.session.document.variables[0].name == "Var1"
    window.variables.table.item(0, 2).setText("=Var1")  # circular
    assert "Circular" in window.variables.message.text()


def test_autosave_and_recovery(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, ext = _open_plate(qtbot, window)
    from fdcad.ui.commands.document import RenameFeature

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.push(RenameFeature(tab.session, ext, "Autosaved"))
    window.autosave()
    tab.autosaver.join()  # written in the background (D724)
    found = recovery.find_recoverable()
    assert len(found) == 1 and found[0].document.feature(ext).name == "Autosaved"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.recover()
    restored = window.current
    assert restored is not None and restored.session.is_dirty
    assert restored.session.document.feature(ext).name == "Autosaved"
    assert recovery.find_recoverable() == []


def test_a_relative_path_opens_once_and_is_remembered_in_full(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bug hunt F5: `fdcad part.fdprt` stored a relative path in the recent list and
    the same file opened a second time from its full path."""
    from fdcad.core.io import fdef

    doc, _ = plate()
    fdef.save(doc, tmp_path / "part.fdprt")
    monkeypatch.chdir(tmp_path)
    window.open_path(Path("part.fdprt"))
    window.open_path(tmp_path / "part.fdprt")
    assert window.tabs.count() == 1
    assert window.settings.recent_files == [str(tmp_path / "part.fdprt")]
    current = window.current
    assert current is not None and current.session.path == tmp_path / "part.fdprt"


def test_recent_files_menu_shows_ampersands_and_drops_missing_files(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bug hunt F8: "R&D" showed as "RD" with D underlined, and a file that no longer
    exists stayed in the recent list for ever, failing every time it was chosen."""
    from fdcad.core.io import fdef

    folder = tmp_path / "R&D"
    folder.mkdir()
    part = folder / "part.fdprt"
    doc, _ = plate()
    fdef.save(doc, part)
    window.open_path(part)
    assert window.close_tab(0)
    window._fill_recent()
    first = window.recent_menu.actions()[0]
    assert first.text() == str(part).replace("&", "&&")
    part.unlink()
    shown: list[str] = []
    from fdcad.ui.main_window import window as window_module

    monkeypatch.setattr(window_module, "show_error", lambda _p, msg, *a, **k: shown.append(msg))
    first.trigger()
    assert shown and "part.fdprt" in shown[0]
    assert window.settings.recent_files == []


def test_a_value_that_cannot_be_saved_names_the_fix_not_the_folder(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bug hunt F11: a variable whose formula overflowed to infinity could not be saved,
    and the message also said to choose another folder, which does not help."""
    from fdcad.core.document.model import Variable
    from fdcad.core.units import Kind

    tab, _ = _open_plate(qtbot, window)
    tab.session.document.variables.append(Variable("Big", Kind.LENGTH, "=1", float("inf")))
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "p"), strings.FILTER_FDEF)
    )
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, msg, *a: shown.append(msg))
    assert not window.save()
    assert shown and "Fix the parameter" in shown[0]
    assert "folder" not in shown[0]
    assert not (tmp_path / "p.fdprt").exists()


def test_save_as_and_export_start_in_the_parts_folder(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bug hunt F13: Save As and Export offered only a bare name, so the dialog
    started in the app's working folder instead of the folder of the open part."""
    from fdcad.core.io import fdef

    folder = tmp_path / "projects"
    folder.mkdir()
    doc, _ = plate()
    fdef.save(doc, folder / "plate.fdprt")
    window.open_path(folder / "plate.fdprt")
    tab = window.current
    assert tab is not None
    qtbot.waitUntil(lambda: tab.session.report is not None, timeout=20000)
    defaults: list[str] = []

    def dialog(_parent: object, _title: str, default: str, *_a: object) -> tuple[str, str]:
        defaults.append(default)
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", dialog)
    window.save_as()
    window.save_as_any()
    window.export("stl")
    assert defaults == [
        str(folder / "plate.fdprt"),
        str(folder / "plate.fdprt"),
        str(folder / "plate.stl"),
    ]


def test_title_bar_forgets_a_closed_part(qtbot: QtBot, window: MainWindow) -> None:
    """Bug hunt F7: after closing the last part the title bar still named it."""
    _open_plate(qtbot, window)
    assert window.windowTitle().startswith("Untitled")
    assert window.close_tab(0)
    assert window.windowTitle() == f"{strings.APP} {__version__}"


def test_recovered_part_keeps_its_file(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bug hunt F4: a recovered part opened as Untitled, cut off from its file."""
    from fdcad.core.io import fdef

    doc, ext = plate()
    original = tmp_path / "bracket.fdprt"
    fdef.save(doc, original)
    doc.feature(ext).name = "Changed"
    recovery.Autosaver().save(doc, original)  # left behind by a crash
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.recover()
    restored = window.current
    assert restored is not None and restored.session.path == original
    assert restored.session.is_dirty and window.isWindowModified()
    assert window.windowTitle().startswith("bracket")
    window.open_path(original)  # opening the file again shows the recovered part
    assert window.tabs.count() == 1
    assert window.save()
    assert fdef.load(original).feature(ext).name == "Changed"
    assert not restored.session.is_dirty


def test_export_needs_a_part(qtbot: QtBot, window: MainWindow) -> None:
    window.export("step")
    assert "empty" in window.status.text()


def test_export_during_the_first_rebuild_says_to_wait(qtbot: QtBot, window: MainWindow) -> None:
    """Bug hunt F9: exporting a part that was still rebuilding said it was empty."""
    doc, _ = plate()
    tab = window.add_session(DocumentSession(doc, None, window))
    assert tab.session.is_rebuilding and tab.session.report is None
    window.export("step")
    assert "empty" not in window.status.text()
    assert window.status.text() == strings.EXPORT_WAIT
    tab.session.wait()


def test_built_in_rows_show_only_their_type(qtbot: QtBot, window: MainWindow) -> None:
    """Origin and the default planes show their type icon, no state mark, never grey."""
    from fdcad.ui.tree.row_icons import row_icon

    _open_plate(qtbot, window)
    tree = window.tree
    assert tree is not None
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(0, FID_ROLE) in {"f1", "f2", "f3", "f4"}:
            name = "tree.origin" if item.data(0, FID_ROLE) == "f1" else "tree.plane"
            expected = row_icon(name).pixmap(18).toImage()
            assert item.icon(0).pixmap(18).toImage() == expected, item.text(0)
            assert item.foreground(0).color().name() != "#9aa0a6"


def test_move_feature_refuses_above_planes(qtbot: QtBot, window: MainWindow) -> None:
    """A feature cannot be dropped at or above any default plane."""
    tab, _ = _open_plate(qtbot, window)
    tree = window.tree
    assert tree is not None
    doc = tab.session.document
    ids = [f.id for f in doc.features]
    ext = ids[-1]
    top = ids[:4]  # origin and the three default planes
    tree.move_feature(ext, 0)  # above the origin
    tree.move_feature(ext, 1)  # above the first plane
    assert [f.id for f in doc.features][:4] == top


def test_built_in_cannot_be_moved(qtbot: QtBot, window: MainWindow) -> None:
    """A drag from a built-in row does nothing."""
    tab, _ = _open_plate(qtbot, window)
    tree = window.tree
    assert tree is not None
    doc = tab.session.document
    ids = [f.id for f in doc.features]
    assert not tree.move_feature("f2", 0)  # a default plane
    assert not tree.move_feature("f1", 0)  # the origin
    assert tab.session.undo.count() == 0
    assert [f.id for f in doc.features] == ids


def test_plane_context_menu_has_sketch(qtbot: QtBot, window: MainWindow) -> None:
    """A plane row offers Sketch, not Roll Back to Here."""
    tab, _ = _open_plate(qtbot, window)
    tree = window.tree
    assert tree is not None
    plane = next(f for f in tab.session.document.features if f.type == "plane")
    item = tree.topLevelItem(0)
    while item.data(0, FID_ROLE) != plane.id:
        item = tree.topLevelItem(tree.indexOfTopLevelItem(item) + 1)
    menu = tree._context_menu(tab.session, item)
    assert menu is not None
    texts = [a.text() for a in menu.actions()]
    assert strings.SKETCH in texts
    assert strings.ROLLBACK_HERE not in texts
    assert strings.PARENTS_CHILDREN in texts
    menu.close()


def test_origin_context_menu_has_no_sketch(qtbot: QtBot, window: MainWindow) -> None:
    """The origin is not a plane, so it gets no Sketch action."""
    tab, _ = _open_plate(qtbot, window)
    tree = window.tree
    assert tree is not None
    item = next(
        tree.topLevelItem(i)
        for i in range(tree.topLevelItemCount())
        if tree.topLevelItem(i).data(0, FID_ROLE) == "f1"
    )
    menu = tree._context_menu(tab.session, item)
    assert menu is not None
    texts = [a.text() for a in menu.actions()]
    assert strings.SKETCH not in texts
    assert strings.ROLLBACK_HERE not in texts
    menu.close()


@pytest.mark.parametrize(
    ("name", "chosen", "written"),
    [
        ("plate.step", strings.FILTER_FDEF, "plate.step"),  # the typed suffix wins
        ("plate", strings.FILTER_STEP, "plate.step"),
        ("plate", strings.FILTER_STL, "plate.stl"),
        ("plate", strings.FILTER_IGES, "plate.iges"),  # TR369
        ("plate", strings.FILTER_BREP, "plate.brep"),
        ("plate.ply", strings.FILTER_FDEF, "plate.ply"),
        ("plate", strings.FILTER_GLB, "plate.glb"),
        ("plate", strings.FILTER_OBJ, "plate.obj"),  # TR336
        ("plate", strings.FILTER_DXF3D, "plate.dxf"),  # TR369 (D1010)
    ],
)
def test_save_as_offers_step_stl_and_3mf(
    qtbot: QtBot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    chosen: str,
    written: str,
) -> None:
    """Owner note 2026-10-30: Save As can write a STEP copy (D435)."""
    tab, _ = _open_plate(qtbot, window)
    offered: list[str] = []

    def dialog(_parent: object, _title: str, _default: str, filters: str) -> tuple[str, str]:
        offered.append(filters)
        return str(tmp_path / name), chosen

    monkeypatch.setattr(QFileDialog, "getSaveFileName", dialog)
    assert window.save_as_any()
    for f in (strings.FILTER_FDEF, strings.FILTER_STEP, strings.FILTER_STL, strings.FILTER_3MF):
        assert f in offered[0]
    qtbot.waitUntil(lambda: (tmp_path / written).exists(), timeout=30000)
    qtbot.waitUntil(lambda: "plate" in window.status.text(), timeout=30000)
    assert tab.session.path is None  # the part itself is not saved as an export


@pytest.mark.parametrize("typed", ["plate", "plate.fdef", "plate.fdprt"])
def test_parts_save_as_fdprt(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, typed: str
) -> None:
    """Owner note 2026-10-30: part files are saved as .fdprt (D575)."""
    tab, _ = _open_plate(qtbot, window)
    defaults: list[str] = []

    def dialog(_parent: object, _title: str, default: str, _filters: str) -> tuple[str, str]:
        defaults.append(default)
        return str(tmp_path / typed), strings.FILTER_FDEF

    monkeypatch.setattr(QFileDialog, "getSaveFileName", dialog)
    assert window.save_as_any()
    assert defaults[0].endswith(".fdprt")
    assert tab.session.path == tmp_path / "plate.fdprt" and tab.session.path.exists()
    assert not (tmp_path / "plate.fdef").exists()


@pytest.mark.parametrize(
    ("typed", "kind", "written"),
    [
        ("plate", "stl", "plate.stl"),
        ("v1.2 plate", "step", "v1.2 plate.step"),
        ("v1.2 plate", "3mf", "v1.2 plate.3mf"),
        ("plate.stp", "step", "plate.stp"),
    ],
)
def test_export_adds_the_suffix_to_a_typed_name(
    qtbot: QtBot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    typed: str,
    kind: str,
    written: str,
) -> None:
    """File, Export with a name typed without a suffix wrote a file with no suffix."""
    _open_plate(qtbot, window)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a: (str(tmp_path / typed), ""))
    window.export(kind)
    qtbot.waitUntil(lambda: (tmp_path / written).exists(), timeout=30000)
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == [written]


@pytest.mark.parametrize(
    ("typed", "chosen", "written"),
    [
        ("rev 1.2", strings.FILTER_FDEF, "rev 1.2.fdprt"),
        ("rev 1.2", strings.FILTER_STL, "rev 1.2.stl"),
    ],
)
def test_save_as_adds_the_suffix_to_a_dotted_name(
    qtbot: QtBot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    typed: str,
    chosen: str,
    written: str,
) -> None:
    """Bug hunt F3: "rev 1.2" was saved as "rev 1.fdprt", over any file of that name."""
    _open_plate(qtbot, window)
    other = tmp_path / "rev 1.fdprt"
    other.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / typed), chosen)
    )
    assert window.save_as_any()
    qtbot.waitUntil(lambda: (tmp_path / written).exists(), timeout=30000)
    assert other.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "rev 1.stl").exists()


def test_save_as_asks_before_replacing_a_file_the_dialog_did_not_name(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bug hunt F3: adding the suffix must not silently replace another file."""
    tab, _ = _open_plate(qtbot, window)
    other = tmp_path / "other.fdprt"
    other.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(tmp_path / "other"), strings.FILTER_FDEF),
    )
    asked: list[str] = []

    def answer(_parent: object, _title: str, text: str, *_a: object) -> object:
        asked.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", answer)
    assert not window.save_as_any()
    assert other.read_text(encoding="utf-8") == "keep" and tab.session.path is None
    assert asked and "other.fdprt" in asked[0]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    assert window.save_as_any()
    assert tab.session.path == other and other.read_text(encoding="utf-8") != "keep"


def test_older_fdef_parts_still_open(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    from fdcad.core.io import fdef

    doc, _ = plate()
    old = tmp_path / "old.fdef"
    fdef.save(doc, old)
    assert fdef.is_part_file(old) and fdef.is_part_file(tmp_path / "new.FDPRT")
    assert not fdef.is_part_file(tmp_path / "part.step")
    window.open_path(old)
    assert window.current is not None and window.current.session.path == old
    assert "*.fdprt" in strings.FILTER_PARTS_OPEN and "*.fdef" in strings.FILTER_PARTS_OPEN


def test_recovery_reads_older_fdef_autosaves(tmp_path: Path) -> None:
    from fdcad.core.io import fdef

    folder = recovery.recovery_dir()
    folder.mkdir(parents=True, exist_ok=True)
    doc, _ = plate()
    fdef.save(doc, folder / "older.fdef")  # written by a build before D575
    saver = recovery.Autosaver()
    saver.save(doc, None)
    assert saver.fdef_path.suffix == ".fdprt"
    found = recovery.find_recoverable()
    assert len(found) == 2
    recovery.discard_all(found)
    assert recovery.find_recoverable() == []


_OTHER_FDCAD = """
import sys, time
from fdcad.core.document.model import new_document
from fdcad.ui.main_window.recovery import Autosaver
saver = Autosaver()
saver.save(new_document(), None)
print("saved", flush=True)
time.sleep(120)
"""


def test_recovery_leaves_the_autosaves_of_a_running_fdcad_alone(tmp_path: Path) -> None:
    """Bug hunt F10: starting a second FDCAD offered the first one's live autosaves as
    parts lost in a crash, and deleted them."""
    import os
    import subprocess
    import sys

    env = dict(os.environ, FDCAD_DATA_DIR=str(tmp_path / "data"))
    other = subprocess.Popen(
        [sys.executable, "-c", _OTHER_FDCAD], env=env, stdout=subprocess.PIPE, text=True
    )
    try:
        assert other.stdout is not None and other.stdout.readline().strip() == "saved"
        assert recovery.find_recoverable() == []
        assert len(list(recovery.recovery_dir().glob("*.fdprt"))) == 1
    finally:
        other.kill()  # now it crashed
        other.wait()
    found = recovery.find_recoverable()
    assert len(found) == 1
    recovery.discard_all(found)
    assert recovery.find_recoverable() == []


def test_first_window_fits_a_small_screen() -> None:
    # The window always opened at 1400 x 900, partly off a 1280 x 720 screen (D635).
    from PySide6.QtCore import QSize

    from fdcad.ui.main_window.window import START_SIZE, start_size

    assert start_size(QSize(2560, 1400)) == START_SIZE
    small = start_size(QSize(1280, 680))
    assert small.width() <= 1280 and small.height() <= 680
    assert start_size(None) == START_SIZE


def test_closed_preferences_dialogs_are_freed(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each Preferences dialog stayed alive, and every later OK restyled all of them:
    # after a long session OK took 70 s (round 10e slow sweep, D637).
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.preferences.dialog import PreferencesDialog

    def accept(dialog: PreferencesDialog) -> int:
        dialog.accept()
        return 1

    monkeypatch.setattr(PreferencesDialog, "exec", accept)
    for _ in range(3):
        window.preferences()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    assert window.findChildren(PreferencesDialog) == []


def test_reopened_popups_and_managers_do_not_pile_up(qtbot: QtBot, window: MainWindow) -> None:
    # Each opening made a new Equations manager, Design Table, shortcut bar, view
    # selector or snap popup and kept the old ones (round 10e, D637).
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.equations.dialog import EquationsDialog
    from fdcad.ui.equations.table_dialog import DesignTableDialog
    from fdcad.ui.main_window.shortcut_bar import ShortcutBar
    from fdcad.ui.main_window.snap_popup import SnapOptions
    from fdcad.ui.viewport.view_selector import ViewSelector

    _open_plate(qtbot, window)
    commands = (
        "tools.equations",
        "tools.design_table",
        "ui.shortcut_bar",
        "view.selector",
        "sketch.snap_options",
    )
    for _ in range(3):
        for cid in commands:
            window.commands.trigger(cid)
            qtbot.wait(5)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    for kind in (EquationsDialog, DesignTableDialog, ShortcutBar, ViewSelector, SnapOptions):
        alive = [w for w in QApplication.allWidgets() if isinstance(w, kind)]
        assert len(alive) <= 1, kind.__name__


def test_preferences_ok_restyles_only_when_the_theme_changed(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every OK restyled the whole app twice, even with the same theme (D638).
    from fdcad.ui.main_window import window as window_module
    from fdcad.ui.preferences.dialog import PreferencesDialog
    from fdcad.ui.preferences.settings import Theme

    calls: list[object] = []
    monkeypatch.setattr(window_module, "apply_theme", lambda _app, t: calls.append(t))
    chosen: list[Theme] = []

    def accept(dialog: PreferencesDialog) -> int:
        if chosen:
            dialog.theme_box.setCurrentIndex(dialog.theme_box.findData(chosen[0]))
        dialog.accept()
        return 1

    monkeypatch.setattr(PreferencesDialog, "exec", accept)
    window.preferences()
    assert calls == []
    other = Theme.DARK if window.settings.theme is not Theme.DARK else Theme.LIGHT
    chosen.append(other)
    window.preferences()
    assert calls == [other]


def test_quit_cancel_on_a_later_part_keeps_every_part(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit D3 item 12 (D710): Discard on one part then Cancel on another closed the
    first part and lost its changes."""
    from fdcad.ui.commands.document import RenameFeature

    tabs = []
    for name in ("First", "Second"):
        tab, ext = _open_plate(qtbot, window)
        with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
            tab.session.undo.push(RenameFeature(tab.session, ext, name))
        tabs.append(tab)
    answers = iter([QMessageBox.StandardButton.Discard, QMessageBox.StandardButton.Cancel])
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: next(answers))
    window.close()
    assert window.tabs.count() == 2
    assert all(t.session.is_dirty for t in tabs)


def test_a_stopped_rebuild_says_so_and_export_refuses_the_partial_body(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    """Audit D3 item 4, E item 12.6 (D710): it said "Rebuilt in N s" and exported the
    partial body."""
    tab, _ext = _open_plate(qtbot, window)
    report = tab.session.report
    assert report is not None
    report.cancelled = True
    window._rebuilt(tab, report)
    assert window.status.text() == strings.REBUILD_STOPPED
    target = tmp_path / "part.step"
    window.export("step", target)
    assert window.status.text() == strings.EXPORT_STOPPED
    assert not target.exists()


def test_export_notes_what_the_file_leaves_out(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.core.features.base import FeatureResult, Issue
    from fdcad.ui.main_window.window import export_warning

    tab, ext = _open_plate(qtbot, window)
    doc, report = tab.session.document, tab.session.report
    assert report is not None
    assert export_warning(doc, report) == ""
    report.results[ext] = FeatureResult(None, [Issue(FeatureState.ERROR, "broken")])
    assert export_warning(doc, report).startswith("Note: 1 feature with errors is not in the file.")
    doc.rollback = ext
    assert export_warning(doc, report) == strings.EXPORT_ROLLED_BACK


def test_save_as_onto_a_file_open_in_another_tab_is_refused(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit D3 item 14 (D723): both tabs then shared one path and overwrote each other."""
    first, _ = _open_plate(qtbot, window)
    target = tmp_path / "shared.fdprt"
    first.session.save(target)
    second, _ = _open_plate(qtbot, window)
    assert window.current is second
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    assert not window.save_as()
    assert "open in another tab" in window.status.text()
    assert second.session.path is None


def test_recovery_cancel_keeps_the_copies_and_newer_files_are_not_overwritten(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit D3 item 9 (D724): No deleted every autosave, and a recovered part saved
    over its file even when that file was newer."""
    import os
    import time

    from fdcad.core.io import fdef

    doc, ext = plate()
    original = tmp_path / "bracket.fdprt"
    fdef.save(doc, original)
    doc.feature(ext).name = "Changed"
    recovery.Autosaver().save(doc, original)
    later = time.time() + 60
    os.utime(original, (later, later))  # saved again after the crash's autosave
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    window.recover()
    assert window.tabs.count() == 0 and len(recovery.find_recoverable()) == 1
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.recover()
    restored = window.current
    assert restored is not None and restored.session.path is None
    assert "saved again" in window.status.text()


def test_damaged_autosaves_are_set_aside(tmp_path: Path) -> None:
    folder = recovery.recovery_dir()
    folder.mkdir(parents=True, exist_ok=True)
    bad = folder / "broken.fdprt"
    bad.write_text("{ not json", encoding="utf-8")
    assert recovery.find_recoverable() == []
    assert not bad.exists() and bad.with_name("broken.fdprt.damaged").exists()


def test_autosave_failure_is_said_once(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit D3 item 10 (D724): autosave failures were swallowed with no sign."""
    from fdcad.core.io import fdef
    from fdcad.ui.commands.document import RenameFeature

    tab, ext = _open_plate(qtbot, window)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.push(RenameFeature(tab.session, ext, "Changed"))

    def full(*_a: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(fdef, "save_text", full)
    window.autosave()
    tab.autosaver.join()
    window.autosave()  # the failure seen by the first write is reported now
    tab.autosaver.join()
    assert "Autosave failed" in window.status.text()


def test_mac_backspace_deletes_the_selected_feature(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit C item 3 (D732): only forward delete removed a feature on a Mac."""
    from PySide6.QtCore import Qt

    import fdcad.ui.tree.feature_tree as ft

    _tab, ext = _open_plate(qtbot, window)
    tree = window.tree
    assert tree is not None
    tree.select(ext)
    deleted: list[str] = []
    monkeypatch.setattr(tree, "delete", deleted.append)
    monkeypatch.setattr(ft.sys, "platform", "darwin")
    qtbot.keyClick(tree, Qt.Key.Key_Backspace)
    assert deleted == [ext]


def test_a_tab_title_keeps_an_ampersand(window: MainWindow, tmp_path: Path) -> None:
    """Audit C item 11 (D738): "Nut & Bolt.fdprt" showed as "Nut  Bolt" with B underlined."""
    from fdcad.core.io import fdef

    doc, _ = plate()
    fdef.save(doc, tmp_path / "Nut & Bolt.fdprt")
    window.open_path(tmp_path / "Nut & Bolt.fdprt")
    assert "&&" in window.tabs.tabText(window.tabs.currentIndex())


def test_export_asks_before_replacing_the_name_with_its_ending(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit D3 item 17 (D744): "part" became "part.stl" and replaced it without asking."""
    _open_plate(qtbot, window)
    existing = tmp_path / "part.stl"
    existing.write_bytes(b"old")
    asked: list[str] = []
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "part"), "")
    )

    def no(*args: object, **kwargs: object) -> QMessageBox.StandardButton:
        asked.append(str(args[2]))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", no)
    window.export("stl")
    assert asked and "part.stl" in asked[0]
    assert existing.read_bytes() == b"old"


def test_quitting_waits_for_a_running_export(window: MainWindow) -> None:
    """Audit D3 item 24 (D744): quitting did not wait for an export being written."""
    window.feedback.begin("export")
    assert not window._wait_for_export(limit_ms=100)
    assert window.status.text() == strings.EXPORT_STILL_RUNNING
    window.feedback.end("export")
    assert window._wait_for_export(limit_ms=100)
