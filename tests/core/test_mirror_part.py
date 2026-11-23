"""Mirror Part to a new file (TR73, D899)."""

from __future__ import annotations

import pytest

from fdcad.core.features.solids import volume_of
from fdcad.core.mirror_part import mirrored_document
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.units import UnitSystem
from tests.core.features.test_features import body, plate


def test_mirrored_part_is_the_opposite_hand_with_the_same_volume() -> None:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    doc, ext = plate()  # 0..50 in X
    shape = body(rebuild(doc), ext).shape
    new = mirrored_document(shape, UnitSystem.MM, "Plate")
    results = rebuild(new)
    final = next(r.body for r in reversed(list(results.values())) if r.body is not None)
    assert volume_of(final.shape) == pytest.approx(volume_of(shape), rel=1e-6)
    box = Bnd_Box()
    BRepBndLib.Add_s(final.shape, box)
    assert box.CornerMax().X() == pytest.approx(0.0, abs=1e-6)  # now from -50 to 0
    assert box.CornerMin().X() == pytest.approx(-50.0, abs=1e-6)
