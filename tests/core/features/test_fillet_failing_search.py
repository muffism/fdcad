"""A failing fillet or chamfer answers quickly and names the right edges (D1043).

Found on a bike frame of joined tubes (2026-11-12): a fillet that failed on a joint
took minutes to say so, because the search for the largest radius went down to a few
hundredths of a millimetre, where the kernel can run without end; every edge of one
smooth chain was tried again though the chain fails as one; and two picked edges
between the same two faces were both called "edge 1", so the Fillet the rest button
took both out.
"""

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features import chamfer, fillet
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fixes import fixed_feature
from fdcad.core.features.modify import edges_of
from fdcad.core.features.solids import line_ends
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, messages, plate
from tests.core.features.test_fillet import add_fillet


def _plate_with_a_bar() -> tuple[Document, NamedShape, list[dict[str, Any]]]:
    """The 50 by 50 by 10 plate with a round bar lying in its top face: 8 mm across,
    along X from x = 10 to x = 40, its axis at y = 45 on the top face. The bar meets the
    top face in two straight edges, at y = 41 and y = 49, which have the same name. The
    second is 1 mm from the plate's side, so a 2 mm round does not fit on it.

    Returns the references of the two edges, the one at y = 41 first."""
    doc, _ext = plate()
    pid = doc.new_feature_id()
    doc.features.append(
        Feature(
            pid,
            "ref_plane",
            "Plane 1",
            params={"method": "offset", "distance": Param("10", 10.0)},
            refs={"first": {"feature": "f4"}},
        )
    )
    plane = rebuild(doc)[pid].plane
    assert plane is not None and plane.origin[0] == pytest.approx(10.0)
    centre = (0.0 - plane.origin[0], 45.0 - plane.origin[1], 10.0 - plane.origin[2])
    x, n = plane.x_dir, plane.normal
    y = (n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0])
    u = sum(a * b for a, b in zip(centre, x, strict=True))
    v = sum(a * b for a, b in zip(centre, y, strict=True))
    s = Sketch()
    s.add_circle(u, v, 4.0)
    bar = add_extrude(doc, add_sketch(doc, s, {"feature": pid}), 30.0)
    b = body(rebuild(doc), bar)
    lines = []
    for edge in edges_of(b.shape):
        ends = line_ends(edge)
        if ends is None:
            continue
        (x0, y0, z0), (x1, _y1, z1) = ends
        if abs(z0 - 10) < 1e-6 and abs(z1 - 10) < 1e-6 and abs(abs(x1 - x0) - 30) < 1e-6:
            lines.append((y0, edge))
    assert [round(y0, 6) for y0, _e in sorted(lines, key=lambda t: t[0])] == [41.0, 49.0]
    refs = [reference_for(b, e) for _y, e in sorted(lines, key=lambda t: t[0])]
    assert all(r is not None for r in refs)
    return doc, b, refs  # type: ignore[return-value]


def test_two_picked_edges_with_one_name_are_told_apart() -> None:
    doc, _b, refs = _plate_with_a_bar()
    assert refs[0]["name"] == refs[1]["name"]  # named by the same two faces
    fid = add_fillet(doc, 2.0, edges=refs)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    # It read "edge 1": the name was looked up in the picked list, and both have it.
    assert "failed on 1 of 2 edges: edge 2" in text
    skip = res.issues[0].fixes[0]
    assert skip.label == "Fillet the rest (skip 1 edge)"
    assert skip.data["positions"] == [2]
    # The button took out both picks, since both have the failing edge's name.
    kept = fixed_feature(doc, fid, skip)
    assert kept is not None and len(kept.refs["edges"]) == 1
    assert kept.refs["edges"][0]["snapshot"]["midpoint"][1] == pytest.approx(41.0)
    doc.features[-1] = kept
    assert rebuild(doc)[fid].state is FeatureState.OK


def test_positions_of_edges_that_share_a_name() -> None:
    a, b, c = "edge(p|q)", "edge(p|r)", "edge(q|r)"
    order = [a, b, a, c]
    assert fillet.positions(order, [a, b, a, c]) == [1, 2, 3, 4]
    # The pieces of one split pick share its place; the next pick of that name is later.
    assert fillet.positions(order, [f"{a}#1", f"{a}#2", b, a, c]) == [1, 1, 2, 3, 4]
    assert fillet.positions([a], [b]) == [0]


def test_the_search_for_the_largest_radius_stops_at_a_sixteenth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing works: the search tried 1/2, 1/4 ... 1/256 of the radius. On a curved
    joint the kernel did not come back from 0.047 mm."""
    tried: list[float] = []

    def never(_fid: str, _body: Any, items: list[Any], law_of: Any) -> None:
        tried.append(law_of(items[0])[0][1])
        return None

    monkeypatch.setattr(fillet, "round_edges", never)
    item = fillet.Item("e", None, 1)  # type: ignore[arg-type]
    assert fillet.largest_radius("f9", None, item, 8.0) is None  # type: ignore[arg-type]
    assert tried == [4.0, 2.0, 1.0, 0.5]


def test_a_found_radius_is_still_refined(monkeypatch: pytest.MonkeyPatch) -> None:
    def up_to_three(_fid: str, _body: Any, items: list[Any], law_of: Any) -> object | None:
        return object() if law_of(items[0])[0][1] <= 3.0 else None

    monkeypatch.setattr(fillet, "round_edges", up_to_three)
    item = fillet.Item("e", None, 1)  # type: ignore[arg-type]
    found = fillet.largest_radius("f9", None, item, 8.0)  # type: ignore[arg-type]
    assert found is not None and 2.9 < found <= 3.0


def test_the_chamfer_search_stops_at_a_sixteenth(monkeypatch: pytest.MonkeyPatch) -> None:
    tried: list[float] = []

    class Size:
        def scaled(self, share: float) -> float:
            tried.append(share)
            return share

    monkeypatch.setattr(chamfer, "bevel", lambda *_a, **_k: None)
    assert chamfer._largest("f9", None, ("e", None), Size()) is None  # type: ignore[arg-type]
    assert tried == [0.5, 0.25, 0.125, 0.0625]


def test_a_smooth_chain_is_tried_once_not_once_per_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    """The plate's four upright edges are rounded, so its top outline is one smooth
    chain of eight edges. A 12 mm round on it fails (the plate is 10 mm thick). Each of
    the eight edges was tried and searched on its own: more than 70 kernel rounds."""
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    upright = []
    for edge in edges_of(b.shape):
        ends = line_ends(edge)
        if ends is not None and abs(ends[0][2] - ends[1][2]) > 1:
            upright.append(reference_for(b, edge))
    first = add_fillet(doc, 5.0, edges=upright)
    b = body(rebuild(doc), first)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    refs = [reference_for(b, e) for e in edges_of(top)]
    assert len(refs) == 8
    fid = add_fillet(doc, 12.0, edges=refs)
    calls = 0
    real = fillet.round_edges

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(fillet, "round_edges", counted)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    assert "failed on 8 of 8 edges" in text and "largest radius" in text
    assert calls <= 30, calls


def test_extra_fix_buttons_are_left_out_when_the_search_was_slow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On a part of several hundred faces the split and limit buttons took half a
    minute to work out. They are offered while the failing edges were named quickly."""
    from fdcad.core.features import fillet_help, fillet_limit_areas

    asked: list[str] = []
    monkeypatch.setattr(fillet_help, "ways", lambda *_a, **_k: asked.append("ways") or [])
    monkeypatch.setattr(
        fillet_limit_areas, "limit_fix", lambda *_a, **_k: asked.append("limit") and None
    )
    doc, _b, refs = _plate_with_a_bar()
    fid = add_fillet(doc, 2.0, edges=refs)
    assert rebuild(doc)[fid].state is FeatureState.ERROR
    assert asked == ["ways", "limit"]  # a small part: both are looked for
    asked.clear()
    monkeypatch.setattr(fillet, "EXTRAS_SECONDS", 0.0)  # as if the search had been slow
    doc.feature(fid).params["radius"] = Param("2.5", 2.5)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and asked == []
    assert res.issues[0].fixes[0].label.startswith("Fillet the rest")  # still offered
