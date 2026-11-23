"""Forming tools (D545): folded shape only; the flat pattern keeps the blank."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.solids import solids
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import add, build, flat_pattern, plate, sheet_doc

T = 2.0


def _formed(line: tuple[float, float, float, float] = (40, 30, 60, 30), **params: Any):  # type: ignore[no-untyped-def]
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(*line)
    sid = add_sketch(doc, sk, top, "Form Places")
    fid = add(doc, "form_tool", {"sketch": {"feature": sid}}, **params)
    flat = flat_pattern(doc, flattened=False)
    report = build(doc)
    return report, report.results[fid], report.results[flat]


def _ok(report, result, flat) -> tuple[dict[str, Any], float]:  # type: ignore[no-untyped-def]
    assert result.issues == [], [i.message for i in result.issues]
    assert isinstance(flat, FlatResult) and flat.flat is not None
    assert len(solids(report.body.shape)) == 1
    return measure(report.body.shape), measure(flat.flat.shape)["volume"]


@pytest.mark.parametrize(
    "params",
    [
        {"tool": "dimple", "diameter": Param("12", 12.0), "height": Param("3", 3.0)},
        {"tool": "rib", "width": Param("8", 8.0), "height": Param("2", 2.0)},
        {
            "tool": "louvre",
            "length": Param("16", 16.0),
            "width": Param("6", 6.0),
            "height": Param("3", 3.0),
        },
    ],
)
def test_forms_rise_from_the_face_and_keep_the_blank(params: dict[str, Any]) -> None:
    m, flat_volume = _ok(*_formed(**params))
    height = params["height"].value
    assert m["bbox"][5] == pytest.approx(T + height)
    blank = 100 * 60 * T
    if params["tool"] == "louvre":
        blank -= 0.02 * 16 * T  # the lance
    assert flat_volume == pytest.approx(blank)


def test_reverse_presses_down() -> None:
    m, _v = _ok(
        *_formed(tool="dimple", diameter=Param("12", 12.0), height=Param("3", 3.0), reverse=True)
    )
    assert m["bbox"][2] == pytest.approx(-3.0)


@pytest.mark.parametrize(
    ("line", "params", "words"),
    [
        ((95, 30, 99, 30), {"diameter": Param("12", 12.0), "height": Param("3", 3.0)}, "runs off"),
        ((40, 30, 60, 30), {"diameter": Param("4", 4.0), "height": Param("3", 3.0)}, "too high"),
    ],
)
def test_form_errors(line: tuple[float, ...], params: dict[str, Any], words: str) -> None:
    _r, result, _f = _formed(line, tool="dimple", **params)  # type: ignore[arg-type]
    assert result.state is FeatureState.ERROR
    assert words in result.issues[0].message


def test_curves_other_than_lines_are_reported() -> None:
    """Audit A item 7 (D727): arcs, circles and splines were dropped with no message."""
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(40, 30, 60, 30)
    sk.sk.add_circle(20, 20, 3)
    sid = add_sketch(doc, sk, top, "Form Places")
    params = {"tool": "dimple", "diameter": Param("12", 12.0), "height": Param("3", 3.0)}
    fid = add(doc, "form_tool", {"sketch": {"feature": sid}}, **params)
    result = build(doc).results[fid]
    assert any(i.code == "form_curves_left_out" for i in result.issues)


def test_rib_with_square_ends_holds_more() -> None:
    """TR283 item 1 (D2311): a bead with square ends instead of round ones."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    def slice_volume(report: Any) -> float:
        """The rib cut by a thin slab just above the sheet (pressing keeps the volume)."""
        slab = BRepPrimAPI_MakeBox(gp_Pnt(-1, -1, T + 0.5), gp_Pnt(101, 61, T + 0.6)).Shape()
        return float(measure(BRepAlgoAPI_Common(report.body.shape, slab).Shape())["volume"])

    rib = {"tool": "rib", "width": Param("8", 8.0), "height": Param("2", 2.0)}
    round_r = _formed(**rib)
    square_r = _formed(rib_ends="square", **rib)
    square_m, flat_volume = _ok(*square_r)
    assert square_m["bbox"][5] == pytest.approx(T + 2.0)
    assert slice_volume(square_r[0]) > slice_volume(round_r[0]) + 1e-3
    assert flat_volume == pytest.approx(100 * 60 * T)


def _custom(**params: Any):  # type: ignore[no-untyped-def]
    """A 20 x 20 frustum tool body 4 mm high (30 degree sides) beside the plate, pressed
    into the plate on a line (TR279, D2313)."""
    from fdcad.core.document.model import Feature
    from fdcad.core.naming.names import centroid
    from fdcad.samples.builder import FRONT

    doc = sheet_doc(T, 1.0)
    plate(doc)
    sk = SketchBuilder()
    sk.rectangle(200, 0, 20, 20)
    tsk = add_sketch(doc, sk, {"feature": FRONT}, "Tool")
    tid = doc.new_feature_id()
    doc.features.append(Feature(tid, "extrude", "Tool", params={
        "operation": "boss", "end_condition": "blind", "depth": Param("4", 4.0),
        "merge": False, "draft_angle": Param("30 deg", 0.5235987756)},
        refs={"sketch": {"feature": tsk}}))  # fmt: skip
    stop, _p = face_ref(doc, (0.0, 0.0, -1.0), lambda f: centroid(f)[0] > 150)
    refs: dict[str, Any] = {"tool_face": [stop]}
    if params.pop("hole", False):
        cap, _p = face_ref(doc, (0.0, 0.0, 1.0), lambda f: centroid(f)[0] > 150)
        refs["remove_faces"] = [cap]
    top, _p = face_ref(doc, (0.0, 0.0, 1.0), lambda f: centroid(f)[0] < 150)
    sk2 = SketchBuilder()
    sk2.sk.add_line(40, 30, 60, 30)
    sid = add_sketch(doc, sk2, top, "Form Places")
    fid = add(doc, "form_tool", {"sketch": {"feature": sid}, **refs}, tool="custom", **params)
    flat = flat_pattern(doc, flattened=False)
    report = build(doc)
    return report, report.results[fid], report.results[flat]


def test_own_forming_tool_from_a_body() -> None:
    """TR279 (D2313): the tool body leaves the part; the sheet takes its shape."""
    report, res, flat = _custom()
    m, flat_volume = _ok(report, res, flat)
    assert m["bbox"][5] == pytest.approx(T + 4.0)
    assert m["bbox"][3] == pytest.approx(100.0)  # the tool body is gone
    assert flat_volume == pytest.approx(100 * 60 * T)
    # The insert point is the stop face's centre: the form is centred on the line.
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    for n, f in report.body.faces:
        if "/form" in n:
            BRepBndLib.Add_s(f, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    assert ((lo.X() + hi.X()) / 2, (lo.Y() + hi.Y()) / 2) == pytest.approx((50, 30), abs=0.05)
    turned = _custom(tool_angle=Param("45 deg", math.pi / 4), mirror=True)
    assert turned[1].state is FeatureState.OK, [i.message for i in turned[1].issues]


def test_own_forming_tool_removed_face_leaves_a_hole() -> None:
    report, res, _flat = _custom(hole=True)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    whole = _custom()[0]
    top = 20 - 2 * 4 * math.tan(math.radians(30))
    lost = measure(whole.body.shape)["volume"] - measure(report.body.shape)["volume"]
    assert lost == pytest.approx(top * top * T, rel=0.05)


def test_own_forming_tool_needs_a_flat_stop_face() -> None:
    _r, res, _f = _custom()
    assert res.state is FeatureState.OK
    _r, res, _f = _formed(tool="custom")
    assert res.state is FeatureState.ERROR and "stop face" in res.issues[0].message
