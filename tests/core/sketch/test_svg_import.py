"""Insert SVG (TR117, D863)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.dxf_import import DxfError, Placement, build
from fdcad.core.sketch.model import Circle, Line, Sketch, Spline
from fdcad.core.sketch.svg_import import parse

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 200 100">
  <rect x="0" y="0" width="200" height="100"/>
  <g transform="translate(100 50)">
    <circle cx="0" cy="0" r="20"/>
  </g>
  <path d="M 10 10 C 30 0 50 20 70 10 A 10 10 0 0 1 90 10 Z"/>
  <text x="1" y="1">ignored</text>
</svg>"""


def test_shapes_scale_and_flip() -> None:
    drawing = parse(SVG)
    assert drawing.units == 4
    sketch = Sketch()
    built = build(drawing, sketch, Placement())
    lines = [e for e in sketch.entities.values() if isinstance(e, Line)]
    circles = [e for e in sketch.entities.values() if isinstance(e, Circle)]
    splines = [e for e in sketch.entities.values() if isinstance(e, Spline)]
    assert len(lines) >= 5 and len(circles) == 1 and len(splines) == 2
    assert circles[0].radius == pytest.approx(10.0)  # 20 user units at 0.5 mm each
    centre = sketch.xy(circles[0].center)
    assert centre == pytest.approx((50.0, -25.0))  # Y turned upward
    assert built.entities
    assert drawing.skipped["text"] == 1


def test_bad_files() -> None:
    with pytest.raises(DxfError, match="not a readable SVG"):
        parse("<svg><line")
    with pytest.raises(DxfError, match="no lines or curves"):
        parse('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    with pytest.raises(DxfError, match="entities"):
        parse('<!DOCTYPE svg [<!ENTITY a "b">]><svg/>')
