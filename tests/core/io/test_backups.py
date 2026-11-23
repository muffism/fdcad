"""Older copies of a part kept on save (TR218 item 3, D961)."""

from __future__ import annotations

from pathlib import Path

from fdcad.core.io.backups import backups_of, keep_backup


def test_keeps_the_chosen_number_newest_first(tmp_path: Path) -> None:
    part = tmp_path / "bracket.fdprt"
    assert keep_backup(part, 3) is None  # nothing saved yet
    for version in range(5):
        part.write_text(f"v{version}", encoding="utf-8")
        keep_backup(part, 3)
    copies = backups_of(part)
    assert [p.name for p in copies] == [
        "bracket.backup1.fdprt",
        "bracket.backup2.fdprt",
        "bracket.backup3.fdprt",
    ]
    assert [p.read_text(encoding="utf-8") for p in copies] == ["v4", "v3", "v2"]
    assert copies[0].parent == tmp_path / "Backups"


def test_chosen_folder_and_off(tmp_path: Path) -> None:
    part = tmp_path / "a.fdprt"
    part.write_text("x", encoding="utf-8")
    assert keep_backup(part, 0) is None
    kept = keep_backup(part, 2, tmp_path / "old")
    assert kept == tmp_path / "old" / "a.backup1.fdprt"
    assert backups_of(part, tmp_path / "old") == [kept]
