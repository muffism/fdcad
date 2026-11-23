"""Bold, italic and rotation per character (TR121 item 2, D2202)."""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.text import (
    SketchText,
    char_style,
    layout,
    set_style,
    text_from_json,
    text_to_json,
)
from tests.core.sketch.test_sketch_text import bounds


def test_runs_set_each_character_and_save() -> None:
    t = SketchText("t1", "ABCD", bold=True)
    set_style(t, 1, 3, italic=True, bold=False)
    set_style(t, 2, 9, angle=math.radians(90))
    set_style(t, 3, 3, bold=False)  # empty: ignored
    assert char_style(t, 0) == (True, False, 0.0)
    assert char_style(t, 1) == (False, True, 0.0)
    assert char_style(t, 2)[:2] == (False, True)
    assert math.isclose(char_style(t, 2)[2], math.pi / 2)
    assert char_style(t, 3) == (True, False, math.pi / 2)
    raw = text_to_json(t)
    assert raw["styles"] == [
        {"start": 1, "end": 3, "bold": False, "italic": True},
        {"start": 2, "end": 4, "angle": math.radians(90)},
    ]
    assert text_from_json(raw) == t
    assert sketch_from_data(sketch_to_data(Sketch(texts=[t]))).texts == [t]
    assert "styles" not in text_to_json(SketchText("t2", "A"))


def test_a_turned_character_changes_the_outline() -> None:
    s = Sketch()
    plain = bounds(layout(SketchText("t1", "HI", height=10.0), s))
    t = SketchText("t1", "HI", height=10.0)
    set_style(t, 1, 2, angle=math.radians(-90))
    turned = bounds(layout(t, s))
    assert turned[1] < plain[1] - 0.5  # the I lies down below the base line


def test_an_italic_character_slants() -> None:
    s = Sketch()
    plain = layout(SketchText("t1", "II", height=10.0), s)
    t = SketchText("t1", "II", height=10.0)
    set_style(t, 1, 2, italic=True)
    slanted = layout(t, s)
    assert bounds(slanted) != bounds(plain)
