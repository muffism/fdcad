"""Screenshots of the visual test plan rows, taken in the real app window."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _pytest.monkeypatch import MonkeyPatch
from qa_common import APP, centre, faces, side_faces, t1, t2, top_edges, top_face
from tests.core.features.test_features import add_extrude, add_sketch
from tests.ui.sweep_support import close_part, install_dialogs, make_window, open_part, settle

from fdcad.core.io import fdef
from fdcad.core.naming.select import reference_for
from fdcad.core.sketch.model import Sketch
from fdcad.ui.body_tools.flow import new_feature as tool_feature
from fdcad.ui.main_window.new_feature import phase2_feature

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def pump(sec: float) -> None:
    end = time.time() + sec
    while time.time() < end:
        APP.processEvents()
        time.sleep(0.01)


def shot(win, tab, name: str) -> None:
    pump(2.5)
    tab.viewport.fit_next_preview = False
    tab.viewport.dump(str(OUT / f"{name}.png"))
    print("shot", name, flush=True)


def begin(win, tab, ftype: str, tool: bool = False, refs=None) -> None:
    doc = tab.session.document
    feature = (
        tool_feature(doc, ftype, {}, refs or {}) if tool else phase2_feature(doc, ftype, "boss")
    )
    win.panel.begin(tab.session, feature, is_new=True)
    pump(0.3)


def shaft_doc():
    from fdcad.core.document.model import new_document

    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 3.0)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f3"}), 20.0)
    return doc


def holes_doc():
    doc, ext = t1()
    s = Sketch()
    s.add_circle(-30, 0, 5)
    add_extrude(
        doc,
        add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"}),
        1.0,
        operation="cut",
        end_condition="through_all",
        reverse=True,
    )
    return doc


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="fdcad_shots_"))
    os.environ["FDCAD_CACHE_DIR"] = str(tmp / "cache")
    os.environ["FDCAD_DATA_DIR"] = str(tmp / "data")
    install_dialogs(MonkeyPatch())
    win = make_window(tmp)
    win.resize(1400, 900)
    parts = {
        "t1": tmp / "t1.fdprt",
        "t2": tmp / "t2.fdprt",
        "shaft": tmp / "shaft.fdprt",
        "holes": tmp / "holes.fdprt",
    }
    fdef.save(t1()[0], parts["t1"])
    fdef.save(t2()[0], parts["t2"])
    fdef.save(shaft_doc(), parts["shaft"])
    fdef.save(holes_doc(), parts["holes"])

    def case(name: str, part: str, run) -> None:
        tab = open_part(win, parts[part])
        pump(1.0)
        try:
            run(tab, tab.session.report.body)
        except Exception:
            print("FAILED", name, traceback.format_exc()[-800:], flush=True)
        settle(win, tab)
        win.section_tool.turn_off()
        close_part(win, tab)

    def fillet(mode: str):
        def run(tab, body) -> None:
            begin(win, tab, "fillet")
            f = win.panel.form
            f.mode.setCurrentIndex(f.mode.findData(mode))
            f.take_shapes(body, top_edges(body.shape)[:3])
            f.fields["radius"].edit.setText("6")
            shot(win, tab, f"FI_{mode}")

        return run

    def chamfer(mode: str):
        def run(tab, body) -> None:
            begin(win, tab, "chamfer")
            f = win.panel.form
            f.mode.setCurrentIndex(f.mode.findData(mode))
            f.take_shapes(body, top_edges(body.shape)[:3])
            f.fields["distance"].edit.setText("6")
            shot(win, tab, f"CH_{mode}")

        return run

    def shell(tab, body) -> None:
        begin(win, tab, "shell")
        win.panel.form.take_shapes(body, [top_face(body.shape)])
        win.panel.form.fields["thickness"].edit.setText("3")
        win.panel.accept()
        tab.session.wait(60000)
        shot(win, tab, "SH_result")

    def draft(tab, body) -> None:
        begin(win, tab, "draft")
        f = win.panel.form
        f.take_shapes(body, [min(faces(body.shape), key=lambda x: centre(x)[1])])
        f.take_shapes(body, side_faces(body.shape))
        f.fields["angle"].edit.setText("10")
        shot(win, tab, "DR_preview")

    def section(tab, body) -> None:
        win.commands.trigger("view.section")
        pump(1.5)
        shot(win, tab, "VW_section_arrow")

    def thread(tab, body) -> None:
        begin(win, tab, "modeled_thread")
        win.panel.form.take_shapes(body, [top_edges(body.shape)[0]])
        pump(0.2)
        print("thread size", win.panel.form.choice_boxes["size"].currentData(), flush=True)
        win.panel.accept()
        tab.session.wait(120000)
        shot(win, tab, "MT_M6_on_6mm_shaft")

    def scale_axis(tab, body) -> None:
        begin(win, tab, "scale", tool=True)
        from PySide6.QtWidgets import QCheckBox

        from fdcad.ui.property_panel.narrow import words_of

        for c in win.panel.findChildren(QCheckBox):
            if words_of(c) == "Uniform scaling":
                c.setChecked(False)
        w = win.panel.body_form.widgets["fx"]
        (w.edit if hasattr(w, "edit") else w).setText("1.5")
        shot(win, tab, "SC_per_axis_preview")

    def pattern(tab, body) -> None:
        doc = tab.session.document
        cut = doc.features[-1].id
        edge = top_edges(body.shape)[0]
        refs = {"direction1": reference_for(body, edge), "features": [{"feature": cut}]}
        begin(win, tab, "linear_pattern", tool=True, refs=refs)
        w = win.panel.body_form.widgets["spacing1"]
        (w.edit if hasattr(w, "edit") else w).setText("20")
        shot(win, tab, "LP_preview")

    def hole(tab, body) -> None:
        begin(win, tab, "hole")
        f = win.panel.form
        box = next(
            b
            for b in f.findChildren(
                type(
                    f.findChildren(
                        __import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox
                    )[0]
                )
            )
            if b.findText("Counterbore") >= 0
        )
        box.setCurrentIndex(box.findText("Counterbore"))
        pump(0.2)
        print("hole form ready", flush=True)
        shot(win, tab, "HO_counterbore_panel")

    case("fillet full", "t1", fillet("full"))
    case("fillet partial", "t1", fillet("partial"))
    case("chamfer full", "t1", chamfer("full"))
    case("chamfer partial", "t1", chamfer("partial"))
    case("shell", "t1", shell)
    case("draft", "t1", draft)
    case("section", "t1", section)
    case("thread", "shaft", thread)
    case("scale", "t1", scale_axis)
    case("pattern", "holes", pattern)
    case("hole", "t1", hole)
    print("done", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
