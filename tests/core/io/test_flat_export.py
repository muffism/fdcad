"""DXF and SVG export of a flat face or a sketch (PLAN Phase 2, DECISIONS D350)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Ax2, gp_Dir, gp_Elips, gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.io import fdef
from fdcad.core.io.export import ExportError
from fdcad.core.io.flat_export import (
    FlatArc,
    FlatLine,
    FlatPolyline,
    export_flat,
    face_edges,
    face_plane,
    flatten,
    sketch_items,
    to_dxf,
    to_svg,
)
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR

GOLDEN = Path(__file__).parents[2] / "golden" / "flat"


def _faces(shape: object) -> list[object]:
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def _plate_face(normal_z: float = 1.0) -> object:
    """The top (or bottom) face of the plate with holes sample."""
    doc = fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt")
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    for face in _faces(body.shape):
        try:
            plane = face_plane(face)
        except ExportError:
            continue
        if abs(plane.Direction().Z() - normal_z) < 1e-9 and len(face_edges(face)) == 9:
            return face
    raise AssertionError("no face found")


def test_plate_face_is_flat_at_true_size() -> None:
    face = _plate_face()
    items = flatten(face_edges(face), face_plane(face))
    lines = [i for i in items if isinstance(i, FlatLine)]
    circles = [i for i in items if isinstance(i, FlatArc)]
    assert len(lines) == 4 and len(circles) == 5
    assert sorted(round(c.radius, 9) for c in circles) == [4, 4, 4, 4, 10]
    assert all(c.full for c in circles)
    lengths = sorted(round(math.dist(i.a, i.b), 9) for i in lines)
    assert lengths == [60, 60, 100, 100]


@pytest.mark.parametrize("kind", ["dxf", "svg"])
def test_plate_face_matches_golden_files(kind: str, tmp_path: Path) -> None:
    face = _plate_face()
    target = tmp_path / f"plate_top.{kind}"
    export_flat(face_edges(face), face_plane(face), target, "mm")
    assert target.read_text(encoding="utf-8") == (GOLDEN / f"plate_top.{kind}").read_text(
        encoding="utf-8"
    )


def test_bottom_face_is_seen_from_outside() -> None:
    """The bottom face is not mirrored: the outline is the same shape seen from below."""
    top, bottom = _plate_face(1.0), _plate_face(-1.0)
    a = flatten(face_edges(top), face_plane(top))
    b = flatten(face_edges(bottom), face_plane(bottom))
    ra = sorted(round(i.radius, 6) for i in a if isinstance(i, FlatArc))
    rb = sorted(round(i.radius, 6) for i in b if isinstance(i, FlatArc))
    assert ra == rb
    plane = face_plane(bottom)
    x, y, z = plane.XDirection(), plane.YDirection(), plane.Direction()
    cross = (
        x.Y() * y.Z() - x.Z() * y.Y(),
        x.Z() * y.X() - x.X() * y.Z(),
        x.X() * y.Y() - x.Y() * y.X(),
    )
    assert cross == pytest.approx((z.X(), z.Y(), z.Z()))  # right handed, not mirrored
    assert z.Z() == pytest.approx(-1.0)


def test_inch_parts_are_written_in_inches(tmp_path: Path) -> None:
    face = _plate_face()
    target = tmp_path / "plate.dxf"
    export_flat(face_edges(face), face_plane(face), target, "in")
    text = target.read_text(encoding="utf-8")
    assert "$INSUNITS\n70\n1\n" in text
    svg = to_svg(flatten(face_edges(face), face_plane(face), 25.4), "in")
    width = re.search(r'width="([0-9.]+)in"', svg)
    assert width is not None and float(width.group(1)) == pytest.approx(100 / 25.4, abs=1e-6)


def _arc_face() -> object:
    """A half disc of radius 10 in the XY plane: one arc and one line."""
    arc = GC_MakeArcOfCircle(gp_Pnt(10, 0, 0), gp_Pnt(0, 10, 0), gp_Pnt(-10, 0, 0)).Value()
    wire = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(arc).Edge(),
        BRepBuilderAPI_MakeEdge(gp_Pnt(-10, 0, 0), gp_Pnt(10, 0, 0)).Edge(),
    ).Wire()
    return BRepBuilderAPI_MakeFace(wire, True).Face()


def test_arcs_run_anticlockwise_and_svg_uses_the_small_arc() -> None:
    face = _arc_face()
    items = flatten(face_edges(face), face_plane(face))
    arcs = [i for i in items if isinstance(i, FlatArc)]
    assert len(arcs) == 1 and not arcs[0].full
    arc = arcs[0]
    plane = face_plane(face)
    # In the face's own frame the arc covers half a turn, anticlockwise.
    assert (arc.end - arc.start) % 360 == pytest.approx(180)
    assert plane.Direction().Z() == pytest.approx(1.0)
    assert (arc.start, arc.end) == (pytest.approx(0), pytest.approx(180))
    dxf = to_dxf(items)
    assert "\nARC\n" in dxf and "\n50\n0\n51\n180\n" in dxf
    assert " 0 0 0 " in to_svg(items)  # radius, then large arc 0 and sweep 0


def test_other_curves_become_polylines_close_to_the_curve() -> None:
    ellipse = gp_Elips(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 20, 10)
    edge = BRepBuilderAPI_MakeEdge(ellipse).Edge()
    face = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(edge).Wire(), True).Face()
    items = flatten(face_edges(face), face_plane(face))
    assert len(items) == 1 and isinstance(items[0], FlatPolyline)
    pts = items[0].points
    center = (pts.max(axis=0) + pts.min(axis=0)) / 2  # the face frame may move and turn it
    radius = np.hypot(pts[:, 0] - center[0], pts[:, 1] - center[1])
    assert radius.max() == pytest.approx(20, abs=0.01)
    assert radius.min() == pytest.approx(10, abs=0.01)
    assert np.allclose(pts[0], pts[-1])  # a closed curve ends where it starts
    assert "POLYLINE" in to_dxf(items) and "<polyline" in to_svg(items)


def test_sketch_export_leaves_construction_out(tmp_path: Path) -> None:
    doc = fdef.load(SAMPLE_DIR / "turned_shaft.fdprt")
    report = RebuildEngine().rebuild(doc)
    sketch = next(f for f in doc.features if f.type == "sketch")
    out = report.results[sketch.id].sketch
    assert out is not None
    edges, plane = sketch_items(out.model, out.plane)
    items = flatten(edges, plane)
    assert len(items) == 8  # the outline, not the centreline
    target = tmp_path / "profile.svg"
    export_flat(edges, plane, target)
    assert 'width="120mm" height="15mm"' in target.read_text(encoding="utf-8")


def test_curved_faces_and_bad_names_are_refused(tmp_path: Path) -> None:
    doc = fdef.load(SAMPLE_DIR / "turned_shaft.fdprt")
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    curved = []
    for face in _faces(body.shape):
        try:
            face_plane(face)
        except ExportError:
            curved.append(face)
    assert curved
    face = _plate_face()
    with pytest.raises(ExportError, match=r"dxf or \.svg"):
        export_flat(face_edges(face), face_plane(face), tmp_path / "x.txt")
    with pytest.raises(ExportError, match="nothing to export"):
        flatten([], face_plane(face))


def test_a_part_arc_is_bounded_by_its_own_extent() -> None:
    """Audit D item 19 (D742): the SVG size counted the whole circle of a part arc."""
    from fdcad.core.io.flat_export import FlatArc, _bounds

    quarter = FlatArc((0.0, 0.0), 10.0, 0.0, 90.0)
    assert _bounds([quarter]) == pytest.approx((0.0, 0.0, 10.0, 10.0), abs=1e-9)
    across = FlatArc((0.0, 0.0), 10.0, 300.0, 60.0)  # passes through 0 degrees
    assert _bounds([across]) == pytest.approx((5.0, -10 * 3**0.5 / 2, 10.0, 10 * 3**0.5 / 2))
    assert _bounds([FlatArc((0.0, 0.0), 10.0)]) == (-10.0, -10.0, 10.0, 10.0)
