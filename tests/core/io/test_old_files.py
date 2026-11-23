"""Files saved before the WP10 extrude and revolve options open and save unchanged
(CLAUDE.md section 4 item 4, D140 to D143)."""

import math
from pathlib import Path

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.io import fdef
from fdcad.core.rebuild.runner import rebuild
from fdcad.samples.make import SAMPLE_DIR

FIXTURE = Path(__file__).parents[2] / "fixtures" / "extrude_revolve_0_1_0.fdef"
NEW_KEYS = {"start_condition", "start_offset", "start_reverse", "end_condition2", "cut_outside"}


def test_old_file_opens_rebuilds_and_saves_byte_for_byte() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    doc = fdef.loads(text)
    results = rebuild(doc)
    assert all(r.state is not FeatureState.ERROR for r in results.values())
    last = results[doc.features[-1].id].body
    assert last is not None
    expected = (
        60 * 40 * 12  # base plate, 10 up and 2 down
        - math.pi * 25 * 12  # Through All hole
        + math.pi * 36 * 4  # Mid Plane boss, half of it above the plate
        + math.pi * (15**2 - 5**2) * 10 / 4  # quarter revolve, kept separate
    )
    assert volume_of(last.shape) == pytest.approx(expected, rel=1e-9)
    assert len(solids(last.shape)) == 2
    assert fdef.dumps(doc) == text


@pytest.mark.parametrize("path", sorted(SAMPLE_DIR.glob("*.fdprt")), ids=lambda p: p.stem)
def test_samples_have_none_of_the_new_keys_and_save_unchanged(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    doc = fdef.loads(text)
    for feature in doc.features:
        assert not NEW_KEYS & set(feature.params)
        assert "start" not in feature.refs
    assert fdef.dumps(doc) == text
