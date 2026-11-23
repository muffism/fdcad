"""The app sweep of the Phase 6 bug hunt (docs/BUG_HUNT.md, D490).

Every command with each kind of selection, every right click menu, the sketch
tools, every preference page, Save and Save As, and the command tabs. Each step
must not raise, must finish in time, and Undo then Redo must give back the same
file text. The quick tests run by default on one part; the full sweep over every
sample part and graph sample is marked slow (run it with ``--run-slow``).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.samples.graphs import SAMPLE_DIR as GRAPH_DIR
from fdcad.samples.make import SAMPLE_DIR
from fdcad.ui import strings
from fdcad.ui.command_tabs.ribbon import RibbonPanel
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.ui.sweep_support import (
    SELECTION_KINDS,
    Dialogs,
    Sweep,
    close_part,
    close_window,
    idle,
    install_dialogs,
    make_window,
    menu_items,
    open_part,
    pump,
    run_commands,
    settle,
    shapes_of,
)

SAMPLES = sorted(SAMPLE_DIR.glob("*.fdprt")) + sorted(GRAPH_DIR.glob("*.fdprt"))
PLATE = SAMPLE_DIR / "plate_with_holes.fdprt"


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def dialogs(monkeypatch: pytest.MonkeyPatch) -> Dialogs:
    return install_dialogs(monkeypatch)


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path, dialogs: Dialogs) -> Iterator[MainWindow]:
    win = make_window(tmp_path)
    yield win
    close_window(win)


def _report(sweep: Sweep) -> None:
    assert sweep.steps > 0
    assert not sweep.failures, f"{len(sweep.failures)} failures:\n\n" + "\n\n".join(
        sweep.failures[:20]
    )


# Commands ----------------------------------------------------------------------------------


def test_every_command_on_a_part(window: MainWindow, dialogs: Dialogs) -> None:
    """Quick sweep: every command with nothing selected, opened and accepted with its
    defaults. The slow sweep adds Cancel and the other selection kinds."""
    tab = open_part(window, PLATE)
    sweep = Sweep(window, tab, dialogs)
    run_commands(sweep, ("none",), (True,))
    _report(sweep)


#: The gearbox is left out of the full command sweep (D1100): every command with every
#: selection on 319 features would take many hours; its own tests build it three ways
#: and check where its material is (test_gearbox_part.py).
SWEPT_SAMPLES = [p for p in SAMPLES if p.stem != "gearbox"]


@pytest.mark.slow
@pytest.mark.parametrize("path", SWEPT_SAMPLES, ids=lambda p: p.stem)
def test_every_command_on_every_sample(window: MainWindow, dialogs: Dialogs, path: Path) -> None:
    """Full sweep: every command, every selection kind, Cancel and OK."""
    tab = open_part(window, path)
    sweep = Sweep(window, tab, dialogs)
    run_commands(sweep, SELECTION_KINDS, (False, True))
    _report(sweep)


# Right click menus -------------------------------------------------------------------------


#: A tree longer than this has its row menus swept on the first and last EDGE_ROWS rows
#: only (D2607): the items are the same on every row, and on generated_200 (about 200
#: rows) each row took 20 to 40 s, the whole test two hours or more.
MOST_ROWS = 60
EDGE_ROWS = 20


def _menu_sweep(window: MainWindow, sweep: Sweep) -> None:
    win, tab = window, sweep.tab
    shapes = shapes_of(tab)
    name = tab.session.title.rstrip("*")
    targets: list[tuple[str, list[object], str | None]] = [("empty space", [], None)]
    targets += [(k, [shapes[k]], None) for k in ("face", "edge", "vertex") if k in shapes]
    planes = [f.id for f in tab.session.document.features if f.type in ("plane", "ref_plane")]
    if planes:
        targets.append(("plane", [], planes[0]))
    for target, picked, plane in targets:
        menu = win.context_menus.build_view_menu(tab, picked, plane=plane, pos=QPointF(5, 5))
        for path, _action in list(menu_items(menu)):
            for accept in (False, True):

                def run(p: str = path, s: list[object] = picked, pl: str | None = plane) -> None:
                    win._selection_changed(tab, s)
                    m = win.context_menus.build_view_menu(tab, s, plane=pl, pos=QPointF(5, 5))
                    found = dict(menu_items(m)).get(p)
                    if found is not None:
                        found.trigger()

                ok = "OK" if accept else "Cancel"
                sweep.step(f"{name}: view menu on {target}, {path}, {ok}", run, accept)
    tree = win.tree
    assert tree is not None
    count = len(tree.all_items())
    rows = (
        range(count)
        if count <= MOST_ROWS
        else [*range(EDGE_ROWS), *range(count - EDGE_ROWS, count)]
    )
    for row in rows:
        settle(win, tab)
        items = tree.all_items()
        if row >= len(items):
            break
        row_name = items[row].text(0)
        menu = tree._context_menu(tab.session, items[row])
        if menu is None:
            continue
        for path, _action in list(menu_items(menu)):
            for accept in (False, True):

                def run_row(r: int = row, p: str = path) -> None:
                    now = tree.all_items()
                    if r >= len(now):
                        return
                    tree.setCurrentItem(now[r])
                    m = tree._context_menu(tab.session, now[r])
                    found = dict(menu_items(m)).get(p) if m is not None else None
                    if found is not None:
                        found.trigger()

                ok = "OK" if accept else "Cancel"
                sweep.step(f"{name}: tree menu on {row_name}, {path}, {ok}", run_row, accept)


def test_right_click_menus_on_a_part(window: MainWindow, dialogs: Dialogs) -> None:
    """Every item of the view and tree menus of the plate, Cancel and OK."""
    tab = open_part(window, PLATE)
    sweep = Sweep(window, tab, dialogs)
    _menu_sweep(window, sweep)
    _report(sweep)


#: The gearbox is left out of the right click sweep too (D2607): Suppress, Roll Back
#: and Delete on each of its 319 tree rows each rebuild the part from that feature on.
@pytest.mark.slow
@pytest.mark.parametrize("path", SWEPT_SAMPLES, ids=lambda p: p.stem)
def test_right_click_menus_on_every_sample(
    window: MainWindow, dialogs: Dialogs, path: Path
) -> None:
    tab = open_part(window, path)
    sweep = Sweep(window, tab, dialogs)
    _menu_sweep(window, sweep)
    _report(sweep)


# Sketch tools ------------------------------------------------------------------------------


def _new_part(window: MainWindow) -> DocumentTab:
    tab = window.add_session(DocumentSession(new_document(), None, window))
    assert idle(tab)
    return tab


def _start_sketch(window: MainWindow, tab: DocumentTab) -> object:
    mode = window.sketch_mode
    assert mode is not None
    front = next(f.id for f in tab.session.document.features if f.name == "Front Plane")
    mode.start(plane_id=front)
    pump(20)
    canvas = mode.canvas
    assert canvas is not None
    canvas.resize(800, 600)
    canvas.scale, canvas.center = 4.0, (20.0, 15.0)
    return canvas


def _click(qtbot: QtBot, canvas: object, x: float, y: float) -> None:
    # A tool panel that grows can resize the view on the first move, so the point is
    # worked out again once the move has settled. That takes more than one turn of the
    # event loop: the panel is fitted to the left panel the turn after its layout
    # changes (D2791), and only then does the view get its size. With one turn the
    # click went to where the point had been, and Offset found no line under it.
    for _ in range(2):
        pump(5)
        p = canvas.to_screen((x, y))  # type: ignore[attr-defined]
        at = QPoint(round(p.x()), round(p.y()))
        qtbot.mouseMove(canvas, at)  # type: ignore[arg-type]
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos=at)  # type: ignore[arg-type]


def _shapes(qtbot: QtBot, canvas: object) -> None:
    """A 40 x 30 rectangle and a circle inside it."""
    canvas.set_tool("corner_rectangle")  # type: ignore[attr-defined]
    _click(qtbot, canvas, 0, 0)
    _click(qtbot, canvas, 40, 30)
    canvas.set_tool("circle")  # type: ignore[attr-defined]
    _click(qtbot, canvas, 20, 15)
    _click(qtbot, canvas, 25, 15)
    canvas.set_tool(None)  # type: ignore[attr-defined]


#: Clicks each tool gets: on the edges, beside them, at the corners and inside.
CLICKS = [(20, 0), (20, -5), (40, 15), (45, 15), (0, 30), (20, 15), (10, 25), (30, 5)]


def test_every_sketch_tool_on_a_fresh_sketch(
    qtbot: QtBot, window: MainWindow, dialogs: Dialogs
) -> None:
    """Each sketch command on a new sketch with a rectangle and a circle: click it
    around the shapes, stop it, exit the sketch, then Undo and Redo."""
    tab = _new_part(window)
    sweep = Sweep(window, tab, dialogs)
    tools = sorted(
        c
        for c in window.commands.actions
        if c.startswith("sketch.") and c not in ("sketch.sketch", "sketch.exit", "sketch.discard")
    )
    assert len(tools) > 25
    for cid in tools:

        def run(c: str = cid) -> None:
            canvas = _start_sketch(window, tab)
            _shapes(qtbot, canvas)
            canvas.selection = list(canvas.edit.sketch.entities)  # type: ignore[attr-defined]
            window.commands.trigger(c)
            pump(5)
            for x, y in CLICKS:
                _click(qtbot, canvas, x, y)
            box = getattr(canvas, "value_box", None)
            if box is not None:
                box.ok.click()
            qtbot.keyClick(canvas, Qt.Key.Key_Escape)  # type: ignore[arg-type]
            qtbot.keyClick(canvas, Qt.Key.Key_Escape)  # type: ignore[arg-type]
            if window.sketch_mode is not None and window.sketch_mode.is_open:
                assert window.sketch_mode.accept()

        sweep.step(f"sketch tool {cid}", run, True)
    _report(sweep)


def test_draw_dimension_trim_offset_and_exit(qtbot: QtBot, window: MainWindow) -> None:
    """The main sketch steps in a row, each checked, then one Undo removes the sketch."""
    tab = _new_part(window)
    canvas = _start_sketch(window, tab)
    _shapes(qtbot, canvas)
    sketch = canvas.edit.sketch  # type: ignore[attr-defined]
    assert len(sketch.entities) >= 5
    canvas.set_tool("dimension")  # type: ignore[attr-defined]
    _click(qtbot, canvas, 20, 0)
    _click(qtbot, canvas, 20, -8)
    box = canvas.value_box  # type: ignore[attr-defined]
    assert box is not None
    box.edit.setText("50")
    box.ok.click()
    canvas.set_tool(None)  # type: ignore[attr-defined]
    assert len(sketch.dimensions) == 1
    lines = len(sketch.entities)
    canvas.set_tool("trim")  # type: ignore[attr-defined]
    _click(qtbot, canvas, 0, 15)  # the left edge goes
    canvas.set_tool(None)  # type: ignore[attr-defined]
    assert len(canvas.edit.sketch.entities) < lines  # type: ignore[attr-defined]
    canvas.set_tool("offset")  # type: ignore[attr-defined]
    _click(qtbot, canvas, 20, 30)
    _click(qtbot, canvas, 20, 35)
    canvas.set_tool(None)  # type: ignore[attr-defined]
    assert any(r.type == "offset" for r in canvas.edit.sketch.relations)  # type: ignore[attr-defined]
    mode = window.sketch_mode
    assert mode is not None
    before = tab.session.undo.index()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert mode.accept()
    assert tab.session.undo.index() == before + 1
    assert tab.session.document.features[-1].type == "sketch"
    tab.session.undo.undo()
    assert tab.session.document.features[-1].type != "sketch"


def test_sketch_right_click_menus(qtbot: QtBot, window: MainWindow) -> None:
    """Every sketch menu item, in empty space and on each kind of item."""
    tab = _new_part(window)
    canvas = _start_sketch(window, tab)
    _shapes(qtbot, canvas)
    edit = canvas.edit  # type: ignore[attr-defined]
    targets = [None, *list(edit.sketch.entities)[:4]]
    for target in targets:
        canvas.selection = [target] if target else []  # type: ignore[attr-defined]
        menu = window.context_menus.build_sketch_menu(canvas, None)  # type: ignore[arg-type]
        for path, _action in list(menu_items(menu)):
            if path in (strings.EXIT_SKETCH, "Discard Changes"):
                continue
            canvas.selection = [t for t in [target] if t and t in edit.sketch.entities]  # type: ignore[attr-defined]
            again = window.context_menus.build_sketch_menu(canvas, None)  # type: ignore[arg-type]
            found = dict(menu_items(again)).get(path)
            if found is not None:
                found.trigger()
                box = getattr(canvas, "value_box", None)
                if box is not None:
                    box.ok.click()
            canvas.set_tool(None)  # type: ignore[attr-defined]
    mode = window.sketch_mode
    assert mode is not None and mode.is_open
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert mode.accept()


# Preferences, files and command tabs -------------------------------------------------------


def _change_every_field(dialog: object) -> None:
    tabs = dialog.tabs  # type: ignore[attr-defined]
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        page = tabs.widget(i)
        for combo in page.findChildren(QComboBox):
            if combo.isEnabled() and combo.count() > 1:
                combo.setCurrentIndex((combo.currentIndex() + 1) % combo.count())
        for box in page.findChildren(QCheckBox):
            if box.isEnabled():
                box.toggle()
        for spin in page.findChildren(QSpinBox) + page.findChildren(QDoubleSpinBox):
            if spin.isEnabled():
                spin.setValue(spin.value() + spin.singleStep())


def test_every_preference_page_cancel_and_ok(window: MainWindow, dialogs: Dialogs) -> None:
    """Change every field on every page: Cancel keeps the settings, OK stores them,
    and the window applies them without an error."""
    from fdcad.ui.preferences.dialog import PreferencesDialog

    store = window.settings.store
    stored = {k: store.value(k) for k in store.allKeys()}
    dialog = PreferencesDialog(window.settings, window)
    _change_every_field(dialog)
    dialog.reject()
    assert {k: store.value(k) for k in store.allKeys()} == stored
    dialog = PreferencesDialog(window.settings, window)
    _change_every_field(dialog)
    dialog.accept()
    assert {k: store.value(k) for k in store.allKeys()} != stored
    dialogs.accept = True
    window.commands.trigger("ui.preferences")  # OK with these values, applied to the window
    pump(10)


@pytest.mark.parametrize(
    ("kind", "name", "chosen"),
    [
        ("fdef", "copy.fdprt", ""),
        ("step", "copy.step", ""),
        ("stl", "copy.stl", ""),
        ("3mf", "copy.3mf", ""),
        ("step", "copy", strings.FILTER_STEP),
    ],
)
def test_save_as_each_type_and_reopen(
    window: MainWindow, dialogs: Dialogs, tmp_path: Path, kind: str, name: str, chosen: str
) -> None:
    """File, Save As writes each type; a saved part reopens with the same text."""
    tab = open_part(window, PLATE)
    target = tmp_path / name
    dialogs.save_path, dialogs.save_filter = str(target), chosen
    assert window.commands.trigger("file.save_as")
    idle(tab, 60)
    written = target if target.suffix else target.with_suffix(f".{kind}")
    assert written.exists() and written.stat().st_size > 0, window.status.text()
    if kind != "fdef":
        assert tab.session.path is None  # an export leaves the part unsaved
        return
    assert tab.session.path == written and not tab.session.is_dirty
    text = fdef.dumps(tab.session.document)
    assert window.commands.trigger("file.save")
    close_part(window, tab)
    window.open_path(written)
    reopened = window.current
    assert reopened is not None and idle(reopened, 60)
    assert fdef.dumps(reopened.session.document) == text
    report = reopened.session.report
    assert report is not None and report.body is not None


def test_every_command_tab_button_runs_a_swept_command(window: MainWindow) -> None:
    """Every button and dropdown entry of every command tab is a window command with a
    handler, so the command sweep above runs it. Choosing a dropdown entry puts it on
    its button."""
    known = {id(a): cid for cid, a in window.commands.actions.items()}
    tabs = window.command_tabs
    seen: set[str] = set()
    for i in range(tabs.count()):
        panel = tabs.widget(i)
        assert isinstance(panel, RibbonPanel), tabs.tabText(i)
        for button in panel.buttons():
            actions = list(button.group_actions)
            for action in actions:
                cid = known.get(id(action))
                assert cid is not None, f"{tabs.tabText(i)}: '{action.text()}' is not a command"
                assert action.receivers("2triggered(bool)") > 0, cid
                seen.add(cid)
            if len(actions) > 1:
                menu = button.menu()
                assert menu is not None and menu.actions() == actions
                actions[-1].trigger()
                settle_all(window)
                assert button.defaultAction() is actions[-1], actions[-1].text()
    assert len(seen) > 100
    assert seen <= set(window.commands.actions)


def settle_all(window: MainWindow) -> None:
    """Leave whatever a command opened when no part is open."""
    mode = window.sketch_mode
    if mode is not None and mode.picker.active:
        mode.picker.cancel()
    if window.panel is not None and window.panel.is_editing:
        window.panel.reject()
