"""Save Increment names (TR305, D923)."""

from __future__ import annotations

from pathlib import Path

from fdcad.core.io.increment import next_name, next_path


def test_next_name() -> None:
    assert next_name("Bracket") == "Bracket 01"
    assert next_name("Bracket 01") == "Bracket 02"
    assert next_name("box_7") == "box_8"
    assert next_name("v009") == "v010"
    assert next_name("part 99") == "part 100"
    assert next_name("2024") == "2024 01"  # only a number: add one, keep the name


def test_next_path_skips_taken_names(tmp_path: Path) -> None:
    part = tmp_path / "Lid.fdprt"
    (tmp_path / "Lid 01.fdprt").write_text("x")
    assert next_path(part) == tmp_path / "Lid 02.fdprt"
