"""Sheet metal and laser checks (TR297, D791)."""

from __future__ import annotations

from fdcad.core import manufacturing as mfg
from fdcad.core.features.sheetmetal.export import ArcPiece, BendMark, FlatDrawing, Segment
from fdcad.core.manufacturing_sheet import loops, sheet_checks

T = 2.0


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[Segment]:
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [Segment(a, b) for a, b in zip(pts, pts[1:] + pts[:1], strict=True)]


def _kinds(drawing: FlatDrawing) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in sheet_checks(drawing, T, mfg.default_profile("sheet_metal")):
        out[f.kind] = out.get(f.kind, 0) + 1
    return out


def test_a_clean_plate_has_no_findings() -> None:
    d = FlatDrawing(outline=[*_rect(0, 0, 100, 60), ArcPiece((50, 30), 3.0, 0.0, 360.0)])
    assert _kinds(d) == {}


def test_layout_rules() -> None:
    d = FlatDrawing(
        outline=[
            *_rect(0, 0, 100, 60),
            ArcPiece((3.5, 30), 0.8, 0.0, 360.0),  # a 1.6 mm hole (under 2), 2.7 from the edge
            ArcPiece((50, 30), 3.0, 0.0, 360.0),
            ArcPiece((58, 30), 3.0, 0.0, 360.0),  # 2 mm from the hole beside it (under 4)
            *_rect(70, 10, 80, 50),  # a cut-out 2 mm from the bend at x = 82
        ],
        bends=[BendMark((82, 0), (82, 60), "up", 90.0), BendMark((95, 0), (95, 60), "up", 90.0)],
    )
    kinds = _kinds(d)
    assert kinds["hole_small"] == 1
    assert kinds["hole_edge"] == 1  # 2.7 mm, under 1.5 times the 2 mm thickness
    assert kinds["hole_hole"] == 1
    assert kinds["hole_bend"] >= 1
    assert kinds["short_flange"] == 1  # the bend at x = 95 leaves a 5 mm flange (under 8)


def test_preflight() -> None:
    open_outline = _rect(0, 0, 100, 60)[:3]
    assert loops(open_outline)[1] == 2
    d = FlatDrawing(
        outline=[
            *_rect(0, 0, 100, 60),
            _rect(0, 0, 100, 60)[0],  # drawn twice
            Segment((10, 10), (10.01, 10)),  # tiny and open
            *_rect(20, 20, 40, 40),  # a cut-out
            *_rect(25, 25, 35, 35),  # an island inside it
        ]
    )
    kinds = _kinds(d)
    assert kinds["duplicate"] == 1 and kinds["tiny"] == 1 and kinds["open_contour"] == 1
    assert kinds["island"] == 1
    small = FlatDrawing(outline=_rect(0, 0, 1, 0.5))
    assert _kinds(small)["units"] == 1


def test_a_part_without_a_flat_pattern_says_so() -> None:
    from tests.core.features.test_features import body, plate, rebuild

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    found = mfg.check("sheet_metal", doc, b, mfg.default_profile("sheet_metal"), {})
    assert [f.kind for f in found] == ["no_flat"]
    assert mfg.has_checks("sheet_metal")


def test_a_real_flat_pattern_is_read() -> None:
    from tests.core.features.sheetmetal.parts import build, flat_pattern, plate, sheet_doc

    doc = sheet_doc(T, 1.0)
    plate(doc)
    flat_pattern(doc, flattened=False)
    report = build(doc)
    found = mfg.check(
        "sheet_metal", doc, report.body, mfg.default_profile("sheet_metal"), dict(report.results)
    )
    assert [f.kind for f in found] == []


def test_tab_minimums() -> None:
    """Short and shallow tabs (TR297 item 1, D802)."""
    from fdcad.core.document.model import Feature, Param, new_document

    doc = new_document()
    doc.features.append(
        Feature(
            "f9",
            "tab_slot",
            "Tab and Slot 1",
            params={"tab_length": Param("3", 3.0), "depth": Param("1", 1.0)},
        )
    )
    kinds = sorted(f.kind for f in mfg.tab_checks(doc, 2.0, mfg.default_profile("sheet_metal")))
    assert kinds == ["shallow_tab", "short_tab"]
    doc.features[-1].params["tab_length"] = Param("5", 5.0)
    doc.features[-1].params["depth"] = Param("2", 2.0)
    assert mfg.tab_checks(doc, 2.0, mfg.default_profile("sheet_metal")) == []


def test_bends_tighter_than_the_material_allows() -> None:
    """With a material, bends under its smallest radius are listed (TR297, D803)."""
    from fdcad.core.materials import Material
    from tests.core.features.sheetmetal.parts import build, flat_pattern
    from tests.core.features.sheetmetal.test_corners import box_tray

    doc = box_tray()
    flat_pattern(doc, flattened=False)
    report = build(doc)

    def kinds() -> list[str]:
        found = mfg.check(
            "sheet_metal", doc, report.body, mfg.default_profile("sheet_metal"),
            dict(report.results),
        )  # fmt: skip
        return [f.kind for f in found]

    assert "tight_bend" not in kinds()  # no material: nothing to compare with
    doc.material = Material("Stainless steel", 8.0, min_bend=5.0).to_data()
    assert "tight_bend" in kinds()
    doc.material = Material("PLA", 1.24).to_data()  # no bend value known
    assert "tight_bend" not in kinds()
