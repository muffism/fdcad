"""Delete and Patch hands the kernel a copy of the body (D2642, IDEAS 56)."""

from __future__ import annotations

from pathlib import Path

import pytest
from OCP.BRepTools import BRepTools
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.base import FeatureState
from fdcad.core.occ import ShapeMap
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.phase3_parts import (
    block_with_hole_and_boss,
    ok_body,
    ref_of,
    run,
    volume_of,
)
from tests.core.features.test_direct_editing import BASE, boss_faces


def _text(shape: TopoDS_Shape, path: Path) -> str:
    BRepTools.Write_s(shape, str(path))
    return path.read_text()


def _shared(a: TopoDS_Shape, b: TopoDS_Shape) -> int:
    """How many faces, edges and corners of ``b`` are the very ones of ``a``."""
    count = 0
    for kind in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
        mine, theirs = ShapeMap(), ShapeMap()
        TopExp.MapShapes_s(a, kind, mine)
        TopExp.MapShapes_s(b, kind, theirs)
        count += sum(1 for i in range(1, theirs.Extent() + 1) if mine.Contains(theirs.FindKey(i)))
    return count


def test_delete_and_patch_leaves_the_body_it_was_given_as_it_was(tmp_path: Path) -> None:
    """The kernel's defeaturing has no safe mode in this build (D1067) and may write
    into the shapes it is given. A body shares its faces, edges and corners with the
    results kept for the features before it, so the tool works on a copy, as Heal
    Edges does (D1066). In this test the kernel did not write into the body even
    without the copy; the check that no piece is shared is what shows the guard."""
    doc, ids = block_with_hole_and_boss()
    body = ok_body(rebuild(doc), ids["boss"])
    before = _text(body.shape, tmp_path / "before.brep")
    refs = {"faces": [ref_of(body, f) for f in boss_faces(body)]}
    res = run("delete_face", body, {"option": "patch"}, refs)
    assert res.state is FeatureState.OK and res.body is not None
    assert volume_of(res.body.shape) == pytest.approx(BASE - 600, rel=1e-7)
    # The body handed in is unchanged, and the result holds none of its pieces, so
    # nothing done to the result later can reach the kept results either.
    assert _text(body.shape, tmp_path / "after.brep") == before
    assert _shared(body.shape, res.body.shape) == 0
    # The faces the patch kept carry their names over from the copy.
    kept = {n for n, _f in body.faces if not n.startswith(ids["boss"])}
    assert kept <= {n for n, _f in res.body.faces}
