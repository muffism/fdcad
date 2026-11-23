"""Slice a body into section sketches (TUTORIAL_REVIEW_SPEC_2 TR151 item 1, D1718).

Several parallel planes, a set distance apart from a base plane, cut the part; or
planes round an axis lying in the base plane, a set angle apart (D2204). Each cut
becomes an offset (or angle) reference plane and a sketch on it holding the cut's
curves as fixed copies (as Intersection Curves does, D759), all in one tree
folder, for laser cut stacks. ``sections`` is kernel work: run it off the UI
thread. ``slice_features`` only builds features.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.sketch.curve_convert import ProjectedCurve, add_curve
from fdcad.core.sketch.model import Sketch, sketch_to_data
from fdcad.core.sketch.profiles import SketchPlane

#: Most slices one command makes.
MAX_SLICES = 200


class SliceError(ValueError):
    """The slices cannot be made; the message says what to do."""


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class SlicePlan:
    """``count`` planes from ``start`` mm off the base plane, ``spacing`` mm apart.

    With ``axis`` (a reference axis feature id, TR151, D2204) the planes turn round
    that axis instead: ``start`` and ``spacing`` are then angles in radians from the
    base plane, which must hold the axis.
    """

    base: str
    count: int
    spacing: float
    start: float = 0.0
    axis: str = ""

    def distances(self) -> list[float]:
        """Each slice's distance from the base plane along its normal, or its angle from
        the base plane round the axis."""
        if not 1 <= self.count <= MAX_SLICES:
            raise SliceError(f"Make 1 to {MAX_SLICES} slices. Enter a count in that range.")
        if self.count > 1 and self.spacing <= 1e-9:
            raise SliceError("Type a spacing larger than zero.")
        return [self.start + i * self.spacing for i in range(self.count)]


def axis_plane(base: SketchPlane, point: Vec3, direction: Vec3, angle: float) -> SketchPlane:
    """The plane through the axis (``point``, unit ``direction``) at ``angle`` radians from
    ``base``, as an angle reference plane makes it (D2204). Raises SliceError when the
    axis does not lie in or parallel to the base plane."""
    from fdcad.core.features.datum import plane_at, rotate, unit

    d = unit(direction)
    n = base.normal
    if d is None or abs(n[0] * d[0] + n[1] * d[1] + n[2] * d[2]) > 1e-6:
        raise SliceError(
            "The axis must lie in or parallel to the base plane. Pick another axis or plane."
        )
    return plane_at(point, rotate(n, d, angle), d)


def slice_planes(
    base: SketchPlane, plan: SlicePlan, axis: tuple[Vec3, Vec3] | None = None
) -> list[SketchPlane]:
    """Every slice plane of ``plan``; ``axis`` (point, direction) for slices round it."""
    if plan.axis:
        if axis is None:
            raise SliceError("The axis is not built. Pick another axis.")
        return [axis_plane(base, axis[0], axis[1], a) for a in plan.distances()]
    return [offset_plane(base, d) for d in plan.distances()]


def offset_plane(base: SketchPlane, d: float) -> SketchPlane:
    """``base`` moved ``d`` mm along its normal, with the same axes."""
    o, n = base.origin, base.normal
    return SketchPlane((o[0] + n[0] * d, o[1] + n[1] * d, o[2] + n[2] * d), n, base.x_dir)


def sections(
    shape: Any, base: SketchPlane, plan: SlicePlan, axis: tuple[Vec3, Vec3] | None = None
) -> list[ProjectedCurve]:
    """The part's cut curves on each slice plane, in plan order. Kernel work."""
    from fdcad.core.sketch.model_curves import intersection_curves

    return [intersection_curves(shape, plane) for plane in slice_planes(base, plan, axis)]


def _unique(doc: Document, stem: str, taken: set[str]) -> str:
    n = 1
    while f"{stem} {n}" in taken:
        n += 1
    name = f"{stem} {n}"
    taken.add(name)
    return name


def slice_features(doc: Document, plan: SlicePlan, cuts: list[ProjectedCurve]) -> list[Feature]:
    """An offset plane and a sketch of its cut for each slice that meets the part.
    Feature ids come from ``doc``; nothing is added to it."""
    distances = plan.distances()
    taken = {f.name for f in doc.features}
    out: list[Feature] = []
    for d, cut in zip(distances, cuts, strict=True):
        if not cut.pieces:
            continue
        pid = doc.new_feature_id()
        if plan.axis:  # TR151 (D2204): an angle plane through the axis
            degrees = math.degrees(abs(d))
            plane = Feature(
                pid,
                "ref_plane",
                _unique(doc, "Slice Plane", taken),
                params={"method": "angle", "angle": Param(f"{degrees:.6g}deg", abs(d))},
                refs={"first": {"feature": plan.base}, "second": {"feature": plan.axis}},
            )
        else:
            plane = Feature(
                pid,
                "ref_plane",
                _unique(doc, "Slice Plane", taken),
                params={"method": "offset", "distance": Param(f"{abs(d):.6g}mm", abs(d))},
                refs={"first": {"feature": plan.base}},
            )
        if d < 0:
            plane.params["flip"] = True
        sketch = Sketch()
        origin = sketch.add_point(0.0, 0.0, construction=True)
        sketch.relate("fixed", origin)
        add_curve(sketch, cut)
        out.append(plane)
        out.append(
            Feature(
                doc.new_feature_id(),
                "sketch",
                _unique(doc, "Slice", taken),
                refs={"plane": {"feature": pid}},
                data=sketch_to_data(sketch),
            )
        )
    if not out:
        raise SliceError(
            "None of the slice planes meets the part. Change the start or the spacing."
        )
    return out
