"""User hole sizes from a file (TR144 item 4, D1914)."""

from __future__ import annotations

import pytest

from fdcad.core.features import hole_data


def test_a_size_file_is_read_with_defaults_for_missing_values() -> None:
    text = "name,diameter,clearance_normal\nM7,7,7.6\nBig,20,\n"
    rows = hole_data.parse_user_sizes(text)
    assert [r.name for r in rows] == ["M7", "Big"]
    assert rows[0].clearance[1] == 7.6 and rows[1].clearance[1] == pytest.approx(22.0)
    assert rows[1].tap_drill == pytest.approx(16.0)


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("size,d\nM7,7\n", "header row"),
        ("name,diameter\nM7,seven\n", "Row 2"),
        ("name,diameter\n,7\n", "Row 2 needs a name"),
        ("name,diameter\n", "no sizes"),
    ],
)
def test_a_bad_file_names_the_problem(text: str, why: str) -> None:
    with pytest.raises(ValueError, match=why):
        hole_data.parse_user_sizes(text)


def test_user_sizes_are_their_own_standard() -> None:
    saved = list(hole_data.USER_SIZES)
    try:
        hole_data.USER_SIZES[:] = hole_data.parse_user_sizes("name,diameter\nM7,7\n")
        assert hole_data.size_names("user") == ["M7"]
        assert hole_data.find("user", "M7") is not None
        assert "M7" not in hole_data.size_names("iso")
    finally:
        hole_data.USER_SIZES[:] = saved
