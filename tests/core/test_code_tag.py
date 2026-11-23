"""QR code tags (TR311, D1215)."""

from __future__ import annotations

import pytest

from fdcad.core.printing.qr_code import capacity, ecc, modules, outline, version_for
from fdcad.core.sketch.code_tag import add_code_tag, size_of
from fdcad.core.sketch.model import Line, Sketch


def test_versions_and_capacity() -> None:
    assert len(modules("HELLO")) == 21
    assert version_for(14) == 1 and version_for(15) == 2
    assert capacity() == 213
    with pytest.raises(ValueError):
        modules("x" * 214)


def test_reed_solomon_codewords_divide_the_generator() -> None:
    from fdcad.core.printing.qr_code import _EXP, _mul

    data = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]
    code = data + ecc(data, 10)
    for i in range(10):  # every syndrome of a good code word is zero
        s = 0
        for c in code:
            s = _mul(s, _EXP[i]) ^ c
        assert s == 0


def test_fixed_patterns() -> None:
    g = modules("Part 42")
    n = len(g)
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):  # the three finder squares
        assert all(g[r0][c0 + k] for k in range(7))
        assert not g[r0 + 1][c0 + 1] and g[r0 + 3][c0 + 3]
    assert g[n - 8][8]  # the dark module
    assert [g[6][c] for c in range(8, n - 8)] == [c % 2 == 0 for c in range(8, n - 8)]


def test_outline_area_matches_the_dark_modules() -> None:
    g = modules("https://example.org")
    loops = outline(g)

    def area(loop: list[tuple[float, float]]) -> float:
        pairs = zip(loop, loop[1:] + loop[:1], strict=True)
        return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in pairs)

    # Each corner cut takes off a small triangle of CORNER_CUT squared over two.
    points = {p for lp in loops for p in lp}
    assert sum(area(lp) for lp in loops) == pytest.approx(sum(map(sum, g)), abs=0.01 * len(points))
    assert len(points) == sum(len(lp) for lp in loops)  # no point is shared


def test_sketch_lines_and_a_raised_tag() -> None:
    from fdcad.core.document.model import new_document
    from fdcad.core.rebuild.runner import rebuild
    from tests.core.features.test_features import add_extrude, add_sketch, body, volume

    s = Sketch()
    lines = add_code_tag(s, "FD-0042", 1.0, (5.0, 5.0))
    assert lines and all(isinstance(s.entities[i], Line) for i in lines)
    assert size_of("FD-0042", 1.0) == pytest.approx(21.0)
    doc = new_document()
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 1.0)
    res = rebuild(doc)
    dark = sum(map(sum, modules("FD-0042")))
    assert volume(body(res, fid).shape) == pytest.approx(dark * 1.0, rel=1e-2)
    with pytest.raises(ValueError):
        add_code_tag(Sketch(), "x", 0.1)
