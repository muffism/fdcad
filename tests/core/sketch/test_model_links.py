"""Model geometry snapping core (WP14, D250): projection, sources and stale copies."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.naming.names import NamedShape
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.links import (
    LinkUpdate,
    ModelCircle,
    ModelLine,
    ModelPoint,
    apply_links,
    check_links,
    link_keys,
    source_data,
    updates_from_data,
    updates_to_data,
)
from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.sketch.projection import find_sources, project_model
from tests.core.features.test_features import add_extrude, add_sketch, body, rect

TOP_FACE = SketchPlane((0.0, 0.0, 10.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))


def _plate_with_hole() -> tuple[object, str, NamedShape]:
    """A 50 by 30 plate, 10 thick, with a radius 5 hole at (20, 15)."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    s.add_circle(20, 15, 5)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 10.0)
    return doc, ext, body(rebuild(doc), ext)


def test_projection_finds_corners_edges_centres_and_origin() -> None:
    _, _, b = _plate_with_hole()
    g = project_model(b, TOP_FACE)
    xy = {(round(p.xy[0], 6), round(p.xy[1], 6)) for p in g.points}
    assert {(0.0, 0.0), (50.0, 0.0), (50.0, 30.0), (0.0, 30.0), (20.0, 15.0)} <= xy
    # Top and bottom corners overlap: kept once, the one on the sketch plane. The corner
    # on the origin is the origin target.
    corners = [p for p in g.points if p.source and p.source[0] == "vertex"]
    assert len(corners) == 3 and all(p.depth == pytest.approx(0.0) for p in corners)
    assert len(g.lines) == 4  # vertical edges project to points and are left out
    assert all(line.source and line.source[1].startswith("edge(") for line in g.lines)
    assert len(g.circles) == 1
    c = g.circles[0]
    assert c.centre == pytest.approx((20.0, 15.0)) and c.radius == pytest.approx(5.0)
    assert c.depth == pytest.approx(0.0)
    assert g.polylines  # everything drawn, including the slanted view's ellipses


def test_names_match_the_naming_module() -> None:
    _, _, b = _plate_with_hole()
    g = project_model(b, TOP_FACE)
    for line in g.lines:
        assert line.source is not None
        assert b.edge(line.source[1]) is not None


def test_slanted_circle_is_drawn_but_not_a_circle_target() -> None:
    _, _, b = _plate_with_hole()
    side = SketchPlane((0.0, 0.0, 0.0), (0.0, -1.0, 0.0), (1.0, 0.0, 0.0))
    g = project_model(b, side)
    assert g.circles == []
    assert len(g.polylines) > 4


def test_empty_part_gives_only_the_origin() -> None:
    plane = SketchPlane((0.0, 0.0, 5.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    g = project_model(None, plane)
    assert g.empty and g.points == [ModelPoint((0.0, 0.0), ("origin", ""), 0.0)]


def test_find_sources_resolves_by_name_and_reports_lost() -> None:
    _, _, b = _plate_with_hole()
    g = project_model(b, TOP_FACE)
    line, circle = g.lines[0], g.circles[0]
    assert line.source is not None and circle.source is not None
    lost = ("edge", "edge(f99/cap/end|f99/side/e1)")
    found = find_sources(b, TOP_FACE, [line.source, circle.source, ("origin", ""), lost])
    assert isinstance(found[line.source], ModelLine)
    assert isinstance(found[circle.source], ModelCircle)
    assert found[("origin", "")] == ModelPoint((0.0, 0.0), ("origin", ""))
    assert found[lost] is None


def _linked_sketch() -> Sketch:
    s = Sketch()
    p = s.add_point(20, 15, True)
    s.entities[p].source = {"kind": "edge", "name": "edge(a|b)"}  # type: ignore[union-attr]
    lid = s.add_line(0, 0, 50, 0, True)
    s.entities[lid].source = {"kind": "edge", "name": "edge(c|d)"}  # type: ignore[union-attr]
    s.relate("fixed", p, lid)
    return s


def test_check_and_apply_links() -> None:
    s = _linked_sketch()
    assert link_keys(s) == {("edge", "edge(a|b)"), ("edge", "edge(c|d)")}
    same = {
        ("edge", "edge(a|b)"): ModelCircle((20, 15), 5, None),
        ("edge", "edge(c|d)"): ModelLine((50, 0), (0, 0), None),  # reversed counts as the same
    }
    assert check_links(s, same) == []
    moved = {
        ("edge", "edge(a|b)"): ModelCircle((25, 15), 5, None),
        ("edge", "edge(c|d)"): None,
    }
    updates = check_links(s, moved)
    assert updates == [LinkUpdate("e1", (25.0, 15.0)), LinkUpdate("e4", None)]
    assert updates[1].lost
    assert updates_from_data(updates_to_data(updates)) == updates
    assert apply_links(s, updates) == 1
    assert s.xy("e1") == (25.0, 15.0) and s.xy("e3") == (50.0, 0.0)


def test_line_update_keeps_its_ends_in_place() -> None:
    s = _linked_sketch()
    line = s.entities["e4"]
    apply_links(s, [LinkUpdate("e4", (52.0, 1.0, 1.0, 1.0))])
    assert s.xy(line.p1) == (1.0, 1.0) and s.xy(line.p2) == (52.0, 1.0)  # type: ignore[union-attr]


def test_source_round_trips_and_older_entities_have_no_key() -> None:
    s = _linked_sketch()
    s.add_point(1, 2)
    data = sketch_to_data(s)
    assert data["entities"][0]["source"] == {"kind": "edge", "name": "edge(a|b)"}
    assert "source" not in data["entities"][-1]
    again = sketch_from_data(data)
    assert sketch_to_data(again) == data
    assert source_data(("origin", "")) == {"kind": "origin"}
    with pytest.raises(ValueError, match="source"):
        sketch_from_data({"entities": [{"id": "e1", "type": "point", "x": 0, "y": 0,
                                        "source": {"kind": "bogus"}}]})  # fmt: skip


def test_rebuild_warns_when_the_part_moves_a_copy_and_offers_update() -> None:
    doc, ext, b = _plate_with_hole()
    centre = project_model(b, TOP_FACE).circles[0]
    assert centre.source is not None
    top = {"kind": "face", "name": f"{ext}/cap/end"}
    s = Sketch()
    copy = s.add_point(20, 15, True)
    s.entities[copy].source = source_data(centre.source)  # type: ignore[union-attr]
    s.relate("fixed", copy)
    q = s.add_point(30, 15)
    s.relate("coincident", q, copy)
    sk2 = add_sketch(doc, s, top)  # type: ignore[arg-type]
    results = rebuild(doc)  # type: ignore[arg-type]
    assert results[sk2].state is FeatureState.OK
    # Move the hole: the copy is now 5 mm away from its source.
    sk1 = doc.features[4]  # type: ignore[attr-defined]
    sk1.data["entities"][-2]["x"] = 25.0  # the circle centre point
    results = rebuild(doc)  # type: ignore[arg-type]
    res = results[sk2]
    assert res.state is FeatureState.WARNING
    issue = next(i for i in res.issues if i.code == "stale_links")
    assert "no longer matches" in issue.message and "Update Copies" in issue.message
    assert issue.fixes[0].label == "Update Copies"
    updates = updates_from_data(issue.fixes[0].data["updates"])
    assert updates == [LinkUpdate(copy, pytest.approx((25.0, 15.0)))]  # type: ignore[arg-type]
    # The copy itself is untouched until the user confirms (CLAUDE.md rule 12).
    assert doc.feature(sk2).data["entities"][0]["x"] == 20  # type: ignore[attr-defined]
    assert "\u2013" not in issue.message and "\u2014" not in issue.message


def test_lost_source_is_a_warning_without_a_fix() -> None:
    doc, ext, _ = _plate_with_hole()
    s = Sketch()
    copy = s.add_point(3, 3, True)
    s.entities[copy].source = {"kind": "vertex", "name": "vertex(x|y|z)"}  # type: ignore[union-attr]
    s.relate("fixed", copy)
    sk2 = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})  # type: ignore[arg-type]
    res = rebuild(doc)[sk2]  # type: ignore[arg-type]
    issue = next(i for i in res.issues if i.code == "lost_links")
    assert issue.fixes == [] and res.state is FeatureState.WARNING


def test_linked_sketch_rebuilds_when_the_part_changes() -> None:
    from fdcad.core.rebuild.engine import RebuildEngine

    doc, ext, _ = _plate_with_hole()
    s = Sketch()
    copy = s.add_point(0, 0, True)
    s.entities[copy].source = {"kind": "origin"}  # type: ignore[union-attr]
    sk2 = add_sketch(doc, s, {"feature": "f3"})  # type: ignore[arg-type]
    engine = RebuildEngine()
    engine.rebuild(doc)  # type: ignore[arg-type]
    doc.feature(ext).params["depth"] = Param("12", 12.0)  # type: ignore[attr-defined]
    report = engine.rebuild(doc)  # type: ignore[arg-type]
    assert sk2 in report.rebuilt


def test_file_with_sources_round_trips() -> None:
    doc, _, _ = _plate_with_hole()
    s = Sketch()
    copy = s.add_point(0, 0, True)
    s.entities[copy].source = {"kind": "origin"}  # type: ignore[union-attr]
    add_sketch(doc, s, {"feature": "f3"})  # type: ignore[arg-type]
    text = fdef.dumps(doc)  # type: ignore[arg-type]
    assert '"source": {' in text
    assert fdef.dumps(fdef.loads(text)) == text


def test_projection_and_snap_queries_stay_fast() -> None:
    """A plate with 144 holes: one projection, then cheap queries (CLAUDE.md 5A, D250)."""
    import time

    from fdcad.ui.sketch_tools.model_snap import ModelSnapIndex

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 240, 240)
    for i in range(12):
        for j in range(12):
            s.add_circle(10 + 20 * i, 10 + 20 * j, 4)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 10.0)
    b = body(rebuild(doc), ext)
    t0 = time.perf_counter()
    g = project_model(b, TOP_FACE)
    projected = time.perf_counter() - t0
    assert len(g.circles) == 144
    assert projected < 5.0
    index = ModelSnapIndex(g)
    t0 = time.perf_counter()
    for k in range(200):
        index.query((k * 1.2, 100.0), 0.5)
    per_query = (time.perf_counter() - t0) / 200
    assert per_query < 0.005


def test_older_files_have_no_sources_and_save_unchanged() -> None:
    from pathlib import Path

    from fdcad.core.features.base import REGISTRY
    from fdcad.samples.make import SAMPLE_DIR

    fixture = Path(__file__).parents[2] / "fixtures" / "extrude_revolve_0_1_0.fdef"
    for path in [fixture, *sorted(SAMPLE_DIR.glob("*.fdprt"))]:
        text = path.read_text(encoding="utf-8")
        doc = fdef.loads(text)
        sketches = [f for f in doc.features if f.type == "sketch"]
        assert not any(REGISTRY["sketch"].reads_body(f) for f in sketches)
        results = rebuild(doc)
        assert not any(
            i.code in ("stale_links", "lost_links") for r in results.values() for i in r.issues
        )
        assert fdef.dumps(doc) == text
