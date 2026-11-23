"""The separate body warning goes once a later feature joins the body (D1047).

Found on a bike frame (2026-11-12): the head tube is made before the top tube that
joins it to the seat tube, so for one feature the part has two bodies. The warning
"Head Tube created a separate body" stayed on the head tube for good.
"""

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect


def _block(doc: Document, x0: float, x1: float) -> str:
    s = Sketch()
    rect(s, x0, 10, x1, 40)
    return add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)


def _codes(report: object, fid: str) -> list[str]:
    return [i.code for i in report.results[fid].issues]  # type: ignore[attr-defined]


def test_the_warning_goes_when_a_later_feature_joins_the_bodies() -> None:
    doc, _ext = plate()  # x from 0 to 50
    engine = RebuildEngine()
    apart = _block(doc, 70, 90)
    report = engine.rebuild(doc)
    assert report.body_count == 2 and _codes(report, apart) == ["separate_body"]
    assert report.results[apart].state is FeatureState.WARNING
    bridge = _block(doc, 40, 80)
    report = engine.rebuild(doc)
    assert report.body_count == 1
    assert _codes(report, apart) == [] and report.results[apart].state is FeatureState.OK
    # The bridge off again: two bodies, and the warning is back.
    doc.feature(bridge).suppressed = True
    report = engine.rebuild(doc)
    assert report.body_count == 2 and _codes(report, apart) == ["separate_body"]


def test_the_warning_stays_while_the_body_is_separate() -> None:
    doc, _ext = plate()
    apart = _block(doc, 70, 90)
    _block(doc, 10, 20)  # a later feature that joins nothing
    report = RebuildEngine().rebuild(doc)
    assert report.body_count == 2 and _codes(report, apart) == ["separate_body"]
