"""Pass 1: test plan rows with an exact expected result.

Each row goes through the property panel as a user would: pick, set values,
OK, then the rebuilt part's volume is compared with the plan.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from PySide6.QtWidgets import QCheckBox, QComboBox
from qa_common import (
    pump,
    session_for,
    side_faces,
    t1,
    t2,
    top_edges,
    top_face,
    volume,
)
from tests.core.features.test_features import add_extrude, add_sketch, rect

from fdcad.core.document.model import Document
from fdcad.core.sketch.model import Sketch
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.narrow import words_of
from fdcad.ui.property_panel.panel import PropertyPanel

PI = math.pi
ROWS: list[dict[str, Any]] = []


def pick_combo(panel: PropertyPanel, text: str) -> None:
    for c in panel.findChildren(QComboBox):
        i = c.findText(text)
        if i >= 0:
            c.setCurrentIndex(i)
            pump(0.02)
            return
    raise LookupError(f"no combo item {text!r}")


def tick(panel: PropertyPanel, text: str, on: bool = True) -> None:
    for c in panel.findChildren(QCheckBox):
        if words_of(c) == text:  # its words may be on two lines in the window (D2806)
            c.setChecked(on)
            pump(0.02)
            return
    raise LookupError(f"no check box {text!r}")


def field(panel: PropertyPanel, name: str, text: str) -> None:
    if panel.form is not None:
        panel.form.fields[name].edit.setText(text)
    else:
        w = panel.body_form.widgets[name]
        (w.edit if hasattr(w, "edit") else w).setText(text)
    pump(0.02)


def via_panel(
    make: Callable[[], tuple[Document, str]],
    ftype: str,
    picks: Callable[[Any], list[Any]] | None,
    setup: Callable[[PropertyPanel, Any], None] | None = None,
) -> dict[str, Any]:
    doc, _ext = make()
    session = session_for(doc)
    body = session.report.body
    panel = PropertyPanel()
    panel.begin(session, phase2_feature(doc, ftype, "boss"), is_new=True)
    pump(0.05)
    if picks is not None:
        msg = panel.form.take_shapes(body, picks(body.shape))
        if msg:
            return {"error": f"pick refused: {msg}"}
    if setup is not None:
        setup(panel, body)
    if panel.current_feature() is None:
        return {"error": f"panel: {panel.message.text()}"}
    panel.accept()
    session.wait(60000)
    pump(0.3)
    report = session.report
    last = doc.features[-1]
    res = report.results.get(last.id)
    issues = [i.message for i in res.issues] if res is not None else ["no result"]
    state = res.state.name if res is not None else "missing"
    vol = volume(report.body.shape) if report.body is not None else None
    return {"volume": vol, "state": state, "issues": issues, "type": last.type}


def via_doc(build: Callable[[], Document]) -> dict[str, Any]:
    doc = build()
    session = session_for(doc)
    report = session.report
    last = doc.features[-1]
    res = report.results.get(last.id)
    issues = [i.message for i in res.issues] if res is not None else ["no result"]
    vol = volume(report.body.shape) if report.body is not None else None
    return {"volume": vol, "state": res.state.name if res else "missing", "issues": issues}


def row(
    rid: str, what: str, expected: float, run: Callable[[], dict[str, Any]], tol: float = 1e-3
) -> None:
    try:
        got = run()
    except Exception:
        got = {"error": traceback.format_exc()[-1200:]}
    vol = got.get("volume")
    ok = (
        vol is not None
        and abs(vol - expected) <= max(abs(expected) * tol, 0.5)
        and not got.get("error")
    )
    if got.get("state") == "ERROR":
        ok = False
    ROWS.append(
        {
            "id": rid,
            "what": what,
            "expected": round(expected, 1),
            "actual": None if vol is None else round(vol, 1),
            "pass": ok,
            **{k: v for k, v in got.items() if k != "volume"},
        }
    )
    print(
        ("PASS" if ok else "FAIL"),
        rid,
        what,
        round(expected, 1),
        None if vol is None else round(vol, 1),
        got.get("error", "")[:200],
        got.get("issues", ""),
        flush=True,
    )


# T1 based documents -------------------------------------------------------------


def block(**params: Any) -> Document:
    doc, _ = t1() if not params else (None, None)
    if params:
        from fdcad.core.document.model import new_document

        doc = new_document()
        s = Sketch()
        rect(s, -50, -30, 50, 30)
        sk = add_sketch(doc, s, {"feature": "f3"})
        add_extrude(doc, sk, 20.0, **params)
    return doc


def hole_on_top(count: int = 1, spacing: float = 20.0) -> Callable[[], Document]:
    def build() -> Document:
        doc, ext = t1()
        s = Sketch()
        for k in range(count):
            s.add_circle(-30 + k * spacing, 0, 5)
        sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
        add_extrude(doc, sk, 1.0, operation="cut", end_condition="through_all", reverse=True)
        return doc

    return build


def longest_top_edge(shape: Any) -> list[Any]:
    return top_edges(shape)[:1]


def main() -> None:
    hole = PI * 25 * 20
    row("T1", "Block 100x60x20", 120000, lambda: via_doc(lambda: t1()[0]))
    row("T2", "Cylinder 40x60", PI * 400 * 60, lambda: via_doc(lambda: t2()[0]))
    row("EX-13", "Mid Plane 20", 120000, lambda: via_doc(lambda: block(end_condition="mid_plane")))
    row(
        "EX-15",
        "Two Directions 20 + 10",
        180000,
        lambda: via_doc(lambda: block(end_condition="two_directions", depth2=10.0)),
    )
    row("EX-14", "Reverse", 120000, lambda: via_doc(lambda: block(reverse=True)))
    row("EX-06", "Through All cut Ø10", 120000 - hole, lambda: via_doc(hole_on_top()))
    row("LP-src", "Three holes 20 apart", 120000 - 3 * hole, lambda: via_doc(hole_on_top(3)))
    # Fillet
    strip = (1 - PI / 4) * 25 * 100
    row(
        "FI-01",
        "Fillet R5 one 100 mm edge",
        120000 - strip,
        lambda: via_panel(t1, "fillet", longest_top_edge, lambda p, b: field(p, "radius", "5")),
    )
    row(
        "FI-02b",
        "Fillet R5 two 100 mm edges",
        120000 - 2 * strip,
        lambda: via_panel(
            t1, "fillet", lambda s: top_edges(s)[:2], lambda p, b: field(p, "radius", "5")
        ),
    )
    # Chamfer
    row(
        "CH-01",
        "Chamfer 5 symmetric",
        118750,
        lambda: via_panel(t1, "chamfer", longest_top_edge, lambda p, b: field(p, "distance", "5")),
    )

    def asym(p: PropertyPanel, b: Any) -> None:
        pick_combo(p, "Asymmetric")
        field(p, "distance", "5")
        field(p, "distance2", "10")

    row("CH-02", "Chamfer 5 x 10", 117500, lambda: via_panel(t1, "chamfer", longest_top_edge, asym))

    def angle(p: PropertyPanel, b: Any) -> None:
        pick_combo(p, "Angle Distance")
        field(p, "distance", "5")
        field(p, "angle", "45")

    row(
        "CH-03",
        "Chamfer 5 at 45 deg",
        118750,
        lambda: via_panel(t1, "chamfer", longest_top_edge, angle),
    )
    # Shell
    row(
        "SH-01",
        "Shell 2, top removed",
        23232,
        lambda: via_panel(
            t1, "shell", lambda s: [top_face(s)], lambda p, b: field(p, "thickness", "2")
        ),
    )

    def outward(p: PropertyPanel, b: Any) -> None:
        field(p, "thickness", "2")
        tick(p, "Shell outward")

    row(
        "SH-03",
        "Shell 2 outward, top removed",
        104 * 64 * 22 - 120000,
        lambda: via_panel(t1, "shell", lambda s: [top_face(s)], outward),
    )
    # Dome on T2 top: spherical cap h=10 on r=20 adds pi*h*(3r^2+h^2)/6
    row(
        "DO-01",
        "Dome 10 on cylinder top",
        PI * 400 * 60 + PI * 10 * (3 * 400 + 100) / 6,
        lambda: via_panel(
            t2, "dome", lambda s: [top_face(s)], lambda p, b: field(p, "distance", "10")
        ),
    )
    # Draft 5 deg on the four sides, neutral face the bottom: a frustum
    t = math.tan(math.radians(5))

    def frustum(h: float, a: float, b: float) -> float:
        a2, b2 = a - 2 * h * t, b - 2 * h * t
        return h / 3 * (a * b + a2 * b2 + math.sqrt(a * b * a2 * b2))

    def draft_setup(p: PropertyPanel, body: Any) -> None:
        field(p, "angle", "5")
        from qa_common import centre as c_of
        from qa_common import faces as all_faces

        bottom = min(all_faces(body.shape), key=lambda f: c_of(f)[1])
        p.form.pick_neutral.setChecked(True)
        p.form.take_shapes(body, [bottom])
        pump(0.05)

    def draft_picks(shape: Any) -> list[Any]:
        return side_faces(shape)

    row(
        "DR-01",
        "Draft 5 deg, 4 sides (volume less than block)",
        frustum(20, 100, 60),
        lambda: via_panel(t1, "draft", draft_picks, draft_setup),
        tol=0.02,
    )

    def body_tool(make, ftype, refs_of, setup):
        def run() -> dict[str, Any]:
            from fdcad.core.naming.select import reference_for
            from fdcad.ui.body_tools.flow import new_feature as tool_feature

            doc, _ext = make()
            session = session_for(doc)
            body = session.report.body
            refs = {k: [reference_for(body, s) for s in v] for k, v in refs_of(body.shape).items()}
            panel = PropertyPanel()
            panel.begin(
                session,
                tool_feature(doc, ftype, {"mode": "offset"} if ftype == "move_face" else {}, refs),
                is_new=True,
            )
            pump(0.05)
            setup(panel)
            if panel.current_feature() is None:
                return {"error": f"panel: {panel.message.text()}"}
            panel.accept()
            session.wait(60000)
            pump(0.3)
            res = session.report.results.get(doc.features[-1].id)
            return {
                "volume": volume(session.report.body.shape),
                "state": res.state.name,
                "issues": [i.message for i in res.issues],
            }

        return run

    row(
        "MF-01",
        "Offset top face 5",
        150000,
        body_tool(
            t1, "move_face", lambda s: {"faces": [top_face(s)]}, lambda p: field(p, "distance", "5")
        ),
    )
    row(
        "SC-01",
        "Scale uniform 2",
        960000,
        body_tool(t1, "scale", lambda s: {}, lambda p: field(p, "factor", "2")),
    )

    def per_axis(p: PropertyPanel) -> None:
        tick(p, "Uniform scaling", False)
        field(p, "fx", "2")

    row("SC-02", "Scale X 2 (per axis)", 240000, body_tool(t1, "scale", lambda s: {}, per_axis))
    print(
        json.dumps({"count": len(ROWS), "failed": [r["id"] for r in ROWS if not r["pass"]]}),
        flush=True,
    )
    Path(sys.argv[1]).write_text(json.dumps(ROWS, indent=1), encoding="utf-8")
    import os

    os._exit(0)


if __name__ == "__main__":
    main()
