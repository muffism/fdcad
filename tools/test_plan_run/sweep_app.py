"""Pass 2 (app level): every feature command from the ribbon, every option in its panel.

Opens test parts in the real main window, selects an edge, face, body or
sketch (whichever the command takes), runs the command, then changes every
combo box and check box in the panel and builds the preview after each change.
Records Python exceptions, preview errors and panel messages.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _pytest.monkeypatch import MonkeyPatch
from PySide6.QtWidgets import QCheckBox, QComboBox
from qa_common import APP, t1, t2  # noqa: F401
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.ui.sweep_support import (
    close_part,
    install_dialogs,
    make_window,
    open_part,
    pump,
    select,
    settle,
    shapes_of,
)

from fdcad.core.document.model import new_document
from fdcad.core.features.preview import build_preview
from fdcad.core.io import fdef
from fdcad.core.sketch.model import Sketch
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.property_panel.narrow import words_of

HOOKED: list[str] = []
sys.excepthook = lambda k, v, tb: HOOKED.append(
    "".join(traceback.format_exception(k, v, tb))[-1500:]
)

SHEET = {
    "feature.base_flange", "feature.edge_flange", "feature.sketched_bend", "feature.hem",
    "feature.miter_flange", "feature.jog", "feature.closed_corner", "feature.break_corner",
    "feature.rip", "feature.tab_slot", "feature.cross_break", "feature.unfold", "feature.fold",
    "feature.form_tool", "feature.flatten",
}  # fmt: skip
SHAFT = {"feature.cosmetic_thread", "feature.modeled_thread"}
ROUND = {"feature.dome", "feature.wrap"}
NOT_PANELS = {
    "feature.import_mesh", "feature.import_step", "feature.gauge_table", "feature.bend_table",
    "feature.convert_sheet", "feature.insert_bends",
}  # fmt: skip
KINDS = ("edge", "face", "body", "sketch", "none")


def save(doc, path: Path) -> Path:
    fdef.save(doc, path)
    return path


def shaft():
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 3.0)
    sk = add_sketch(doc, s, {"feature": "f3"})
    add_extrude(doc, sk, 20.0)
    return doc


def sheet_sketch():
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 120, 80)
    add_sketch(doc, s, {"feature": "f3"})
    return doc


def evaluate(win, tab) -> dict:
    panel = win.panel
    out: dict = {}
    if panel is None or not panel.is_editing:
        out["message"] = "no panel"
        return out
    try:
        feature = panel.current_feature()
    except Exception:
        out["exception"] = traceback.format_exc()[-1500:]
        return out
    if feature is None:
        out["message"] = panel.message.text()[:200]
        return out
    try:
        preview = panel.form.for_preview(feature) if panel.form is not None else feature
        if preview is None:
            out["preview"] = "none"
            return out
        report = tab.session.report
        g = build_preview(tab.session.document, preview, report.results if report else {})
        out["preview"] = "ok" if g.error is None else "error"
        if g.error:
            out["error"] = g.error[:240]
    except Exception:
        out["exception"] = traceback.format_exc()[-1500:]
    return out


def options(win, tab, log: dict) -> None:
    panel = win.panel
    for combo in list(panel.findChildren(QComboBox)):
        if not combo.isVisibleTo(panel):
            continue
        start = combo.currentIndex()
        for i in range(combo.count()):
            if i == start:
                continue
            n = len(HOOKED)
            try:
                combo.setCurrentIndex(i)
                pump(20)
                result = evaluate(win, tab)
            except Exception:
                result = {"exception": traceback.format_exc()[-1500:]}
            if len(HOOKED) > n:
                result["slot_exception"] = HOOKED[n:]
            log["options"].append(
                {"option": f"{combo.toolTip()[:50]!r} = {combo.itemText(i)}", **result}
            )
            if not panel.is_editing:
                return
        try:
            combo.setCurrentIndex(start)
            pump(20)
        except Exception:
            pass
    for check in list(panel.findChildren(QCheckBox)):
        if not check.text() or not check.isVisibleTo(panel):
            continue
        n = len(HOOKED)
        try:
            check.setChecked(not check.isChecked())
            pump(20)
            result = evaluate(win, tab)
            check.setChecked(not check.isChecked())
            pump(20)
        except Exception:
            result = {"exception": traceback.format_exc()[-1500:]}
        if len(HOOKED) > n:
            result["slot_exception"] = HOOKED[n:]
        log["options"].append({"option": f"toggle {words_of(check)}", **result})
        if not panel.is_editing:
            return


def good_shapes(tab) -> dict:
    """The top face, its longest edge, a vertex and the solid."""
    from qa_common import top_edges, top_face

    out = shapes_of(tab)
    report = tab.session.report
    if report is not None and report.body is not None:
        out["face"] = top_face(report.body.shape)
        out["edge"] = top_edges(report.body.shape)[0]
    return out


def run(win, tab, cid: str) -> dict:
    log: dict = {"command": cid, "kind": None, "options": []}
    shapes = good_shapes(tab)
    chosen = None
    for kind in KINDS:
        settle(win, tab)
        if not select(win, tab, kind, shapes):
            continue
        n = len(HOOKED)
        try:
            win.commands.trigger(cid)
            pump(50)
        except Exception:
            log["trigger_exception"] = traceback.format_exc()[-1500:]
            return log
        if len(HOOKED) > n:
            log["trigger_slot_exception"] = HOOKED[n:]
        if win.panel is None or not win.panel.is_editing:
            log.setdefault("no_panel", []).append(f"{kind}: {win.status.text()[:120]}")
            continue
        chosen = chosen or kind
        if win.panel.current_feature() is not None:
            chosen = kind
            break
    if chosen is None:
        return log
    if log.get("kind") is None and (win.panel is None or not win.panel.is_editing):
        settle(win, tab)
        select(win, tab, chosen, shapes)
        win.commands.trigger(cid)
        pump(50)
    log["kind"] = chosen
    log["base"] = evaluate(win, tab)
    if win.panel is not None and win.panel.is_editing:
        options(win, tab, log)
    settle(win, tab)
    return log


def make_sheet(win, tab) -> bool:
    """Turn the sketch part into T4: Sheet Metal Parameters, then Base Flange."""
    settle(win, tab)
    win.commands.trigger("feature.base_flange")
    pump(100)
    if win.panel is None or not win.panel.is_editing:
        return False
    win.panel.accept()  # the sheet values
    pump(300)
    if win.panel is not None and win.panel.is_editing:
        win.panel.accept()  # the base flange
    pump(300)
    settle(win, tab)
    return any(f.type == "base_flange" for f in tab.session.document.features)


def main() -> None:
    out = Path(sys.argv[1])
    only = set(sys.argv[2:])
    tmp = Path(tempfile.mkdtemp(prefix="fdcad_qa_"))
    os.environ["FDCAD_CACHE_DIR"] = str(tmp / "cache")
    os.environ["FDCAD_DATA_DIR"] = str(tmp / "data")
    mp = MonkeyPatch()
    install_dialogs(mp)
    win = make_window(tmp)
    parts = {
        "t1": save(t1()[0], tmp / "t1.fdprt"),
        "t2": save(t2()[0], tmp / "t2.fdprt"),
        "shaft": save(shaft(), tmp / "shaft.fdprt"),
        "sheet": save(sheet_sketch(), tmp / "sheet.fdprt"),
    }
    commands = sorted(c for c in BY_ID if c.startswith("feature.") and c not in NOT_PANELS)
    if only:
        commands = [c for c in commands if c in only or c.split(".", 1)[1] in only]
    logs = []
    groups = {
        "t1": [c for c in commands if c not in SHEET | SHAFT | ROUND],
        "t2": [c for c in commands if c in ROUND],
        "shaft": [c for c in commands if c in SHAFT],
        "sheet": [c for c in commands if c in SHEET],
    }
    for part, cids in groups.items():
        if not cids:
            continue
        for cid in cids:
            tab = open_part(win, parts[part])
            if part == "sheet" and cid != "feature.base_flange" and not make_sheet(win, tab):
                logs.append({"command": cid, "error": "could not make the sheet part"})
                close_part(win, tab)
                continue
            print(part, cid, flush=True)
            try:
                logs.append(run(win, tab, cid))
            except Exception:
                logs.append({"command": cid, "harness": traceback.format_exc()[-1500:]})
            close_part(win, tab)
            out.write_text(json.dumps(logs, indent=1), encoding="utf-8")
    print("done", len(logs), flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
