"""Insert a DXF file into a sketch (TR5, D695)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.dxf_import import DxfError, Placement, build, extent, parse
from fdcad.core.sketch.model import Arc, Circle, Ellipse, EllipseArc, Line, Sketch, Spline
from fdcad.core.sketch.solver import SketchStatus, solve


def _dxf(*entities: str, units: int | None = 4) -> str:
    header = f"0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n{units}\n0\nENDSEC\n" if units else ""
    body = "".join(entities)
    return f"{header}0\nSECTION\n2\nENTITIES\n{body}0\nENDSEC\n0\nEOF\n"


LINE = "0\nLINE\n8\nOutline\n10\n0\n20\n0\n11\n20\n21\n0\n"
CIRCLE = "0\nCIRCLE\n8\nHoles\n10\n10\n20\n5\n40\n2\n"
ARC = "0\nARC\n8\nOutline\n10\n0\n20\n0\n40\n5\n50\n0\n51\n90\n"
TEXT = "0\nTEXT\n8\nNotes\n10\n0\n20\n0\n1\nHello\n"
# A 20 by 10 rectangle whose top right corner is rounded by a quarter arc.
RECT = (
    "0\nLWPOLYLINE\n8\nOutline\n90\n4\n70\n1\n"
    "10\n0\n20\n0\n10\n20\n20\n0\n10\n20\n20\n10\n42\n0\n10\n0\n20\n10\n"
)
ELLIPSE = "0\nELLIPSE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n0\n40\n0.5\n41\n0\n42\n6.283185307179586\n"
SPLINE = "0\nSPLINE\n8\n0\n11\n0\n21\n0\n11\n5\n21\n3\n11\n10\n21\n0\n"


def _kinds(sk: Sketch) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in sk.entities.values():
        out[type(e).__name__] = out.get(type(e).__name__, 0) + 1
    return out


def test_reads_the_supported_entities_and_skips_the_rest() -> None:
    drawing = parse(_dxf(LINE, CIRCLE, ARC, TEXT, ELLIPSE, SPLINE))
    assert drawing.units == 4
    assert [e.kind for e in drawing.entities] == ["LINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE"]
    assert drawing.skipped["TEXT"] == 1
    assert drawing.layers == ["Outline", "Holes", "0"]
    sk = Sketch()
    built = build(drawing, sk, Placement())
    assert len(built.entities) == 5
    kinds = _kinds(sk)
    assert kinds["Line"] == 1 and kinds["Circle"] == 1 and kinds["Arc"] == 1
    assert kinds["Ellipse"] == 1 and kinds["Spline"] == 1


def test_true_size_scale_turn_and_offset() -> None:
    sk = Sketch()
    build(parse(_dxf(LINE, CIRCLE)), sk, Placement(scale=25.4, angle=math.pi / 2, offset=(1, 2)))
    line = next(e for e in sk.entities.values() if isinstance(e, Line))
    assert sk.xy(line.p1) == pytest.approx((1, 2))
    assert sk.xy(line.p2) == pytest.approx((1, 2 + 20 * 25.4))
    circle = next(e for e in sk.entities.values() if isinstance(e, Circle))
    assert circle.radius == pytest.approx(2 * 25.4)


def test_arc_runs_counter_clockwise_between_its_angles() -> None:
    sk = Sketch()
    build(parse(_dxf(ARC)), sk, Placement())
    arc = next(e for e in sk.entities.values() if isinstance(e, Arc))
    assert sk.xy(arc.start) == pytest.approx((5, 0)) and sk.xy(arc.end) == pytest.approx((0, 5))


def test_polyline_with_bulge_is_joined_and_under_defined() -> None:
    sk = Sketch()
    built = build(parse(_dxf(RECT)), sk, Placement())
    kinds = _kinds(sk)
    assert kinds["Line"] == 4 and len(built.entities) == 4
    assert sum(r.type == "coincident" for r in sk.relations) == 4
    result = solve(sk)
    assert result.solved and result.status is SketchStatus.UNDER


def test_bulge_makes_an_arc() -> None:
    quarter = math.tan(math.pi / 8)  # a 90 degree arc
    poly = f"0\nLWPOLYLINE\n8\n0\n90\n2\n70\n0\n10\n10\n20\n0\n42\n{quarter}\n10\n0\n20\n10\n"
    sk = Sketch()
    build(parse(_dxf(poly)), sk, Placement())
    arc = next(e for e in sk.entities.values() if isinstance(e, Arc))
    assert sk.xy(arc.center) == pytest.approx((0, 0), abs=1e-9)
    assert sk.radius(arc.id) == pytest.approx(10)


def test_layers_can_be_left_out() -> None:
    sk = Sketch()
    built = build(parse(_dxf(LINE, CIRCLE)), sk, Placement(layers={"Holes"}))
    assert len(built.entities) == 1 and _kinds(sk)["Circle"] == 1


def test_partial_ellipse() -> None:
    part = ELLIPSE.replace("6.283185307179586", "3.141592653589793")
    sk = Sketch()
    build(parse(_dxf(part)), sk, Placement())
    assert any(isinstance(e, EllipseArc) for e in sk.entities.values())
    assert not any(isinstance(e, Ellipse) for e in sk.entities.values())


def test_spline_passes_through_the_fit_points() -> None:
    sk = Sketch()
    build(parse(_dxf(SPLINE)), sk, Placement())
    spline = next(e for e in sk.entities.values() if isinstance(e, Spline))
    assert [sk.xy(p) for p in spline.points] == [(0, 0), (5, 3), (10, 0)]


def test_nothing_usable_or_not_dxf_says_so() -> None:
    with pytest.raises(DxfError):
        build(parse(_dxf(TEXT)), Sketch(), Placement())
    with pytest.raises(DxfError):
        parse("this is\nnot a dxf\nfile at all\n")
    assert extent(parse(_dxf(TEXT))) is None
    assert extent(parse(_dxf(LINE, CIRCLE))) == ((0, 0), (20, 5))


@pytest.mark.parametrize("bad", ["abc", "nan", "inf", "1e999"])
def test_a_value_that_is_not_a_number_is_a_dxf_error(bad: str) -> None:
    """Audit D12 item 6 (D709): bad values raised other errors or reached the sketch."""
    line = LINE.replace("11\n20\n", f"11\n{bad}\n")
    with pytest.raises(DxfError, match="not a"):
        build(parse(_dxf(line)), Sketch(), Placement())


def test_many_lines_join_quickly() -> None:
    """Audit D item 3, D12 item 5 (D709): joining was quadratic, 13 s for 6000 lines."""
    import time

    lines = "".join(f"0\nLINE\n8\n0\n10\n{i}\n20\n0\n11\n{i + 1}\n21\n0\n" for i in range(6000))
    drawing = parse(_dxf(lines))
    sk = Sketch()
    start = time.perf_counter()
    build(drawing, sk, Placement())
    assert time.perf_counter() - start < 3.0
    assert sum(1 for r in sk.relations if r.type == "coincident") == 5999


def test_too_many_entities_say_what_to_do(monkeypatch: pytest.MonkeyPatch) -> None:
    import fdcad.core.sketch.dxf_import as dxf

    monkeypatch.setattr(dxf, "MAX_ENTITIES", 1)
    with pytest.raises(DxfError, match="one layer at a time"):
        build(parse(_dxf(LINE, CIRCLE)), Sketch(), Placement())


def test_two_vertex_closed_polyline_is_a_full_circle() -> None:
    """Audit D item 1 (D722): the usual DXF circle came in as half an arc."""
    poly = "0\nLWPOLYLINE\n8\n0\n90\n2\n70\n1\n10\n0\n20\n0\n42\n1\n10\n10\n20\n0\n42\n1\n"
    sk = Sketch()
    build(parse(_dxf(poly)), sk, Placement())
    arcs = [e for e in sk.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 2
    assert all(sk.xy(a.center) == pytest.approx((5, 0)) for a in arcs)


def test_entities_seen_from_below_are_not_mirrored() -> None:
    """Audit D item 2 (D722): circles and polylines with extrusion -Z landed mirrored."""
    circle = "0\nCIRCLE\n8\n0\n10\n10\n20\n5\n40\n2\n230\n-1\n"
    poly = "0\nLWPOLYLINE\n8\n0\n90\n2\n70\n0\n10\n10\n20\n0\n10\n20\n20\n0\n230\n-1\n"
    sk = Sketch()
    build(parse(_dxf(circle, poly)), sk, Placement())
    c = next(e for e in sk.entities.values() if isinstance(e, Circle))
    assert sk.xy(c.center) == pytest.approx((-10, 5))
    line = next(e for e in sk.entities.values() if isinstance(e, Line))
    assert sorted([sk.xy(line.p1)[0], sk.xy(line.p2)[0]]) == pytest.approx([-20, -10])


def _blocks(*blocks: str) -> str:
    return "0\nSECTION\n2\nBLOCKS\n" + "".join(blocks) + "0\nENDSEC\n"


def test_blocks_are_inserted_moved_turned_and_scaled() -> None:
    """Audit D item 4 (D722): a drawing made of blocks gave "nothing to insert"."""
    block = "0\nBLOCK\n8\n0\n2\nBOLT\n10\n0\n20\n0\n" + CIRCLE + "0\nENDBLK\n"
    insert = "0\nINSERT\n8\n0\n2\nBOLT\n10\n100\n20\n0\n41\n2\n50\n90\n"
    text = _dxf(insert).replace(
        "0\nSECTION\n2\nENTITIES", _blocks(block) + "0\nSECTION\n2\nENTITIES"
    )
    sk = Sketch()
    build(parse(text), sk, Placement())
    c = next(e for e in sk.entities.values() if isinstance(e, Circle))
    # The block's circle at (10, 5) r 2, scaled 2 and turned 90 degrees about the base.
    assert sk.xy(c.center) == pytest.approx((100 - 10, 20))
    assert c.radius == pytest.approx(4)


def test_paper_space_invisible_and_hidden_layers_are_left_out() -> None:
    """Audit D item 5 (D722): they were imported with model space."""
    tables = (
        "0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n"
        "0\nLAYER\n2\nFrozen\n70\n1\n62\n7\n0\nLAYER\n2\nOff\n70\n0\n62\n-7\n0\nENDTAB\n0\nENDSEC\n"
    )
    paper = LINE.replace("8\nOutline\n", "8\nOutline\n67\n1\n")
    hidden = LINE.replace("8\nOutline\n", "8\nOutline\n60\n1\n")
    frozen = CIRCLE.replace("8\nHoles\n", "8\nFrozen\n")
    off = CIRCLE.replace("8\nHoles\n", "8\nOff\n")
    text = tables + _dxf(paper, hidden, frozen, off, ARC)
    sk = Sketch()
    built = build(parse(text), sk, Placement())
    assert len(built.entities) == 1  # only the arc
    assert built.skipped["paper space"] == 1 and built.skipped["invisible"] == 1
    assert built.skipped["hidden layer"] == 2


def test_form_feeds_3d_polylines_and_z_are_handled() -> None:
    """Audit D item 11 (D733): a form feed in a skipped text failed the whole file,
    3D polylines came in as stray lines, and Z values were flattened silently."""
    ff = chr(12)
    text_entity = f"0\nTEXT\n8\n0\n10\n0\n20\n0\n1\nPage{ff}two\n"
    poly3d = (
        "0\nPOLYLINE\n8\n0\n70\n8\n"
        "0\nVERTEX\n8\n0\n10\n0\n20\n0\n0\nVERTEX\n8\n0\n10\n5\n20\n5\n0\nSEQEND\n"
    )
    raised = LINE.replace("21\n0\n", "21\n0\n31\n7\n")
    sk = Sketch()
    built = build(parse(_dxf(text_entity, poly3d, raised)), sk, Placement())
    assert built.skipped["3D polyline or mesh"] == 1
    assert built.skipped["Z flattened"] == 1
    assert len(built.entities) == 1


def test_more_unit_codes_and_the_measurement_hint() -> None:
    """Audit D item 18 (D742): microns, nanometres and others were read as no unit; the
    metric or imperial header was not used."""
    from fdcad.core.sketch.dxf_import import UNIT_MM, UNIT_NAMES

    assert parse(_dxf(LINE, units=13)).units == 13
    assert UNIT_MM[13] == 1e-3 and UNIT_NAMES[12] == "nm"
    header = "0\nSECTION\n2\nHEADER\n9\n$MEASUREMENT\n70\n0\n0\nENDSEC\n"
    assert parse(header + _dxf(LINE, units=None)).measurement == 0
    assert parse(_dxf(LINE)).measurement is None
