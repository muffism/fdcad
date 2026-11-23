"""Flow along curve (PLAN Phase 4, PHASE4_SPEC P4.9 item 6, D393).

Params: the common ones (``feature.py``) plus ``fit`` (optional boolean,
default false): when true, the region between the trim planes is scaled along
its length to the curve's length; otherwise one millimetre along the triad's
third axis follows one millimetre of curve.

Refs: ``path``: a sketch whose curves form one chain or a curve feature, or
``path_edges``: a chain of edge references (as for Pipe and Sweep).

The start trim plane goes to the curve's start. The triad's first axis
follows a frame carried along the curve without twisting; the part keeps its
place across the curve (its X and Y in the triad frame). Beyond the curve's
ends it goes on straight along the end tangents.
"""

from __future__ import annotations

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_CompCurve
from OCP.GCPnts import GCPnts_AbscissaPoint, GCPnts_UniformAbscissa
from OCP.gp import gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Wire

from fdcad.core.deform import maps
from fdcad.core.deform.feature import COMMON_PARAMS, DeformFeature, local_box
from fdcad.core.deform.maps import CurveSamples, Frame, PointMap
from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, ParamSpec, register

#: Samples along the curve for the frame (enough for smooth paths, bounded).
SAMPLES = 400


def sample_curve(wire: TopoDS_Wire, start_normal: tuple[float, float, float]) -> CurveSamples:
    """The wire sampled by arc length, with a frame carried along it without twisting."""
    curve = BRepAdaptor_CompCurve(wire)
    length = GCPnts_AbscissaPoint.Length_s(curve)
    if length < 1e-6:
        raise ValueError("the curve has no length")
    spacing = GCPnts_UniformAbscissa(curve, SAMPLES)
    if not spacing.IsDone():
        raise ValueError("the curve could not be measured")
    count = spacing.NbPoints()
    points = np.empty((count, 3))
    tangents = np.empty((count, 3))
    for k in range(count):  # bounded: one sample per frame step, not per triangle
        p, v = gp_Pnt(), gp_Vec()
        curve.D1(spacing.Parameter(k + 1), p, v)
        points[k] = (p.X(), p.Y(), p.Z())
        tangents[k] = (v.X(), v.Y(), v.Z())
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
    s *= length / s[-1]
    return maps.rotation_minimizing(s, points, tangents, start_normal)


def bend_reach(
    curve: CurveSamples, used: float, lo: tuple[float, ...], hi: tuple[float, ...]
) -> float:
    """How far a box across the curve reaches towards the curve's centres of curvature.

    ``lo`` and ``hi`` bound the bodies across the curve (first and second axis),
    ``used`` is the length of curve the region between the trim planes covers.
    A point at (x, y) folds over where ``x * kn + y * kb`` reaches 1 (``kn`` and
    ``kb`` the curvature along the normal and the binormal); the largest value
    over the box corners and the used samples is returned.
    """
    if len(curve.s) < 2:
        return 0.0
    ds = np.diff(curve.s)
    keep = (ds > 1e-12) & (curve.s[:-1] < used - 1e-9)
    if not keep.any():
        return 0.0
    turn = np.diff(curve.tangents, axis=0)[keep] / ds[keep][:, None]
    normals = curve.normals[:-1][keep]
    binormals = np.cross(curve.tangents[:-1][keep], normals)
    kn = np.einsum("ij,ij->i", turn, normals)
    kb = np.einsum("ij,ij->i", turn, binormals)
    xs = np.array([lo[0], hi[0]])
    ys = np.array([lo[1], hi[1]])
    reach = kn[:, None, None] * xs[None, :, None] + kb[:, None, None] * ys[None, None, :]
    return float(reach.max())


@register
class Flow(DeformFeature):
    """Lays bodies along a curve."""

    type_name = "flow"
    main_value = "trim planes"
    params = (*COMMON_PARAMS, ParamSpec("fit", default=False, optional=True))

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """Flow the region between the trim planes along the path."""
        from fdcad.core.features.sweep import path_wire

        if not feature.refs.get("path") and not feature.refs.get("path_edges"):
            raise FeatureError(f"{feature.name} has no curve. Choose a sketch or curve.")
        wire, _issues = path_wire(feature, ctx)
        samples = sample_curve(wire, frame.x)
        scale = samples.length / (z1 - z0) if feature.params.get("fit") is True else 1.0
        lo, hi = local_box(self.setup(feature, ctx)[0].shape, frame)
        if bend_reach(samples, (z1 - z0) * scale, lo, hi) >= 1.0 - 1e-6:
            raise FeatureError(
                f"{feature.name}: the curve bends tighter than the bodies are wide, so they "
                "would fold through themselves. Use a curve with larger bends, move the "
                "triad or turn it with Turn first axis."
            )
        return maps.flow(frame, z0, z1, samples, scale)
