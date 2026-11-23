"""Closed Corner (D533) and Break Corner (D534)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.naming.names import centroid
from fdcad.samples.builder import face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    build,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)

T, R = 2.0, 1.0
WALL = 20 - (R + T)  # flange wall width: length from the outer virtual sharp


def box_tray() -> Document:
    """Plate 100 x 60 with 20 mm flanges on the y = 60 and x = 100 edges."""
    doc = sheet_doc(T, R)
    plate(doc)
    edges = [edge_ref(doc, on(y=60.0, z=T)), edge_ref(doc, on(x=100.0, z=T))]
    add(
        doc,
        "edge_flange",
        {"edges": edges},
        length=Param("20", 20.0),
        trim_side_bends=True,
        gap=Param("1", 1.0),
    )
    return doc


def _volumes(doc: Document, flat: str) -> tuple[float, float]:
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.flat is not None
    return measure(report.body.shape)["volume"], measure(result.flat.shape)["volume"]


def _end_face(doc: Document) -> dict[str, Any]:
    ref, _plane = face_ref(doc, (1.0, 0.0, 0.0), lambda f: abs(centroid(f)[0] - 96) < 1e-6)
    return ref


@pytest.mark.parametrize(
    ("kind", "grow"),
    [
        ("overlap", (4.0 + 1.9) * WALL * T),
        ("underlap", (1.9 + 4.0) * WALL * T),
        # Both walls meet the 45 degree plane, each 0.05 mm short of it.
        ("butt", 2 * (3.0 - 0.05 * 2**0.5) * WALL * T),
    ],
)
def test_closed_corner_adds_exact_tabs(kind: str, grow: float) -> None:
    doc = box_tray()
    flat = flat_pattern(doc, flattened=False)
    before = _volumes(doc, flat)
    doc.features.pop()
    add(doc, "closed_corner", {"faces": [_end_face(doc)]}, corner_type=kind, gap=Param("0.1", 0.1))
    flat = flat_pattern(doc, flattened=False)
    after = _volumes(doc, flat)
    added = after[1] - before[1]
    assert after[0] - before[0] == pytest.approx(added)  # walls only: folded = flat
    assert added == pytest.approx(grow)


def test_closed_corner_needs_a_wall_end() -> None:
    doc = box_tray()
    top, _p = face_ref(doc, (0.0, 0.0, 1.0), lambda f: centroid(f)[2] < 2.5)
    cid = add(doc, "closed_corner", {"faces": [top]})
    result = build(doc).results[cid]
    assert result.state is FeatureState.ERROR
    assert "end of a flange wall" in result.issues[0].message


def _broken(**params: Any) -> tuple[Document, str, str]:
    doc = sheet_doc(T, R)
    plate(doc)
    corner = edge_ref(doc, on(x=100.0, y=60.0))
    bid = add(doc, "break_corner", {"edges": [corner]}, **params)
    return doc, bid, flat_pattern(doc, flattened=False)


@pytest.mark.parametrize(
    ("params", "removed"),
    [
        ({"distance": Param("5", 5.0)}, 5 * 5 / 2 * T),
        ({"break_type": "fillet", "radius": Param("8", 8.0)}, 64 * (1 - 3.141592653589793 / 4) * T),
    ],
)
def test_break_corner_volume_and_flat(params: dict[str, Any], removed: float) -> None:
    doc, _b, flat = _broken(**params)
    folded, flat_vol = _volumes(doc, flat)
    assert folded == pytest.approx(100 * 60 * T - removed)
    assert flat_vol == pytest.approx(folded)


@pytest.mark.parametrize(
    ("params", "words"),
    [
        ({"distance": Param("70", 70.0)}, "larger than"),
        ({"break_type": "fillet", "radius": Param("0", 0.0)}, "greater than zero"),
    ],
)
def test_break_corner_errors(params: dict[str, Any], words: str) -> None:
    doc, bid, _f = _broken(**params)
    result = build(doc).results[bid]
    assert result.state is FeatureState.ERROR
    assert words in result.issues[0].message


def test_break_corner_on_a_flange_end() -> None:
    doc = box_tray()
    flat = flat_pattern(doc, flattened=False)
    before = _volumes(doc, flat)
    doc.features.pop()

    def top_corner(a: Any, b: Any) -> bool:
        return all(abs(p[0]) < 1e-6 and abs(p[2] - 20) < 1e-6 for p in (a, b))

    add(doc, "break_corner", {"edges": [edge_ref(doc, top_corner)]}, distance=Param("3", 3.0))
    flat = flat_pattern(doc, flattened=False)
    after = _volumes(doc, flat)
    assert before[0] - after[0] == pytest.approx(3 * 3 / 2 * T)
    assert before[1] - after[1] == pytest.approx(3 * 3 / 2 * T)


def _l_plate() -> Document:
    from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch

    doc = sheet_doc(T, R)
    sk = SketchBuilder()
    pts = [(0, 0), (100, 0), (100, 30), (50, 30), (50, 60), (0, 60)]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        sk.sk.add_line(p[0], p[1], q[0], q[1])
    sid = add_sketch(doc, sk, {"feature": FRONT}, "L")
    add(doc, "base_flange", {"sketch": {"feature": sid}})
    return doc


def test_break_corner_collects_all_outside_corners() -> None:
    """TR174 item 5 (D1107)."""
    doc = sheet_doc(T, R)
    plate(doc)
    add(doc, "break_corner", collect_all=True, distance=Param("5", 5.0))
    folded, flat_vol = _volumes(doc, flat_pattern(doc, flattened=False))
    assert folded == pytest.approx(100 * 60 * T - 4 * 12.5 * T)
    assert flat_vol == pytest.approx(folded)


@pytest.mark.parametrize(
    ("params", "added"),
    [
        ({"distance": Param("5", 5.0)}, 12.5 * T),
        ({"break_type": "fillet", "radius": Param("8", 8.0)}, 64 * (1 - 3.141592653589793 / 4) * T),
    ],
)
def test_break_corner_fills_inside_corners(params: dict[str, Any], added: float) -> None:
    doc = _l_plate()
    base = (100 * 60 - 50 * 30) * T
    add(doc, "break_corner", collect_all=True, corner_kind="inside", **params)
    folded, flat_vol = _volumes(doc, flat_pattern(doc, flattened=False))
    assert folded == pytest.approx(base + added)
    assert flat_vol == pytest.approx(folded)


def test_closed_corner_overlap_ratio() -> None:
    """TR174 item 2 (D1107): the cover wall reaches half way across the other wall."""
    doc = box_tray()
    flat = flat_pattern(doc, flattened=False)
    before = _volumes(doc, flat)
    doc.features.pop()
    add(
        doc, "closed_corner", {"faces": [_end_face(doc)]}, corner_type="overlap",
        gap=Param("0.1", 0.1), overlap_ratio=Param("0.5", 0.5),
    )  # fmt: skip
    after = _volumes(doc, flat_pattern(doc, flattened=False))
    assert after[0] - before[0] == pytest.approx((3.0 + 1.9) * WALL * T)
    doc.features[-2].params["overlap_ratio"] = Param("2", 2.0)
    res = build(doc).results[doc.features[-2].id]
    assert res.state is FeatureState.ERROR and "Enter another ratio" in res.issues[0].message


def test_closed_bend_region_fills_the_corner_between_the_bends() -> None:
    """TR174 item 2 (D2308): folded part only, the flat pattern is unchanged."""
    doc = box_tray()
    add(doc, "closed_corner", {"faces": [_end_face(doc)]}, gap=Param("0.1", 0.1))
    open_ = _volumes(doc, flat_pattern(doc, flattened=False))
    doc = box_tray()
    add(
        doc, "closed_corner", {"faces": [_end_face(doc)]}, gap=Param("0.1", 0.1),
        bend_region="closed",
    )  # fmt: skip
    closed = _volumes(doc, flat_pattern(doc, flattened=False))
    assert closed[1] == pytest.approx(open_[1])
    # At most the vault where two quarter tubes of radius 1 to 3 cross: 16 / 3 (3^3 - 1).
    grown = closed[0] - open_[0]
    assert 0.5 < grown < 16 / 3 * 26 / 8 + 1e-6
    report = build(doc)
    from fdcad.core.features.solids import solids

    assert len(solids(report.body.shape)) == 1


# A tray with four walls (D1071) ------------------------------------------------------
#
# Found on a sheet metal stress part (2026-11-12). Every test above has two walls at
# most, never two that face each other. A pick on the back or left wall was matched to
# the front or right wall, which is parallel to it and comes first.


def four_wall_tray() -> Document:
    """Plate 100 x 60 with 20 mm flanges on all four edges."""
    doc = sheet_doc(T, R)
    plate(doc)
    edges = [
        edge_ref(doc, on(y=0.0, z=T)),
        edge_ref(doc, on(x=100.0, z=T)),
        edge_ref(doc, on(y=60.0, z=T)),
        edge_ref(doc, on(x=0.0, z=T)),
    ]
    add(doc, "edge_flange", {"edges": edges}, length=Param("20", 20.0), trim_side_bends=True)
    return doc


def _inside(doc: Document, point: tuple[float, float, float]) -> bool:
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    body = build(doc).body
    assert body is not None
    return bool(BRepClass3d_SolidClassifier(body.shape, gp_Pnt(*point), 1e-7).State() == TopAbs_IN)


#: Each wall: a point just inside its top corner at the low end, and at the high end.
TOP_CORNERS = {
    "front": ((3.5, 1.0, 19.5), (96.5, 1.0, 19.5)),
    "right": ((99.0, 3.5, 19.5), (99.0, 56.5, 19.5)),
    "back": ((3.5, 59.0, 19.5), (96.5, 59.0, 19.5)),
    "left": ((1.0, 3.5, 19.5), (1.0, 56.5, 19.5)),
}


@pytest.mark.parametrize("wall", ["front", "right", "back", "left"])
def test_break_corner_cuts_the_corner_of_the_wall_that_was_picked(wall: str) -> None:
    doc = four_wall_tray()
    # The corner edge runs through the sheet: along Y on the front and back walls.
    axis = 1 if wall in ("front", "back") else 0
    end = [3.0, 3.0, 20.0]
    end[axis] = {"front": 1.0, "back": 59.0, "right": 99.0, "left": 1.0}[wall]
    edge = edge_ref(doc, lambda a, b: all(
        abs((a[i] + b[i]) / 2 - end[i]) < 1e-6 for i in range(3)
    ))  # fmt: skip
    assert all(_inside(doc, p) for pair in TOP_CORNERS.values() for p in pair)
    add(doc, "break_corner", {"edges": [edge]}, distance=Param("2", 2.0))
    cut = {name: [not _inside(doc, p) for p in pair] for name, pair in TOP_CORNERS.items()}
    assert cut == {name: [name == wall, False] for name in TOP_CORNERS}


@pytest.mark.parametrize(
    ("wall", "pick", "filled"),
    [
        ("front", (97.0, 1.0, 12.0), (99.0, 1.0, 12.0)),
        ("back", (97.0, 59.0, 12.0), (99.0, 59.0, 12.0)),
        ("right", (99.0, 57.0, 12.0), (99.0, 59.0, 12.0)),
        ("left", (1.0, 57.0, 12.0), (1.0, 59.0, 12.0)),
    ],
)
def test_closed_corner_closes_the_corner_of_the_wall_that_was_picked(
    wall: str, pick: tuple[float, float, float], filled: tuple[float, float, float]
) -> None:
    doc = four_wall_tray()
    corners = [(1.0, 1.0, 12.0), (99.0, 1.0, 12.0), (99.0, 59.0, 12.0), (1.0, 59.0, 12.0)]
    assert not any(_inside(doc, c) for c in corners)
    normal = (1.0, 0.0, 0.0) if wall in ("front", "back") else (0.0, 1.0, 0.0)
    ref, _plane = face_ref(
        doc,
        normal,
        lambda f: all(abs(centroid(f)[i] - pick[i]) < (1.5, 1.5, 4.0)[i] for i in range(3)),
    )
    add(doc, "closed_corner", {"faces": [ref]}, gap=Param("0.2", 0.2))
    assert [c for c in corners if _inside(doc, c)] == [filled]
