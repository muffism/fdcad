"""Where a feature's value labels sit in the view (TOOL_SPEC T15.2, DECISIONS D440).

Features with drag handles put their value on the handle. The others put
their values at the first item the user picked: the middle of the first edge,
the centre of the first face. With nothing picked that the part can name
(a sketch, a hole position), the labels go to the middle of the feature's own
preview solid, and with no preview solid to the middle of the part.

Kernel work: runs on the preview worker, never on the UI thread.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBndLib import BRepBndLib
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Edge, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.naming.names import NamedShape, centroid

Vec3 = tuple[float, float, float]

#: Reference keys looked at first, in this order (draft: the neutral face, T15.2).
FIRST_KEYS = ("neutral",)


def _refs(feature: Feature) -> Iterator[dict[str, Any]]:
    """Every picked reference of ``feature`` with a name, preferred keys first."""
    keys = [k for k in FIRST_KEYS if k in feature.refs]
    keys += [k for k in feature.refs if k not in keys]
    for key in keys:
        value = feature.refs[key]
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                yield item


def edge_middle(edge: TopoDS_Edge) -> Vec3:
    """The point halfway along ``edge``."""
    curve = BRepAdaptor_Curve(edge)
    p = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
    return p.X(), p.Y(), p.Z()


def box_centre(shape: TopoDS_Shape) -> Vec3 | None:
    """The middle of ``shape``'s bounding box, or None for an empty shape."""
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        return None
    a, b = box.CornerMin(), box.CornerMax()
    return (a.X() + b.X()) / 2, (a.Y() + b.Y()) / 2, (a.Z() + b.Z()) / 2


def named_edge(body: NamedShape, name: str) -> TopoDS_Edge | None:
    """The edge ``edge(<face>|<face>)``: the edge the two named faces share.

    Cheaper than naming every edge of the part. A seam edge names one face twice.
    """
    inner = name[len("edge(") : -1] if name.startswith("edge(") and name.endswith(")") else ""
    parts = inner.split("|")
    if len(parts) != 2:
        return None
    a, b = body.face(parts[0]), body.face(parts[1])
    if a is None or b is None:
        return None
    from fdcad.core.features.modify import edges_of

    seam = parts[0] == parts[1]
    others = edges_of(b)
    for edge in edges_of(a):
        if seam and BRep_Tool.IsClosed_s(edge, a):
            return edge
        if not seam and any(edge.IsSame(other) for other in others):
            return edge
    return None


def _first_solid(shape: TopoDS_Shape) -> TopoDS_Shape:
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    return explorer.Current() if explorer.More() else shape


def pick_anchor(
    feature: Feature, body: NamedShape | None, tool: TopoDS_Shape | None
) -> Vec3 | None:
    """Where the value labels of ``feature`` go. Never raises; None when nothing fits."""
    try:
        if body is not None:
            for ref in _refs(feature):
                name = ref["name"]
                if name.startswith("edge("):
                    edge = named_edge(body, name)
                    if edge is not None:
                        return edge_middle(edge)
                    continue
                face = body.face(name)
                if face is not None:
                    return centroid(face)
        if tool is not None and not tool.IsNull():
            found = box_centre(_first_solid(tool))
            if found is not None:
                return found
        if body is not None:
            return box_centre(body.shape)
    except Exception:  # a label place must never break the preview
        return None
    return None
