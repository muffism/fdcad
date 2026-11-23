"""Shell Both Sides (TR322, D1411)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_shell import _face_ref, add_shell


def test_open_shell_wall_straddles_the_old_surface() -> None:
    doc, ext = plate()
    top = _face_ref(doc, ext, "cap/end")
    fid = add_shell(doc, 2.0, faces=[top])
    doc.feature(fid).params["both_sides"] = True
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    # Outer box 52 x 52 x 11 (grows 1 mm on the sides and bottom, open top stays at 10),
    # less the inner pocket 48 x 48 x 9 (from z = 1 up to the open top).
    expected = 52 * 52 * 11 - 48 * 48 * 9
    assert volume(res.body.shape) == pytest.approx(expected, rel=1e-6)
    names = [n for n, _f in res.body.faces]
    assert any(n.startswith(f"{fid}/outer/") for n in names)
    assert any(n.startswith(f"{fid}/shell/") for n in names)


def test_closed_hollow_both_sides() -> None:
    doc, _ext = plate()
    fid = add_shell(doc, 2.0)
    doc.feature(fid).params["both_sides"] = True
    res = body(rebuild(doc), fid)
    expected = 52 * 52 * 12 - 48 * 48 * 8
    assert volume(res.shape) == pytest.approx(expected, rel=1e-6)
