"""Linked dimension values (TR193, D978)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.links_values import LinkError, follow, link, unlink
from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data


def _two() -> tuple[Sketch, str, str]:
    sk = Sketch()
    a = sk.add_line(0, 0, 20, 0)
    b = sk.add_line(0, 10, 15, 10)
    d1 = sk.dimension("distance", [a], Param("20mm", 20.0))
    d2 = sk.dimension("distance", [b], Param("15mm", 15.0))
    return sk, d1.id, d2.id


def test_link_follow_unlink_and_save() -> None:
    sk, d1, d2 = _two()
    assert link(sk, [d1, d2], "Width") == [d1, d2]
    one, two = sk.dimensions
    assert two.param == one.param
    two.param = Param("25mm", 25.0)
    assert follow(sk, two) == [d1] and one.param.value == 25.0
    again = sketch_from_data(sketch_to_data(sk))
    assert [d.link for d in again.dimensions] == ["Width", "Width"]
    assert unlink(sk, [d1]) == 1 and one.link is None


def test_refused_links() -> None:
    sk, d1, d2 = _two()
    with pytest.raises(LinkError, match="starts with a letter"):
        link(sk, [d1, d2], "2 wide")
    with pytest.raises(LinkError, match="two or more"):
        link(sk, [d1], "W")
    a = sk.add_line(0, 0, 0, 10)
    b = sk.add_line(0, 0, 10, 10)
    ang = sk.dimension("angle", [a, b], Param("45deg", 0.785398))
    with pytest.raises(LinkError, match="one kind"):
        link(sk, [d1, ang.id], "Mixed")
