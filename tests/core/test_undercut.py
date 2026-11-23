"""Undercut analysis (TR83, D864)."""

from __future__ import annotations

from collections import Counter

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.undercut import undercut_faces


def test_box_has_tops_bottoms_and_sides() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    groups = Counter(f.group for f in undercut_faces(box, (0, 0, 1)))
    assert groups == {"above": 1, "below": 1, "side": 4}


def test_a_side_pocket_is_an_undercut() -> None:
    block = BRepPrimAPI_MakeBox(20.0, 20.0, 20.0).Shape()
    # A pocket cut in from the side, under the top: its ceiling and floor are hidden.
    pocket = BRepPrimAPI_MakeBox(gp_Pnt(-1, 5, 8), 8.0, 10.0, 4.0).Shape()
    part = BRepAlgoAPI_Cut(block, pocket).Shape()
    groups = Counter(f.group for f in undercut_faces(part, (0, 0, 1)))
    assert groups["undercut"] >= 2  # the pocket's ceiling and floor
    assert groups["above"] == 1 and groups["below"] == 1
