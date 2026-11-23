"""Saved parts and exports get normal file permissions (bug hunt F2)."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.io import export, fdef

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")


@pytest.fixture
def umask_022() -> Iterator[None]:
    old = os.umask(0o022)
    yield
    os.umask(old)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.mark.usefixtures("umask_022")
def test_a_new_part_file_follows_the_umask(tmp_path: Path) -> None:
    target = tmp_path / "part.fdprt"
    fdef.save(new_document(), target)
    assert _mode(target) == 0o644


@pytest.mark.usefixtures("umask_022")
def test_saving_over_a_part_keeps_its_permissions(tmp_path: Path) -> None:
    target = tmp_path / "shared.fdprt"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o664)
    fdef.save(new_document(), target)
    assert _mode(target) == 0o664
    assert fdef.load(target).next_id == new_document().next_id


@pytest.mark.usefixtures("umask_022")
def test_exports_follow_the_umask(tmp_path: Path) -> None:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    shape = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    for name, write in (
        ("box.step", export.export_step),
        ("box.stl", export.export_stl),
        ("box.3mf", export.export_3mf),
    ):
        target = tmp_path / name
        write(shape, target)
        assert _mode(target) == 0o644, name
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".fdcad-")]
