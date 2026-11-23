"""Insert Part keeps the path of a part in its own folder tree relative (IDEAS 61, D2625).

A part file is written with the path relative to itself when the inserted part is
in its folder or below, so the two files can move together, to another folder or
another computer. In memory the path is always absolute, so a session and its file
build the same and have the same cache key.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from fdcad.core.cache import disk
from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import messages, plate, volume


def _inserting(source: Path) -> tuple[Document, str]:
    doc = new_document()
    fid = doc.new_feature_id()
    params = {"part_file": str(source), "dx": Param("100", 100.0)}
    doc.features.append(Feature(fid, "insert_part", "Insert Part 1", params=params, refs={}))
    return doc, fid


def _stored(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    (feature,) = (f for f in data["features"] if f["type"] == "insert_part")
    return str(feature["params"]["part_file"])


def _builds(path: Path, fid: str) -> None:
    res = RebuildEngine().rebuild(fdef.load(path)).results[fid]
    assert res.state is FeatureState.OK, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(25000, rel=1e-9)


def _folder_with_parts(root: Path, sub: str = "") -> tuple[Path, str]:
    """A folder holding an assembly part that inserts a plate kept in ``sub``."""
    (root / sub).mkdir(parents=True, exist_ok=True)
    source = root / sub / "plate.fdprt"
    fdef.save(plate()[0], source)
    doc, fid = _inserting(source)
    fdef.save(doc, root / "assembly.fdprt")
    return root / "assembly.fdprt", fid


@pytest.mark.parametrize(("sub", "text"), [("", "plate.fdprt"), ("parts", "parts/plate.fdprt")])
def test_a_folder_of_parts_moves_together(tmp_path: Path, sub: str, text: str) -> None:
    part, fid = _folder_with_parts(tmp_path / "first", sub)
    assert _stored(part) == text
    shutil.copytree(tmp_path / "first", tmp_path / "moved")
    shutil.rmtree(tmp_path / "first")
    _builds(tmp_path / "moved" / "assembly.fdprt", fid)


def test_a_part_outside_the_folder_keeps_its_full_path(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    source = tmp_path / "a" / "plate.fdprt"
    fdef.save(plate()[0], source)
    doc, fid = _inserting(source)
    fdef.save(doc, tmp_path / "b" / "assembly.fdprt")
    assert Path(_stored(tmp_path / "b" / "assembly.fdprt")) == source
    _builds(tmp_path / "b" / "assembly.fdprt", fid)


def test_an_old_file_with_a_full_path_still_opens(tmp_path: Path) -> None:
    source = tmp_path / "plate.fdprt"
    fdef.save(plate()[0], source)
    doc, fid = _inserting(source)
    part = tmp_path / "old" / "assembly.fdprt"
    part.parent.mkdir()
    fdef.save_text(fdef.dumps(doc), part)  # written as before D2625: the full path
    assert Path(_stored(part)) == source
    _builds(part, fid)


def test_an_old_full_path_that_is_gone_finds_the_part_beside(tmp_path: Path) -> None:
    """Moved to another computer: the full path is gone, the part was copied beside."""
    doc, fid = _inserting(tmp_path / "elsewhere" / "plate.fdprt")
    part = tmp_path / "here" / "assembly.fdprt"
    part.parent.mkdir()
    fdef.save(plate()[0], part.parent / "plate.fdprt")
    fdef.save_text(fdef.dumps(doc), part)
    _builds(part, fid)


def test_save_as_to_another_folder_rewrites_the_path(tmp_path: Path) -> None:
    part, fid = _folder_with_parts(tmp_path / "project" / "first")
    doc = fdef.load(part)
    fdef.save(doc, tmp_path / "project" / "assembly.fdprt")  # one folder up: still a tree
    assert _stored(tmp_path / "project" / "assembly.fdprt") == "first/plate.fdprt"
    _builds(tmp_path / "project" / "assembly.fdprt", fid)
    (tmp_path / "other").mkdir()
    fdef.save(doc, tmp_path / "other" / "assembly.fdprt")  # outside: the full path
    stored = Path(_stored(tmp_path / "other" / "assembly.fdprt"))
    assert stored == tmp_path / "project" / "first" / "plate.fdprt"
    _builds(tmp_path / "other" / "assembly.fdprt", fid)


def test_an_opened_part_has_the_key_of_the_session_that_saved_it(tmp_path: Path) -> None:
    """The saved solid (D1102) is used on open only when the keys match."""
    (tmp_path / "parts").mkdir()
    source = tmp_path / "parts" / "plate.fdprt"
    fdef.save(plate()[0], source)
    doc, _fid = _inserting(source)
    fdef.save(doc, tmp_path / "assembly.fdprt")
    assert disk.document_key(fdef.load(tmp_path / "assembly.fdprt")) == disk.document_key(doc)
