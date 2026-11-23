"""File round trip of every sheet metal tool of D530 to D545 (CLAUDE.md 4 item 4).

Each part is written, read back and written again byte for byte, and rebuilds to
the same volume. The written files are kept as schema fixtures in
tests/fixtures/sheet_metal, so tests/core/io/test_schema_keys.py checks their keys
against FDEF_SPEC.md. Set FDCAD_UPDATE_FIXTURES=1 to rewrite them.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.io import fdef
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal import (
    test_convert,
    test_corners,
    test_cuts,
    test_hem,
    test_jog,
    test_miter,
    test_unfold,
)
from tests.core.features.sheetmetal.parts import add, build, edge_ref, on, plate, sheet_doc

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "sheet_metal"


def _hem() -> Document:
    return test_hem._hem(
        hem_type="teardrop",
        radius=Param("2", 2.0),
        length=Param("8", 8.0),
        angle=Param("200", 3.490658503988659),
        corner_gap=Param("0.5", 0.5),
    )[0]


def _jog() -> Document:
    return test_jog._jog(offset=Param("10", 10.0), offset_from="inner_faces")[0]


def _miter() -> Document:
    return test_miter._miter(gap=Param("1", 1.0))[0]


def _closed() -> Document:
    doc = test_corners.box_tray()
    add(
        doc,
        "closed_corner",
        {"faces": [test_corners._end_face(doc)]},
        corner_type="butt",
        gap=Param("0.1", 0.1),
    )
    return doc


def _break() -> Document:
    return test_corners._broken(break_type="fillet", radius=Param("8", 8.0))[0]


def _rip_tab() -> Document:
    doc = test_cuts._touching()
    slot_face, _p = face_ref(
        doc, (0.0, 1.0, 0.0), lambda f: abs(_c(f)[1] - 60) < 1e-6 and _c(f)[2] > 3
    )
    edge = edge_ref(doc, test_cuts._inner_corner)
    add(
        doc,
        "tab_slot",
        {"edge": edge, "face": slot_face},
        tab_count=Param("2", 2.0),
        tab_length=Param("4", 4.0),
        depth=Param("2", 2.0),
        spacing=Param("8", 8.0),
        clearance=Param("0.1", 0.1),
    )
    top, _p = face_ref(doc, (0.0, 0.0, 1.0), lambda f: _c(f)[2] < 2.5)
    sk = SketchBuilder()
    sk.sk.add_line(50, 0, 50, 30)
    sid = add_sketch(doc, sk, top, "Rip Line")
    add(doc, "rip", {"sketch": {"feature": sid}}, gap=Param("0.2", 0.2), flip=True)
    add(doc, "cross_break", {"face": top}, reverse=True)
    return doc


def _c(face: object) -> tuple[float, float, float]:
    from fdcad.core.naming.names import centroid

    return centroid(face)  # type: ignore[arg-type]


def _convert() -> Document:
    return test_convert._converted(gap=Param("0.1", 0.1))[0]


def _insert() -> Document:
    doc = test_convert._thin_tray()
    bottom, _p = face_ref(doc, (0.0, 0.0, -1.0))
    add(doc, "insert_bends", {"face": bottom}, gap=Param("0.1", 0.1))
    return doc


def _unfold() -> Document:
    doc = test_unfold._flanged()
    unfold = add(doc, "unfold", {}, all_bends=True)
    test_unfold._cut(doc, lambda b: b.circle(50, 58.5, 2.0))
    add(doc, "fold", {"unfold": {"feature": unfold}})
    return doc


def _forms() -> Document:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(40, 30, 60, 30)
    sid = add_sketch(doc, sk, top, "Form Places")
    add(
        doc,
        "form_tool",
        {"sketch": {"feature": sid}},
        tool="louvre",
        length=Param("16", 16.0),
        width=Param("6", 6.0),
        height=Param("3", 3.0),
        reverse=False,
    )
    sk = SketchBuilder()
    sk.sk.add_line(70, 15, 80, 15)
    sid = add_sketch(doc, sk, top, "Dimple Places")
    add(
        doc,
        "form_tool",
        {"sketch": {"feature": sid}},
        tool="dimple",
        diameter=Param("8", 8.0),
        height=Param("2", 2.0),
        reverse=True,
    )
    return doc


def _folder_options() -> Document:
    doc = sheet_doc(
        1.5, 2.0, gauge="16 gauge", corner_relief="circular", corner_relief_size=Param("2", 2.0)
    )
    doc.features[-1].data["gauge_table"] = "name,thickness,radii\n16 gauge,1.5,1,2\n"
    plate(doc)
    edges = [edge_ref(doc, on(y=60.0, z=1.5)), edge_ref(doc, on(x=100.0, z=1.5))]
    add(
        doc,
        "edge_flange",
        {"edges": edges},
        length=Param("20", 20.0),
        trim_side_bends=True,
        gap=Param("1", 1.0),
        relief="tear",
        corner_relief="circular",
        corner_relief_size=Param("1.6", 1.6),
    )
    return doc


PARTS: dict[str, Callable[[], Document]] = {
    "hem": _hem,
    "jog": _jog,
    "miter_flange": _miter,
    "closed_corner": _closed,
    "break_corner": _break,
    "rip_tab_cross": _rip_tab,
    "convert_sheet": _convert,
    "insert_bends": _insert,
    "unfold_fold": _unfold,
    "form_tool": _forms,
    "folder_options": _folder_options,
}


@pytest.mark.parametrize("name", list(PARTS))
def test_round_trip_and_fixture(name: str) -> None:
    doc = PARTS[name]()
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    text = fdef.dumps(doc)
    again = fdef.loads(text)
    assert fdef.dumps(again) == text
    first = measure(report.body.shape)["volume"]  # type: ignore[union-attr]
    second = measure(build(again).body.shape)["volume"]  # type: ignore[union-attr]
    assert second == pytest.approx(first)
    path = FIXTURES / f"{name}.fdef"
    if os.environ.get("FDCAD_UPDATE_FIXTURES") or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    saved = fdef.load(path)
    assert fdef.dumps(saved) == fdef.dumps(fdef.loads(path.read_text(encoding="utf-8")))
    assert measure(build(saved).body.shape)["volume"] == pytest.approx(first)  # type: ignore[union-attr]
