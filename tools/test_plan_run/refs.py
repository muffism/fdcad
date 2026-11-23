"""Reference geometry: every method of Plane, Axis, Point and Coordinate System."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _pytest.monkeypatch import MonkeyPatch
from OCP.TopAbs import TopAbs_VERTEX
from PySide6.QtWidgets import QCheckBox
from qa_common import (  # noqa: F401
    APP,
    centre,
    edges,
    faces,
    subshapes,
    t1,
    t2,
    top_edges,
    top_face,
)
from tests.ui.sweep_support import close_part, install_dialogs, make_window, open_part, pump, settle

from fdcad.core.io import fdef
from fdcad.ui.property_panel.narrow import words_of


def vertices(shape):
    return subshapes(shape, TopAbs_VERTEX)


def bottom_face(shape):
    return min(faces(shape), key=lambda f: centre(f)[1])


def side_face(shape):
    return max(faces(shape), key=lambda f: centre(f)[0])


def curved_face(shape):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopoDS import TopoDS

    return next(
        f for f in faces(shape) if BRepAdaptor_Surface(TopoDS.Face(f)).GetType() == GeomAbs_Cylinder
    )


def top_vertices(shape):
    return [v for v in vertices(top_face(shape))]


def bottom_vertex(shape):
    return vertices(bottom_face(shape))[0]


B = "t1"
C = "t2"
CASES = [
    ("ref_plane", "offset", B, lambda s: [top_face(s)], {"distance": "10"}),
    ("ref_plane", "angle", B, lambda s: [top_face(s), top_edges(s)[0]], {"angle": "30"}),
    ("ref_plane", "three_points", B, lambda s: top_vertices(s)[:3], {}),
    ("ref_plane", "normal_to_curve", B, lambda s: [top_edges(s)[0]], {}),
    ("ref_plane", "mid_plane", B, lambda s: [top_face(s), bottom_face(s)], {}),
    ("ref_plane", "parallel_point", B, lambda s: [top_face(s), bottom_vertex(s)], {}),
    ("ref_plane", "project", B, lambda s: [bottom_vertex(s), top_face(s)], {}),
    ("ref_plane", "screen", B, lambda s: [top_vertices(s)[0]], {}),
    ("ref_axis", "line", B, lambda s: [top_edges(s)[0]], {}),
    ("ref_axis", "two_planes", B, lambda s: [top_face(s), side_face(s)], {}),
    ("ref_axis", "two_points", B, lambda s: top_vertices(s)[:2], {}),
    ("ref_axis", "cylinder", C, lambda s: [curved_face(s)], {}),
    ("ref_axis", "point_normal", B, lambda s: [top_vertices(s)[0], bottom_face(s)], {}),
    ("ref_point", "arc_centre", C, lambda s: [top_edges(s)[0]], {}),
    ("ref_point", "face_centre", B, lambda s: [top_face(s)], {}),
    ("ref_point", "intersection", B, lambda s: [top_edges(s)[0], top_edges(s)[2]], {}),
    ("ref_point", "projection", B, lambda s: [bottom_vertex(s), top_face(s)], {}),
    ("ref_point", "along_curve", B, lambda s: [top_edges(s)[0]], {"distance": "25"}),
    ("ref_point", "sketch_point", B, lambda s: [top_vertices(s)[0]], {}),
    ("ref_point", "values", B, lambda s: [], {"x": "10", "y": "5", "z": "3"}),
    ("coord_system", "directions", B, lambda s: [], {}),
    ("coord_system", "angles", B, lambda s: [], {"rx": "90"}),
]


def main() -> None:
    out = Path(sys.argv[1])
    tmp = Path(tempfile.mkdtemp(prefix="fdcad_qa_ref_"))
    os.environ["FDCAD_CACHE_DIR"] = str(tmp / "cache")
    os.environ["FDCAD_DATA_DIR"] = str(tmp / "data")
    install_dialogs(MonkeyPatch())
    win = make_window(tmp)
    parts = {"t1": tmp / "t1.fdprt", "t2": tmp / "t2.fdprt"}
    fdef.save(t1()[0], parts["t1"])
    fdef.save(t2()[0], parts["t2"])
    logs = []
    for ftype, method, part, picks, values in CASES:
        tab = open_part(win, parts[part])
        tool = win.reference_tool
        log = {"type": ftype, "method": method}
        try:
            tool.start(ftype)
            pump(50)
            panel = tool.panel
            i = panel.method.findData(method)
            log["listed"] = i >= 0
            panel.method.setCurrentIndex(i)
            pump(20)
            body = tab.session.report.body.shape
            for k, shape in enumerate(picks(body)):
                panel.set_active(k)
                tool._last_pick = None
                tool._picked([shape])
                pump(20)
            for name, text in values.items():
                box = getattr(panel, "fields", {}).get(name) if hasattr(panel, "fields") else None
                if box is None:
                    box = panel.findChild(object, f"ref_value_{name}")
                if box is not None:
                    (box.edit if hasattr(box, "edit") else box).setText(text)
                else:
                    log.setdefault("missing_field", []).append(name)
                pump(20)
            tool._timer.stop()
            tool._preview()
            tool.wait()
            pump(100)
            log["missing"] = panel.missing()
            log["defined"] = panel.fully_defined
            checks = [words_of(c) for c in panel.findChildren(QCheckBox) if c.isVisibleTo(panel)]
            log["checks"] = checks
            before = len(tab.session.document.features)
            tool.accept()
            pump(50)
            tab.session.wait(30000)
            pump(100)
            doc = tab.session.document
            log["added"] = len(doc.features) > before
            if log["added"]:
                res = tab.session.report.results.get(doc.features[-1].id)
                log["state"] = res.state.name if res else "missing"
                log["issues"] = [x.message for x in res.issues] if res else []
        except Exception:
            log["exception"] = traceback.format_exc()[-1200:]
        ok = log.get("added") and log.get("state") in ("OK", "WARNING")
        print(
            "PASS" if ok else "FAIL",
            ftype,
            method,
            log.get("missing"),
            log.get("issues"),
            log.get("missing_field", ""),
            log.get("exception", "")[-200:],
            flush=True,
        )
        logs.append(log)
        settle(win, tab)
        tool.close()
        close_part(win, tab)
    out.write_text(json.dumps(logs, indent=1), encoding="utf-8")
    os._exit(0)


if __name__ == "__main__":
    main()
