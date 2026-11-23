"""Overlapping bodies on export (TR411, D907)."""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.features.solids import compound, solids, volume_of
from fdcad.core.io.export import MeshSettings
from fdcad.core.printing.overlaps import find, resolve, warning


def _two() -> object:
    a = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 10.0, 10.0, 10.0).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(5, 0, 0), 10.0, 10.0, 10.0).Shape()  # half inside a
    return compound([a, b])


def test_find_join_and_first_wins() -> None:
    shape = _two()
    pairs = find(shape)
    assert len(pairs) == 1 and pairs[0][:2] == (1, 2) and pairs[0][2] == pytest.approx(500.0)
    assert "overlap" in warning(pairs)
    joined = resolve(shape, "join")
    assert len(solids(joined)) == 1 and volume_of(joined) == pytest.approx(1500.0)
    first = resolve(shape, "first")
    vols = sorted(volume_of(s) for s in solids(first))
    assert vols == pytest.approx([500.0, 1000.0])
    assert resolve(shape, "warn") is shape


def test_setting_is_saved_only_when_set() -> None:
    assert "overlaps" not in MeshSettings().to_data()
    s = MeshSettings(overlaps="join")
    assert MeshSettings.from_data(s.to_data()).overlaps == "join"
