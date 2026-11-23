"""Weak names are checked against the stored snapshot (audit E item 13, DECISIONS D720).

A split piece (``#k``), a position fallback name (``<feature>/face#k``) and an
imported face index (``<feature>/face/<k>``) are numbered by position or by file
order, so an upstream edit can hand the number to another face. Each test builds
a reference on such a name, makes the edit that renumbers it, and checks that
the feature never stays OK on the wrong face: it warns and uses the right face,
or reports a lost reference. A plain dimension edit must still give no warning.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS
from tests.core.features.test_features import add_extrude, add_sketch, body, bounds, rect
from tests.core.features.test_patterns import X, centred, ok_body, pattern

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.import_replace import new_source
from fdcad.core.features.import_step import new_step_import
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.names import NamedShape, centroid, faces_of
from fdcad.core.naming.resolve import face_snapshot
from fdcad.core.naming.select import edge_snapshot, reference_for
from fdcad.core.occ import ShapeMap
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Point, Sketch, sketch_to_data
from fdcad.samples.step_source import colored_step_bytes


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def poly(s: Sketch, pts: list[tuple[float, float]]) -> None:
    """A closed outline of lines through ``pts``."""
    ids = [s.add_point(x, y) for x, y in pts]
    for p, q in zip(ids, ids[1:] + ids[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)


def messages(res: Any) -> list[str]:
    return [i.message for i in res.issues]


def midpoint(edge: Any, b: NamedShape) -> list[float]:
    return list(edge_snapshot(edge, b.shape)["midpoint"])


# Split pieces -------------------------------------------------------------------------


def slotted(
    slots: list[list[tuple[float, float]]], width: float = 50.0
) -> tuple[Document, str, str]:
    """A ``width`` by 50 by 10 plate with one through cut whose sketch holds ``slots``."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, width, 50)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    cut_sketch = Sketch()
    for outline in slots:
        poly(cut_sketch, outline)
    sk = add_sketch(doc, cut_sketch, {"kind": "face", "name": f"{ext}/cap/end"})
    cut = add_extrude(doc, sk, 1.0, operation="cut", end_condition="through_all", reverse=True)
    return doc, ext, cut


def across_y(x0: float, x1: float) -> list[tuple[float, float]]:
    """A slot from front to back between x0 and x1: it splits the top into left and right."""
    return [(x0, -5), (x1, -5), (x1, 55), (x0, 55)]


def across_x(y0: float, y1: float, tilt: float = 0.0) -> list[tuple[float, float]]:
    """A slot from left to right: it splits the top into front and back pieces."""
    return [(-5, y0), (55, y0 + tilt), (55, y1 + tilt), (-5, y1)]


def top_piece(doc: Document, ext: str, cut: str, near: tuple[float, float]) -> dict[str, Any]:
    """The reference to the piece of the plate's top whose centre is nearest ``near``."""
    b = body(rebuild(doc), cut)
    pieces = [f for n, f in b.faces if n.startswith(f"{ext}/cap/end#")]
    face = min(pieces, key=lambda f: math.dist(centroid(f)[:2], near))
    ref = reference_for(b, face)
    assert ref is not None
    return ref


def move_face(doc: Document, ref: dict[str, Any], distance: float = 2.0) -> str:
    fid = doc.new_feature_id()
    params = {"mode": "offset", "distance": P(distance), "reverse": False}
    doc.features.append(
        Feature(fid, "move_face", "Move Face 1", params=params, refs={"faces": [ref]})
    )
    return fid


def raised_top(b: NamedShape) -> tuple[float, float]:
    """The X and Y centre of the face that Move Face raised to z = 12."""
    for face in faces_of(b.shape):
        snap = face_snapshot(face)
        if snap.get("normal") == pytest.approx([0, 0, 1]) and snap["point"][2] == pytest.approx(12):
            return snap["point"][0], snap["point"][1]
    raise AssertionError("no face was raised")


def test_second_slot_in_the_cut_sketch_keeps_the_right_hand_piece() -> None:
    doc, ext, cut = slotted([across_y(20, 25)])
    ref = top_piece(doc, ext, cut, (40, 25))
    assert ref["name"] == f"{ext}/cap/end#2"
    doc, ext, cut = slotted([across_y(20, 25), across_y(5, 10)])
    mf = move_face(doc, ref)
    res = rebuild(doc)[mf]
    assert res.state is FeatureState.WARNING, messages(res)
    assert raised_top(res.body)[0] == pytest.approx(37.5)


def test_tilted_slot_keeps_the_back_piece() -> None:
    doc, ext, cut = slotted([across_x(20, 25)])
    ref = top_piece(doc, ext, cut, (25, 40))
    assert ref["name"] == f"{ext}/cap/end#2"
    doc, ext, cut = slotted([across_x(20, 25, tilt=0.001)])
    mf = move_face(doc, ref)
    res = rebuild(doc)[mf]
    assert res.state is FeatureState.WARNING, messages(res)
    assert raised_top(res.body)[1] == pytest.approx(37.5, abs=0.01)


def test_slot_tilted_the_other_way_keeps_the_numbers_and_gives_no_warning() -> None:
    doc, ext, cut = slotted([across_x(20, 25)])
    ref = top_piece(doc, ext, cut, (25, 40))
    doc, ext, cut = slotted([across_x(20, 25, tilt=-0.001)])
    mf = move_face(doc, ref)
    res = rebuild(doc)[mf]
    assert res.state is FeatureState.OK, messages(res)
    assert raised_top(res.body)[1] == pytest.approx(37.5, abs=0.01)


@pytest.mark.parametrize(
    ("slots", "width"),
    [
        ([across_y(22, 27)], 50.0),  # the slot moves 2 mm
        ([across_y(20, 25)], 60.0),  # the plate gets wider
        ([across_y(20, 25)], 40.0),  # the plate gets narrower
        ([across_y(30, 34)], 50.0),  # the slot moves past the old centre of the piece
    ],
)
def test_dimension_edit_on_a_split_piece_gives_no_warning(
    slots: list[list[tuple[float, float]]], width: float
) -> None:
    doc, ext, cut = slotted([across_y(20, 25)])
    ref = top_piece(doc, ext, cut, (40, 25))
    doc, ext, cut = slotted(slots, width)
    mf = move_face(doc, ref)
    res = rebuild(doc)[mf]
    assert res.state is FeatureState.OK, messages(res)
    x1 = slots[0][1][0]
    assert raised_top(res.body)[0] == pytest.approx((x1 + width) / 2)


def test_dimension_edit_on_a_front_and_back_split_gives_no_warning() -> None:
    doc, ext, cut = slotted([across_x(20, 25)])
    ref = top_piece(doc, ext, cut, (25, 40))
    doc, ext, cut = slotted([across_x(35, 40)])
    mf = move_face(doc, ref)
    res = rebuild(doc)[mf]
    assert res.state is FeatureState.OK, messages(res)
    assert raised_top(res.body)[1] == pytest.approx(45)


# Revolve fallback names ------------------------------------------------------------------


@dataclass
class Turned:
    """A stepped shaft: radius 10 up to y = 20, radius 6 up to y = 40, revolved fully."""

    doc: Document
    rev: str
    sketch_id: str
    sketch: Sketch
    ids: dict[str, str]

    def add_step(self) -> None:
        """Edit the profile: a new step at y = 10 to radius 8, so the shaft has 3 steps.

        The corner point at (10, 20) moves down to (10, 10) and two lines are added;
        every other entity keeps its id, as an edit in the sketch would.
        """
        s = self.sketch
        corner = s.entities[self.ids["c"]]
        assert isinstance(corner, Point)
        corner.y = 10.0
        q1, q2 = s.add_point(8, 10), s.add_point(8, 20)
        shoulder = s.entities[self.ids["cd"]]
        assert isinstance(shoulder, Line)
        shoulder.p1 = q2
        for p, q in ((self.ids["c"], q1), (q1, q2)):
            eid = s.new_id()
            s.entities[eid] = Line(eid, p, q)
        self.doc.feature(self.sketch_id).data = sketch_to_data(s)


def turned() -> Turned:
    doc = new_document()
    s = Sketch()
    keys = "abcdef"
    outline = [(0, 0), (10, 0), (10, 20), (6, 20), (6, 40), (0, 40)]
    ids = {k: s.add_point(x, y) for k, (x, y) in zip(keys, outline, strict=True)}
    for k, n in zip(keys, keys[1:] + keys[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, ids[k], ids[n])
        ids[k + n] = eid
    axis = s.add_line(0, -5, 0, 45, construction=True)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    params = {
        "operation": "boss",
        "direction": "one_direction",
        "angle": Param("360", 2 * math.pi),
    }
    refs = {"sketch": {"feature": sk}, "axis": {"sketch_entity": axis}}
    doc.features.append(Feature(fid, "revolve", "Revolve 1", params=params, refs=refs))
    return Turned(doc, fid, sk, s, ids)


def test_revolve_profile_gaining_a_segment_keeps_the_sketch_on_its_ring() -> None:
    shaft = turned()
    b = body(rebuild(shaft.doc), shaft.rev)
    ring = next(f for f in faces_of(b.shape) if centroid(f)[1] == pytest.approx(20))
    ref = reference_for(b, ring)
    assert ref is not None and "#" in ref["name"]  # a position fallback name
    s = Sketch()
    s.add_circle(7, 0, 0.5)
    sk = add_sketch(shaft.doc, s, ref)
    assert rebuild(shaft.doc)[sk].state is FeatureState.OK
    shaft.add_step()
    res = rebuild(shaft.doc)[sk]
    assert res.state is FeatureState.WARNING, messages(res)
    assert res.plane is not None
    assert res.plane.origin[1] == pytest.approx(20)
    assert res.plane.normal == pytest.approx((0, 1, 0))


def all_edges(shape: Any) -> list[Any]:
    emap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, emap)
    return [TopoDS.Edge(emap.FindKey(i)) for i in range(1, emap.Extent() + 1)]


def add_fillet(doc: Document, ref: dict[str, Any], radius: float) -> str:
    fid = doc.new_feature_id()
    params = {"fillet_type": "constant", "radius": P(radius)}
    doc.features.append(Feature(fid, "fillet", "Fillet 1", params=params, refs={"edges": [ref]}))
    return fid


def test_revolve_profile_gaining_a_segment_does_not_move_a_fillet_silently() -> None:
    """The picked corner (radius 10 at y = 20) is gone after the edit; the name now
    belongs to the corner at y = 10. The fillet must not stay OK on that corner."""
    shaft = turned()
    b = body(rebuild(shaft.doc), shaft.rev)
    corner = next(
        e
        for e in all_edges(b.shape)
        if edge_snapshot(e, b.shape).get("radius", 0) == pytest.approx(10)
        and edge_snapshot(e, b.shape)["midpoint"][1] == pytest.approx(20)
    )
    ref = reference_for(b, corner)
    assert ref is not None and "#" in ref["name"]
    fid = add_fillet(shaft.doc, ref, 1.0)
    assert rebuild(shaft.doc)[fid].state is FeatureState.OK
    shaft.add_step()
    after = body(rebuild(shaft.doc), shaft.rev)
    renamed = after.edges(ref["name"])
    assert len(renamed) == 1
    assert edge_snapshot(renamed[0], after.shape)["midpoint"][1] == pytest.approx(10)
    res = rebuild(shaft.doc)[fid]
    assert res.state is not FeatureState.OK, "the fillet moved to another corner silently"


# Imported faces, Replace From File -----------------------------------------------------------


def box_step(path: Path, extra: bool) -> bytes:
    """A 40 by 30 by 20 box, with a 10 by 10 by 5 block on its -X side when ``extra``.

    The block's faces come first in the file, so every face of the box gets a
    higher index than before, while the box itself is unchanged.
    """
    shape = BRepPrimAPI_MakeBox(40.0, 30.0, 20.0).Shape()
    if extra:
        block = BRepPrimAPI_MakeBox(gp_Pnt(-10, 0, 0), gp_Pnt(0, 10, 5)).Shape()
        shape = BRepAlgoAPI_Fuse(block, shape).Shape()
    path.write_bytes(colored_step_bytes(shape, "#888888"))
    return path.read_bytes()


def imported(tmp_path: Path) -> tuple[Document, str, NamedShape]:
    doc = new_document()
    bid, block, feature = new_step_import(doc, "box.step", box_step(tmp_path / "box.step", False))
    doc.embedded[bid] = block
    doc.features.append(feature)
    return doc, feature.id, body(rebuild(doc), feature.id)


def replace(doc: Document, fid: str, tmp_path: Path) -> NamedShape:
    data = box_step(tmp_path / "more.step", True)
    bid, block = new_source(doc, doc.feature(fid), "more.step", data)
    doc.embedded[bid] = block
    doc.feature(fid).refs["source"] = {"embedded": bid}
    return body(rebuild(doc), fid)


def test_replace_from_file_keeps_a_top_sketch_on_the_top(tmp_path: Path) -> None:
    doc, imp, b = imported(tmp_path)
    top = next(f for f in faces_of(b.shape) if centroid(f)[2] == pytest.approx(20))
    ref = reference_for(b, top)
    assert ref is not None
    s = Sketch()
    rect(s, 5, 5, 15, 15)
    sk = add_sketch(doc, s, ref)
    boss = add_extrude(doc, sk, 5.0)
    assert rebuild(doc)[boss].state is FeatureState.OK
    after = replace(doc, imp, tmp_path)
    moved = after.face(ref["name"])
    assert moved is not None and centroid(moved)[2] != pytest.approx(20)  # the index moved
    results = rebuild(doc)
    assert results[sk].state is FeatureState.WARNING, messages(results[sk])
    res = results[boss]
    cap = res.body.face(f"{boss}/cap/end")  # type: ignore[union-attr]
    assert cap is not None and centroid(cap)[2] == pytest.approx(25)


def filleted_import(
    tmp_path: Path, where: tuple[float, float, float]
) -> tuple[Document, str, str, dict[str, Any], NamedShape]:
    """An imported box with a 2 mm fillet on the edge whose midpoint is ``where``,
    then the file replaced; returns the document, ids, the reference and the new body."""
    doc, imp, b = imported(tmp_path)
    edge = next(e for e in all_edges(b.shape) if midpoint(e, b) == pytest.approx(list(where)))
    ref = reference_for(b, edge)
    assert ref is not None
    fid = add_fillet(doc, ref, 2.0)
    assert rebuild(doc)[fid].state is FeatureState.OK
    after = replace(doc, imp, tmp_path)
    found = after.edges(ref["name"])
    assert len(found) == 1 and midpoint(found[0], after) != pytest.approx(list(where))
    return doc, imp, fid, ref, after


def test_replace_from_file_keeps_a_fillet_on_its_edge(tmp_path: Path) -> None:
    """The top right edge's name now names an edge of the new block."""
    doc, _imp, fid, _ref, after = filleted_import(tmp_path, (40, 15, 20))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.WARNING, messages(res)
    removed = volume_of(after.shape) - volume_of(res.body.shape)  # type: ignore[union-attr]
    assert removed == pytest.approx(30 * (1 - math.pi / 4) * 4, rel=1e-3)


def test_replace_from_file_never_fillets_another_edge_silently(tmp_path: Path) -> None:
    """The left front edge is cut short by the new block; its name names a block edge."""
    doc, _imp, fid, _ref, _after = filleted_import(tmp_path, (0, 0, 10))
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.OK, "the fillet moved to another edge silently"


def test_replace_from_file_keeps_move_face_on_its_face(tmp_path: Path) -> None:
    doc, imp, b = imported(tmp_path)
    side = next(f for f in faces_of(b.shape) if centroid(f)[1] == pytest.approx(30))  # back
    ref = reference_for(b, side)
    assert ref is not None
    mf = move_face(doc, ref)
    assert rebuild(doc)[mf].state is FeatureState.OK
    after = replace(doc, imp, tmp_path)
    moved = after.face(ref["name"])
    assert moved is not None and centroid(moved)[1] != pytest.approx(30)  # the index moved
    res = rebuild(doc)[mf]
    assert res.state is FeatureState.WARNING, messages(res)
    grown = volume_of(res.body.shape) - volume_of(after.shape)  # type: ignore[union-attr]
    assert grown == pytest.approx(40 * 20 * 2, rel=1e-6)


# Mirror ---------------------------------------------------------------------------------------


def test_mirrored_boss_top_faces_up_and_a_boss_on_it_grows_up() -> None:
    doc, _plate, boss = centred()  # boss top at z = 16
    fid, results = pattern(doc, "mirror", {}, {"plane": X, "features": [{"feature": boss}]})
    b = ok_body(results, fid)
    top = b.face(f"{fid}/mirror1/{boss}/cap/end")
    assert top is not None
    assert face_snapshot(top)["normal"] == pytest.approx([0, 0, 1])
    ref = reference_for(b, top)
    assert ref is not None
    s = Sketch()
    rect(s, -12, 8, -8, 12)
    sk = add_sketch(doc, s, ref)
    plane = rebuild(doc)[sk].plane
    assert plane is not None and plane.normal == pytest.approx((0, 0, 1))
    up = add_extrude(doc, sk, 3.0)
    res = rebuild(doc)[up]
    assert res.state is FeatureState.OK, messages(res)
    cap = res.body.face(f"{up}/cap/end")  # type: ignore[union-attr]
    assert cap is not None
    assert bounds(cap) == pytest.approx((-12, 8, 19, -8, 12, 19), abs=1e-6)


def test_faces_numbered_by_position_are_weak_names() -> None:
    """D1068: Indent and Half Lap number their new faces. A reference to one is
    checked against where it was picked, as for the other numbered names."""
    from fdcad.core.naming import weak

    assert weak.is_weak("f225/indent/2") and weak.is_weak("f225/indent/w13")
    assert weak.is_weak("f236/lap/10")
    assert weak.family_root("f225/indent/2") == "f225/indent/*"
    assert weak.family_root("f225/indent/w13") == "f225/indent/w*"
    assert weak.family_root("f236/lap/10") == "f236/lap/*"
    assert weak.family_root("edge(f225/indent/2|f6/cap/end)") == "edge(f225/indent/*|f6/cap/end)"
    for stable in ("f6/side/e3", "f9/zone1.plane1", "f58/relief/2", "f6/cap/end"):
        assert not weak.is_weak(stable)
        assert weak.family_root(stable) == stable
