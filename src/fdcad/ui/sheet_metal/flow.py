"""Sheet Metal tab: starting the tools, the flatten toggle, bend tables and flat export.

The main window calls ``register`` before it builds the command tabs and
``build_tab`` to make the Sheet Metal tab. Every document change is one
undoable command (CLAUDE.md rule 3); exports run on the thread pool
(CLAUDE.md rule 2).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import QFileDialog, QLabel

from fdcad.core.document.dependencies import BUILT_IN_COUNT
from fdcad.core.document.model import Document, Feature
from fdcad.core.kernel import kernel_job
from fdcad.ui import strings_sheetmetal as text
from fdcad.ui.body_tools.flow import new_feature
from fdcad.ui.sheet_metal import forms as _forms  # noqa: F401  (adds the panels)
from fdcad.ui.strings import clause

if TYPE_CHECKING:
    from PySide6.QtGui import QAction

    from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
    from fdcad.core.rebuild.engine import RebuildReport
    from fdcad.ui.command_tabs.ribbon import RibbonPanel
    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.session import DocumentSession

#: Command id to the feature type it starts.
FEATURE_COMMANDS = {
    "feature.base_flange": "base_flange",
    "feature.edge_flange": "edge_flange",
    "feature.sketched_bend": "sketched_bend",
    "feature.hem": "hem",
    "feature.miter_flange": "miter_flange",
    "feature.jog": "jog",
    "feature.closed_corner": "closed_corner",
    "feature.break_corner": "break_corner",
    "feature.rip": "rip",
    "feature.tab_slot": "tab_slot",
    "feature.convert_sheet": "convert_sheet",
    "feature.insert_bends": "insert_bends",
    "feature.cross_break": "cross_break",
    "feature.unfold": "unfold",
    "feature.fold": "fold",
    "feature.form_tool": "form_tool",
    "feature.gusset": "gusset",  # TR12
    "feature.flat_marks": "flat_marks",
    "feature.stamp": "stamp",  # TR77 (D1816)
    "feature.perforation": "perforation",
    "feature.extend_wall": "extend_wall",
    "feature.sheet_corner_relief": "sheet_corner_relief",
    "feature.edit_bends": "edit_bends",
    "feature.sheet_tab": "sheet_tab",
}
COMMANDS = (
    *FEATURE_COMMANDS,
    "feature.sheet_metal",
    "feature.bend_table",
    "feature.gauge_table",
    "feature.flatten",
    "file.export_flat",
    "feature.bend_list",
    "feature.sheet_rules",
)
#: Types that start a sheet metal part (they add the folder first, D330 and D547).
STARTERS = ("base_flange", "convert_sheet", "insert_bends")
#: Types whose panel starts with the newest unused sketch.
SKETCH_TYPES = (
    "base_flange",
    "sketched_bend",
    "miter_flange",
    "jog",
    "rip",
    "form_tool",
    "sheet_tab",
    "perforation",
    "flat_marks",
    "stamp",
)
#: Types that take the selected edges as their ``edges`` pick.
EDGE_TYPES = ("edge_flange", "hem", "miter_flange", "break_corner")

#: Sheet Metal tab layout (format of ``command_tabs/tabs.py``).
SHEET_GROUPS: list[tuple[str, list[str | list[str]], list[list[str | list[str]]]]] = [
    (
        text.GROUP_SHEET,
        ["feature.base_flange", "feature.edge_flange", "feature.sketched_bend"],
        [
            [
                "feature.sheet_metal",
                "feature.sheet_rules",
                "feature.bend_table",
                "feature.gauge_table",
                "feature.edit_bends",
            ]
        ],
    ),
    (
        text.GROUP_FLANGES,
        ["feature.miter_flange", "feature.hem"],
        [["feature.jog", "feature.sheet_tab", "feature.extend_wall"]],
    ),
    (
        text.GROUP_CORNERS,
        [],
        [
            [
                "feature.closed_corner",
                "feature.break_corner",
                "feature.gusset",
                "feature.sheet_corner_relief",
            ]
        ],
    ),
    (
        text.GROUP_CUTS,
        [],
        [
            [
                "feature.rip",
                "feature.tab_slot",
                "feature.cross_break",
                "feature.perforation",
                "feature.flat_marks",
            ]
        ],
    ),
    (
        text.GROUP_CONVERT_TAB,
        [],
        [["feature.convert_sheet", "feature.insert_bends"]],
    ),
    (text.GROUP_FORMS, ["feature.form_tool", "feature.stamp"], []),
    (
        text.GROUP_FLAT,
        ["feature.flatten"],
        [["file.export_flat", "feature.bend_list", "feature.unfold", "feature.fold"]],
    ),
]
TAB_NAME = "sheet_metal"


def build_tab(actions: dict[str, QAction]) -> RibbonPanel:
    """The Sheet Metal command tab."""
    from fdcad.ui.command_tabs.tabs import build_panel

    return build_panel(TAB_NAME, SHEET_GROUPS, actions)


def register(window: MainWindow) -> None:
    """Add the sheet metal commands to the window (before the command tabs are built)."""
    from functools import partial

    handlers: dict[str, Callable[[], object]] = {
        "feature.sheet_metal": partial(edit_parameters, window),
        "feature.bend_table": partial(load_bend_table, window),
        "feature.gauge_table": partial(load_gauge_table, window),
        "feature.flatten": partial(toggle_flatten, window),
        "file.export_flat": partial(export_flat, window),
        "feature.bend_list": partial(bend_table, window),
        "feature.sheet_rules": partial(sheet_rules, window),
    }
    for cid, ftype in FEATURE_COMMANDS.items():
        handlers[cid] = partial(start, window, ftype)
    for cid, handler in handlers.items():
        if cid not in window.commands.actions:
            window.commands.add(cid, handler, repeatable=cid in FEATURE_COMMANDS)


# Finding things -------------------------------------------------------------------


def folder_of(doc: Document) -> Feature | None:
    """The Sheet Metal folder, if the part has one."""
    return next((f for f in doc.features if f.type == "sheet_metal"), None)


def folders(doc: Document) -> list[Feature]:
    """Every Sheet Metal folder of the part: one per sheet body (TR281, D2312)."""
    return [f for f in doc.features if f.type == "sheet_metal"]


def _folder_ref(feature: Feature) -> str:
    ref = feature.refs.get("sheet_metal")
    return str(ref.get("feature", "")) if isinstance(ref, dict) else ""


def free_folder(doc: Document) -> Feature | None:
    """A Sheet Metal folder that has no sheet yet, or None (D2312)."""
    used = {_folder_ref(f) for f in doc.features if f.type in STARTERS and not f.suppressed}
    if len(folders(doc)) == 1 and used:
        used.add(folders(doc)[0].id)  # a sheet made without a folder pick (old parts)
    return next((f for f in reversed(folders(doc)) if f.id not in used), None)


def folder_for(tab: DocumentTab) -> Feature | None:
    """The folder of the sheet picked in the view, else of the newest sheet (D2312)."""
    doc = tab.session.document
    report = tab.session.report
    body = report.body if report is not None else None
    if body is not None:
        import re

        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
        from OCP.TopoDS import TopoDS

        for shape in tab.selection:
            kind = shape.ShapeType()
            name = (
                body.primary_name(TopoDS.Face(shape)) if kind == TopAbs_FACE
                else body.edge_name(TopoDS.Edge(shape)) if kind == TopAbs_EDGE
                else None
            )  # fmt: skip
            match = re.search(r"(f\d+)/", name or "")
            if match is None:
                continue
            try:
                maker = doc.feature(match.group(1))
            except KeyError:
                continue
            fid = _folder_ref(maker)
            if fid:
                return next((f for f in folders(doc) if f.id == fid), None)
    for f in reversed(doc.features):
        if f.type in STARTERS and not f.suppressed and _folder_ref(f):
            return next((g for g in folders(doc) if g.id == _folder_ref(f)), folder_of(doc))
    return folder_of(doc)


def flat_of(doc: Document) -> Feature | None:
    """The Flat Pattern feature, if the part has one."""
    return next((f for f in doc.features if f.type == "flatten"), None)


def has_sheet(doc: Document) -> bool:
    """True when the part has a feature that starts the sheet (Base Flange or a conversion)."""
    return any(f.type in STARTERS for f in doc.features)


def flat_result(report: RebuildReport | None, doc: Document) -> FlatResult | None:
    """The Flat Pattern's result, when it built."""
    from fdcad.core.features.sheetmetal.flat_pattern import FlatResult

    flat = flat_of(doc)
    if report is None or flat is None:
        return None
    result = report.results.get(flat.id)
    return result if isinstance(result, FlatResult) else None


def bend_line_shapes(report: RebuildReport | None) -> list[Any]:
    """Bend lines (while flat) and cross break lines to draw in the view."""
    from fdcad.core.features.sheetmetal.flat_pattern import FlatResult

    if report is None:
        return []
    out = []
    for r in report.results.values():
        if isinstance(r, FlatResult):
            out += [e for e in (r.bend_edges, r.mark_edges) if e is not None]
    return out


def _unused_sketch(doc: Document) -> str | None:
    """The newest sketch no feature uses yet, to start a panel with."""
    used: set[str] = set()
    for f in doc.features:
        ref = f.refs.get("sketch")
        if isinstance(ref, dict) and isinstance(ref.get("feature"), str):
            used.add(ref["feature"])
    for f in reversed(doc.features):
        if f.type == "sketch" and f.id not in used:
            return f.id
    return None


# Commands -------------------------------------------------------------------------


def _ready(window: MainWindow) -> DocumentTab | None:
    tab, panel = window.current, window.panel
    if tab is None or panel is None:
        return None
    if window.sketch_mode is not None and window.sketch_mode.is_open:
        window.status.setText("Exit the sketch first.")
        return None
    if panel.is_editing:
        panel.reject()
    return tab


def add_folder(session: DocumentSession) -> Feature:
    """Add the Sheet Metal folder just below the default planes (one undoable step)."""
    from fdcad.core.features.sheetmetal.params import new_sheet_metal
    from fdcad.ui.commands.document import AddFeature

    doc = session.document
    folder = new_sheet_metal(doc)
    index = min(BUILT_IN_COUNT, len(doc.features))
    existing = folders(doc)
    if existing:  # a later sheet body's folder goes after the others (TR281, D2312)
        index = doc.features.index(existing[-1]) + 1
    command = AddFeature(session, folder, index)
    command.setText(text.ADD_FOLDER_UNDO)
    session.undo.push(command)
    return folder


def add_flat_pattern(
    session: DocumentSession, flattened: bool = False, folder: str | None = None
) -> Feature:
    """Add the Flat Pattern at the end of the tree (one undoable step). ``folder`` names
    the sheet it flattens when the part has several (TR281, D2312)."""
    from fdcad.ui.commands.document import AddFeature

    doc = session.document
    refs = {"sheet_metal": {"feature": folder}} if folder else {}
    flat = new_feature(doc, "flatten", {"flattened": flattened}, refs)
    flat.name = text.TYPE_NAMES["flatten"]
    command = AddFeature(session, flat)  # just above a rollback bar (D719)
    command.setText(text.ADD_FLAT_UNDO)
    session.undo.push(command)
    return flat


def start(window: MainWindow, ftype: str) -> bool:
    """Open the panel for a new sheet metal feature."""
    tab, panel = _ready(window), window.panel
    if tab is None or panel is None:  # _ready checks both
        return False
    session = tab.session
    doc = session.document
    label = text.TYPE_NAMES[ftype]
    if ftype not in STARTERS and not has_sheet(doc):
        window.status.setText(text.NEEDS_SHEET.format(tool=label))
        return False
    # TR281 (D2312): a start goes in a folder without a sheet; a part whose folders all
    # have one gets a new folder, asked for first like the first one. Other tools take
    # the folder of the sheet picked in the view, else the newest sheet's.
    folder = free_folder(doc) if ftype in STARTERS else folder_for(tab)
    if folder is None:
        # First sheet metal feature: ask for the part's sheet values first (D330).
        another = bool(folders(doc))  # a new sheet body beside the first (D2312)
        folder = add_folder(session)
        added_at = session.undo.index()

        def next_step() -> None:
            # OK opens the Base Flange panel; Cancel takes the new folder back (B2).
            if panel.accepted:
                start(window, ftype)
            elif session.undo.index() == added_at:
                session.undo.undo()

        _once(panel.finished, next_step)
        panel.begin(session, doc.feature(folder.id), is_new=False)
        window._left_tab(1)
        window.status.setText(text.NEW_SHEET if another else text.FIRST_SHEET)
        return True
    refs: dict[str, Any] = {"sheet_metal": {"feature": folder.id}}
    if ftype in SKETCH_TYPES:
        sketch = _unused_sketch(doc)
        if sketch is not None:
            refs["sketch"] = {"feature": sketch}
    if ftype in EDGE_TYPES:
        picked = _edge_refs(tab)
        if picked:
            refs["edges"] = picked
    if ftype == "fold":
        unfold = open_unfold(doc)
        if unfold is None:
            window.status.setText(text.NO_UNFOLD)
            return False
        refs["unfold"] = {"feature": unfold}
    feature = new_feature(doc, ftype, {}, refs)
    if ftype in STARTERS:
        _once(panel.finished, lambda: _ensure_flat_pattern(session))
    panel.begin(session, feature, is_new=True, preset=True)  # TR326
    window._left_tab(1)
    _connect(window, tab)
    return True


def open_unfold(doc: Document) -> str | None:
    """The newest Unfold that no Fold closes yet (D547)."""
    closed = set()
    found: str | None = None
    for f in doc.features:
        if f.type == "fold":
            ref = f.refs.get("unfold")
            if isinstance(ref, dict) and isinstance(ref.get("feature"), str):
                closed.add(ref["feature"])
            elif found is not None:
                closed.add(found)
        if f.type == "unfold":
            found = f.id
    open_ones = [f.id for f in doc.features if f.type == "unfold" and f.id not in closed]
    return open_ones[-1] if open_ones else None


def _once(signal: Any, slot: Callable[[], object]) -> None:
    """Connect ``slot`` to ``signal`` for one emission only."""

    def fire() -> None:
        signal.disconnect(fire)
        slot()

    signal.connect(fire)


def _ensure_flat_pattern(session: DocumentSession) -> None:
    """A sheet metal part always ends with a Flat Pattern (P5.5 item 1)."""
    doc = session.document
    if has_sheet(doc) and flat_of(doc) is None:
        add_flat_pattern(session)
        return
    # TR281 (D2312): with several sheets each folder gets its own Flat Pattern.
    if len(folders(doc)) < 2:
        return
    flats = [f for f in doc.features if f.type == "flatten"]
    covered = {_folder_ref(f) for f in flats}
    if "" in covered:  # the first Flat Pattern, made before a folder was named on it
        covered.add(_folder_ref(next(f for f in doc.features if f.type in STARTERS)))
    for folder in folders(doc):
        has = any(_folder_ref(f) == folder.id for f in doc.features if f.type in STARTERS)
        if has and folder.id not in covered:
            add_flat_pattern(session, folder=folder.id)


def _edge_refs(tab: DocumentTab) -> list[dict[str, Any]]:
    from OCP.TopAbs import TopAbs_EDGE

    from fdcad.core.naming.select import reference_for

    report = tab.session.report
    body = report.body if report is not None else None
    if body is None:
        return []
    out = []
    for shape in tab.selection:
        if shape.ShapeType() == TopAbs_EDGE:
            ref = reference_for(body, shape)
            if ref is not None:
                out.append(ref)
    return out


def _connect(window: MainWindow, tab: DocumentTab) -> None:
    from fdcad.ui.body_tools import flow as phase3

    phase3._connect_form(window, tab)


def edit(window: MainWindow, fid: str) -> bool:
    """Open a sheet metal feature in the panel; the Flat Pattern also shows its size."""
    tab = _ready(window)
    if tab is None:
        return False
    feature = tab.session.document.feature(fid)
    panel = window.panel
    if panel is None:  # _ready checked it
        return False
    panel.begin(tab.session, feature, is_new=False)
    window._left_tab(1)
    _connect(window, tab)
    if feature.type == "flatten":
        show_flat_size(window, tab)
    return True


def show_flat_size(window: MainWindow, tab: DocumentTab) -> QLabel | None:
    """Add the flat size row (length x width, along the grain) to the open panel."""
    form = getattr(window.panel, "body_form", None)
    if form is None or not form.groups:
        return None
    result = flat_result(tab.session.report, tab.session.document)
    label = QLabel(flat_size_text(result))
    label.setObjectName("flat_size")
    rows = form.groups[0][0].form
    rows.addRow(text.FLAT_SIZE, label)
    if result is not None:  # quoting data (TR172, D1106)
        for name, value in quote_rows(result):
            row = QLabel(value)
            row.setObjectName(f"quote_{name}")
            rows.addRow(text.QUOTE_LABELS[name], row)
    return label


def quote_rows(result: FlatResult) -> list[tuple[str, str]]:
    """The quoting values as the panel shows them: (name, text) in mm."""
    from fdcad.core.features.sheetmetal.quote import QUOTE_NAMES

    out = []
    for name in QUOTE_NAMES[:5]:
        value = result.extras.get(name)
        if not isinstance(value, int | float):
            continue
        if name in ("cut_outs", "bends"):
            out.append((name, f"{value:.0f}"))
        elif name == "blank_area":
            out.append((name, f"{value:.2f} mm\u00b2"))
        else:
            out.append((name, f"{value:.2f} mm"))
    return out


def flat_size_text(result: FlatResult | None) -> str:
    """The flat size as the panel shows it, in mm."""
    if result is None or result.size is None:
        return text.FLAT_SIZE_NONE
    length, width = result.size
    return text.FLAT_SIZE_TEXT.format(length=f"{length:.2f} mm", width=f"{width:.2f} mm")


def _rip_faces(body: Any, fid: str) -> list[str]:
    """Names of the faces a Rip feature cut (``<fid>/slit...``, ``<fid>/edge...``)."""
    if body is None:
        return []
    return [n for n, _f in body.faces if n.startswith((f"{fid}/slit", f"{fid}/edge"))]


def bend_table(window: MainWindow, fill: Callable[[Any], bool] | None = None) -> bool:
    """Show the Bend Table (TR282, D1110). OK adds an Edit Bends feature per changed bend
    and sets the Flat Pattern's bend order, in one undo step. ``fill`` stands in for the
    person (tests): it gets the window, types into it and says whether OK was clicked."""
    from fdcad.core.document.model import Param
    from fdcad.core.features.sheetmetal.bend_list import bend_rows, rip_rows
    from fdcad.core.naming.select import reference_for
    from fdcad.ui.commands.document import AddFeature, ReplaceFeature
    from fdcad.ui.sheet_metal.bend_table_dialog import BendTableDialog

    tab = _ready(window)
    if tab is None:
        return False
    session = tab.session
    doc = session.document
    result = flat_result(session.report, doc)
    flat = flat_of(doc)
    if result is None or result.sheet is None or flat is None or not result.sheet.bends:
        window.status.setText(text.BEND_LIST_NONE)
        return False
    rows = bend_rows(result.sheet)
    names = {f.id: f.name for f in doc.features}
    rips = rip_rows(doc.features[: doc.features.index(flat)])  # TR282 (D2310)
    dialog = BendTableDialog(rows, names, result.order, window, rips)
    dialog.picked.connect(lambda bid: window.highlight_names([f"{bid}/inner", f"{bid}/outer"]))
    body_now = session.report.body if session.report is not None else None
    dialog.rip_picked.connect(lambda fid: window.highlight_names(_rip_faces(body_now, fid)))
    ok = bool(dialog.exec()) if fill is None else fill(dialog)
    window.highlight_names([])
    if not ok:
        return False
    index = doc.features.index(flat)
    before = session.report.results.get(doc.features[index - 1].id) if session.report else None
    body = getattr(before, "body", None)
    folder = folder_of(doc)
    commands: list[Any] = []
    for bid, (radius, allowance) in dialog.changes().items():
        face = body.face(f"{bid}/inner") if body is not None else None
        ref = reference_for(body, face) if body is not None and face is not None else None
        if ref is None:
            continue
        params: dict[str, Any] = {}
        if radius is not None:
            params["radius"] = Param(f"{radius:g}", radius)
        if allowance is not None:
            params["method"] = "bend_allowance"
            params["allowance"] = Param(f"{allowance:g}", allowance)
        refs: dict[str, Any] = {"bends": [ref]}
        if folder is not None:
            refs["sheet_metal"] = {"feature": folder.id}
        fid = doc.new_feature_id()
        number = next(r.number for r in rows if r.bid == bid)
        feature = Feature(fid, "edit_bends", text.BEND_LIST_FEATURE.format(n=number),
                          params=params, refs=refs)  # fmt: skip
        commands.append(AddFeature(session, feature, index + len(commands)))
    order = dialog.order_text()
    default = ", ".join(str(r.number) for r in rows)
    current = flat.params.get("bend_order")
    edited = None
    if order != (current if isinstance(current, str) else default):
        edited = copy.deepcopy(flat)
        if order == default:
            edited.params.pop("bend_order", None)
        else:
            edited.params["bend_order"] = order
    for fid, gap in dialog.rip_changes().items():  # TR282 (D2310)
        rip = copy.deepcopy(doc.feature(fid))
        rip.params["gap"] = Param(f"{gap:g}", gap)
        commands.append(ReplaceFeature(session, rip))
    if not commands and edited is None:
        return False
    session.undo.beginMacro(text.BEND_LIST_UNDO)
    for command in commands:
        session.undo.push(command)
    if edited is not None:  # made after the adds, so it finds the Flat Pattern's new row
        session.undo.push(ReplaceFeature(session, edited))
    session.undo.endMacro()
    return True


#: Settings key of the shared rule library file (TR332, D1111).
RULES_KEY = "sheet_metal/rule_library"


def rule_library(window: MainWindow) -> str:
    """The rule library file: the one last used, or sheet_metal_rules.json in FDCAD's
    data folder."""
    from fdcad.ui.main_window.recovery import data_dir

    store = window.settings.store
    saved = store.value(RULES_KEY)
    if isinstance(saved, str) and saved:
        return saved
    return str(data_dir() / "sheet_metal_rules.json")  # beside the program when portable


def sheet_rules(
    window: MainWindow, library: str | None = None, act: Callable[[Any], bool] | None = None
) -> bool:
    """Show the Sheet Metal Rules window (TR332, D1111); Apply copies the rule into the
    Sheet Metal folder in one undo step. ``act`` stands in for the person (tests)."""
    from fdcad.core.features.sheetmetal.rules import apply_rule
    from fdcad.ui.commands.document import ReplaceFeature
    from fdcad.ui.sheet_metal.rules_dialog import SheetRulesDialog

    tab = _ready(window)
    if tab is None:
        return False
    session = tab.session
    folder = folder_of(session.document)
    if folder is None:
        window.status.setText(text.NEEDS_SHEET.format(tool=text.RULES_TITLE))
        return False
    dialog = SheetRulesDialog(library or rule_library(window), folder, window)
    ok = bool(dialog.exec()) if act is None else act(dialog)
    if library is None:
        window.settings.store.setValue(RULES_KEY, dialog.path)
    name = dialog.chosen
    if not ok or name is None or name not in dialog.rules:
        return False
    edited = apply_rule(folder, name, dialog.rules[name])
    session.undo.push(ReplaceFeature(session, edited, text.RULES_UNDO.format(name=name)))
    window.status.setText(text.RULES_APPLIED.format(name=name))
    return True


def edit_parameters(window: MainWindow) -> bool:
    """Open the Sheet Metal folder in the panel."""
    tab = _ready(window)
    if tab is None:
        return False
    folder = folder_of(tab.session.document)
    if folder is None:
        window.status.setText(text.NEEDS_SHEET.format(tool=text.TYPE_NAMES["sheet_metal"]))
        return False
    return edit(window, folder.id)


def toggle_flatten(window: MainWindow) -> bool:
    """Show the part flat or folded (one undoable step)."""
    from fdcad.ui.commands.document import SetParam

    tab = _ready(window)
    if tab is None:
        return False
    session = tab.session
    doc = session.document
    if not has_sheet(doc):
        window.status.setText(text.NEEDS_SHEET.format(tool=text.TYPE_NAMES["flatten"]))
        return False
    flat = flat_of(doc)
    if flat is None:
        add_flat_pattern(session, flattened=True)
        window.status.setText(text.FLAT_ON)
        return True
    if flat.suppressed:
        window.status.setText(text.FLAT_SUPPRESSED)
        return False
    from fdcad.core.document.rollback import rolled_back

    if flat.id in rolled_back(doc):
        window.status.setText(text.FLAT_ROLLED_BACK)
        return False
    on = flat.params.get("flattened", False) is not True
    command = SetParam(session, flat.id, "flattened", on)
    command.setText(text.FLATTEN_UNDO if on else text.FOLD_UNDO)
    session.undo.push(command)
    window.status.setText(text.FLAT_ON if on else text.FLAT_OFF)
    return True


def load_bend_table(window: MainWindow, path: str | None = None) -> bool:
    """Read a CSV bend table into the Sheet Metal folder (one undoable step)."""
    from fdcad.core.features.base import FeatureError
    from fdcad.core.features.sheetmetal.params import parse_bend_table
    from fdcad.ui.commands.document import ReplaceFeature

    tab = _ready(window)
    if tab is None:
        return False
    session = tab.session
    folder = folder_of(session.document)
    if folder is None:
        window.status.setText(text.NEEDS_SHEET.format(tool=text.TYPE_NAMES["sheet_metal"]))
        return False
    if path is None:
        path, _ = QFileDialog.getOpenFileName(
            window, text.BEND_TABLE_UNDO, "", text.FILTER_BEND_TABLE
        )
        if not path:
            return False
    try:
        content = Path(path).read_text(encoding="utf-8-sig")
        rows = parse_bend_table(content, folder.name)
    except FeatureError as exc:
        window.status.setText(text.BEND_TABLE_BAD.format(error=exc))
        return False
    except (OSError, UnicodeDecodeError) as exc:
        window.status.setText(text.BEND_TABLE_UNREADABLE.format(error=clause(exc)))
        return False
    edited = copy.deepcopy(folder)
    edited.data["bend_table"] = content
    edited.params["method"] = "bend_table"
    session.undo.push(ReplaceFeature(session, edited, text.BEND_TABLE_UNDO))
    window.status.setText(text.BEND_TABLE_LOADED.format(rows=len(rows)))
    return True


def load_gauge_table(window: MainWindow, path: str | None = None, gauge: str | None = None) -> bool:
    """Read a CSV gauge table into the Sheet Metal folder and pick a gauge (one undoable step).

    ``gauge`` chooses without asking: a gauge name, or "" for no gauge.
    """
    from fdcad.core.document.model import Param
    from fdcad.core.features.base import FeatureError
    from fdcad.core.features.sheetmetal.params import parse_gauge_table
    from fdcad.core.units import UnitSystem
    from fdcad.ui.commands.document import ReplaceFeature

    tab = _ready(window)
    if tab is None:
        return False
    session = tab.session
    folder = folder_of(session.document)
    if folder is None:
        window.status.setText(text.NEEDS_SHEET.format(tool=text.TYPE_NAMES["sheet_metal"]))
        return False
    if path is None:
        path, _ = QFileDialog.getOpenFileName(
            window, text.GAUGE_TABLE_UNDO, "", text.FILTER_GAUGE_TABLE
        )
        if not path:
            return False
    try:
        content = Path(path).read_text(encoding="utf-8-sig")
        gauges = parse_gauge_table(content, folder.name)
    except FeatureError as exc:
        window.status.setText(text.GAUGE_BAD.format(error=exc))
        return False
    except (OSError, UnicodeDecodeError) as exc:
        window.status.setText(text.GAUGE_UNREADABLE.format(error=clause(exc)))
        return False
    if gauge is None:
        from PySide6.QtWidgets import QInputDialog

        names = [*gauges, text.GAUGE_NONE]
        chosen, ok = QInputDialog.getItem(
            window, text.GAUGE_PICK_TITLE, text.GAUGE_PICK_LABEL, names, 0, False
        )
        if not ok:
            return False
        gauge = "" if chosen == text.GAUGE_NONE else str(chosen)
    edited = copy.deepcopy(folder)
    edited.data["gauge_table"] = content
    if gauge and gauge in gauges:
        thickness, radii = gauges[gauge]
        if "before_gauge" not in edited.data:
            # Keep the typed values, so No gauge brings them back (audit A item 3, D727).
            edited.data["before_gauge"] = {
                k: {"expr": v.expr, "value": v.value}
                for k in ("thickness", "radius")
                if isinstance(v := edited.params.get(k), Param)
            }
        edited.params["gauge"] = gauge
        # Gauge tables are in mm: say so in the typed text of a part in inches.
        unit = "" if session.document.units is UnitSystem.MM else " mm"
        edited.params["thickness"] = Param(f"{thickness:g}{unit}", thickness)
        edited.params["radius"] = Param(f"{radii[0]:g}{unit}", radii[0])
        message = text.GAUGE_SET.format(name=gauge)
    else:
        edited.params.pop("gauge", None)
        before = edited.data.pop("before_gauge", None)
        if isinstance(before, dict):
            for key, raw in before.items():
                if isinstance(raw, dict) and {"expr", "value"} <= set(raw):
                    edited.params[key] = Param(str(raw["expr"]), float(raw["value"]))
        message = text.GAUGE_LOADED.format(rows=len(gauges))
    session.undo.push(ReplaceFeature(session, edited, text.GAUGE_TABLE_UNDO))
    window.status.setText(message)
    return True


class _Signals(QObject):
    done = Signal(str)


class _ExportJob(QRunnable):
    """Writes the flat pattern off the UI thread (CLAUDE.md rule 2)."""

    def __init__(self, work: Callable[[], str]) -> None:
        super().__init__()
        self.work = work
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        try:
            message = self.work()
        except Exception as exc:  # report, never crash
            message = text.EXPORT_FLAT_FAILED.format(error=clause(exc))
        self.signals.done.emit(message)


def format_of(path: str, chosen_filter: str = "") -> str:
    """ "step", "dxf" or "svg" from the file name, or from the chosen filter."""
    suffix = Path(path).suffix.lower()
    if suffix in (".step", ".stp"):
        return "step"
    if suffix in (".dxf", ".svg", ".csv"):
        return suffix[1:]
    lowered = chosen_filter.lower()
    if "csv" in lowered:
        return "csv"  # quoting data (TR172, D1106)
    return "dxf" if "dxf" in lowered else "svg" if "svg" in lowered else "step"


def with_extension(path: str, fmt: str) -> str:
    """The path with the format's extension added when it has none of the three, so
    "flat" or "flat.txt" is not written as an unnamed STEP file (audit A item 27, D739)."""
    if Path(path).suffix.lower() in (".step", ".stp", ".dxf", ".svg", ".csv"):
        return path
    return f"{path}.{fmt}"


def export_flat(
    window: MainWindow, path: str | None = None, ask: bool | None = None
) -> _ExportJob | None:
    """Save the flat pattern as STEP, DXF, SVG or quoting CSV in the background. ``ask``
    shows the Flat Pattern Output dialog for DXF and SVG (by default only when the path
    is chosen in the file dialog)."""
    from fdcad.core.features.sheetmetal import export

    tab = _ready(window)
    if tab is None:
        return None
    result = flat_result(tab.session.report, tab.session.document)
    if result is None or result.flat is None:
        window.status.setText(text.NEEDS_FLAT)
        return None
    chosen = ""
    if ask is None:
        ask = path is None
    if path is None:
        default = tab.session.title.rstrip("*") + " flat.dxf"
        path, chosen = QFileDialog.getSaveFileName(
            window, text.EXPORT_FLAT_TITLE, default, text.FILTER_FLAT
        )
        if not path:
            return None
    fmt = format_of(path, chosen)
    flat = tab.session.document.feature(flat_of(tab.session.document).id)  # type: ignore[union-attr]
    box = flat.params.get("bounding_box") is True
    target = with_extension(path, fmt)
    output = None
    if fmt in ("dxf", "svg") and ask:  # TR173 (D1108): what to write and where
        from fdcad.ui.sheet_metal.flat_output_dialog import FlatOutputDialog

        dialog = FlatOutputDialog(export.flat_drawing(result, True), box, window)
        if not dialog.exec():
            return None
        output = dialog.options()
        box = output.box

    def work() -> str:
        export.export_flat(result, target, fmt, bounding_box=box, output=output)
        return text.EXPORT_FLAT_DONE.format(name=Path(target).name)

    job = _ExportJob(work)
    job.signals.done.connect(window.status.setText)
    QThreadPool.globalInstance().start(job)
    return job


__all__ = [
    "COMMANDS",
    "SHEET_GROUPS",
    "bend_line_shapes",
    "build_tab",
    "edit",
    "export_flat",
    "load_bend_table",
    "load_gauge_table",
    "register",
    "start",
    "toggle_flatten",
]
