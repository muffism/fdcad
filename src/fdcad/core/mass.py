"""Mass properties (TR79, DECISIONS D764; widens D6 and D29 as D750 approved).

For one or more solids and a density: mass, volume, surface area, centre of
mass, principal axes and moments, and the moments of inertia about the centre
of mass or about a chosen coordinate system. The kernel's global properties
give the volume, area, centre and the inertia about the centre for unit
density; the density scales them, and the parallel axis rule moves them to
another frame. Kernel work, run in a kernel job (CLAUDE.md 5.2).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.measure import Frame

Vec3 = tuple[float, float, float]
Matrix = tuple[Vec3, Vec3, Vec3]
#: g/cm3 to g/mm3.
_PER_MM3 = 1e-3


@dataclass(frozen=True)
class MassProperties:
    """Everything in millimetres and grams: mass g, volume mm3, area mm2, inertia g mm2."""

    bodies: int
    density: float  # g/cm3
    mass: float
    volume: float
    area: float
    centre: Vec3
    #: Inertia tensor about the centre of mass, in model axes.
    inertia: Matrix
    #: Principal moments (smallest first) and their axes.
    principal: Vec3
    axes: Matrix

    def inertia_in(self, frame: Frame) -> Matrix:
        """The inertia tensor about ``frame``'s origin, in ``frame``'s axes."""
        tensor = np.array(self.inertia)
        d = np.array(self.centre) - np.array(frame.origin)
        tensor = tensor + self.mass * (float(d @ d) * np.eye(3) - np.outer(d, d))
        rot = np.array([frame.x, frame.y, frame.z])
        out = rot @ tensor @ rot.T
        return tuple(tuple(float(v) for v in row) for row in out)  # type: ignore[return-value]


def mass_properties(bodies: Sequence[TopoDS_Shape], density: float) -> MassProperties:
    """Mass properties of ``bodies`` together at ``density`` g/cm3. Raises ValueError for
    no bodies or a density that is not positive."""
    if not bodies:
        raise ValueError("there is no body to measure. Rebuild the part, then try again.")
    if not density > 0:
        raise ValueError("the density must be more than 0. Type a density.")
    volume = GProp_GProps()
    for body in bodies:
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(body, props)
        volume.Add(props)
    area = 0.0
    for body in bodies:
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(body, props)
        area += props.Mass()
    rho = density * _PER_MM3
    centre = volume.CentreOfMass()
    matrix = volume.MatrixOfInertia()
    tensor = np.array([[matrix.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)]) * rho
    tensor = (tensor + tensor.T) / 2
    moments, vectors = np.linalg.eigh(tensor)
    return MassProperties(
        bodies=len(bodies),
        density=density,
        mass=abs(volume.Mass()) * rho,
        volume=abs(volume.Mass()),
        area=area,
        centre=(centre.X(), centre.Y(), centre.Z()),
        inertia=tuple(tuple(float(v) for v in row) for row in tensor),  # type: ignore[arg-type]
        principal=tuple(float(m) for m in moments),  # type: ignore[arg-type]
        axes=tuple(tuple(float(v) for v in vectors[:, k]) for k in range(3)),  # type: ignore[arg-type]
    )


#: A number this many times smaller than the largest one beside it is rounding
#: noise of the kernel, and is shown as 0 (D1034).
NOISE = 1e-9


def tidy(values: Iterable[float]) -> list[float]:
    """``values`` with rounding noise set to 0: a centre of mass that should be on a
    plane reads 0, not 4.2e-16."""
    numbers = [float(v) for v in values]
    largest = max((abs(v) for v in numbers), default=0.0)
    return [0.0 if abs(v) <= largest * NOISE else v for v in numbers]


def report(
    props: MassProperties, inch: bool, frame: Frame | None = None, frame_name: str = ""
) -> list[tuple[str, str]]:
    """Label and value rows for the window and the Copy button."""
    length, mass_unit = ("in", "lb") if inch else ("mm", "g")
    k = 1 / 25.4 if inch else 1.0
    m = 1 / 453.59237 if inch else 1.0
    # Noise is judged against the size of the part, not against the other two
    # coordinates: a part far from the origin still has an exact 0 where it is 0.
    size = props.volume ** (1 / 3) if props.volume > 0 else 0.0

    def vec(v: Vec3) -> str:
        shown = tidy([*v, size])[:3]
        return ", ".join(f"{c * k:.6g}" for c in shown) + f" {length}"

    rows = [
        ("Bodies", str(props.bodies)),
        ("Density", f"{props.density:.6g} g/cm^3"),
        ("Mass", f"{props.mass * m:.6g} {mass_unit}"),
        ("Volume", f"{props.volume * k**3:.6g} {length}^3"),
        ("Surface area", f"{props.area * k**2:.6g} {length}^2"),
        ("Centre of mass", vec(props.centre)),
    ]
    scale = m * k * k
    for i, (moment, axis) in enumerate(zip(props.principal, props.axes, strict=True), start=1):
        rows.append(
            (
                f"Principal moment {i}",
                f"{moment * scale:.6g} {mass_unit} {length}^2 about "
                + ", ".join(f"{c:.4g}" for c in tidy(axis)),
            )
        )
    tensor = props.inertia if frame is None else props.inertia_in(frame)
    where = "the centre of mass" if frame is None else frame_name or "the coordinate system"
    clean = tidy(v for row in tensor for v in row)  # noise against the whole tensor
    for index, name in enumerate(("x", "y", "z")):
        row = clean[3 * index : 3 * index + 3]
        rows.append(
            (
                f"Inertia I{name} (about {where})",
                ", ".join(f"{v * scale:.6g}" for v in row) + f" {mass_unit} {length}^2",
            )
        )
    return rows


# Mass overrides (TR80, DECISIONS D1021) -------------------------------------------


@dataclass(frozen=True)
class MassOverride:
    """Typed mass properties for a part whose bodies are imported or simplified. ``mass`` in
    grams; ``centre`` in mm and ``inertia`` (about the centre, model axes, g mm2) are None
    when the measured ones are kept."""

    mass: float
    centre: Vec3 | None = None
    inertia: Matrix | None = None

    def to_data(self) -> dict[str, object]:
        """As saved in the part (``Document.mass_override``)."""
        out: dict[str, object] = {"mass": self.mass}
        if self.centre is not None:
            out["centre"] = list(self.centre)
        if self.inertia is not None:
            out["inertia"] = [list(row) for row in self.inertia]
        return out


def _numbers(raw: object, count: int) -> list[float] | None:
    if not isinstance(raw, list) or len(raw) != count:
        return None
    out = []
    for v in raw:
        if isinstance(v, bool) or not isinstance(v, int | float) or not np.isfinite(v):
            return None
        out.append(float(v))
    return out


def override_from_data(raw: object) -> MassOverride | None:
    """A saved override, or None when there is none or it is damaged (the part still opens
    and the measured values are used)."""
    if not isinstance(raw, dict):
        return None
    mass = raw.get("mass")
    if isinstance(mass, bool) or not isinstance(mass, int | float) or not mass > 0:
        return None
    centre = _numbers(raw.get("centre"), 3) if "centre" in raw else None
    if "centre" in raw and centre is None:
        return None
    inertia: Matrix | None = None
    if "inertia" in raw:
        rows = raw["inertia"]
        found = [_numbers(r, 3) for r in rows] if isinstance(rows, list) and len(rows) == 3 else []
        if len(found) != 3 or any(r is None for r in found):
            return None
        tensor = np.array(found, dtype=float)
        if not np.allclose(tensor, tensor.T, rtol=1e-9, atol=1e-9):
            return None
        inertia = tuple(tuple(float(v) for v in row) for row in tensor)  # type: ignore[assignment]
    return MassOverride(
        float(mass),
        tuple(centre) if centre is not None else None,  # type: ignore[arg-type]
        inertia,
    )


def check_override(override: MassOverride) -> str | None:
    """Why the override cannot be used, or None. Inertia must be a physical tensor:
    symmetric, no negative principal moment, each no more than the other two together."""
    if not override.mass > 0:
        return "the mass must be more than 0. Type a mass."
    if override.inertia is not None:
        tensor = np.array(override.inertia, dtype=float)
        if not np.allclose(tensor, tensor.T):
            return "the inertia must be symmetric. Type the same value for each pair."
        moments = np.linalg.eigvalsh(tensor)
        scale = max(float(np.abs(moments).max()), 1e-12)
        if moments[0] < -1e-9 * scale or any(
            moments[i] > moments[(i + 1) % 3] + moments[(i + 2) % 3] + 1e-9 * scale
            for i in range(3)
        ):
            return "these moments of inertia cannot belong to a real body. Check the values."
    return None


def apply_override(props: MassProperties, override: MassOverride) -> MassProperties:
    """``props`` with the typed values put in. Without a typed inertia the measured one is
    scaled by the mass ratio (same shape, new mass); the volume and area stay measured."""
    tensor = (
        np.array(override.inertia, dtype=float)
        if override.inertia is not None
        else np.array(props.inertia) * (override.mass / props.mass if props.mass else 0.0)
    )
    moments, vectors = np.linalg.eigh(tensor)
    density = override.mass / props.volume / _PER_MM3 if props.volume else props.density
    return MassProperties(
        bodies=props.bodies,
        density=density,
        mass=override.mass,
        volume=props.volume,
        area=props.area,
        centre=override.centre if override.centre is not None else props.centre,
        inertia=tuple(tuple(float(v) for v in row) for row in tensor),  # type: ignore[arg-type]
        principal=tuple(float(m) for m in moments),  # type: ignore[arg-type]
        axes=tuple(tuple(float(v) for v in vectors[:, k]) for k in range(3)),  # type: ignore[arg-type]
    )


def part_override(doc: object) -> MassOverride | None:
    """The part's override, or None."""
    return override_from_data(getattr(doc, "mass_override", None))
