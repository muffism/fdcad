"""Free disk space and memory for the low space warnings (TR220, D968)."""

from __future__ import annotations

import sys
from pathlib import Path

from fdcad.core.resources import Shortage, disk_of, free_disk, free_memory, shortages


def test_free_disk_of_a_missing_file_uses_its_folder(tmp_path: Path) -> None:
    free = free_disk(tmp_path / "not" / "there.fdprt")
    assert free is not None and free > 0


def test_free_memory_reads_on_windows_only() -> None:
    assert free_memory("darwin") is None
    if sys.platform == "win32":
        found = free_memory()
        assert found is not None and found > 0


def test_shortages_list_each_disk_once_and_memory() -> None:
    folders = [Path("C:/a"), Path("C:/b"), Path("D:/c")]
    low = shortages(
        folders,
        disk_free=lambda f: 10 if str(f).startswith("C") else 10**12,
        memory_free=lambda: 5,
        low_disk=100,
        low_memory=100,
    )
    assert low == [Shortage("disk", 10, str(Path("C:/a"))), Shortage("memory", 5)]
    assert shortages(folders, disk_free=lambda f: None, memory_free=lambda: None) == []


def test_two_folders_on_one_disk_are_one_disk(tmp_path: Path) -> None:
    """D2707: also true where paths have no drive letter, and for folders not made yet."""
    assert disk_of(tmp_path / "a") == disk_of(tmp_path / "b" / "c.fdprt")
    assert disk_of(Path("C:/a")) == disk_of(Path("C:/b"))
    low = shortages(
        [tmp_path / "a", tmp_path / "b"], disk_free=lambda f: 10, memory_free=lambda: None
    )
    assert low == [Shortage("disk", 10, str(tmp_path / "a"))]
