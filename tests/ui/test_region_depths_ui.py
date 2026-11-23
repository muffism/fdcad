"""Own depth per region in the Selected Regions box (TR242, D842)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.ui.property_panel.groups import Group
from fdcad.ui.property_panel.region_group import RegionControls


def test_depths_are_kept_in_each_pick(qtbot: QtBot) -> None:
    picks = [{"kind": "region", "name": "region(a)"}, {"kind": "region", "name": "region(b)"}]
    feature = Feature("f6", "extrude", "Extrude 1", refs={"regions": picks})
    group = Group("Regions", "tip")
    qtbot.addWidget(group)
    box = RegionControls(group, feature)
    assert not box.own_depths.isChecked() and box.depths.isHidden()
    box.own_depths.setChecked(True)
    assert box.depths.rowCount() == 2
    cell = box.depths.item(1, 1)
    assert cell is not None
    cell.setText("7mm")
    out = Feature("f6", "extrude", "Extrude 1")
    assert box.apply(out) is None
    assert "depth" not in out.refs["regions"][0]
    assert out.refs["regions"][1]["depth"] == {"expr": "7mm", "value": 7.0}
    cell.setText("seven")
    assert "Region 2" in (box.apply(out) or "")
    again = RegionControls(
        Group("Regions", "tip"),
        Feature(
            "f6",
            "extrude",
            "E",
            refs={"regions": [*picks[:1], {**picks[1], "depth": {"expr": "7mm", "value": 7.0}}]},
        ),
    )
    assert again.own_depths.isChecked()
