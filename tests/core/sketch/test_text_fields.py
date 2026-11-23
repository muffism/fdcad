"""Text linked to a value (TR54, D897)."""

from __future__ import annotations

from fdcad.core.document.model import Param, Variable, new_document
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.text_fields import expand, field_values
from fdcad.core.units import Kind, UnitSystem


def test_fields_show_variables_dimensions_and_properties() -> None:
    doc = new_document()
    doc.units = UnitSystem.IN
    doc.variables.append(Variable("width", Kind.LENGTH, "2in", 50.8))
    doc.properties = [{"name": "Part", "kind": "text", "value": "A-17"}]
    s = Sketch()
    lid = s.add_line(0, 0, 25.4, 0)
    dim = s.dimension("distance", [lid], Param("1in", 25.4))
    values = field_values(doc, s)
    assert expand("W {width} in", values) == "W 2 in"
    assert expand("{width:.2f}", values) == "2.00"
    assert expand(f"{{{dim.id}}}", values) == "1"
    assert expand("{Part} rev {missing}", values) == "A-17 rev {missing}"


def test_text_follows_the_variable_on_rebuild() -> None:
    from fdcad.core.rebuild.engine import RebuildEngine
    from fdcad.core.sketch.text import SketchText
    from tests.core.features.test_features import add_sketch

    doc = new_document()
    doc.variables.append(Variable("n", Kind.NUMBER, "1", 1.0))
    s = Sketch()
    s.texts.append(SketchText(id="t1", text="{n}", x=0.0, y=0.0, height=10.0))
    sid = add_sketch(doc, s, {"feature": "f2"})
    engine = RebuildEngine()
    first = engine.rebuild(doc).results[sid].sketch
    assert first is not None and first.profile is not None
    doc.variables[0] = Variable("n", Kind.NUMBER, "88", 88.0)
    second = engine.rebuild(doc).results[sid].sketch
    assert second is not None and second.profile is not None
    assert len(second.profile.faces) > len(first.profile.faces)
