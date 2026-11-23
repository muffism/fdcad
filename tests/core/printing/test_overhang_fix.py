"""Fix overhangs from the analysis (TR410, D909)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.select import reference_for
from fdcad.core.printing.overhang_fix import overhang_chamfer, underside_faces
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect


def test_a_ledge_underside_is_found_and_chamfered() -> None:
    doc = new_document()
    base = Sketch()
    rect(base, 0, 0, 10, 10)
    add_extrude(doc, add_sketch(doc, base, {"feature": "f2"}), 20.0)
    ledge = Sketch()
    rect(ledge, 0, 0, 20, 10)
    led = add_extrude(
        doc,
        add_sketch(doc, ledge, {"feature": "f2"}),
        10.0,
        start_condition="offset",
        start_offset=Param("10", 10.0),
    )
    part = body(rebuild(doc), led)
    found = underside_faces(part, (0.0, 0.0, 1.0))
    assert len(found) == 1  # the ledge's underside at 10 mm; the bed face is left out
    refs = [reference_for(part, f) for f in found]
    feature = overhang_chamfer(doc, [r for r in refs if r is not None], 1.0)
    doc.features.append(feature)
    res = rebuild(doc)
    assert res[feature.id].state is not FeatureState.ERROR, res[feature.id].issues
    assert volume_of(res[feature.id].body.shape) != pytest.approx(volume_of(part.shape))
