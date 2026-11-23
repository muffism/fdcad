"""What the changed feature did, in numbers (TUTORIAL_REVIEW_SPEC_2 TR290, DECISIONS D878).

After a rebuild that reused earlier results, the first feature that was built
again is the one the user just added or edited. Its body is compared with the
body before it: the net volume added or removed and the change in face count. The
rebuild worker calls :func:`describe` (kernel work stays off the UI thread); the
status bar shows the result. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fdcad.core.document.model import Document
    from fdcad.core.rebuild.engine import RebuildReport


@dataclass(frozen=True)
class Change:
    """The changed feature's name and what it did. Volumes in mm3."""

    name: str
    added: float
    removed: float
    faces: int
    #: The feature failed: the part after it is the part before it (D1041).
    failed: bool = False


def describe(doc: Document, report: RebuildReport) -> Change | None:
    """The change made by the first rebuilt solid feature, or None when the whole part
    was built (opening a file) or nothing solid changed."""
    from fdcad.core.features.base import FeatureState
    from fdcad.core.features.solids import volume_of
    from fdcad.core.naming.names import faces_of

    if not report.reused or not report.rebuilt or report.cancelled:
        return None
    order = [f.id for f in doc.features]
    fid = next(
        (
            i
            for i in sorted(report.rebuilt, key=lambda i: order.index(i) if i in order else 1 << 30)
            if i in report.results and report.results[i].body is not None and _solid(doc, i)
        ),
        None,
    )
    if fid is None or fid not in order:
        return None
    after = report.results[fid].body
    if report.results[fid].state is FeatureState.ERROR:
        return Change(doc.feature(fid).name, 0.0, 0.0, 0, failed=True)
    before = None
    for earlier in reversed(order[: order.index(fid)]):
        result = report.results.get(earlier)
        if result is not None and result.body is not None:
            before = result.body
            break
    assert after is not None
    if before is None:
        return Change(
            doc.feature(fid).name, volume_of(after.shape), 0.0, len(faces_of(after.shape))
        )
    if before.shape.IsSame(after.shape):
        return Change(doc.feature(fid).name, 0.0, 0.0, 0)
    # The net change: two volumes are cheap, where booleans would slow every rebuild.
    net = volume_of(after.shape) - volume_of(before.shape)
    added, removed = max(net, 0.0), max(-net, 0.0)
    faces = len(faces_of(after.shape)) - len(faces_of(before.shape))
    return Change(doc.feature(fid).name, added, removed, faces)


def _solid(doc: Document, fid: str) -> bool:
    """True for a feature that makes or changes the solid (not a sketch or plane)."""
    from fdcad.core.features import REGISTRY

    try:
        ftype = REGISTRY.get(doc.feature(fid).type)
    except KeyError:
        return False
    return ftype is not None and bool(getattr(ftype, "makes_solid", False))
