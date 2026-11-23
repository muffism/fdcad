"""Where a sweep crosses itself, for its error message (TUTORIAL_REVIEW_SPEC_2 TR139,
DECISIONS D1509).

A swept solid crosses itself where the path bends tighter than the profile reaches
from it: the inside of the bend folds over. :func:`tight_bend` samples the path's
curvature and returns the place of the tightest bend, and :func:`crossing_message`
names it in the error with the three ways out the spec lists: a larger path radius,
a smaller profile, or splitting the path.
"""

from __future__ import annotations

from dataclasses import dataclass

from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepLProp import BRepLProp_CLProps
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopoDS import TopoDS_Shape, TopoDS_Wire

_SAMPLES_PER_EDGE = 24


@dataclass(frozen=True)
class Bend:
    """The tightest bend: how far along the path, the path's length and the radius."""

    along: float
    length: float
    radius: float


def tight_bend(path: TopoDS_Wire) -> Bend | None:
    """The point of the path with the smallest bend radius, or None for a straight path."""
    best: tuple[float, float] | None = None  # (radius, distance along)
    walked = 0.0
    explorer = BRepTools_WireExplorer(path)
    while explorer.More():
        curve = BRepAdaptor_Curve(explorer.Current())
        u0, u1 = curve.FirstParameter(), curve.LastParameter()
        length = GCPnts_AbscissaPoint.Length_s(curve)
        for k in range(_SAMPLES_PER_EDGE + 1):
            u = u0 + (u1 - u0) * k / _SAMPLES_PER_EDGE
            props = BRepLProp_CLProps(curve, u, 2, 1e-7)
            bend = props.Curvature() if props.IsTangentDefined() else 0.0
            if bend > 1e-9:
                radius = 1.0 / bend
                if best is None or radius < best[0]:
                    part = GCPnts_AbscissaPoint.Length_s(curve, u0, u) if u > u0 else 0.0
                    if explorer.Current().Orientation() == TopAbs_REVERSED:
                        part = length - part  # the wire runs this edge backwards
                    best = (radius, walked + part)
        walked += length
        explorer.Next()
    if best is None:
        return None
    return Bend(best[1], walked, best[0])


def reach(shapes: list[TopoDS_Shape], start: gp_Pnt) -> float:
    """How far the profile reaches from the path's start: the farthest box corner."""
    box = Bnd_Box()
    for shape in shapes:
        BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        return 0.0
    low, high = box.CornerMin(), box.CornerMax()
    x0, y0, z0 = low.X(), low.Y(), low.Z()
    x1, y1, z1 = high.X(), high.Y(), high.Z()
    return float(
        max(start.Distance(gp_Pnt(x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1))
    )


def crossing_message(owner: str, path: TopoDS_Wire, profile_reach: float) -> str:
    """The self crossing error, naming the tightest bend when there is one."""
    bend = tight_bend(path)
    if bend is None or bend.length <= 0:
        return (
            f"{owner}: the swept result intersects itself. Use a smaller profile or a gentler "
            "path, or change the twist."
        )
    share = 100.0 * bend.along / bend.length
    where = (
        f"about {bend.along:.4g} mm along the path ({share:.0f}% of its length), where it "
        f"bends with a radius of {bend.radius:.4g} mm"
    )
    if profile_reach > bend.radius:
        where += f", less than the profile reaches from the path ({profile_reach:.4g} mm)"
    return (
        f"{owner}: the swept result crosses itself {where}. Make that bend's radius larger "
        "than the profile, use a smaller profile, or split the path there and sweep each "
        "part."
    )
