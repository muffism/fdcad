"""The last Phase 3 and Phase 4 sample parts (PLAN Phase 3 and 4, DECISIONS D415).

- ``patterned_flange``: a round flange with a hub, a bore and six bolt holes
  made by a circular pattern of one hole.
- ``multibody_split_part``: a bracket block split by a plane into two bodies.
- ``tapped_housing``: a bearing housing with tapped holes and cosmetic threads.
- ``printable_enclosure``: a shelled box with a lip, mounting bosses, heat set
  insert holes and snap hooks.

Every sketch is fully defined. Standard sizes come from the Hole Tool tables
(compiled from the published standards, CLAUDE.md 7.6).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from OCP.TopoDS import TopoDS_Face

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.hole import defaults_for
from fdcad.core.naming.names import centroid
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.units import UnitSystem
from fdcad.samples.builder import (
    FRONT,
    RIGHT,
    PointsSketch,
    SketchBuilder,
    add_feature,
    add_sketch,
    face_ref,
    length,
    to_local,
)


def _p(value: float) -> Param:
    return length(f"{value:g}", value)


def _deg(degrees: float) -> Param:
    return Param(f"{degrees:g}", math.radians(degrees))


def _add(doc: Document, ftype: str, name: str, refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, ftype, name, params=dict(params), refs=refs))
    return fid


def _named_ref(doc: Document, name: str) -> dict[str, Any]:
    """Reference of the face called ``name`` (or the first one starting with it)."""
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    face = body.face(name) or next((f for n, f in body.faces if n.startswith(name)), None)
    assert face is not None, name
    ref = reference_for(body, face)
    assert ref is not None
    return ref


def _extrude(doc: Document, sketch: str, name: str, depth: float, **params: Any) -> str:
    values: dict[str, Any] = {
        "operation": "boss", "end_condition": "blind", "depth": _p(depth), "reverse": False
    }  # fmt: skip
    values.update(params)
    return add_feature(doc, "extrude", name, sketch, **values)


def _hole_values(values: dict[str, float]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in values.items():
        out[key] = _p(round(value, 6))
    return out


# Phase 3 ------------------------------------------------------------------------------


def patterned_flange() -> Document:
    """A 100 mm flange, 10 mm thick, with a 40 mm hub 25 mm tall, a 20 mm bore and
    six 8 mm bolt holes on a 70 mm circle (one hole and a circular pattern)."""
    doc = new_document(UnitSystem.MM)
    disc = SketchBuilder()
    disc.circle(0, 0, 100)
    plate = _extrude(doc, add_sketch(doc, disc, {"feature": FRONT}, "Flange Sketch"), "Flange", 10)
    hub = SketchBuilder()
    hub.circle(0, 0, 40)
    top = _named_ref(doc, f"{plate}/cap/end")
    hub_id = _extrude(doc, add_sketch(doc, hub, top, "Hub Sketch"), "Hub", 15)
    bore = SketchBuilder()
    bore.circle(0, 0, 20)
    _extrude(
        doc, add_sketch(doc, bore, {"feature": FRONT}, "Bore Sketch"), "Bore", 1,
        operation="cut", end_condition="through_all", reverse=False,
    )  # fmt: skip
    hole = SketchBuilder()
    hole.circle(35, 0, 8)
    bolt = _extrude(
        doc, add_sketch(doc, hole, {"feature": FRONT}, "Bolt Hole Sketch"), "Bolt Hole", 1,
        operation="cut", end_condition="through_all", reverse=False,
    )  # fmt: skip
    axis = _named_ref(doc, f"{hub_id}/side/")
    _add(
        doc, "circular_pattern", "Bolt Circle", {"axis": axis, "features": [{"feature": bolt}]},
        count1=Param("6", 6.0), angle1=_deg(360), equal_spacing=True,
    )  # fmt: skip
    return doc


def multibody_split_part() -> Document:
    """A 120 by 40 by 20 mm block with a 20 mm boss, split by the Right plane into two
    bodies that are both kept."""
    doc = new_document(UnitSystem.MM)
    base = SketchBuilder()
    base.rectangle(-60, 0, 120, 40)
    block = _extrude(doc, add_sketch(doc, base, {"feature": FRONT}, "Block Sketch"), "Block", 20)
    boss = SketchBuilder()
    boss.circle(-30, 20, 20)
    _extrude(doc, add_sketch(doc, boss, _named_ref(doc, f"{block}/cap/end"), "Boss Sketch"),
             "Boss", 10)  # fmt: skip
    _add(doc, "split", "Split at Right Plane", {"tools": [{"feature": RIGHT}]})
    return doc


# Phase 4 ------------------------------------------------------------------------------


def tapped_housing() -> Document:
    """A 80 by 60 by 30 mm housing with a 30 mm bore, four M5 tapped holes on the top
    and two M4 tapped holes on the front, all with cosmetic threads."""
    doc = new_document(UnitSystem.MM)
    base = SketchBuilder()
    base.rectangle(0, 0, 80, 60)
    block = _extrude(doc, add_sketch(doc, base, {"feature": FRONT}, "Housing Sketch"), "Housing",
                     30)  # fmt: skip
    bore = SketchBuilder()
    bore.circle(40, 30, 30)
    _extrude(
        doc, add_sketch(doc, bore, {"feature": FRONT}, "Bore Sketch"), "Bore", 1,
        operation="cut", end_condition="through_all", reverse=False,
    )  # fmt: skip
    top = _named_ref(doc, f"{block}/cap/end")
    top_plane = face_ref(doc, (0.0, 0.0, 1.0))[1]
    corners = [(10.0, 10.0), (70.0, 10.0), (70.0, 50.0), (10.0, 50.0)]
    points = PointsSketch([_local(top_plane, (x, y, 30.0)) for x, y in corners])
    tsk = add_sketch(doc, points, top, "Top Hole Positions")
    m5 = defaults_for("tapped", "iso", "M5")
    _add(
        doc, "hole", "M5 Tapped Hole", {"sketch": {"feature": tsk}, "face": [top]},
        hole_type="tapped", standard="iso", size="M5", end_condition="blind",
        cosmetic_thread=True, **_hole_values(m5),
    )  # fmt: skip
    front, plane = face_ref(doc, (0.0, -1.0, 0.0))
    side = PointsSketch([_local(plane, (x, 0.0, 15.0)) for x in (15.0, 65.0)])
    fsk = add_sketch(doc, side, front, "Front Hole Positions")
    m4 = defaults_for("tapped", "iso", "M4")
    _add(
        doc, "hole", "M4 Tapped Hole", {"sketch": {"feature": fsk}, "face": [front]},
        hole_type="tapped", standard="iso", size="M4", end_condition="blind",
        cosmetic_thread=True, **_hole_values(m4),
    )  # fmt: skip
    return doc


#: Inside corners of the enclosure's bosses, in mm (the box is 100 by 70 by 40).
_BOSSES = ((12.0, 12.0), (88.0, 12.0), (88.0, 58.0), (12.0, 58.0))


def printable_enclosure() -> Document:
    """A 100 by 70 by 40 mm box, 2 mm walls, open at the top with a lip on the rim; four
    mounting bosses on the floor with M3 heat set insert holes, and two snap hooks."""
    doc = new_document(UnitSystem.MM)
    base = SketchBuilder()
    base.rectangle(0, 0, 100, 70)
    box = _extrude(doc, add_sketch(doc, base, {"feature": FRONT}, "Box Sketch"), "Box", 40)
    rim = _named_ref(doc, f"{box}/cap/end")
    _add(doc, "shell", "Shell", {"faces": [rim]}, thickness=_p(2))
    rim = _named_ref(doc, f"{box}/cap/end")
    _add(doc, "lip_groove", "Lip", {"lip_faces": [rim]}, lip_width=_p(1), lip_height=_p(2))
    floor, _plane = face_ref(doc, (0.0, 0.0, 1.0), lambda f: abs(centroid(f)[2] - 2.0) < 1e-6)
    for i, (x, y) in enumerate(_BOSSES):
        _add(
                doc, "mounting_boss", f"Boss {i + 1}", {"face": [floor]},
                boss_type="screw_thread", boss_diameter=_p(9), boss_height=_p(10),
                hole_diameter=_p(2.5), hole_depth=_p(8), fin_count=Param("0", 0.0),
                pos_x=_p(x), pos_y=_p(y), pos_z=_p(2),
        )  # fmt: skip
    tops, plane = face_ref(doc, (0.0, 0.0, 1.0), lambda f: _near(f, _BOSSES[0], 12.0))
    points = PointsSketch([_local(plane, (x, y, 12.0)) for x, y in _BOSSES])
    psk = add_sketch(doc, points, tops, "Insert Positions")
    insert = defaults_for("heat_set_insert", "iso", "M3")
    _add(
        doc, "hole", "M3 Insert", {"sketch": {"feature": psk}},
        hole_type="heat_set_insert", standard="iso", size="M3", end_condition="blind",
        **_hole_values(insert),
    )  # fmt: skip
    for i, x in enumerate((35.0, 65.0)):
        _add(
            doc, "snap_hook", f"Snap Hook {i + 1}", {"face": [floor]},
            body_height=_p(20), base_depth=_p(3), top_depth=_p(2), total_width=_p(8),
            overhang=_p(1.5), hook_height=_p(3), lip_height=_p(1), top_draft=_deg(30),
            pos_x=_p(x), pos_y=_p(35), pos_z=_p(2),
        )  # fmt: skip
    return doc


def _local(plane: Any, p: tuple[float, float, float]) -> tuple[float, float]:
    """Sketch coordinates of model point ``p``, rounded so the file stays tidy."""
    x, y = to_local(plane, p)
    return round(x, 9) + 0.0, round(y, 9) + 0.0


def _near(face: TopoDS_Face, xy: tuple[float, float], z: float) -> bool:
    c = centroid(face)
    return abs(c[0] - xy[0]) < 1e-6 and abs(c[1] - xy[1]) < 1e-6 and abs(c[2] - z) < 1e-6


PHASE34_SAMPLES: dict[str, Callable[[], Document]] = {
    "patterned_flange": patterned_flange,
    "multibody_split_part": multibody_split_part,
    "tapped_housing": tapped_housing,
    "printable_enclosure": printable_enclosure,
}
