"""The features that made one body of a multibody part (TR153 item 2, D972).

A face's lasting name starts with the feature that made it and, for copies, holds
the features it came through ("f9/instance2.1/f5/cap/end"). The body's history is
every feature named by one of its faces, with the sketches those features use, in
tree order. Kernel work: run it off the UI thread. No Qt.
"""

from __future__ import annotations

from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp

from fdcad.core.document.dependencies import parents_of
from fdcad.core.document.model import Document
from fdcad.core.features.solids import solids
from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import ShapeMap


def body_history(doc: Document, named: NamedShape, index: int) -> list[str]:
    """Ids of the features that made body ``index`` (Solid Bodies order), in tree
    order. An index past the bodies gives none."""
    bodies = solids(named.shape) or [named.shape]
    if not 0 <= index < len(bodies):
        return []
    faces = ShapeMap()
    TopExp.MapShapes_s(bodies[index], TopAbs_FACE, faces)
    known = {f.id for f in doc.features}
    found: set[str] = set()
    for name, face in named.faces:
        if faces.Contains(face):
            found.update(part for part in str(name).split("/") if part in known)
    for fid in list(found):  # the sketches they are drawn from
        found.update(p.id for p in parents_of(doc, fid) if p.type == "sketch")
    return [f.id for f in doc.features if f.id in found]
