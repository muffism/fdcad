"""Phase 2 sample parts (PLAN Phase 2): an enclosure with shell and fillets, a lofted
handle and a swept spring. Built in code and fully defined, like ``parts.py``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Line
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.units import UnitSystem
from fdcad.samples.builder import (
    FRONT,
    SketchBuilder,
    add_feature,
    add_sketch,
    face_ref,
    length,
    to_local,
)


def _body(doc: Document) -> NamedShape:
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    return body


def _edges(body: NamedShape, keep: Callable[[Any, Any], bool]) -> list[dict[str, Any]]:
    """References of the straight edges of ``body`` whose two ends ``keep`` accepts."""
    out = []
    explorer = TopExp_Explorer(body.shape, TopAbs_EDGE)
    seen: list[Any] = []
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        if any(edge.IsSame(s) for s in seen):
            continue
        seen.append(edge)
        curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
        if curve.GetType() != GeomAbs_Line:
            continue
        a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
        if keep((a.X(), a.Y(), a.Z()), (b.X(), b.Y(), b.Z())):
            ref = reference_for(body, edge)
            assert ref is not None
            out.append(ref)
    return out


def _add(doc: Document, ftype: str, name: str, refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, ftype, name, params=dict(params), refs=refs))
    return fid


def enclosure() -> Document:
    """An 80 by 60 by 40 mm box with rounded corners, open at the top, 2 mm walls."""
    doc = new_document(UnitSystem.MM)
    base = SketchBuilder()
    base.rectangle(0, 0, 80, 60)
    sk = add_sketch(doc, base, {"feature": FRONT}, "Box Sketch")
    box = add_feature(
        doc, "extrude", "Box", sk, operation="boss", end_condition="blind",
        depth=length("40", 40.0), reverse=False,
    )  # fmt: skip
    corners = _edges(_body(doc), lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-6)
    assert len(corners) == 4
    _add(doc, "fillet", "Corner Fillet", {"edges": corners},
         fillet_type="constant", radius=length("8", 8.0))  # fmt: skip
    bottom = _edges(_body(doc), lambda a, b: abs(a[2]) + abs(b[2]) < 1e-6)
    assert len(bottom) == 4
    _add(doc, "fillet", "Bottom Fillet", {"edges": bottom[:1]},
         fillet_type="constant", radius=length("3", 3.0))  # fmt: skip
    body = _body(doc)
    top = body.face(f"{box}/cap/end")
    assert top is not None
    ref = reference_for(body, top)
    assert ref is not None
    _add(doc, "shell", "Shell", {"faces": [ref]}, thickness=length("2", 2.0))
    return doc


def lofted_handle() -> Document:
    """A 100 mm grip lofted from a 24 by 16 mm rectangle to a 20 mm circle round a core."""
    doc = new_document(UnitSystem.MM)
    core = SketchBuilder()
    core.circle(0, 0, 8)
    csk = add_sketch(doc, core, {"feature": FRONT}, "Core Sketch")
    add_feature(
        doc, "extrude", "Core", csk, operation="boss", end_condition="blind",
        depth=length("100", 100.0), reverse=False,
    )  # fmt: skip
    low = SketchBuilder()
    low.rectangle(-12, -8, 24, 16)
    lsk = add_sketch(doc, low, {"feature": FRONT}, "Grip Base")
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    high = SketchBuilder()
    cx, cy = to_local(plane, (0.0, 0.0, 100.0))
    high.circle(cx, cy, 20)
    hsk = add_sketch(doc, high, top, "Grip End")
    _add(doc, "loft", "Grip", {"profiles": [{"feature": lsk}, {"feature": hsk}]},
         operation="boss")  # fmt: skip
    return doc


def swept_spring() -> Document:
    """A compression spring: a 2 mm wire swept along a 20 mm helix, 6 mm pitch, 5 turns."""
    doc = new_document(UnitSystem.MM)
    guide = SketchBuilder()
    guide.circle(0, 0, 20)
    gsk = add_sketch(doc, guide, {"feature": FRONT}, "Spring Circle")
    hid = _add(doc, "helix", "Spring Path", {"sketch": {"feature": gsk}},
               definition="pitch_turns", pitch=length("6", 6.0), turns=Param("5", 5.0))  # fmt: skip
    _add(doc, "sweep", "Spring Wire", {"path": {"feature": hid}},
         operation="boss", profile_type="circular", diameter=length("2", 2.0))  # fmt: skip
    return doc


def twisted_sweep() -> Document:
    """A 4 by 8 mm bar swept 60 mm straight up with a 90 degree twist (D703).

    The section keeps its area, so the exact volume is 4 * 8 * 60 = 1920 mm3.
    """
    from fdcad.core.sketch.model import Line

    doc = new_document(UnitSystem.MM)
    section = SketchBuilder()
    section.rectangle(-2, -4, 4, 8)
    psk = add_sketch(doc, section, {"feature": FRONT}, "Bar Section")
    path = SketchBuilder()
    lid = path.sk.add_line(0, 0, -60, 0)  # Right plane: sketch X is model -Z, so this runs up
    line = path.sk.entities[lid]
    assert isinstance(line, Line)
    path.sk.relate("horizontal", lid)
    path.sk.dimension("distance", [lid], length("60", 60.0))
    path._place(line.p1, 0.0, 0.0, None, None)
    qsk = add_sketch(doc, path, {"feature": "f4"}, "Bar Path")
    _add(doc, "sweep", "Twisted Bar", {"profile": {"feature": psk}, "path": {"feature": qsk}},
         operation="boss", twist="angle", twist_angle=Param("90", math.pi / 2))  # fmt: skip
    return doc


#: File name to builder.
PHASE2_SAMPLES: dict[str, Callable[[], Document]] = {
    "enclosure": enclosure,
    "lofted_handle": lofted_handle,
    "swept_spring": swept_spring,
    "twisted_sweep": twisted_sweep,
}
