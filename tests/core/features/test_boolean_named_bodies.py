"""The named boolean works on the bodies it reaches, one at a time (D1055, D1056).

Found on a gearbox of 318 features (2026-11-12): a table pattern of studs on one plate
joined two blocks elsewhere in the part that were locked together with Interlock
teeth. Patterns and 30 other callers hand ``boolean_named`` the whole part, and it
handed the whole part to the kernel.
"""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.booleans import boolean_named
from fdcad.core.features.solids import precise_volume, solids
from fdcad.core.naming.names import NamedShape, centroid, faces_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect


def _plate_and_locked_blocks() -> NamedShape:
    """The 50 by 50 by 10 plate, and far from it two blocks locked with teeth."""
    doc, _ext = plate()
    s = Sketch()
    rect(s, 100, 0, 120, 20)
    lower = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0, merge=False)
    body = RebuildEngine().rebuild(doc).body
    top = next(
        f for n, f in body.faces if n.startswith(f"{lower}/") and abs(centroid(f)[2] - 5) < 1e-9
    )
    top_ref = reference_for(body, top)
    assert top_ref is not None
    s = Sketch()
    rect(s, 100, 0, 120, 20)
    add_extrude(doc, add_sketch(doc, s, top_ref), 5.0, merge=False)
    teeth = doc.new_feature_id()
    doc.features.append(
        Feature(teeth, "interlock", "Interlock 1",
                params={"tooth_size": Param("4", 4.0), "tooth_depth": Param("1", 1.0)},
                refs={"face": [top_ref]})
    )  # fmt: skip
    report = RebuildEngine().rebuild(doc)
    assert report.results[teeth].state is FeatureState.OK
    assert report.body is not None and len(solids(report.body.shape)) == 3
    return report.body


def _named(shape, prefix: str) -> NamedShape:  # type: ignore[no-untyped-def]
    return NamedShape(shape, [(f"{prefix}/{k}", f) for k, f in enumerate(faces_of(shape), 1)])


def _stud(x: float, y: float, z: float, height: float = 6.0):  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), 2.0, height).Shape()


def test_a_fuse_on_one_body_leaves_bodies_that_touch_each_other_apart() -> None:
    body = _plate_and_locked_blocks()
    before = sorted(precise_volume(s) for s in solids(body.shape))
    done = boolean_named("fuse", body, _named(_stud(25, 25, 9), "f99/stud"), "f99", "Studs")
    after = sorted(precise_volume(s) for s in solids(done.shape))
    assert len(after) == 3  # it was 2: the blocks came back as one body
    assert after[:2] == pytest.approx(before[:2])  # the two blocks, as they were
    assert before[2] == pytest.approx(25000.0)
    assert after[2] == pytest.approx(25000.0 + 3.141592653589793 * 4 * 5, rel=1e-6)
    assert any(n.startswith("f99/stud/") for n, _f in done.faces)


def test_a_fuse_that_touches_nothing_adds_a_body_beside_the_others() -> None:
    body = _plate_and_locked_blocks()
    done = boolean_named("fuse", body, _named(_stud(200, 200, 0), "f99/stud"), "f99", "Studs")
    assert len(solids(done.shape)) == 4
    names = {n for n, _f in done.faces}
    assert {n for n, _f in body.faces} <= names


def test_a_cut_through_two_touching_bodies_cuts_each_alone() -> None:
    lower = BRepPrimAPI_MakeBox(20, 20, 5).Shape()
    upper = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 5), 20, 20, 5).Shape()
    far = BRepPrimAPI_MakeBox(gp_Pnt(100, 0, 0), 5, 5, 5).Shape()
    from fdcad.core.features.solids import compound

    shape = compound([lower, upper, far])
    body = _named(shape, "f1/face")
    drill = _named(_stud(10, 10, -1, 12.0), "f99/hole")
    done = boolean_named("cut", body, drill, "f99", "Drill")
    after = solids(done.shape)
    assert len(after) == 3  # no plug left behind as a body
    hole = 3.141592653589793 * 4 * 5
    assert [precise_volume(s) for s in after] == pytest.approx(
        [2000 - hole, 2000 - hole, 125.0], rel=1e-6
    )
    assert after[2].IsSame(far)  # the body out of reach is the very same body


def test_a_new_block_somewhere_else_leaves_locked_blocks_apart() -> None:
    """D1078: found by building the gearbox with two locked blocks in the part from the
    start. Its first feature, a plain Extrude of a block that touches nothing, joined
    the two blocks: the fuse that only had to add a body was run on the whole part."""
    from fdcad.core.features.solids import combine

    body = _plate_and_locked_blocks()
    before = sorted(precise_volume(s) for s in solids(body.shape))
    block = BRepPrimAPI_MakeBox(gp_Pnt(300, 300, 0), 10, 10, 10).Shape()
    done = combine("f99", "Block", body, _named(block, "f99/side"), "boss")
    after = sorted(precise_volume(s) for s in solids(done.shape))
    assert len(after) == 4  # it was 3: the two locked blocks came back as one
    assert after == pytest.approx(sorted([*before, 1000.0]))
    names = {n for n, _f in done.faces}
    assert {n for n, _f in body.faces} <= names and "f99/side/1" in names
