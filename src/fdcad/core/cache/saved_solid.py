"""The finished solid saved inside the part file (FDEF_SPEC 13A, D1102).

The local solid cache (FDEF_SPEC 13) shows a part at once only on a computer that has
built it before; the first open anywhere else built every feature first (about 40 s for
a bike frame of 103 features). Save now writes the finished solid into the part file:
the body in OpenCascade's binary BRep format without display meshes, gzip compressed
and base64 encoded, with its face names, each feature's state and messages, and the
cache key of the document it was built from.

On open the solid is used only while that key matches the document, so a file whose
features were changed by another program, or by an older FDCAD that kept the key as an
unknown key (FDEF_SPEC 14 item 4), is built from its tree as before. The rebuild still
runs behind the shown solid, as with the local cache. Kernel work: off the UI thread.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import io
from typing import TYPE_CHECKING, Any

from OCP.BinTools import BinTools, BinTools_FormatVersion
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.naming.names import NamedShape, faces_of

if TYPE_CHECKING:
    from fdcad.core.cache.disk import CachedPart
    from fdcad.core.document.model import Document
    from fdcad.core.features.base import FeatureResult

FORMAT = 1


def encode(key: str, body: NamedShape | None, results: dict[str, FeatureResult]) -> dict[str, Any]:
    """The ``solid`` entry of a part file for a finished rebuild; empty with no body."""
    from fdcad.core.occ import ShapeMap

    if body is None:
        return {}
    stream = io.BytesIO()
    BinTools.Write_s(
        body.shape, stream, False, False, BinTools_FormatVersion.BinTools_FormatVersion_CURRENT
    )
    packed = base64.b64encode(gzip.compress(stream.getvalue(), compresslevel=6))
    index = ShapeMap()
    for face in faces_of(body.shape):
        index.Add(face)
    names = []
    for name, face in body.faces:
        k = index.FindIndex(face)
        if k:
            names.append([name, k - 1])
    states = {
        fid: {
            "state": r.state.value,
            "messages": [i.message for i in r.issues],
            "seconds": round(r.seconds, 3),  # D1106: how long a rebuild would take
        }
        for fid, r in results.items()
    }
    return {
        "format": FORMAT,
        "key": key,
        "brep": packed.decode("ascii"),
        "names": names,
        "states": states,
    }


def build_seconds(states: Any) -> float:
    """The seconds a rebuild took, added up from saved feature states (D1106); 0 when
    they hold no times, as in files and caches written before times were kept."""
    total = 0.0
    if not isinstance(states, dict):
        return total
    for state in states.values():
        with contextlib.suppress(TypeError, ValueError, AttributeError):
            total += max(0.0, float(state.get("seconds", 0.0)))
    return total


def decode(doc: Document, key: str) -> CachedPart | None:
    """The part saved in ``doc.solid``, or None when there is none, it is damaged, or it
    was built from another state of the document (its key is not ``key``)."""
    from fdcad.core.cache.disk import CachedPart

    saved = doc.solid
    if not saved or saved.get("format") != FORMAT or saved.get("key") != key:
        return None
    try:
        raw = gzip.decompress(base64.b64decode(str(saved["brep"]), validate=True))
        shape = TopoDS_Shape()
        BinTools.Read_s(shape, io.BytesIO(raw))
        if shape.IsNull():
            return None
        faces = faces_of(shape)
        body = NamedShape(shape, [(str(n), faces[int(i)]) for n, i in saved["names"]])
        states = saved.get("states", {})
        return CachedPart(body, dict(states) if isinstance(states, dict) else {})
    except Exception:  # the kernel raises its own types on damaged data
        return None
