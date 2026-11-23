"""Shell names two faces too close for a wall on each (D2616)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from fdcad.core.document.model import Document, new_document
from fdcad.core.features import shell as shell_mod
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, messages, rect
from tests.core.features.test_shell import add_shell

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


def _block_with_two_holes() -> tuple[Document, str]:
    # Two 3 mm holes 9 mm apart leave 3 mm of material between them.
    doc = new_document()
    s = Sketch()
    rect(s, -20, -10, 20, 10)
    s.add_circle(-4.5, 0, 3.0)
    s.add_circle(4.5, 0, 3.0)
    return doc, add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)


def _no_search(*_a: Any, **_k: Any) -> Any:
    raise AssertionError("the search for a face to skip ran")


def test_two_holes_too_close_are_named(monkeypatch: pytest.MonkeyPatch) -> None:
    doc, ext = _block_with_two_holes()
    fid = add_shell(doc, 1.6, faces=[])
    monkeypatch.setattr(shell_mod, "skip_help", _no_search)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    assert "3 mm apart" in text and "thinner than 1.5 mm" in text
    highlight = res.issues[0].highlight
    assert highlight is not None and len(highlight) == 2
    assert all(n.startswith(f"{ext}/") for n in highlight)


def test_a_wall_that_fits_between_the_holes_still_builds() -> None:
    doc, _ext = _block_with_two_holes()
    fid = add_shell(doc, 1.0, faces=[])
    assert rebuild(doc)[fid].state is not FeatureState.ERROR


def test_a_shell_of_the_attractor_plate_fails_quickly(monkeypatch: pytest.MonkeyPatch) -> None:
    # Two of the plate's holes are 2 mm apart, so a 1 mm shell cannot be made. The
    # search for a face to skip took about 15 s before giving the plain message.
    from fdcad.core.document.model import Feature, Param
    from fdcad.core.io import fdef

    doc = fdef.load(SAMPLES / "graphs" / "attractor_plate.fdprt")
    doc.solid = {}
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "shell", "Shell 1", params={"thickness": Param("1", 1.0)}, refs={})
    )
    monkeypatch.setattr(shell_mod, "skip_help", _no_search)
    start = time.perf_counter()
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "2 mm apart" in messages(res)
    assert time.perf_counter() - start < 6.0
