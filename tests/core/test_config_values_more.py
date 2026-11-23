"""More values per configuration: sketch plane, dimension driving, face and body
colours, and a preview built on a copy (TR197, D2101)."""

import pytest

from fdcad.core import config_preview
from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.features.solids import volume_of
from fdcad.core.io import fdef
from tests.core.equations.test_equations import _plate


def test_sketch_plane_and_driving_through_the_table() -> None:
    doc = _plate()
    sketch = next(f for f in doc.features if f.type == "sketch")
    dim = sketch.data["dimensions"][0]["id"]
    plane, driving = f"{sketch.id}.plane", f"{sketch.id}.{dim}:driving"
    table = dt.Table(
        [plane, driving],
        [("Default", ["Front Plane", "true"]), ("Flat", ["top plane", "false"])],
    )
    dt.apply(doc, table)
    assert sketch.refs["plane"] == {"feature": doc.features[1].id}
    configs.activate(doc, "Flat")
    sketch = doc.feature(sketch.id)
    assert sketch.refs["plane"] == {"feature": doc.features[2].id}
    assert sketch.data["dimensions"][0]["driving"] is False
    shown = dt.from_configurations(doc, [plane, driving]).rows
    assert shown == [("Default", ["Front Plane", "true"]), ("Flat", ["Top Plane", "false"])]
    with pytest.raises(dt.DesignTableError, match="no plane named"):
        dt.apply(doc, dt.Table([plane], [("Default", ["Nowhere"])]))


def test_colours_by_configuration() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    configs.add(doc, "Red")
    config_preview.set_colours_vary(doc, True)
    assert config_preview.colours_vary(doc)
    configs.activate(doc, "Red")
    doc.appearance["features"] = {ext: "#FF0000"}
    configs.activate(doc, "Default")
    assert "features" not in doc.appearance
    again = fdef.loads(fdef.dumps(doc))
    configs.activate(again, "Red")
    assert again.appearance["features"] == {ext: "#FF0000"}
    config_preview.set_colours_vary(again, False)
    assert not config_preview.colours_vary(again)
    with pytest.raises(dt.DesignTableError, match="cannot be a table column"):
        dt.value_kind(again, configs.PART_COLORS)


def test_preview_builds_a_copy() -> None:
    doc = _plate()
    ext = doc.features[-1].id
    configs.add(doc, "Thin")
    configs.activate(doc, "Thin")
    configs.set_scoped(doc, f"{ext}.suppressed", True, "this")
    configs.activate(doc, "Default")
    before = fdef.dumps(doc)
    found = config_preview.build(doc, "Thin")
    assert found.name == "Thin" and found.failed == 0
    full = config_preview.build(doc, "Default")
    assert volume_of(full.shape) == pytest.approx(60 * 40 * 10)
    assert found.shape is None or volume_of(found.shape) == pytest.approx(0.0)
    assert fdef.dumps(doc) == before
    with pytest.raises(configs.ConfigurationError):
        config_preview.build(doc, "Missing")
