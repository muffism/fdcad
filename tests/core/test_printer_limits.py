"""No print zones and head clearance (TR413, D992)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.TopoDS import TopoDS_Compound

from fdcad.core.printing.orientation import check_fit
from fdcad.core.printing.profiles import GENERIC, PrinterProfile, parse_zones, zones_text


def test_zones_round_trip_and_bad_text() -> None:
    zones = parse_zones("0 0 20 20; 200, 0, 220, 20")
    assert zones == ((0.0, 0.0, 20.0, 20.0), (200.0, 0.0, 220.0, 20.0))
    assert parse_zones(zones_text(zones)) == zones
    stored = replace(GENERIC, no_zones=zones, head_clearance=30.0).to_dict()
    again = PrinterProfile.from_dict({**stored, "no_zones": [list(z) for z in zones]})
    assert again.no_zones == zones and again.head_clearance == 30.0
    with pytest.raises(ValueError, match="four numbers"):
        parse_zones("1 2 3")


def test_zone_under_the_part_and_tall_bodies() -> None:
    box = BRepPrimAPI_MakeBox(20.0, 20.0, 10.0).Shape()
    middle = replace(GENERIC, no_zones=((100.0, 100.0, 120.0, 120.0),))
    assert check_fit(box, None, middle).in_zones == 1
    corner = replace(GENERIC, no_zones=((0.0, 0.0, 10.0, 10.0),))
    assert check_fit(box, None, corner).in_zones == 0
    builder, pair = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(pair)
    builder.Add(pair, BRepPrimAPI_MakeBox(10.0, 10.0, 50.0).Shape())
    builder.Add(pair, BRepPrimAPI_MakeBox(gp_Pnt(30, 0, 0), 10.0, 10.0, 60.0).Shape())
    low = replace(GENERIC, head_clearance=40.0)
    assert check_fit(pair, None, low).too_tall == 2
    assert check_fit(pair, None, replace(GENERIC, head_clearance=55.0)).too_tall == 0
