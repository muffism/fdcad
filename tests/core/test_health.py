"""Model health report (TR286, D775)."""

from __future__ import annotations

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.health import MOVE_TO_END, report
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def _kinds(doc):  # type: ignore[no-untyped-def]
    built = RebuildEngine().rebuild(doc)
    return {i.kind: i for i in report(doc, built.results)}


def _plate():  # type: ignore[no-untyped-def]
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 40, 30)  # no relation to the origin
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    return doc, ext


def test_an_untied_sketch_and_default_names() -> None:
    doc, _ext = _plate()
    kinds = _kinds(doc)
    assert "untied" in kinds and kinds["untied"].fid == doc.features[-2].id
    # The test helpers name features "Extrude f6": default names.
    assert "default_names" in kinds


def test_a_cut_that_removes_nothing() -> None:
    doc, _ext = _plate()
    far = Sketch()
    rect(far, 100, 100, 110, 110)
    add_extrude(doc, add_sketch(doc, far, {"feature": "f2"}), 5.0, operation="cut")
    item = _kinds(doc)["no_effect"]
    assert "removes nothing" in item.message and item.fid == doc.features[-1].id


def test_an_early_fillet_and_a_feature_on_its_faces() -> None:
    doc, ext = _plate()
    fillet = doc.new_feature_id()
    doc.features.append(
        Feature(
            fillet,
            "fillet",
            "Fillet 1",
            params={"fillet_type": "constant", "radius": Param("2", 2.0)},
            refs={"faces": [{"kind": "face", "name": f"{ext}/cap/end"}]},
        )
    )
    s = Sketch()
    rect(s, 5, 5, 15, 15)
    add_extrude(doc, add_sketch(doc, s, {"kind": "face", "name": f"{fillet}/fillet/x"}), 3.0)
    kinds = _kinds(doc)
    assert kinds["early_round"].fid == fillet and kinds["early_round"].fix == MOVE_TO_END
    assert "on_rounding" in kinds and "Fillet 1" in kinds["on_rounding"].message


def test_repeated_one_circle_sketches() -> None:
    doc, _ext = _plate()
    for x in (5.0, 15.0, 25.0):
        s = Sketch()
        s.add_circle(x, 10.0, 2.0)
        add_sketch(doc, s, {"feature": "f2"})
    assert "repeated_sketch" in _kinds(doc)


def test_a_tidy_part_has_no_sketch_advice() -> None:
    from fdcad.core.io import fdef
    from fdcad.samples.make import SAMPLE_DIR

    doc = fdef.load(SAMPLE_DIR / f"plate_with_holes{fdef.PART_SUFFIX}")
    kinds = _kinds(doc)
    assert "untied" not in kinds and "no_effect" not in kinds


def test_typed_values_that_should_be_linked() -> None:
    """TR351, D905."""
    from fdcad.core.document.model import Param, Variable, new_document
    from fdcad.core.health import LINK_VARIABLE, linked, unlinked_values
    from fdcad.core.sketch.model import Sketch
    from fdcad.core.units import Kind
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    doc = new_document()
    doc.variables.append(Variable("thick", Kind.LENGTH, "10", 10.0))
    s = Sketch()
    rect(s, 0, 0, 40, 40)
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    found = [i for i in unlinked_values(doc, doc.features) if i.fid == fid]
    assert len(found) == 1 and found[0].fix == LINK_VARIABLE
    fixed = linked(doc, found[0])
    assert fixed is not None and fixed.params["depth"].expr == "thick"
    doc.feature(fid).params["depth"] = Param("thick", 10.0)
    assert not [i for i in unlinked_values(doc, doc.features) if i.fid == fid]
