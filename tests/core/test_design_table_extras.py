"""Design table description, part colour and custom property columns (TR90 item 1, D2100)."""

import pytest

from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.io import fdef
from tests.core.equations.test_equations import _plate


def _doc():  # type: ignore[no-untyped-def]
    doc = _plate()
    doc.properties = [{"name": "PartNo", "kind": "text", "value": "A-1"}]
    return doc


def _table() -> dt.Table:
    return dt.Table(
        [dt.DESCRIPTION, configs.PART_COLOR, "prop.PartNo"],
        [
            ("Default", ["Short plate", "#B4BCC4", "A-1"]),
            ("Long", ["Long plate", "#3366cc", "A-2"]),
        ],
    )


def test_description_colour_and_property_columns_apply() -> None:
    doc = _doc()
    dt.apply(doc, _table())
    items = {i["name"]: i for i in configs.items(doc)}
    assert items["Long"]["description"] == "Long plate"
    assert doc.appearance["part_color"] == "#B4BCC4"
    configs.activate(doc, "Long")
    assert doc.appearance["part_color"] == "#3366CC"
    assert doc.properties[0]["configs"] == {"Long": "A-2"}
    assert dt.from_configurations(doc, _table().columns).rows == [
        ("Default", ["Short plate", "#B4BCC4", "A-1"]),
        ("Long", ["Long plate", "#3366CC", "A-2"]),
    ]


def test_extra_columns_survive_saving() -> None:
    doc = _doc()
    dt.apply(doc, _table())
    again = fdef.loads(fdef.dumps(doc))
    stored = dt.stored(again)
    assert stored is not None
    assert stored.columns == _table().columns
    assert stored.rows[1] == ("Long", ["Long plate", "#3366CC", "A-2"])
    configs.activate(again, "Long")
    assert again.appearance["part_color"] == "#3366CC"


def test_bad_colour_and_unknown_property_are_refused() -> None:
    doc = _doc()
    bad = dt.Table([configs.PART_COLOR], [("Default", ["blue"])])
    with pytest.raises(dt.DesignTableError, match="not a colour"):
        dt.apply(doc, bad)
    with pytest.raises(dt.DesignTableError, match="names no value"):
        dt.apply(doc, dt.Table(["prop.Missing"], [("Default", ["x"])]))
