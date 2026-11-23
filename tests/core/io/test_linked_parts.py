"""Bodies to linked part files (TR280, D2421)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from fdcad.core.io.export import ExportError
from fdcad.core.io.save_bodies import save_linked_parts
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import plate, volume


def test_linked_parts_follow_the_master(tmp_path: Path) -> None:
    master, ext = plate()
    path = tmp_path / "master.fdprt"
    fdef.save(master, path)
    out = tmp_path / "parts"
    out.mkdir()
    written = save_linked_parts(path, [("Plate", 1)], out)
    assert [p.name for p in written] == ["Plate.fdprt"]
    part = fdef.load(written[0])
    report = RebuildEngine().rebuild(part)
    assert report.body is not None and volume(report.body.shape) == pytest.approx(25000)
    master.feature(ext).params["depth"] = Param("20", 20.0)
    fdef.save(master, path)
    report = RebuildEngine().rebuild(fdef.load(written[0]))
    assert report.body is not None and volume(report.body.shape) == pytest.approx(50000)
    with pytest.raises(ExportError, match="Save the part first"):
        save_linked_parts(tmp_path / "missing.fdprt", [("x", 1)], out)
