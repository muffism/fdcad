"""Portable mode (D1033): a marker file or the program's name turns it on."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from fdcad import portable


def test_not_portable_from_source_or_without_a_marker(tmp_path: Path) -> None:
    exe = tmp_path / "FDCAD.exe"
    exe.write_bytes(b"")
    assert portable.portable_folder(exe, frozen=False) is None
    assert portable.portable_folder(exe, frozen=True) is None
    assert not (tmp_path / portable.DATA_FOLDER).exists()


def test_marker_file_or_program_name_turns_it_on(tmp_path: Path) -> None:
    exe = tmp_path / "FDCAD.exe"
    exe.write_bytes(b"")
    (tmp_path / portable.MARKER).write_text("", encoding="utf-8")
    assert portable.portable_folder(exe, frozen=True) == tmp_path / portable.DATA_FOLDER
    other = tmp_path / "one" / "FDCAD-portable.exe"
    other.parent.mkdir()
    other.write_bytes(b"")
    assert portable.portable_folder(other, frozen=True) == other.parent / portable.DATA_FOLDER


def test_enable_points_every_folder_and_the_preferences_beside_the_program(
    tmp_path: Path,
) -> None:
    exe = tmp_path / "FDCAD-portable.exe"
    exe.write_bytes(b"")
    env: dict[str, str] = {}
    try:
        folder = portable.enable(env, exe, frozen=True)
        assert folder == tmp_path / portable.DATA_FOLDER
        assert env["FDCAD_DATA_DIR"] == str(folder)
        assert env["FDCAD_CACHE_DIR"] == str(folder / "Cache")
        store = portable.settings()
        assert store.format() == QSettings.Format.IniFormat
        store.setValue("check", "1")
        store.sync()
        assert Path(store.fileName()) == folder / portable.SETTINGS_FILE
        assert Path(store.fileName()).is_file()
        assert portable.active() == folder
    finally:
        portable._ACTIVE = None
    assert portable.settings().format() == QSettings.Format.NativeFormat


def test_read_only_folder_falls_back_to_the_normal_places(tmp_path: Path) -> None:
    exe = tmp_path / "FDCAD-portable.exe"
    exe.write_bytes(b"")
    (tmp_path / portable.DATA_FOLDER).write_text("a file, so no folder can be made here")
    assert portable.portable_folder(exe, frozen=True) is None
