"""Selection breadcrumbs (TR20, DECISIONS D756).

For a picked face, edge or vertex, the chain shown at the top left of the view:
the part, its body (when the part has more than one), the feature that made it
and that feature's sketch. A face is made by the feature its name starts with
(``f6/cap/end`` comes from ``f6``); an edge or vertex by the feature of the first
named face it touches. Small topology queries only (DECISIONS D75), so the UI
thread may call them.
"""

from __future__ import annotations

from dataclasses import dataclass

from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.body_visibility import body_of
from fdcad.core.document.model import Document
from fdcad.core.features.solids import solids
from fdcad.core.naming.names import NamedShape, faces_of


@dataclass(frozen=True)
class Crumb:
    """One step of the chain. ``target`` is a feature id, a body index or None (part)."""

    kind: str  # "part", "body", "feature" or "sketch"
    label: str
    target: str | int | None = None


def _feature_of_name(name: str | None) -> str | None:
    if not name:
        return None
    head = name.split("/", 1)[0]
    return head or None


def making_feature(body: NamedShape, sub: TopoDS_Shape) -> str | None:
    """The id of the feature that made the picked face, edge or vertex, or None."""
    if sub.ShapeType() == TopAbs_FACE:
        return _feature_of_name(body.primary_name(TopoDS.Face(sub)))
    for face in faces_of(body.shape):
        explorer = TopExp_Explorer(face, sub.ShapeType())
        while explorer.More():
            if explorer.Current().IsSame(sub):
                found = _feature_of_name(body.primary_name(face))
                if found is not None:
                    return found
                break
            explorer.Next()
    return None


def crumbs(doc: Document, part_name: str, body: NamedShape, sub: TopoDS_Shape) -> list[Crumb]:
    """The chain for a picked sub shape, part first."""
    out = [Crumb("part", part_name)]
    if len(solids(body.shape)) > 1:
        index = body_of(body.shape, sub)
        if index >= 0:
            out.append(Crumb("body", f"Body {index + 1}", index))
    fid = making_feature(body, sub)
    feature = next((f for f in doc.features if f.id == fid), None)
    if feature is None:
        return out
    out.append(Crumb("feature", feature.name, feature.id))
    ref = feature.refs.get("sketch")
    sid = ref.get("feature") if isinstance(ref, dict) else None
    sketch = next((f for f in doc.features if f.id == sid), None)
    if sketch is not None:
        out.append(Crumb("sketch", sketch.name, sketch.id))
    return out
