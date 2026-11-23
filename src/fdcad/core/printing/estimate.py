"""Volume and print weight estimate (PLAN Phase 2, DECISIONS D355).

A solid part estimate: the volume of the bodies times the material density.
The slicer gives the real figure with its walls and infill.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.solids import precise_volume, solids
from fdcad.core.occ import ShapeMap

#: Cubic millimetres in one cubic centimetre.
MM3_PER_CM3 = 1000.0


@dataclass(frozen=True)
class VolumeEstimate:
    """The measured bodies and their total volume in mm3."""

    bodies: int
    volume: float
    #: Surface area in mm2, for the walls of a printed part (TR187, D988).
    area: float = 0.0

    def weight(
        self,
        density: float,
        infill: float = 100.0,
        walls: int = 2,
        line_width: float = 0.4,
    ) -> float:
        """Weight in grams for a density in g/cm3. Below 100 percent ``infill``, the
        walls (``walls`` lines of ``line_width`` mm round every surface, the top and
        bottom included) are solid and the rest is filled to the infill percent."""
        printed = self.volume
        if infill < 100.0:
            shell = min(self.volume, self.area * max(walls, 0) * max(line_width, 0.0))
            printed = shell + max(infill, 0.0) / 100.0 * (self.volume - shell)
        return printed / MM3_PER_CM3 * density


def bodies_for(shape: TopoDS_Shape, picks: Sequence[TopoDS_Shape] = ()) -> list[TopoDS_Shape]:
    """The bodies of ``shape`` that hold any of ``picks``; every body when nothing is picked."""
    bodies = solids(shape)
    if not picks:
        return bodies
    chosen = []
    for body in bodies:
        found = ShapeMap()
        for kind in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
            TopExp.MapShapes_s(body, kind, found)
        if any(found.Contains(p) for p in picks):
            chosen.append(body)
    return chosen or bodies


def estimate(bodies: Sequence[TopoDS_Shape]) -> VolumeEstimate:
    """Total volume and surface area of ``bodies``."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    area = 0.0
    for body in bodies:
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(body, props)
        area += abs(props.Mass())
    return VolumeEstimate(len(bodies), sum(abs(precise_volume(b)) for b in bodies), area)
