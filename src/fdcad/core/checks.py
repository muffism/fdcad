"""Expected value checks (TUTORIAL_REVIEW_SPEC_2 TR359, DECISIONS D889).

A part can keep target results with a tolerance in ``Document.extra["checks"]``: a
list of ``{"kind", "value", "tolerance"}`` (and ``"feature"`` and ``"key"`` for a
saved measurement). After each rebuild the worker runs :func:`evaluate` and the
status bar and the Expected Values list show which pass.

Kinds: ``volume`` (mm3), ``size_x``, ``size_y``, ``size_z`` (bounding box, mm),
``faces`` and ``holes`` (counts), and ``measurement`` (a value a Measurement
feature found, TR191). Only volume and sizes are read from the part, so this
needs no change to the file's geometry rules. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KINDS = ("volume", "size_x", "size_y", "size_z", "faces", "holes", "measurement")
KEY = "checks"


@dataclass(frozen=True)
class CheckResult:
    """One check after a rebuild. ``actual`` is None when it could not be found."""

    index: int
    kind: str
    expected: float
    tolerance: float
    actual: float | None

    @property
    def passed(self) -> bool:
        """True when the actual value is within the tolerance of the expected one."""
        return self.actual is not None and abs(self.actual - self.expected) <= self.tolerance + 1e-9


def stored(doc: Any) -> list[dict[str, Any]]:
    """The part's checks, skipping entries that are not usable."""
    raw = doc.extra.get(KEY)
    if not isinstance(raw, list):
        return []
    out = []
    for entry in raw:
        if (
            isinstance(entry, dict)
            and entry.get("kind") in KINDS
            and isinstance(entry.get("value"), (int, float))
        ):
            out.append(entry)
    return out


def _holes(shape: Any) -> int:
    """Round holes: cylinder faces whose surface faces their own axis, one per axis."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_REVERSED

    from fdcad.core.naming.names import faces_of

    axes: list[tuple[float, ...]] = []
    for face in faces_of(shape):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
        props = BRepLProp_SLProps(surface, (u0 + u1) / 2, (v0 + v1) / 2, 1, 1e-7)
        n = props.Normal()
        if face.Orientation() == TopAbs_REVERSED:
            n.Reverse()
        axis = surface.Cylinder().Axis()
        p, a, d = props.Value(), axis.Location(), axis.Direction()
        w = (p.X() - a.X(), p.Y() - a.Y(), p.Z() - a.Z())
        along = w[0] * d.X() + w[1] * d.Y() + w[2] * d.Z()
        radial = (w[0] - along * d.X(), w[1] - along * d.Y(), w[2] - along * d.Z())
        if radial[0] * n.X() + radial[1] * n.Y() + radial[2] * n.Z() >= 0:
            continue  # the outside of a shaft or boss
        key = (round(a.X(), 4), round(a.Y(), 4), round(a.Z(), 4), round(abs(d.Z()), 4))
        if key not in axes:
            axes.append(key)
    return len(axes)


def actual_value(kind: str, entry: dict[str, Any], doc: Any, shape: Any) -> float | None:
    """The part's current value for one check."""
    if kind == "measurement":
        found = doc.measured.get(str(entry.get("feature", "")), {})
        value = found.get(str(entry.get("key", "")))
        return float(value) if isinstance(value, (int, float)) else None
    if shape is None:
        return None
    from fdcad.core.features.solids import volume_of
    from fdcad.core.naming.names import faces_of

    if kind == "volume":
        return volume_of(shape)
    if kind == "faces":
        return float(len(faces_of(shape)))
    if kind == "holes":
        return float(_holes(shape))
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    sizes: dict[str, float] = {
        "size_x": hi.X() - lo.X(),
        "size_y": hi.Y() - lo.Y(),
        "size_z": hi.Z() - lo.Z(),
    }
    return sizes[kind]


def evaluate(doc: Any, shape: Any) -> list[CheckResult]:
    """Every stored check against the rebuilt part ``shape`` (None when empty)."""
    out = []
    for i, entry in enumerate(stored(doc)):
        kind = str(entry["kind"])
        tolerance = entry.get("tolerance", 0.0)
        tol = float(tolerance) if isinstance(tolerance, (int, float)) else 0.0
        try:
            actual = actual_value(kind, entry, doc, shape)
        except Exception:  # a check never breaks a rebuild (CLAUDE.md 5.7)
            actual = None
        out.append(CheckResult(i, kind, float(entry["value"]), abs(tol), actual))
    return out
