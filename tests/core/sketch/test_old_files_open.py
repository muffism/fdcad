"""Older `.fdef` files keep opening unchanged after the relation and dimension additions.

CLAUDE.md section 4 item 4: the saved samples were written before WP5 and WP6.
"""

from __future__ import annotations

import pytest

from fdcad.core.io import fdef
from fdcad.core.sketch.model import Point, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import solve
from fdcad.samples.make import SAMPLE_DIR

NAMES = sorted(p.stem for p in SAMPLE_DIR.glob("*.fdprt"))


@pytest.mark.parametrize("name", NAMES)
def test_existing_sample_saves_byte_for_byte(name: str) -> None:
    text = (SAMPLE_DIR / f"{name}.fdprt").read_text(encoding="utf-8")
    assert fdef.dumps(fdef.loads(text)) == text


@pytest.mark.parametrize("name", NAMES)
def test_existing_sample_sketches_solve_in_place(name: str) -> None:
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    for feature in doc.features:
        if feature.type != "sketch":
            continue
        sketch = sketch_from_data(feature.data)
        before = {e.id: (e.x, e.y) for e in sketch.entities.values() if isinstance(e, Point)}
        assert solve(sketch).solved, feature.name
        for eid, xy in before.items():
            assert sketch.xy(eid) == pytest.approx(xy, abs=1e-6), (feature.name, eid)
        data = sketch_to_data(sketch_from_data(feature.data))
        assert [d.get("measure_to") for d in data["dimensions"]] == [None] * len(data["dimensions"])
