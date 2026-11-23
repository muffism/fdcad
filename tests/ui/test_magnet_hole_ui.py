"""Magnet pocket in the Hole Tool panel (TR179, D869)."""

from __future__ import annotations

from fdcad.core.features import hole_data
from fdcad.ui import strings_phase4 as text


def test_magnet_type_and_sizes_are_offered() -> None:
    assert "magnet" in hole_data.HOLE_TYPES and text.HOLE_TYPES["magnet"] == "Magnet Pocket"
    assert "Round 6 x 3" in hole_data.MAGNETS and "Block 20 x 10 x 3" in hole_data.MAGNETS
    assert "magnet" in text.TIPS and "magnet_skin" in text.TIPS
