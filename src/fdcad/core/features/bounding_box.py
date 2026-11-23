"""Bounding Box (TUTORIAL_REVIEW_SPEC_2 TR69, DECISIONS D809).

Type ``bounding_box``. The smallest box (or cylinder) around the part, for stock
sizes and quotes.

Params:

- ``box_shape``: ``box`` (default) or ``cylinder`` (its axis is the frame's Z).
- ``orient``: ``axes`` (default: square to the part's X, Y and Z, so the box
  never turns), ``best_fit`` (the box turned to fit the part closely; a
  cylinder's axis is along the part's longest extent), or ``frame`` (the
  plane, face or coordinate system in ``refs.frame``).
- ``make_solid``: optional boolean. Off: the box is drawn as a thin outline and
  the part is unchanged. On: the box is added as a separate body.

Measured values (formulas read them as ``"length@Bounding Box 1"``, D793):
``length``, ``width`` and ``height`` (the sizes along the frame's X, Y and Z; a
cylinder's diameter twice), and ``volume`` (mm3).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from OCP.Bnd import Bnd_Box, Bnd_OBB
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.naming.names import NamedShape, restrict

SHAPES = ("box", "cylinder")
ORIENTS = ("axes", "best_fit", "frame")


def _frame(feature: Feature, ctx: BuildContext, shape: Any) -> gp_Ax3:
    """The box's frame: the part's axes, a best fit, or the picked frame."""
    orient = str(feature.params.get("orient", "axes"))
    if orient == "best_fit":
        obb = Bnd_OBB()
        BRepBndLib.AddOBB_s(shape, obb, True, True, False)
        axes = [
            (obb.XHSize(), obb.XDirection()),
            (obb.YHSize(), obb.YDirection()),
            (obb.ZHSize(), obb.ZDirection()),
        ]
        if feature.params.get("box_shape") == "cylinder":
            axes.sort(key=lambda a: a[0])  # Z along the longest size
        z, x = axes[-1][1], axes[0][1]
        c = obb.Center()
        return gp_Ax3(gp_Pnt(c.X(), c.Y(), c.Z()), gp_Dir(z), gp_Dir(x))
    if orient == "frame":
        return frame_from_ref(ctx, feature.refs.get("frame"), feature.name)
    return gp_Ax3()


def frame_from_ref(ctx: BuildContext, ref: Any, owner: str) -> gp_Ax3:
    """A frame from a pick: a coordinate system or plane feature by its datum (with its X
    direction), else a plane or flat face through its point and normal."""
    if not isinstance(ref, dict):
        raise FeatureError(f"{owner}: pick a plane, a flat face or a coordinate system.")
    fid = ref.get("feature")
    if isinstance(fid, str) and "kind" not in ref:
        datum = ctx.result(fid).datum
        if datum is not None and datum.direction is not None:
            x = datum.x_dir
            if x is not None:
                return gp_Ax3(gp_Pnt(*datum.origin), gp_Dir(*datum.direction), gp_Dir(*x))
            return gp_Ax3(gp_Pnt(*datum.origin), gp_Dir(*datum.direction))
    from fdcad.core.features.geometry_refs import resolve_placement

    place = resolve_placement(ctx, ref, owner, "plane")
    origin = place.point
    if ref.get("kind") == "face" and ctx.body is not None:  # a face: its middle (D813)
        from fdcad.core.naming.names import centroid
        from fdcad.core.naming.resolve import resolve_face

        face, _found = resolve_face(ctx.body, ref, owner)
        origin = centroid(face)
    return gp_Ax3(gp_Pnt(*origin), gp_Dir(*place.direction))


def _points(shape: Any) -> np.ndarray:
    """Mesh points of ``shape`` (whole arrays, PLAN 5A item 2)."""
    from fdcad.core.io.export import MeshSettings, triangles

    tris = triangles(shape, MeshSettings(0.01, 0.3))
    return np.asarray(tris, dtype=float).reshape(-1, 3)


@register
class BoundingBox(FeatureType):
    """A box or cylinder around the part, reporting its sizes."""

    type_name = "bounding_box"
    params = (
        ParamSpec("box_shape", choices=SHAPES, default="box", optional=True),
        ParamSpec("orient", choices=ORIENTS, default="axes", optional=True),
        ParamSpec("make_solid", default=False, optional=True),
    )

    def reads_body(self, feature: Feature) -> bool:
        """It measures the part as built so far."""
        return True

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Measure the part and draw (or add) the box."""
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        frame = _frame(feature, ctx, ctx.body.shape)
        to_frame = gp_Trsf()
        to_frame.SetTransformation(frame)  # world to frame coordinates
        local = BRepBuilderAPI_Transform(ctx.body.shape, to_frame, True).Shape()
        cylinder = feature.params.get("box_shape") == "cylinder"
        if cylinder:
            pts = _points(local)
            if not len(pts):
                raise FeatureError(f"{name}: the part has no faces to measure. Add a body first.")
            lo, hi = pts.min(axis=0), pts.max(axis=0)
            cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
            radius = float(np.max(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)))
            height = float(hi[2] - lo[2])
            made = BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(cx, cy, float(lo[2])), gp_Dir(0, 0, 1)), radius, height
            ).Shape()
            sizes = (2 * radius, 2 * radius, height)
            volume = math.pi * radius * radius * height
        else:
            box = Bnd_Box()
            BRepBndLib.AddOptimal_s(local, box, False, False)
            a, b = box.CornerMin(), box.CornerMax()
            sizes = (b.X() - a.X(), b.Y() - a.Y(), b.Z() - a.Z())
            made = BRepPrimAPI_MakeBox(gp_Pnt(a.X(), a.Y(), a.Z()), *sizes).Shape()
            volume = sizes[0] * sizes[1] * sizes[2]
        back = BRepBuilderAPI_Transform(made, to_frame.Inverted(), True).Shape()
        extras: dict[str, Any] = {
            "length": sizes[0],
            "width": sizes[1],
            "height": sizes[2],
            "volume": volume,
            "report": [
                f"Length {sizes[0]:.4g} mm, width {sizes[1]:.4g} mm, height {sizes[2]:.4g} mm",
                f"Volume {volume:.6g} mm3",
            ],
        }
        if feature.params.get("make_solid") is True:
            from fdcad.core.features.solids import compound, solids

            shape = compound([*solids(ctx.body.shape), back])
            faces = [*ctx.body.faces, *restrict([], back, f"{feature.id}/box")]
            return FeatureResult(body=NamedShape(shape, restrict(faces, shape, feature.id)),
                                 extras=extras)  # fmt: skip
        extras["reference"] = _outline(back)
        return FeatureResult(body=ctx.body, extras=extras)


def _outline(shape: Any) -> Any:
    """The edges of ``shape``, drawn as a thin outline."""
    from fdcad.core.features.solids import compound

    edges = []
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    while ex.More():
        edges.append(ex.Current())
        ex.Next()
    return compound(edges)
