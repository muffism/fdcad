"""A sheet metal part of eleven bodies, built feature by feature (D1071 to D1076).

The third large test part, after the bike frame and the gearbox: every sheet metal
feature type, on seven sheets of one part, with Draft, Mounting Boss, Landing Pad,
Graph Body and Insert Part on solid bodies. It builds in about fifteen seconds. Each
feature is followed by a check that material is where it should be and nowhere else:
most of the faults it found built with no error, in the wrong place.
"""

from __future__ import annotations

import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt

from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.model import SheetResult, inside
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.sheet_builder import Sheet
from tests.core.features.test_gearbox_part import _names, _spoiled

SHEET_METAL = {
    "base_flange", "break_corner", "closed_corner", "convert_sheet", "cross_break",
    "edge_flange", "edit_bends", "extend_wall", "flat_marks", "flatten", "fold", "form_tool",
    "gusset", "hem", "insert_bends", "jog", "miter_flange", "perforation", "rip",
    "sheet_corner_relief", "sheet_metal", "sheet_tab", "sketched_bend", "stamp", "tab_slot",
    "unfold",
}  # fmt: skip
SOLID = {"draft", "mounting_boss", "landing_pad", "graph_body", "insert_part"}
#: Length along the grain and width across of each flat pattern, mm.
FLAT_SIZES = {
    "Tray Flat Pattern": (286.71858256, 198.04778684),
    "Channel Flat Pattern": (60.0, 150.78584013),
    "Strip Flat Pattern": (120.0, 40.0),
    "Lid Flat Pattern": (104.52389342, 62.26194671),
    "Box Flat Pattern": (116.52389342, 96.52389342),
    "Angle Flat Pattern": (40.0, 76.52389342),
    "Hat Flat Pattern": (88.0, 151.43008761),
}


#: Seven sheets and four solid bodies, and the four canary bodies (D1078).
BODIES = 11 + 4


def _built(stages: list[str], canaries: bool = False) -> Sheet:
    part = Sheet()
    part.b.quiet = True
    part.watch_valid = False
    if canaries:  # four bodies no feature works on
        part.canaries_at_start = part.add_canaries()  # type: ignore[attr-defined]
    part.build(stages)
    return part


def _not_ok(part: Sheet) -> dict[str, list[str]]:
    report = part.b.rebuild()
    return {
        part.b.doc.feature(fid).name: [i.message for i in result.issues]
        for fid, result in report.results.items()
        if result.state is not FeatureState.OK
    }


@pytest.fixture(scope="module")
def part() -> Sheet:
    return _built([], canaries=True)


def test_every_feature_builds_and_every_sheet_metal_type_is_there(part: Sheet) -> None:
    assert _not_ok(part) == {}
    types = {f.type for f in part.b.doc.features}
    assert types >= SHEET_METAL and types >= SOLID
    assert len(part.b.doc.features) > 100
    assert part.b.rebuild().body_count == BODIES and part.b.valid()


def test_every_feature_put_its_material_where_it_belongs(part: Sheet) -> None:
    """D1071, D1072: Break Corner and Closed Corner on the back wall changed the front
    wall; a row of slots drawn on the far brim found no wall."""
    assert part.wrong == []
    assert part.checks > 100


def test_no_two_bodies_share_material(part: Sheet) -> None:
    """D1083, D1085: on the gearbox a lip and a hinge put one body inside another."""
    assert part.overlaps() == []


def test_no_feature_disturbs_the_bodies_it_does_not_work_on(part: Sheet) -> None:
    """D1073, D1078: the part is built with four canary bodies in it from the start."""
    assert part.canaries() == part.canaries_at_start  # type: ignore[attr-defined]


def test_the_session_a_new_engine_and_the_file_agree(part: Sheet) -> None:
    session = part.b.rebuild()
    fresh = RebuildEngine().rebuild(part.b.doc)
    doc = fdef.loads(fdef.dumps(part.b.doc))
    opened = RebuildEngine().rebuild(doc)
    names = _names(part.b.doc, session)
    assert names == _names(part.b.doc, fresh)
    assert names == _names(doc, opened)
    assert opened.body_count == BODIES
    assert _spoiled(part, session) == []  # type: ignore[arg-type]


def test_the_cut_made_across_an_unfolded_bend_is_folded_back(part: Sheet) -> None:
    """D1076: with two gussets on the tray Fold said "a feature after Unfold adds
    material". It cuts the part after the slot by the part before it; the two share
    nearly every face, and the kernel's safe mode gave back the whole part."""
    doc = part.b.doc
    fold = next(f for f in doc.features if f.type == "fold")
    result = part.b.rebuild().results[fold.id]
    assert result.state is FeatureState.OK, [i.message for i in result.issues]
    assert sum(1 for f in doc.features if f.type == "gusset") == 2
    # The slot is in the floor and, wrapped round the bend, in the front wall.
    assert not part.b.inside((145, 5, 1)) and not part.b.inside((145, 1, 6))
    assert part.b.inside((130, 5, 1)) and part.b.inside((130, 1, 5))


def test_every_flat_pattern_switched_on_keeps_the_other_bodies(part: Sheet) -> None:
    """D1075: with one Flat Pattern on, the other ten bodies were gone."""
    flats = [f for f in part.b.doc.features if f.type == "flatten"]
    assert {f.name for f in flats} == set(FLAT_SIZES)
    try:
        for flat in flats:
            flat.params["flattened"] = True
            report = part.b.rebuild()
            result = report.results[flat.id]
            assert isinstance(result, FlatResult) and result.flat is not None
            assert result.state is FeatureState.OK, (flat.name, [i.message for i in result.issues])
            assert report.body_count == BODIES, flat.name
            assert result.size == pytest.approx(FLAT_SIZES[flat.name], rel=1e-6)
            # Every mark of the sheet lies on its flat pattern (D1072: marks drawn on the
            # far brim were stored on the near one).
            for a, b, _title in result.marks or []:
                middle = gp_Pnt((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
                gap = BRepExtrema_DistShapeShape(
                    BRepBuilderAPI_MakeVertex(middle).Vertex(), result.flat.shape
                )
                assert gap.IsDone() and gap.Value() < 1e-6, (flat.name, _title)
            flat.params["flattened"] = False
    finally:
        for flat in flats:
            flat.params["flattened"] = False
        part.b.rebuild()
    assert part.b.rebuild().body_count == BODIES


def test_features_drawn_on_the_far_one_of_two_walls_in_one_plane() -> None:
    """D1072: the two brims of a hat section lie in one plane. Perforation and Flat
    Marks took the first wall in the sketch's plane: slots drawn on the far brim found
    "no slot on the wall", and marks drawn there were stored on the near brim."""
    hat = _built(["hat"])
    assert _not_ok(hat) == {}
    assert getattr(hat, "wrong", []) == []
    doc = hat.b.doc
    marks = next(f for f in doc.features if f.type == "flat_marks")
    result = hat.b.rebuild().results[marks.id]
    assert isinstance(result, SheetResult) and result.sheet is not None
    model = result.sheet
    mine = [m for m in model.marks if m[3] == "Far"]
    assert len(mine) == 1
    wid, p, q, _title = mine[0]
    middle = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, model.thickness / 2)
    assert inside(model.piece(wid).shape, middle)
