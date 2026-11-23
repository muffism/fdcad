"""Split saves its kept bodies to separate files (PHASE3_SPEC P3.4 item 3, D528)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fdcad.core.features.base import BuildContext
from fdcad.core.features.preview import body_before
from fdcad.core.features.split import Split
from fdcad.core.io import fdef
from fdcad.core.io.export import ExportError
from fdcad.core.io.mesh_import import read_mesh
from fdcad.core.io.save_bodies import file_stem, save_bodies
from fdcad.core.io.step_import import read_step
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import add_feature, add_sketch, volume_of
from tests.core.features.test_multibody import BLOCK, two_blocks


def split_part() -> tuple[object, list[tuple[int, object]]]:
    doc = two_blocks()[0]
    s = Sketch()
    s.add_line(15, -5, 15, 25)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = add_feature(doc, "split", {}, {"tools": [{"feature": sk}]})
    doc.feature(fid).data["keep"] = [1, 4]
    results = rebuild(doc)
    feature = doc.feature(fid)
    ctx = BuildContext(doc, body_before(doc, feature, results), results)
    return doc, Split().kept_bodies(feature, ctx)


def mesh_volume(path: Path, fmt: str) -> float:
    corners = read_mesh(path.read_bytes(), fmt).corners().astype(np.float64)
    a, b, c = corners[:, 0], corners[:, 1], corners[:, 2]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def test_kept_bodies_are_the_ticked_pieces() -> None:
    _doc, kept = split_part()
    assert [k for k, _shape in kept] == [1, 4]
    volumes = [volume_of(shape) for _k, shape in kept]
    assert volumes == pytest.approx([15 * 20 * 10, 15 * 20 * 10], rel=1e-9)
    assert sum(volumes) < 2 * BLOCK


@pytest.mark.parametrize("fmt", ["fdef", "step", "stl", "3mf"])
def test_each_body_reimports_with_its_volume(tmp_path: Path, fmt: str) -> None:
    _doc, kept = split_part()
    bodies = [(f"Body {k}", shape) for k, shape in kept]
    written = save_bodies(bodies, tmp_path, fmt)
    ext = "fdprt" if fmt == "fdef" else fmt
    assert [p.name for p in written] == [f"Body 1.{ext}", f"Body 4.{ext}"]
    for path, (_name, shape) in zip(written, bodies, strict=True):
        want = volume_of(shape)
        if fmt == "fdef":
            part = fdef.load(path)
            assert [f.type for f in part.features][-1] == "import_step"
            result = rebuild(part)[part.features[-1].id]
            assert result.body is not None
            assert volume_of(result.body.shape) == pytest.approx(want, rel=1e-6)
        elif fmt == "step":
            assert volume_of(read_step(path.read_bytes()).shape) == pytest.approx(want, rel=1e-6)
        else:
            assert mesh_volume(path, fmt) == pytest.approx(want, rel=1e-3)


def test_names_are_made_safe_and_unique(tmp_path: Path) -> None:
    _doc, kept = split_part()
    shape = kept[0][1]
    written = save_bodies([("Lid: top/left", shape), ("lid_ top_left", shape)], tmp_path, "step")
    assert [p.name for p in written] == ["Lid_ top_left.step", "lid_ top_left 2.step"]
    assert file_stem("  ..  ", "Body 3") == "Body 3"


@pytest.mark.parametrize(
    ("name", "stem"),
    [
        ("CON", "CON_"),
        ("nul", "nul_"),
        ("Com1", "Com1_"),
        ("aux.top", "aux_.top"),
        ("nul .x", "nul_.x"),
        ("Console", "Console"),
    ],
)
def test_windows_device_names_are_not_used(name: str, stem: str) -> None:
    """A body named CON or NUL gave a file Windows cannot write."""
    assert file_stem(name, "Body 1") == stem


def test_errors_name_what_failed(tmp_path: Path) -> None:
    _doc, kept = split_part()
    with pytest.raises(ExportError, match="does not exist"):
        save_bodies([("A", kept[0][1])], tmp_path / "missing", "step")
    with pytest.raises(ExportError, match="Unknown format"):
        save_bodies([("A", kept[0][1])], tmp_path, "obj")
