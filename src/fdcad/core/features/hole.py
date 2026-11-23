"""Hole Tool (PHASE4_SPEC P4.1, PLAN Phase 4, DECISIONS D310 to D313).

One feature makes holes of one type at every position point. The positions come
from a sketch: the feature's own position sketch, or an existing sketch whose
points, end points and centres can each be counted or not.

Params (FDEF_SPEC 5.3.21):

- ``hole_type``: ``simple``, ``counterbore``, ``countersink``, ``tapped``,
  ``heat_set_insert``, ``nut_trap`` or ``nut_slot``.
- ``standard`` (``iso`` or ``ansi``), ``purpose`` (``drill``, ``tap_drill``,
  ``clearance``), ``size`` (a size name such as ``M5``) and ``fit`` (``close``,
  ``normal``, ``loose``): what the values were filled from. The geometry only
  uses the stored lengths below, so a file rebuilds the same when tables change.
- ``diameter``: length, the hole (or tap drill, or insert) diameter.
- ``end_condition``: ``blind`` (with ``depth``), ``through_all``,
  ``up_to_face`` (with ``refs.up_to``), ``up_to_next`` (to where the axis
  first comes out of the material) or ``up_to_vertex`` (with
  ``refs.up_to_vertex``: a vertex reference or a sketch point; TOOL_SPEC T16
  item 4). ``bottom``: optional, ``drill_point`` with ``tip_angle`` (angle); left
  out for a flat bottom.
- Counterbore: ``cbore_diameter``, ``cbore_depth``. Countersink:
  ``csk_diameter``, ``csk_angle`` (included angle). Counterdrill (TR144, D1506):
  ``cbore_diameter``, ``cbore_depth`` and ``cdrill_angle`` (the included angle of
  the cone from the counterbore's floor down to the hole, 118 degrees if left out).
- ``head_clearance``: optional length, the head bore carried up above the face.
- ``near_csk`` with ``near_csk_diameter``, ``near_csk_angle``; ``far_csk`` with
  ``far_csk_diameter``, ``far_csk_angle`` (Through All only).
- Tapered pipe tapped (``pipe_tapped``, TR145, D1511): as tapped, and the whole
  wall always tapers 1 in 16 on the diameter (NPT and Rc sizes fill the values;
  ``diameter`` is the size at the face).
- Tapped: ``thread_depth``, ``thread_diameter`` (major), ``pitch`` (lengths),
  ``cosmetic_thread`` and ``modeled_thread`` (optional booleans, P4.2 and P4.3).
- Nut trap and nut slot: ``nut_flats``, ``nut_height`` (lengths), ``nut_angle``
  (angle); nut slot also ``slot_offset`` (face to the top of the slot) and
  ``slot_length`` (axis to the open end).
- ``print_fit``: optional, ``clearance``, ``slip`` or ``press`` with
  ``fit_tolerance`` (length, copied from the printer profile when chosen).
- ``use_points``, ``use_ends``, ``use_centres``: optional booleans, which points
  of an existing sketch get holes (default points and end points).
- Slots (``simple``, ``counterbore`` and ``countersink`` only, DECISIONS D524):
  ``slot`` (optional boolean) with ``slot_span`` (length), ``slot_span_mode``
  (optional, ``overall``; centre to centre when left out) and ``slot_angle``
  (optional angle in the face plane from the position sketch's X axis).

Skipped points (TR143, D1520): with an existing sketch, ``data.skip_points`` lists
the ids of its points that get no hole (clicked off on the Positions tab).

Positions: the hole's own position sketch is kept in ``data.positions`` (sketch
data as in FDEF_SPEC 6, points only) on ``refs.plane`` (a plane feature or a flat
face). An existing sketch is used instead with ``refs.sketch`` (DECISIONS D312).

Placed with no sketch (TR143, D1911): ``refs.place_edges`` (two straight edges, with
``place_distance1`` and ``place_distance2``) or ``refs.concentric`` (a round edge or
cylinder face) on ``refs.plane`` give one hole (``hole_place``).

Start plane (TR144, D1913): ``refs.start_plane`` (a plane or flat face) moves every
hole along its axis to start there, in place of the face it is placed on.

Refs: ``sketch`` or ``plane``, ``face`` (one face reference, flat or curved, that
the holes start on; without it holes start on the sketch plane and go against
its normal), ``up_to`` (one face reference), ``up_to_vertex`` (one vertex
reference or sketch point).

Printing (TR175, D780): ``print_top`` (optional): ``teardrop`` or ``flat`` gives a
hole that runs sideways a pointed or a flat top toward the printer's up, so it
prints without supports; up is the model's +Z, or straight off the bed when a
face is laid flat (``print_setup.down_face``). Holes along up are left round.
The extra faces are ``hole/<p>/top/<k>``.

Bridging (TR176, D781): ``print_bridge`` (optional), for counterbores and
countersinks printed head down: ``sacrificial`` leaves one layer over the small
bore at the head's floor, to drill out after printing; ``stepped`` leaves two
layers that print as bridges: a slot as wide as the bore across the head, then a
square as wide as the bore. ``bridge_layer`` (length) is one layer, copied from
the printer profile's layer height.

Face roles, per position point ``p``: ``hole/<p>/wall``, ``hole/<p>/bottom``,
``hole/<p>/tip``, ``hole/<p>/cbore_wall``, ``hole/<p>/cbore_floor``,
``hole/<p>/csk``, ``hole/<p>/cdrill``, ``hole/<p>/far_csk``, ``hole/<p>/head``,
``hole/<p>/hex/<k>``, ``hole/<p>/hex/floor``, ``hole/<p>/slot/<k>``. A slot hole names its straight
sides ``hole/<p>/<role>/side1`` and ``side2`` and its round ends
``hole/<p>/<role>/end1`` and ``end2``; faces across the slot keep the plain role.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepIntCurveSurface import BRepIntCurveSurface_Inter
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.gp import gp_Ax1, gp_Dir, gp_Lin, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features import hole_data, hole_heads
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    SketchOutput,
    ThreadMark,
    Vec3,
    register,
)
from fdcad.core.features.modify import require_body, resolve_faces
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    bounding_size,
    check_result,
    compound,
    solids,
)
from fdcad.core.naming.names import NamedFace, NamedShape, carry, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, ShapeList, shape_list
from fdcad.core.sketch.model import Arc, Circle, Ellipse, EllipseArc, Line, Point, Sketch, Spline
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.units import Kind

#: Lengths every hole type uses, and those of each type (validation and the panel).
TYPE_LENGTHS: dict[str, tuple[str, ...]] = {
    "simple": (),
    "counterbore": ("cbore_diameter", "cbore_depth"),
    "countersink": ("csk_diameter",),
    "tapped": ("thread_depth", "pitch"),
    "heat_set_insert": (),
    "nut_trap": ("nut_flats", "nut_height"),
    "nut_slot": ("nut_flats", "nut_height", "slot_offset", "slot_length"),
    "self_tapping": (),
    "magnet": (),
    "dowel": (),
    "bearing": ("cbore_diameter", "cbore_depth"),
    "counterdrill": ("cbore_diameter", "cbore_depth"),  # TR144 (D1506)
    "pipe_tapped": ("thread_depth", "pitch"),  # TR145 (D1511)
}
#: Hole end conditions, in list order (TOOL_SPEC T16 item 4).
END_CONDITIONS = ("blind", "through_all", "up_to_next", "up_to_vertex", "up_to_face")
#: Types that can have a near side countersink of their own.
NEAR_CSK_TYPES = ("simple", "tapped", "heat_set_insert", "self_tapping", "dowel")
#: Types that can be slots (D524), and how a slot length is measured.
SLOT_TYPES = ("simple", "counterbore", "countersink")
SLOT_SPAN_MODES = ("centre", "overall")


@dataclass(frozen=True)
class Placement:
    """Where one hole goes: its point id, start point and direction into the part."""

    point: str
    origin: Vec3
    direction: Vec3
    curved: bool


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3, s: float = 1.0) -> Vec3:
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 1.0)


def _curve_points(entity: object) -> list[str]:
    """Every point id a curve uses."""
    from fdcad.core.sketch.model import entity_points

    return [p for p in entity_points(entity) if p != getattr(entity, "id", None)]  # type: ignore[arg-type]


def point_kinds(sketch: Sketch) -> dict[str, str]:
    """Kind of every sketch point: ``point`` (on its own), ``end``, ``centre`` or ``helper``.

    A point that is both a centre and an end counts as an end. ``helper`` points
    shape a curve (the axis ends of an ellipse, the points and tangent handles of
    a spline) and never get a hole or a pattern copy (D605).
    """
    ends: set[str] = set()
    centres: set[str] = set()
    helpers: set[str] = set()
    for entity in sketch.entities.values():
        if getattr(entity, "construction", False) and not isinstance(entity, Point):
            # Construction curves lay out the sketch; their points get no holes unless
            # a drawn curve also uses them (audit A item 6, D716).
            helpers.update(_curve_points(entity))
            continue
        if isinstance(entity, Line):
            ends.update((entity.p1, entity.p2))
        elif isinstance(entity, Arc):
            ends.update((entity.start, entity.end))
            centres.add(entity.center)
        elif isinstance(entity, Circle):
            centres.add(entity.center)
        elif isinstance(entity, EllipseArc):
            ends.update((entity.start, entity.end))
            centres.add(entity.center)
            helpers.update((entity.major, entity.minor))
        elif isinstance(entity, Ellipse):
            centres.add(entity.center)
            helpers.update((entity.major, entity.minor))
        elif isinstance(entity, Spline):
            ends.update((entity.points[0], entity.points[-1]) if entity.points else ())
            helpers.update(entity.points[1:-1])
            helpers.update(entity.handles)
    out: dict[str, str] = {}
    for eid, entity in sketch.entities.items():
        if isinstance(entity, Point):
            if entity.construction:
                out[eid] = "helper"
            elif eid in ends:
                out[eid] = "end"
            elif eid in centres:
                out[eid] = "centre"
            elif eid in helpers:
                out[eid] = "helper"
            else:
                out[eid] = "centre" if eid in centres else "point"
    return out


def position_points(feature: Feature, sketch: Sketch) -> list[tuple[str, float, float]]:
    """The sketch points that get holes, as (id, x, y), in sketch order."""
    use = {
        "point": feature.params.get("use_points", True) is not False,
        "end": feature.params.get("use_ends", True) is not False,
        "centre": feature.params.get("use_centres", False) is True,
    }
    skip: set[str] = set()
    if "sketch" not in feature.refs:
        use = {"point": True, "end": True, "centre": True}  # the hole's own points
    else:  # TR143 (D1520): points of an existing sketch clicked off
        raw = feature.data.get("skip_points", [])
        skip = {str(p) for p in raw} if isinstance(raw, list) else set()
    kinds = point_kinds(sketch)
    out: list[tuple[str, float, float]] = []
    for eid, kind in kinds.items():
        entity = sketch.entities[eid]
        if eid in skip:
            continue
        if use.get(kind, False) and isinstance(entity, Point):
            out.append((eid, entity.x, entity.y))
    return out


def line_hits(
    shape: TopoDS_Shape, origin: Vec3, direction: Vec3
) -> list[tuple[float, Vec3, TopoDS_Face, float, float]]:
    """Where the infinite line through ``origin`` meets ``shape``: (t, point, face, u, v)."""
    inter = BRepIntCurveSurface_Inter()
    inter.Init(shape, gp_Lin(gp_Pnt(*origin), gp_Dir(*direction)), 1e-7)
    out = []
    while inter.More():
        p = inter.Pnt()
        out.append((inter.W(), (p.X(), p.Y(), p.Z()), inter.Face(), inter.U(), inter.V()))
        inter.Next()
    out.sort(key=lambda h: h[0])
    return out


def outward_normal(face: TopoDS_Face, u: float, v: float) -> Vec3 | None:
    """The face normal at (u, v), pointing out of the part."""
    props = BRepLProp_SLProps(BRepAdaptor_Surface(face), u, v, 1, 1e-7)
    if not props.IsNormalDefined():
        return None
    n = props.Normal()
    out = (n.X(), n.Y(), n.Z())
    if face.Orientation() == TopAbs_REVERSED:
        out = (-out[0], -out[1], -out[2])
    return out


def is_flat(face: TopoDS_Face) -> bool:
    """True for a planar face."""
    from OCP.GeomAbs import GeomAbs_Plane

    return bool(BRepAdaptor_Surface(face).GetType() == GeomAbs_Plane)


def placements(feature: Feature, sketch: SketchOutput, face: TopoDS_Face | None) -> list[Placement]:
    """Start point and direction of every hole (on the picked face, or the sketch plane)."""
    plane = sketch.plane
    normal = _unit(plane.normal)
    out: list[Placement] = []
    points = position_points(feature, sketch.model)
    if not points:
        raise FeatureError(
            f"{feature.name}: the position sketch has no points. "
            "Add points on the Positions tab or tick more kinds of points."
        )
    curved = face is not None and not is_flat(face)
    for pid, x, y in points:
        p3 = plane.to_3d(x, y)
        start: Vec3 = (p3.X(), p3.Y(), p3.Z())
        if face is None:
            out.append(Placement(pid, start, (-normal[0], -normal[1], -normal[2]), False))
            continue
        hits = line_hits(face, start, normal)
        if not hits and feature.refs.get("concentric") and is_flat(face):
            # TR143 (D1911): over an existing hole, start on the face's plane.
            out.append(Placement(pid, start, (-normal[0], -normal[1], -normal[2]), False))
            continue
        if not hits:
            raise FeatureError(
                f"{feature.name}: point {pid} is not over the picked face. "
                "Move the point onto the face or pick another face.",
                highlight=[pid],
            )
        _t, at, hit_face, u, v = min(hits, key=lambda h: abs(h[0]))
        n = outward_normal(hit_face, u, v)
        if n is None:
            raise FeatureError(
                f"{feature.name}: the face has no clear direction at point {pid}. Move the point."
            )
        out.append(Placement(pid, at, (-n[0], -n[1], -n[2]), curved))
    return out


@dataclass
class _Spec:
    """The hole profile values in mm and radians, after the fit preset."""

    hole_type: str
    radius: float
    depth: float  # along the axis from the start point; through holes reach the exit
    exit: float | None  # where the axis leaves the part, for the far side countersink
    drill_point: bool
    tip_angle: float
    top: float  # how far the profile starts above the face (head clearance)
    cbore_radius: float = 0.0
    cbore_depth: float = 0.0
    csk_radius: float = 0.0
    csk_angle: float = 0.0
    far_radius: float = 0.0
    far_angle: float = 0.0
    nut_flats: float = 0.0
    nut_height: float = 0.0
    nut_angle: float = 0.0
    slot_offset: float = 0.0
    slot_length: float = 0.0
    slot_half: float = 0.0  # half the centre to centre length of a slot hole (D524)
    slot_angle: float = 0.0
    magnet_length: float = 0.0  # a block magnet's length; 0 for a round one (TR179)
    magnet_relief: bool = False
    groove_width: float = 0.0  # a bearing seat's retaining ring groove (TR251)
    groove_radius: float = 0.0
    groove_at: float = 0.0  # where the groove starts along the axis
    taper: float = 0.0  # the wall's taper from the axis, narrowing inward (TR144, D1505)
    stack: tuple[tuple[str, float, float], ...] = ()  # a custom hole (TR144, D1912)
    point_inside: bool = False  # the drill point ends at the depth (TR144, D1505)


def _num(feature: Feature, name: str, label: str, positive: bool = True) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param):
        raise FeatureError(f"{feature.name}: the {label} is missing. Enter a value.")
    if positive and value.value <= 0:
        raise FeatureError(
            f"{feature.name}: the {label} must be greater than zero. Enter a larger value."
        )
    return value.value


def _opt(feature: Feature, name: str, default: float) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def fit_extra(feature: Feature) -> float:
    """What the printing fit preset adds to diameters (D311)."""
    fit = str(feature.params.get("print_fit", "none"))
    if fit == "none":
        return 0.0
    tol = _opt(feature, "fit_tolerance", hole_data.DEFAULT_FIT_TOLERANCE)
    return hole_data.fit_offset(fit, tol)


def _cone_drop(r_big: float, r_small: float, angle: float) -> float:
    """Axial length of a cone from ``r_big`` down to ``r_small`` with included ``angle``."""
    return (r_big - r_small) / math.tan(angle / 2.0)


def hole_spec(feature: Feature) -> _Spec:
    """Read and check the values (before any kernel call)."""
    name = feature.name
    kind = str(feature.params.get("hole_type", "simple"))
    extra = fit_extra(feature)
    if kind == "custom":  # TR144 item 1 (D1912): a stack of elements, no table sizes
        return _custom_spec(feature, extra)
    diameter = _num(feature, "diameter", "hole diameter") + extra
    radius = diameter / 2.0
    end = str(feature.params.get("end_condition", "blind"))
    depth = _num(feature, "depth", "depth") if end == "blind" else 0.0
    drill = feature.params.get("bottom") == "drill_point" and end != "through_all"
    tip = _opt(feature, "tip_angle", math.radians(118.0))
    if drill and not 0.0 < tip < math.pi:
        raise FeatureError(
            f"{name}: the drill point angle must be between 0 and 180 degrees. "
            "Enter an angle in that range."
        )
    top = max(_opt(feature, "head_clearance", 0.0), 0.0)
    spec = _Spec(kind, radius, depth, None, drill, tip, top)
    if kind in ("counterbore", "bearing", "counterdrill"):  # TR251 bearing, TR144
        spec.cbore_radius = (_num(feature, "cbore_diameter", "counterbore diameter") + extra) / 2
        spec.cbore_depth = _num(feature, "cbore_depth", "counterbore depth")
        if spec.cbore_radius <= radius:
            raise FeatureError(
                f"{name}: the counterbore diameter must be larger than the hole diameter. "
                "Enter a larger counterbore diameter."
            )
    if kind == "counterdrill":  # TR144 (D1506): a cone at the counterbore's floor
        spec.csk_angle = _opt(feature, "cdrill_angle", math.radians(118.0))
        if not 0.0 < spec.csk_angle < math.pi:
            raise FeatureError(
                f"{name}: the counterdrill angle must be between 0 and 180 degrees. "
                "Enter an angle in that range."
            )
    bevel = kind == "self_tapping" and feature.params.get("near_csk") is not False
    if bevel and not isinstance(feature.params.get("near_csk_diameter"), Param):
        # A self tapping hole has an entry bevel unless turned off (TR255, D840).
        spec.csk_radius = (diameter - extra) * hole_data.SELF_TAP_BEVEL / 2 + extra / 2
        spec.csk_angle = _opt(feature, "near_csk_angle", math.radians(90.0))
    elif kind == "countersink" or (
        kind in NEAR_CSK_TYPES and (feature.params.get("near_csk") is True or bevel)
    ):
        key = "csk" if kind == "countersink" else "near_csk"
        spec.csk_radius = (_num(feature, f"{key}_diameter", "countersink diameter") + extra) / 2
        spec.csk_angle = _num(feature, f"{key}_angle", "countersink angle")
        if spec.csk_radius <= radius:
            raise FeatureError(
                f"{name}: the countersink diameter must be larger than the hole diameter. "
                "Enter a larger countersink diameter."
            )
        if not 0.0 < spec.csk_angle < math.pi:
            raise FeatureError(
                f"{name}: the countersink angle must be between 0 and 180 degrees. "
                "Enter an angle in that range."
            )
    if feature.params.get("far_csk") is True and end == "through_all":
        spec.far_radius = (_num(feature, "far_csk_diameter", "far side countersink") + extra) / 2
        spec.far_angle = _num(feature, "far_csk_angle", "far side countersink angle")
        if spec.far_radius <= radius or not 0.0 < spec.far_angle < math.pi:
            raise FeatureError(
                f"{name}: the far side countersink must be larger than the hole, "
                "with an angle between 0 and 180 degrees. Change its diameter or angle."
            )
    if kind in ("tapped", "pipe_tapped"):
        thread = _num(feature, "thread_depth", "thread depth")
        if end == "blind" and thread > depth + 1e-9:
            raise FeatureError(
                f"{name}: the thread depth is larger than the hole depth. "
                "Make the thread shorter or the hole deeper."
            )
    if kind in ("nut_trap", "nut_slot"):
        spec.nut_flats = _num(feature, "nut_flats", "nut width across flats") + extra
        spec.nut_height = _num(feature, "nut_height", "nut height") + extra
        spec.nut_angle = _opt(feature, "nut_angle", 0.0)
        if spec.nut_flats <= diameter:
            raise FeatureError(f"{name}: the nut must be wider than the hole. Check the nut size.")
    if kind == "nut_slot":
        spec.slot_offset = _num(feature, "slot_offset", "slot offset", positive=False)
        spec.slot_length = _num(feature, "slot_length", "slot length")
        if spec.slot_offset < 0:
            raise FeatureError(f"{name}: the slot offset cannot be negative. Enter zero or more.")
    if kind == "magnet":  # TR179 (D869)
        _magnet_spec(feature, spec, end, extra)
    if kind == "bearing" and feature.params.get("bearing_groove") is True:  # TR251 (D873)
        # The seat grows by the groove and a land above it, so the bearing still sits
        # its full width below the ring.
        width = _opt(feature, "bearing_width", spec.cbore_depth)
        if width <= 0 or width > spec.cbore_depth + 1e-9:
            raise FeatureError(
                f"{name}: the bearing width must be above zero and no more than the seat "
                "depth. Pick the bearing size again."
            )
        bore = 2 * spec.cbore_radius
        spec.groove_width, spec.groove_radius = hole_data.bearing_groove(bore - extra)
        spec.groove_radius += extra / 2
        grow = spec.groove_width + GROOVE_LAND
        spec.cbore_depth += grow
        spec.depth += grow
        spec.groove_at = spec.cbore_depth - width - spec.groove_width
    if slot_on(feature):
        spec.slot_half = _slot_centres(feature) / 2.0
        spec.slot_angle = _opt(feature, "slot_angle", 0.0)
    if kind == "tapped" and feature.params.get("thread_chamfer") is True:  # TR256 (D1922)
        from fdcad.core.features.thread_relief import CHAMFER_RATIO

        spec.csk_radius = CHAMFER_RATIO * _thread_major(feature) / 2.0 + extra / 2.0
        spec.csk_angle = math.radians(90.0)
    _taper_spec(feature, spec)
    return spec


def _thread_major(feature: Feature) -> float:
    """A tapped hole's thread diameter: the typed one, else from the tap drill."""
    from fdcad.core.features.cosmetic_thread import basic_major

    wall = _opt(feature, "diameter", 0.0)
    return _opt(feature, "thread_diameter", basic_major(wall, _opt(feature, "pitch", 0.0)))


def _relief_rings(feature: Feature, places: list[Placement]) -> list[TopoDS_Shape]:
    """A tapped hole's thread relief grooves (TR256, D1922): at the thread's bottom,
    sized from the pitch."""
    from fdcad.core.features.thread_relief import groove_ring, groove_size

    pitch = _opt(feature, "pitch", 0.0)
    depth = _opt(feature, "thread_depth", 0.0)
    across, width = groove_size(_thread_major(feature), pitch, True)
    if pitch <= 0 or width >= depth:
        raise FeatureError(
            f"{feature.name}: the thread relief groove ({width:g} mm) is as long as the thread. "
            "Make the thread deeper, or turn off Thread Relief."
        )
    inner = _opt(feature, "diameter", 0.0) / 2.0 - 0.5
    return [
        groove_ring(p.origin, p.direction, inner, across / 2.0, depth - width, depth)
        for p in places
    ]


#: Types whose plain wall can taper (TR144, D1505).
TAPER_TYPES = ("simple", "counterbore", "countersink", "tapped")


def _taper_spec(feature: Feature, spec: _Spec) -> None:
    """Whole hole taper and a drill point inside the depth (TR144 item 3, D1505)."""
    name = feature.name
    spec.point_inside = spec.drill_point and feature.params.get("point_in_depth") is True
    if spec.hole_type == "pipe_tapped":  # TR145 (D1511): always the pipe taper
        if slot_on(feature) or spec.far_radius > 0:
            raise FeatureError(
                f"{name}: a tapered pipe hole cannot be a slot or have a far side "
                "countersink. Turn them off."
            )
        spec.taper = math.atan(hole_data.PIPE_TAPER / 2.0)
        return
    if feature.params.get("taper") is not True:
        return
    if spec.hole_type not in TAPER_TYPES:
        raise FeatureError(
            f"{name}: this hole type cannot taper. Turn off Taper, or choose a simple, "
            "counterbore, countersink or tapped hole."
        )
    if slot_on(feature) or spec.far_radius > 0:
        raise FeatureError(
            f"{name}: a tapered hole cannot be a slot or have a far side countersink. Turn "
            "off Taper, or turn off the slot or the far side countersink."
        )
    spec.taper = _num(feature, "taper_angle", "taper angle")
    if spec.taper >= math.radians(45.0):
        raise FeatureError(
            f"{name}: the taper angle must be less than 45 degrees. Enter a smaller angle."
        )


def _magnet_spec(feature: Feature, spec: _Spec, end: str, extra: float) -> None:
    """A magnet pocket: a block's length, relief slots, and a closed skin over a blind
    pocket (it starts that far under the face, so the magnet is printed in)."""
    length = _opt(feature, "magnet_length", 0.0)
    if length < 0:
        raise FeatureError(
            f"{feature.name}: the magnet length cannot be negative. Enter 0 for a round magnet."
        )
    spec.magnet_length = length + extra if length > 0 else 0.0
    spec.magnet_relief = feature.params.get("magnet_relief") is True
    skin = _opt(feature, "magnet_skin", 0.0)
    if skin < 0:
        raise FeatureError(f"{feature.name}: the skin cannot be negative. Enter 0 or more.")
    if skin > 0 and end == "blind":
        spec.top = -skin
        spec.depth += skin


def _magnet_tools(prefix: str, place: Placement, spec: _Spec, hint: Vec3) -> list[NamedShape]:
    """A block magnet's box, and the relief slots of either shape."""
    d = _unit(place.direction)
    x, y = _frame(d, hint)
    start = _add(place.origin, d, -spec.top)
    vector = _scale(d, spec.top + spec.depth)
    out: list[NamedShape] = []
    if spec.magnet_length > 0:
        hw, hl = spec.radius, spec.magnet_length / 2.0
        corners = [(hl, hw), (-hl, hw), (-hl, -hw), (hl, -hw)]
        box = [_add(_add(start, x, a), y, b) for a, b in corners]
        out.append(_prism(prefix, "pocket", box, vector, "pocket/floor"))
        if spec.magnet_relief:
            s = MAGNET_RELIEF / 2.0
            for k, (a, b) in enumerate(corners, start=1):
                c = _add(_add(start, x, a), y, b)
                square = [_add(_add(c, x, i * s), y, j * s) for i, j in _SQUARE]
                out.append(_prism(prefix, f"relief{k}", square, vector))
        return out
    if spec.magnet_relief:
        reach = spec.radius + MAGNET_RELIEF
        s = MAGNET_RELIEF / 2.0
        for k in range(3):
            a = k * 2.0 * math.pi / 3.0
            u = _add(_scale(x, math.cos(a)), y, math.sin(a))
            v = _cross(d, u)
            slot = [
                _add(_add(start, v, s), u, 0.0),
                _add(_add(start, v, s), u, reach),
                _add(_add(start, v, -s), u, reach),
                _add(_add(start, v, -s), u, 0.0),
            ]
            out.append(_prism(prefix, f"relief{k + 1}", slot, vector))
    return out


def _groove(prefix: str, place: Placement, spec: _Spec, hint: Vec3) -> NamedShape:
    """A bearing seat's retaining ring groove: a ring in the seat wall (TR251)."""
    d = _unit(place.direction)
    x = _frame(d, hint)[0]
    z0, z1 = spec.groove_at, spec.groove_at + spec.groove_width
    r0, r1 = spec.cbore_radius - 0.01, spec.groove_radius
    section = [(r0, z0), (r1, z0), (r1, z1), (r0, z1)]
    pts3 = [_add(_add(place.origin, x, r), d, z) for r, z in section]
    face, edges = _wire_face(pts3)
    maker = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(*place.origin), gp_Dir(*d)), 2 * math.pi)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("The ring groove could not be made. Check the bearing size.")
    names: list[NamedFace] = []
    for role, edge in zip(("groove/top", "groove/wall", "groove/bottom", ""), edges, strict=True):
        if not role:
            continue
        for made in shape_list(maker.Generated(edge)):
            if made.ShapeType() == TopAbs_FACE:
                names.append((f"{prefix}/{role}", TopoDS.Face(made)))
    shape = maker.Shape()
    return NamedShape(shape, restrict(names, shape, prefix))


#: Material left between a bearing seat's ring groove and the face (mm, TR251).
GROOVE_LAND = 0.5
#: Width of a magnet pocket's relief slot, and how far it runs past the pocket (mm).
MAGNET_RELIEF = 0.8
_SQUARE = ((1, 1), (-1, 1), (-1, -1), (1, -1))


def slot_on(feature: Feature) -> bool:
    """True for a slot hole: ``slot`` ticked on a type that can be a slot (D524)."""
    return feature.params.get("slot") is True and feature.params.get("hole_type") in SLOT_TYPES


def _slot_centres(feature: Feature) -> float:
    """The distance between the centres of a slot's round ends, in mm."""
    name = feature.name
    span = _num(feature, "slot_span", "slot length", positive=False)
    mode = str(feature.params.get("slot_span_mode", "centre"))
    if mode not in SLOT_SPAN_MODES:
        raise FeatureError(
            f"{name}: unknown slot length type '{mode}'. Choose another type in the property panel."
        )
    if mode == "overall":
        # Measured over the nominal hole; the fit widens both ends like the width.
        centres = span - _num(feature, "diameter", "hole diameter")
        if centres <= 1e-9:
            raise FeatureError(
                f"{name}: the overall slot length must be greater than the hole diameter. "
                "Enter a longer slot or measure it centre to centre."
            )
        return centres
    if span <= 1e-9:
        raise FeatureError(
            f"{name}: the slot length must be greater than zero. Enter a longer slot."
        )
    return span


def _start_on_plane(
    feature: Feature, ctx: BuildContext, places: list[Placement]
) -> list[Placement]:
    """Each hole moved along its axis to start on ``refs.start_plane`` (TR144 item 3,
    D1913), a plane or flat face other than the face it is placed on."""
    from fdcad.core.features.geometry_refs import resolve_placement

    ref = feature.refs["start_plane"]
    ref = ref[0] if isinstance(ref, list) and ref else ref
    plane = resolve_placement(ctx, ref, feature.name, "plane")
    out = []
    for place in places:
        across = _dot(place.direction, plane.direction)
        if abs(across) < 1e-9:
            raise FeatureError(
                f"{feature.name}: the start plane runs along the hole's axis, so the hole "
                "never meets it. Pick a plane across the hole."
            )
        t = _dot(_sub(plane.point, place.origin), plane.direction) / across
        out.append(
            Placement(place.point, _add(place.origin, place.direction, t), place.direction, False)
        )
    return out


def _custom_spec(feature: Feature, extra: float) -> _Spec:
    """A custom hole's values (TR144 item 1, D1912): the stack sets the sizes."""
    from fdcad.core.features.hole_stack import parse_stack, stack_depth

    name = feature.name
    stack = parse_stack(name, str(feature.params.get("stack", "") or ""))
    stack = [(k, r + extra / 2, v) for k, r, v in stack]
    end = str(feature.params.get("end_condition", "blind"))
    if end != "blind":
        raise FeatureError(
            f"{name}: a custom hole is as deep as its elements. Choose Blind as the end condition."
        )
    drill = feature.params.get("bottom") == "drill_point"
    tip = _opt(feature, "tip_angle", math.radians(118.0))
    top = max(_opt(feature, "head_clearance", 0.0), 0.0)
    spec = _Spec("custom", stack[-1][1], stack_depth(stack), None, drill, tip, top)
    spec.stack = tuple(stack)
    return spec


def _profile(spec: _Spec) -> list[tuple[float, float, str]]:
    """The half section as (r, z, role of the edge that ends here); z goes into the part."""
    if spec.hole_type == "custom":  # TR144 item 1 (D1912)
        from fdcad.core.features.hole_stack import stack_profile

        return stack_profile(list(spec.stack), spec.top, spec.drill_point, spec.tip_angle)
    r, z_top = spec.radius, -spec.top
    pts: list[tuple[float, float, str]] = [(0.0, z_top, "")]
    if spec.hole_type in ("counterbore", "bearing"):
        pts.append((spec.cbore_radius, z_top, "head"))
        pts.append((spec.cbore_radius, spec.cbore_depth, "cbore_wall"))
        pts.append((r, spec.cbore_depth, "cbore_floor"))
        wall_start = spec.cbore_depth
    elif spec.hole_type == "counterdrill":  # TR144 (D1506)
        pts.append((spec.cbore_radius, z_top, "head"))
        pts.append((spec.cbore_radius, spec.cbore_depth, "cbore_wall"))
        wall_start = spec.cbore_depth + _cone_drop(spec.cbore_radius, r, spec.csk_angle)
        pts.append((r, wall_start, "cdrill"))
    elif spec.csk_radius > 0:
        pts.append((spec.csk_radius, z_top, "head"))
        if z_top < 0:
            pts.append((spec.csk_radius, 0.0, "head_wall"))
        drop = _cone_drop(spec.csk_radius, r, spec.csk_angle)
        pts.append((r, drop, "csk"))
        wall_start = drop
    else:
        pts.append((r, z_top, "head"))
        wall_start = z_top
    bottom = spec.depth
    slope = math.tan(spec.taper)  # TR144 (D1505): radius lost per mm of depth
    if spec.point_inside:  # the tip, not the wall's end, reaches the depth
        k = math.tan(spec.tip_angle / 2.0)
        bottom = (spec.depth - (r + wall_start * slope) / k) / (1.0 - slope / k)
    r_end = r - (bottom - wall_start) * slope
    if r_end <= 1e-6:
        raise FeatureError(
            "The tapered hole closes before its bottom. Use a smaller taper angle or a "
            "shallower hole."
        )
    if spec.far_radius > 0 and spec.exit is not None:
        drop = _cone_drop(spec.far_radius, r, spec.far_angle)
        far_start = max(spec.exit - drop, wall_start)
        pts.append((r, far_start, "wall"))
        pts.append((spec.far_radius, spec.exit, "far_csk"))
        pts.append((spec.far_radius, bottom, "far_wall"))
        pts.append((0.0, bottom, "bottom"))
    elif spec.drill_point:
        pts.append((r_end, bottom, "wall"))
        pts.append((0.0, bottom + r_end / math.tan(spec.tip_angle / 2.0), "tip"))
    else:
        pts.append((r_end, bottom, "wall"))
        pts.append((0.0, bottom, "bottom"))
    if bottom <= wall_start + 1e-9:
        raise FeatureError(
            "The hole is shorter than its counterbore or countersink. "
            "Make the hole deeper or the head smaller."
        )
    out: list[tuple[float, float, str]] = []
    for p in pts:
        if out and abs(out[-1][0] - p[0]) < 1e-9 and abs(out[-1][1] - p[1]) < 1e-9:
            continue
        out.append(p)
    return out


def _frame(direction: Vec3, hint: Vec3) -> tuple[Vec3, Vec3]:
    """Two unit vectors square to ``direction``: the first follows ``hint``."""
    d = _unit(direction)
    h = _sub(hint, (d[0] * _dot(hint, d), d[1] * _dot(hint, d), d[2] * _dot(hint, d)))
    if math.sqrt(_dot(h, h)) < 1e-6:
        other = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
        h = _sub(other, (d[0] * _dot(other, d), d[1] * _dot(other, d), d[2] * _dot(other, d)))
    x = _unit(h)
    return x, _cross(d, x)


def _wire_face(points: list[Vec3]) -> tuple[TopoDS_Face, list[TopoDS_Edge]]:
    """A flat face through ``points`` (a closed loop), with its edges in loop order.

    The edges are taken from the made face (matched by midpoint), so the kernel's
    history of later operations knows them.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    wire = BRepBuilderAPI_MakeWire()
    mids: list[Vec3] = []
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge())
        mids.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
    face = BRepBuilderAPI_MakeFace(wire.Wire(), True).Face()
    found: list[tuple[Vec3, TopoDS_Edge]] = []
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        curve = BRepAdaptor_Curve(edge)
        m = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
        found.append(((m.X(), m.Y(), m.Z()), edge))
        explorer.Next()
    edges: list[TopoDS_Edge] = []
    for mid in mids:
        best = min(found, key=lambda item: _dot(_sub(item[0], mid), _sub(item[0], mid)))
        edges.append(best[1])
    return face, edges


def _revolved(
    prefix: str,
    place: Placement,
    spec: _Spec,
    hint: Vec3,
    angle: float = 2 * math.pi,
    start: Vec3 | None = None,
) -> NamedShape:
    """The round part of one hole as a named solid.

    ``angle`` less than a full turn starts from ``start`` (square to the axis); the
    end faces of such a part are left unnamed (a slot fuses them away).
    """
    d = _unit(place.direction)
    x = start if start is not None else _frame(d, hint)[0]
    section = _profile(spec)
    pts3 = [_add(_add(place.origin, x, r), d, z) for r, z, _role in section]
    face, edges = _wire_face(pts3)
    maker = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(*place.origin), gp_Dir(*d)), angle)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("The hole shape could not be made. Check the hole values.")
    names: list[NamedFace] = []
    roles = [role for _r, _z, role in section[1:]] + [""]
    # Edges that end on the axis make faces the kernel's history does not report;
    # those faces are matched by their height along the axis instead (D312).
    silent: list[tuple[float, str]] = []
    for i, (edge, role) in enumerate(zip(edges, roles, strict=True)):
        if not role:
            continue
        made_faces = [m for m in shape_list(maker.Generated(edge)) if m.ShapeType() == TopAbs_FACE]
        if not made_faces:
            z_mid = (section[i][1] + section[(i + 1) % len(section)][1]) / 2.0
            silent.append((z_mid, role))
        for k, made in enumerate(made_faces, start=1):
            suffix = "" if k == 1 else f"#{k}"
            names.append((f"{prefix}/{role}{suffix}", TopoDS.Face(made)))
    shape = maker.Shape()
    if silent:
        from fdcad.core.naming.names import centroid, faces_of

        ends = [maker.FirstShape(), maker.LastShape()] if angle < 2 * math.pi else []
        for face in faces_of(shape):
            if any(face.IsSame(f) for _n, f in names) or any(face.IsSame(e) for e in ends):
                continue
            height = _dot(_sub(centroid(face), place.origin), d)
            _z, role = min(silent, key=lambda item: abs(item[0] - height))
            names.append((f"{prefix}/{role}", face))
    return NamedShape(shape, restrict(names, shape, prefix))


PRINT_TOPS = ("teardrop", "flat")
BRIDGES = ("sacrificial", "stepped")
#: The layer height used when the feature has none, in mm.
DEFAULT_LAYER = 0.2


def _floor(spec: _Spec) -> float | None:
    """Where the head ends and the small bore starts, along the axis; None without a head."""
    if spec.hole_type in ("counterbore", "bearing") and spec.cbore_radius > spec.radius:
        return spec.cbore_depth
    if spec.csk_radius > spec.radius:
        return _cone_drop(spec.csk_radius, spec.radius, spec.csk_angle)
    return None


def _bridged(
    feature: Feature, prefix: str, place: Placement, spec: _Spec, hint: Vec3, tool: NamedShape
) -> NamedShape:
    """The hole tool with the bridge layers left in (see the module notes)."""
    from fdcad.core.features.booleans import boolean_named

    floor = _floor(spec)
    if floor is None:
        return tool
    layer_value = feature.params.get("bridge_layer")
    layer = (
        layer_value.value
        if isinstance(layer_value, Param) and layer_value.value > 0
        else DEFAULT_LAYER
    )
    layers = 1 if feature.params.get("print_bridge") == "sacrificial" else 2
    if floor + layers * layer >= spec.depth - 1e-6:
        raise FeatureError(
            "The bridge layers fill the whole small bore. Make the hole deeper or the layer "
            "height smaller."
        )
    d = _unit(place.direction)
    x, y = _frame(d, hint)
    big = max(spec.cbore_radius, spec.csk_radius) + 1.0

    def square(half_x: float, half_y: float, z0: float, z1: float, role: str) -> NamedShape:
        c = _add(place.origin, d, z0)
        corners = [
            _add(_add(c, x, sx * half_x), y, sy * half_y)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]
        return _prism(prefix, role, corners, _scale(d, z1 - z0))

    keep = square(big, big, floor, floor + layers * layer, "bridge_layer")
    out = boolean_named("cut", tool, NamedShape(keep.shape, []), prefix, feature.name, unify=False)
    if layers == 2:
        head = max(spec.cbore_radius, spec.csk_radius)
        slot = square(head, spec.radius, floor, floor + layer, "bridge_slot")
        out = boolean_named("fuse", out, slot, prefix, feature.name, unify=False)
        step = square(spec.radius, spec.radius, floor + layer, floor + 2 * layer, "bridge_square")
        out = boolean_named("fuse", out, step, prefix, feature.name, unify=False)
    return out


def print_up(ctx: BuildContext) -> Vec3:
    """The printer's up in model coordinates: +Z, or off the bed face when one is laid
    flat (TR175). A bed face that cannot be found gives +Z."""
    setup = ctx.document.print_setup if isinstance(ctx.document.print_setup, dict) else {}
    ref = setup.get("down_face")
    if isinstance(ref, dict) and ctx.body is not None:
        try:
            from fdcad.core.naming.resolve import resolve_face

            face, _issues = resolve_face(ctx.body, ref, "")
            from fdcad.core.features.face_picks import outward_normal as plane_normal

            n = plane_normal(face)
            if n is not None:
                return (-n[0], -n[1], -n[2])
        except FeatureError:
            pass
    return (0.0, 0.0, 1.0)


def _print_top(
    feature: Feature, ctx: BuildContext, prefix: str, place: Placement, spec: _Spec
) -> NamedShape | None:
    """The pointed or flat top that lets a sideways hole print without supports."""
    kind = feature.params.get("print_top")
    if kind not in PRINT_TOPS:
        return None
    start = _add(place.origin, _unit(place.direction), -spec.top)
    return top_prism(
        prefix, start, place.direction, spec.radius, spec.top + spec.depth, print_up(ctx), kind
    )


def top_prism(
    prefix: str, start: Vec3, direction: Vec3, r: float, length: float, up: Vec3, kind: str
) -> NamedShape | None:
    """The pointed (``teardrop``) or ``flat`` top of a round hole of radius ``r`` running
    ``length`` from ``start`` along ``direction``; None when it runs along ``up``. Also
    used by Extruded Cut (TR175)."""
    d = _unit(direction)
    across = _add(up, d, -_dot(up, d))  # up, square to the hole's axis
    size = math.sqrt(_dot(across, across))
    if size < 0.1:  # the hole runs (nearly) along up: its top is not overhanging
        return None
    u = _scale(across, 1 / size)
    w = _cross(d, u)
    c45 = math.sqrt(0.5)
    t1 = _add(_scale(u, r * c45), w, r * c45)
    t2 = _add(_scale(u, r * c45), w, -r * c45)
    apex = _scale(u, r * math.sqrt(2.0))
    if kind == "teardrop":
        section = [(0.0, 0.0, 0.0), t1, apex, t2]
    else:
        s = (r - r * c45) / (r * math.sqrt(2.0) - r * c45)
        f1 = _add(t1, _sub(apex, t1), s)
        f2 = _add(t2, _sub(apex, t2), s)
        section = [(0.0, 0.0, 0.0), t1, f1, f2, t2]
    outline = [_add(start, p) for p in section]
    return _prism(prefix, "top", outline, _scale(d, length))


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _prism(
    prefix: str, role: str, outline: list[Vec3], vector: Vec3, floor: str = ""
) -> NamedShape:
    """A prism from a closed outline along ``vector``, its sides named ``role/<k>``."""
    face, edges = _wire_face(outline)
    maker = BRepPrimAPI_MakePrism(face, gp_Vec(*vector))
    maker.Build()
    names: list[NamedFace] = []
    for k, edge in enumerate(edges, start=1):
        for made in shape_list(maker.Generated(edge)):
            if made.ShapeType() == TopAbs_FACE:
                names.append((f"{prefix}/{role}/{k}", TopoDS.Face(made)))
    if floor:
        names.append((f"{prefix}/{floor}", TopoDS.Face(maker.LastShape())))
    shape = maker.Shape()
    return NamedShape(shape, restrict(names, shape, prefix))


def _hexagon(centre: Vec3, x: Vec3, y: Vec3, flats: float, angle: float) -> list[Vec3]:
    """Corners of a hexagon with ``flats`` across flats; a corner points along ``angle``."""
    radius = flats / math.sqrt(3.0)
    out = []
    for k in range(6):
        a = angle + k * math.pi / 3.0
        out.append(_add(_add(centre, x, radius * math.cos(a)), y, radius * math.sin(a)))
    return out


def _nut_tools(prefix: str, place: Placement, spec: _Spec, hint: Vec3) -> list[NamedShape]:
    """The hexagonal pocket of a nut trap, or the hexagon and slot of a nut slot."""
    d = _unit(place.direction)
    x, y = _frame(d, hint)
    if spec.hole_type == "nut_trap":
        top = _add(place.origin, d, -spec.top)
        hexagon = _hexagon(top, x, y, spec.nut_flats, spec.nut_angle)
        height = spec.top + spec.nut_height
        return [_prism(prefix, "hex", hexagon, _add((0, 0, 0), d, height), "hex/floor")]
    top = _add(place.origin, d, spec.slot_offset)
    vector = _add((0.0, 0.0, 0.0), d, spec.nut_height)
    hexagon = _hexagon(top, x, y, spec.nut_flats, spec.nut_angle)
    along = _add(_add((0.0, 0.0, 0.0), x, math.cos(spec.nut_angle)), y, math.sin(spec.nut_angle))
    side = _cross(d, along)
    half = spec.nut_flats / 2.0
    slot = [
        _add(top, side, half),
        _add(_add(top, along, spec.slot_length), side, half),
        _add(_add(top, along, spec.slot_length), side, -half),
        _add(top, side, -half),
    ]
    return [
        _prism(prefix, "hex", hexagon, vector),
        _prism(prefix, "slot", slot, vector),
    ]


def _slot_axis(place: Placement, spec: _Spec, plane: SketchPlane) -> Vec3:
    """Unit vector along a slot: the sketch X axis turned by the slot angle, square to the hole."""
    ax = plane.ax3()
    xd, yd = ax.XDirection(), ax.YDirection()
    c, s = math.cos(spec.slot_angle), math.sin(spec.slot_angle)
    along = (c * xd.X() + s * yd.X(), c * xd.Y() + s * yd.Y(), c * xd.Z() + s * yd.Z())
    d = _unit(place.direction)
    flat = _add(along, d, -_dot(along, d))
    if math.sqrt(_dot(flat, flat)) < 1e-6:
        raise FeatureError(
            f"the slot at point {place.point} runs along the hole axis. Change the slot angle."
        )
    return _unit(flat)


def _side(a: tuple[float, float, str], b: tuple[float, float, str], side: str) -> str:
    """The side tag of a slot edge: none for a flat edge across the slot."""
    return "" if abs(a[1] - b[1]) < 1e-12 else side


def _slot_section(spec: _Spec) -> tuple[list[tuple[float, float]], list[tuple[str, str]]]:
    """The whole section across a slot, as (r, z) corners and (role, side) of each edge.

    The hole's half section goes down one side (``side1``, r > 0) and back up the
    mirrored side (``side2``). Flat edges (heads and floors) have no side, and
    the two that meet on the axis are joined into one edge across the slot.
    """
    half = _profile(spec)
    n = len(half)
    corners = [(r, z) for r, z, _role in half]
    corners += [(-half[i][0], half[i][1]) for i in range(n - 2, 0, -1)]
    tags = [(half[i][2], _side(half[i - 1], half[i], "side1")) for i in range(1, n)]
    tags += [(half[i][2], _side(half[i - 1], half[i], "side2")) for i in range(n - 1, 0, -1)]
    # Edge k runs from corner k to corner k + 1; corners 0 and n - 1 lie on the axis.
    for at in (n - 1, 0):
        before = (at - 1) % len(corners)
        a, b, c = corners[before], corners[at], corners[(at + 1) % len(corners)]
        straight = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-12
        if straight and tags[before][0] == tags[at][0]:
            tags[before] = (tags[before][0], "")
            del corners[at]
            del tags[at]
    return corners, tags


def _slot(prefix: str, place: Placement, spec: _Spec, plane: SketchPlane) -> NamedShape:
    """One slot hole: the section swept between the end centres plus two half turned ends."""
    from fdcad.core.occ import BRepAlgoAPI_Fuse

    d = _unit(place.direction)
    along = _slot_axis(place, spec, plane)
    side = _cross(d, along)  # turning ``side`` a quarter turn about d gives -along
    h = spec.slot_half
    first = _add(place.origin, along, -h)
    second = _add(place.origin, along, h)
    corners, tags = _slot_section(spec)
    outline = [_add(_add(first, side, r), d, z) for r, z in corners]
    face, edges = _wire_face(outline)
    maker = BRepPrimAPI_MakePrism(face, gp_Vec(*_add((0.0, 0.0, 0.0), along, 2 * h)))
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("The slot shape could not be made. Check the hole values.")
    names: list[NamedFace] = []
    across: set[str] = set()
    for edge, (role, where) in zip(edges, tags, strict=True):
        if not role:
            continue
        if not where:
            across.add(role)
        for made in shape_list(maker.Generated(edge)):
            if made.ShapeType() == TopAbs_FACE:
                label = f"{prefix}/{role}/{where}" if where else f"{prefix}/{role}"
                names.append((label, TopoDS.Face(made)))
    middle = NamedShape(maker.Shape(), names)
    ends: list[NamedShape] = []
    back = (-side[0], -side[1], -side[2])
    for k, (centre, start) in enumerate(((first, side), (second, back)), start=1):
        at = Placement(place.point, centre, d, place.curved)
        piece = _revolved(prefix, at, spec, start, math.pi, start)
        renamed: list[NamedFace] = []
        for label, f in piece.faces:
            role = label[len(prefix) + 1 :]
            renamed.append((label if role in across else f"{label}/end{k}", f))
        ends.append(NamedShape(piece.shape, renamed))
    fuse = BRepAlgoAPI_Fuse()
    args, others = ShapeList(), ShapeList()
    args.Append(middle.shape)
    for e in ends:
        others.Append(e.shape)
    fuse.SetArguments(args)
    fuse.SetTools(others)
    fuse.SetFuzzyValue(FUZZY_TOLERANCE)
    fuse.SetToFillHistory(True)
    fuse.Build()
    if not fuse.IsDone():
        raise FeatureError("The slot shape could not be made. Check the hole values.")
    named = carry(middle.faces + [f for e in ends for f in e.faces], fuse.History())
    from fdcad.core.unify import unify_faces

    shape, history = unify_faces(fuse.Shape())
    if len(solids(shape)) != 1:
        raise FeatureError("The slot shape could not be made. Check the hole values.")
    if history is not None:
        named = carry(named, history)
    return NamedShape(shape, restrict(named, shape, prefix))


def _through(body: NamedShape, place: Placement) -> tuple[float, float | None]:
    """Through All depth and where the axis leaves the part (for the far countersink)."""
    size = bounding_size(body.shape)
    hits = [h for h in line_hits(body.shape, place.origin, place.direction) if h[0] > 1e-6]
    exit_at = hits[-1][0] if hits else None
    return 2.0 * size + 1.0, exit_at


def _up_to(feature: Feature, face: TopoDS_Face, place: Placement) -> float:
    """Depth from the start point to the Up to Face face along the hole axis."""
    hits = [h for h in line_hits(face, place.origin, place.direction) if h[0] > 1e-6]
    if not hits:
        raise FeatureError(
            f"{feature.name}: the hole at point {place.point} does not reach the Up to "
            "Face face. Pick a face the hole axis meets."
        )
    return hits[0][0]


def _up_to_next(feature: Feature, body: NamedShape, place: Placement) -> float:
    """Depth to where the hole axis first comes out of the material (Up to Next)."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN

    hits = [h[0] for h in line_hits(body.shape, place.origin, place.direction) if h[0] > 1e-6]
    parts = solids(body.shape)
    o, d = place.origin, place.direction
    before = 0.0
    for t in hits:
        mid = (before + t) / 2
        p = gp_Pnt(o[0] + d[0] * mid, o[1] + d[1] * mid, o[2] + d[2] * mid)
        for solid in parts:
            if BRepClass3d_SolidClassifier(solid, p, 1e-7).State() == TopAbs_IN:
                return t
        before = t
    raise FeatureError(
        f"{feature.name}: the hole at point {place.point} finds no face to stop at. "
        "Choose Blind or Through All."
    )


def _up_to_vertex(feature: Feature, ctx: BuildContext) -> Vec3:
    """The Up to Vertex point: ``refs.up_to_vertex``, a vertex reference or a sketch point."""
    from fdcad.core.features.extrude_end import end_vertex

    ref = feature.refs.get("up_to_vertex")
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    if not isinstance(ref, dict):
        raise FeatureError(
            f"{feature.name}: Up to Vertex needs a vertex. Pick a vertex or a sketch point."
        )
    try:
        point, _issues = end_vertex(feature, ctx, ref)
    except FeatureError as exc:
        raise FeatureError(
            f"{feature.name}: the Up to Vertex point was lost. Pick the vertex again."
        ) from exc
    return point


def _vertex_depth(feature: Feature, vertex: Vec3, place: Placement) -> float:
    """Depth along the hole axis to the level of ``vertex``."""
    rel = _sub(vertex, place.origin)
    depth = _dot(rel, place.direction)
    if depth <= 1e-6:
        raise FeatureError(
            f"{feature.name}: the vertex is not below the start of the hole at point "
            f"{place.point}. Pick a vertex inside the part or choose Blind."
        )
    return depth


def _sketch_output(feature: Feature, ctx: BuildContext) -> SketchOutput:
    """The position sketch: an existing sketch, or the hole's own points (D312)."""
    ref = feature.refs.get("sketch")
    if isinstance(ref, dict) and "feature" in ref:
        out = ctx.result(str(ref["feature"])).sketch
        if out is None:
            raise FeatureError(
                f"{feature.name}: the position feature is not a sketch. "
                "Pick a sketch for the positions."
            )
        return out
    plane_ref = feature.refs.get("plane")
    data = feature.data.get("positions")
    from fdcad.core.features.hole_place import placed_point, places

    if places(feature) and isinstance(plane_ref, dict):  # TR143 item 1 (D1911)
        from fdcad.core.features.sketch import plane_of as _plane_of
        from fdcad.core.sketch.solver import solve as _solve

        placed_plane, _found = _plane_of(plane_ref, ctx, feature.name)
        u, v = placed_point(feature, ctx, placed_plane)
        model = Sketch()
        model.add_point(u, v)
        return SketchOutput(placed_plane, model, _solve(model), None)
    if not isinstance(plane_ref, dict) or not isinstance(data, dict):
        raise FeatureError(
            f"{feature.name} has no hole positions. Place holes on the Positions tab."
        )
    from fdcad.core.features.sketch import plane_of
    from fdcad.core.sketch.model import sketch_from_data
    from fdcad.core.sketch.solver import solve

    plane, _issues = plane_of(plane_ref, ctx, feature.name)
    try:
        model = sketch_from_data(data)
        solved = solve(model)
    except Exception as exc:
        raise FeatureError(
            f"{feature.name}: the hole positions cannot be read. Pick the positions again."
        ) from exc
    return SketchOutput(plane, model, solved, None)


def own_positions(points: list[tuple[float, float]]) -> dict[str, Any]:
    """``data.positions`` for the hole's own points (sketch coordinates in mm)."""
    from fdcad.core.sketch.model import sketch_to_data

    model = Sketch()
    for x, y in points:
        model.add_point(x, y)
    return sketch_to_data(model)


@register
class Hole(FeatureType):
    """Holes of one type at every position point, cut in one boolean."""

    type_name = "hole"
    makes_solid = True
    pattern_operation = "cut"  # a bolt circle patterns the hole feature
    params = (
        ParamSpec("hole_type", choices=hole_data.HOLE_TYPES, default="simple"),
        ParamSpec(  # TR143 (D1911): how the panel places the hole; the refs decide
            "place_by", choices=("points", "edges", "concentric", "radial", "point"), optional=True
        ),
        ParamSpec("stack", optional=True),  # TR144 (D1912): a custom hole's elements
        ParamSpec("thread_relief", default=False, optional=True),  # TR256 (D1922)
        ParamSpec("thread_chamfer", default=False, optional=True),
        ParamSpec("radial_distance", kind=Kind.LENGTH, optional=True),  # TR397 (D1915)
        ParamSpec("radial_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("place_distance1", kind=Kind.LENGTH, optional=True),  # TR143 (D1911)
        ParamSpec("place_distance2", kind=Kind.LENGTH, optional=True),
        ParamSpec("diameter", kind=Kind.LENGTH, optional=True),  # a custom hole has none
        ParamSpec("end_condition", choices=END_CONDITIONS, default="blind"),
        ParamSpec("print_top", choices=("none", *PRINT_TOPS), optional=True),  # TR175
        ParamSpec("cbore_head", choices=hole_heads.CBORE_HEADS, optional=True),  # TR253
        ParamSpec("csk_head", choices=hole_heads.CSK_HEADS, optional=True),
        ParamSpec("print_bridge", choices=("none", *BRIDGES), optional=True),  # TR176
        ParamSpec("bridge_layer", kind=Kind.LENGTH, optional=True),
    )

    def kind_of(self, name: str) -> Kind | None:
        """Every number is a length except the angles."""
        if name.endswith("_angle"):
            return Kind.ANGLE
        if name in (
            "depth",
            "cbore_diameter",
            "cbore_depth",
            "csk_diameter",
            "near_csk_diameter",
            "far_csk_diameter",
            "head_clearance",
            "thread_depth",
            "thread_diameter",
            "pitch",
            "nut_flats",
            "nut_height",
            "slot_offset",
            "slot_length",
            "slot_span",
            "fit_tolerance",
        ):
            return Kind.LENGTH
        return super().kind_of(name)

    def validate(self, feature: Feature) -> None:
        """Check the choices and every value the type needs."""
        super().validate(feature)
        hole_spec(feature)

    def _tools(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[NamedShape], list[Issue], list[Placement]]:
        body = require_body(feature, ctx)
        spec = hole_spec(feature)
        sketch = _sketch_output(feature, ctx)
        issues: list[Issue] = []
        face: TopoDS_Face | None = None
        if feature.refs.get("face"):
            picked, found = resolve_faces(feature, ctx, "face")
            issues += found
            face = picked[0][1]
        end = str(feature.params.get("end_condition", "blind"))
        up_to: TopoDS_Face | None = None
        if end == "up_to_face":
            picked, found = resolve_faces(feature, ctx, "up_to", required=False)
            if not picked:
                raise FeatureError(
                    f"{feature.name}: Up to Face needs a face. Pick the face to stop at."
                )
            issues += found
            up_to = picked[0][1]
        vertex = _up_to_vertex(feature, ctx) if end == "up_to_vertex" else None
        tools: list[NamedShape] = []
        places = placements(feature, sketch, face)
        if feature.refs.get("hole_axis"):  # TR397 item 1 (D1915): not square to the face
            from fdcad.core.features.hole_place import hole_axis

            places = hole_axis(feature, ctx, places)
        if feature.refs.get("start_plane"):  # TR144 item 3 (D1913)
            places = _start_on_plane(feature, ctx, places)
        for place in places:
            prefix = f"{feature.id}/hole/{place.point}"
            one = _Spec(**{**spec.__dict__})
            if place.curved:
                # Carry the head up over the curve so it cuts cleanly (D312).
                one.top = max(one.top, max(one.radius, one.cbore_radius, one.csk_radius))
            if end == "through_all":
                one.depth, one.exit = _through(body, place)
                if one.far_radius > 0 and one.exit is None:
                    raise FeatureError(
                        f"{feature.name}: the hole at {place.point} misses the part. "
                        "Move the position onto the part."
                    )
            elif end == "up_to_face":
                assert up_to is not None
                one.depth = _up_to(feature, up_to, place)
            elif end == "up_to_next":
                one.depth = _up_to_next(feature, body, place)
            elif end == "up_to_vertex":
                assert vertex is not None
                one.depth = _vertex_depth(feature, vertex, place)
            try:
                if one.slot_half > 0:
                    tools.append(_slot(prefix, place, one, sketch.plane))
                elif one.hole_type == "magnet" and one.magnet_length > 0:
                    tools.extend(_magnet_tools(prefix, place, one, sketch.plane.x_dir))
                else:
                    tools.append(_revolved(prefix, place, one, sketch.plane.x_dir))
                    top = _print_top(feature, ctx, prefix, place, one)
                    if top is not None:
                        tools.append(top)
                    if feature.params.get("print_bridge") in BRIDGES:
                        tools[-1 if top is None else -2] = _bridged(
                            feature,
                            prefix,
                            place,
                            one,
                            sketch.plane.x_dir,
                            tools[-1 if top is None else -2],
                        )
                if one.hole_type in ("nut_trap", "nut_slot"):
                    tools.extend(_nut_tools(prefix, place, one, sketch.plane.x_dir))
                if one.hole_type == "magnet" and one.magnet_length == 0:
                    tools.extend(_magnet_tools(prefix, place, one, sketch.plane.x_dir))
                if one.groove_width > 0:
                    tools.append(_groove(prefix, place, one, sketch.plane.x_dir))
            except FeatureError as exc:
                raise FeatureError(f"{feature.name}: {exc}") from exc
            except Exception as exc:
                raise FeatureError(
                    f"{feature.name} failed: the hole at point {place.point} could not be made. "
                    "Check the hole values."
                ) from exc
        return tools, issues, places

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut every hole from the part in one boolean."""
        body = require_body(feature, ctx)
        tools, issues, places = self._tools(feature, ctx)
        if feature.params.get("hole_type") == "heat_set_insert" and fit_extra(feature) > 0:
            # Spec 2 section 20 item 18 (D714): a fit makes an insert's hole looser.
            issues = [
                *issues,
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: Print Fit makes the heat set insert's hole wider, so the "
                    "insert may not grip. Set Print Fit to None unless your printer prints "
                    "holes small.",
                    code="insert_fit",
                ),
            ]
        if feature.params.get("slot") is True and not slot_on(feature):
            # Slot stays ticked when the type changes; say it is not used (audit A item 18).
            issues = [
                *issues,
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: this hole type cannot be a slot, so Slot is not used. "
                    "Choose Simple, Counterbore or Countersink for a slot, or untick Slot.",
                    code="slot_ignored",
                ),
            ]
        try:
            if feature.params.get("bodies_scope", "all") == "selected":
                from fdcad.core.features.bodies import scoped

                result, picked = scoped(feature, ctx, lambda part: cut_all(feature, part, tools))
                issues = [*issues, *picked]
            else:
                result = cut_all(feature, body, tools)
        except FeatureError as exc:  # TR400 (D2109): name the holes that fail
            from fdcad.core.features import partial

            points = [place.point for place in places] if len(places) == len(tools) else []
            failed = partial.failing_points(
                feature, points, lambda i: cut_all(feature, body, [tools[i]])
            )
            if failed is None:
                raise
            raise partial.skip_error(feature, failed, exc) from exc
        if feature.params.get("hole_type") == "tapped" and feature.params.get("thread_relief"):
            rings = _relief_rings(feature, places)  # TR256 (D1922)
            groove = compound(rings)
            named = NamedShape(groove, restrict([], groove, f"{feature.id}/relief"))
            from fdcad.core.features.solids import combine

            result = combine(feature.id, feature.name, result, named, "cut")
        modelled = feature.params.get("modeled_thread") and not ctx.simplify_threads  # TR347
        if feature.params.get("hole_type") == "tapped" and modelled:
            from fdcad.core.features.modeled_thread import hole_threads

            wall = _num(feature, "diameter", "hole diameter") + fit_extra(feature)
            result = hole_threads(feature, result, places, wall)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(
            body=result,
            issues=issues,
            threads=thread_marks(feature, places, shown=bool(ctx.simplify_threads), body=body),
            # TR316 hole table; TR397 (D1508): "count@Hole 1" for formulas.
            extras={"holes": [place.origin for place in places], "count": len(places)},
        )

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The hole shapes, for the preview."""
        tools, _issues, _places = self._tools(feature, ctx)
        return NamedShape(compound([t.shape for t in tools]), [])


def material_depth(shape: TopoDS_Shape, origin: Vec3, direction: Vec3) -> float | None:
    """How far the material goes on from ``origin`` along ``direction``: the distance
    to where the line first leaves ``shape``. None when it does not cross it again."""
    exits = [hit[0] for hit in line_hits(shape, origin, direction) if hit[0] > 1e-4]
    return min(exits) if exits else None


def thread_marks(
    feature: Feature,
    places: list[Placement],
    shown: bool = False,
    body: NamedShape | None = None,
) -> list[ThreadMark]:
    """Cosmetic thread marks of a tapped hole with ``cosmetic_thread`` (P4.2), or with a
    modelled thread shown as cosmetic while editing (``shown``, TR347, D1921).

    With ``body`` (the part before the holes were cut) a mark is no longer than the
    material its hole goes through (D1050): an M10 thread 20 mm deep in a 6 mm plate
    was drawn 14 mm out into the air behind the plate.
    """
    if feature.params.get("hole_type") not in ("tapped", "pipe_tapped") or (
        feature.params.get("cosmetic_thread") is not True and not shown
    ):
        return []
    from fdcad.core.features.cosmetic_thread import basic_major, hole_marks

    wall = _opt(feature, "diameter", 0.0) + fit_extra(feature)
    pitch = _opt(feature, "pitch", 0.0)
    major = _opt(feature, "thread_diameter", basic_major(wall, pitch))
    length = _opt(feature, "thread_depth", 0.0)
    size = str(feature.params.get("size", ""))
    out = []
    for p in places:
        own = length
        if body is not None:
            reach = material_depth(body.shape, p.origin, p.direction)
            if reach is not None:
                own = min(length, reach)
        out.append(hole_marks(p.origin, p.direction, wall, major, pitch, own, size))
    return out


def cut_all(feature: Feature, body: NamedShape, tools: list[NamedShape]) -> NamedShape:
    """Cut every tool from ``body`` in one boolean, names carried from both (5A.5).
    A part of several bodies is cut one body at a time (D1056, ``solids.each_body``)."""
    if len(solids(body.shape)) > 1:
        from fdcad.core.features.solids import each_body

        return each_body(
            feature.id, body, [t.shape for t in tools],
            lambda sub: cut_all(feature, sub, tools),
            f"{feature.name} removes the whole part. Make the holes smaller.",
        )  # fmt: skip
    op = BRepAlgoAPI_Cut()
    args, tool_list = ShapeList(), ShapeList()
    args.Append(body.shape)
    for t in tools:
        tool_list.Append(t.shape)
    op.SetArguments(args)
    op.SetTools(tool_list)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.SetRunParallel(True)
    op.SetToFillHistory(True)
    try:
        op.Build()
    except Exception as exc:
        raise FeatureError(
            f"{feature.name} failed: the kernel could not cut it from the part. "
            "Move the holes slightly so faces do not almost touch."
        ) from exc
    if not op.IsDone():
        raise FeatureError(
            f"{feature.name} failed: the kernel could not cut it from the part. "
            "Move the holes slightly so faces do not almost touch."
        )
    names = carry(body.faces + [f for t in tools for f in t.faces], op.History())
    shape = op.Shape()
    if not solids(shape):
        from fdcad.core.features.solids import WholeBodyCutError

        raise WholeBodyCutError(f"{feature.name} removes the whole part. Make the holes smaller.")
    return NamedShape(shape, restrict(names, shape, feature.id))


def defaults_for(
    hole_type: str,
    standard: str,
    size: str,
    purpose: str = "clearance",
    fit: str = "normal",
    inserts: list[hole_data.InsertSize] | None = None,
    head: str = "",
) -> dict[str, float]:
    """Table values for a hole type and size, in mm and radians (the panel fills them in).

    Unknown sizes give an empty dict.
    """
    out: dict[str, float] = {}
    if hole_type == "heat_set_insert":
        for row in inserts if inserts is not None else list(hole_data.INSERTS):
            if row.name == size:
                return {"diameter": row.diameter, "depth": row.depth}
        return out
    if hole_type == "pipe_tapped":  # TR145 (D1511): the hole tapers to the drill
        for pipe in hole_data.pipe_sizes(standard):
            if pipe.name == size:
                return {
                    "diameter": round(pipe.drill + pipe.length * hole_data.PIPE_TAPER, 4),
                    "depth": pipe.length,
                    "thread_depth": pipe.length,
                    "thread_diameter": round(pipe.major, 4),
                    "pitch": round(pipe.pitch, 4),
                }
        return out
    if hole_type == "bearing":  # TR251: ``purpose`` is the fit, press or slip
        bearing = hole_data.BEARINGS.get(size)
        if bearing is None:
            return out
        bore, outer, width = bearing
        extra = hole_data.DOWEL_SLIP if purpose == "slip" else 0.0
        shoulder = round((bore + outer) / 2, 4)
        return {
            "cbore_diameter": round(outer + extra, 4),
            "cbore_depth": width,
            "bearing_width": width,
            "diameter": shoulder,
            "depth": round(width + max(1.0, 0.25 * width), 4),
        }
    if hole_type == "dowel":  # TR252: ``purpose`` is the dowel fit here
        nominal = hole_data.dowel_size(standard, size)
        if nominal is None:
            return out
        extra = hole_data.DOWEL_SLIP if purpose == "slip" else 0.0
        return {"diameter": round(nominal + extra, 4), "depth": round(1.5 * nominal, 4)}
    if hole_type == "magnet":  # TR179
        magnet = hole_data.MAGNETS.get(size)
        if magnet is None:
            return out
        return {"diameter": magnet[0], "magnet_length": magnet[1], "depth": magnet[2]}
    if hole_type == "self_tapping":  # TR255: ``inserts`` is the self tapping table here
        for row in inserts if inserts is not None else list(hole_data.SELF_TAPPING):
            if row.name == size:
                return {
                    "diameter": row.diameter,
                    "depth": row.depth,
                    "near_csk_diameter": round(row.diameter * hole_data.SELF_TAP_BEVEL, 4),
                    "near_csk_angle": math.radians(90.0),
                }
        return out
    screw = hole_data.find(standard, size)
    if screw is None:
        return out
    clearance = screw.clearance[hole_data.FITS.index(fit) if fit in hole_data.FITS else 1]
    if hole_type == "tapped":
        out["diameter"] = screw.tap_drill
        out["thread_diameter"] = screw.diameter
        out["pitch"] = screw.pitch
        out["thread_depth"] = round(2.0 * screw.diameter, 4)
        out["depth"] = round(2.0 * screw.diameter + 3.0 * screw.pitch, 4)
        return out
    if hole_type == "simple":
        out["diameter"] = {
            "drill": screw.diameter,
            "tap_drill": screw.tap_drill,
        }.get(purpose, clearance)
        return out
    out["diameter"] = clearance
    if hole_type in ("counterbore", "counterdrill"):
        cbore = hole_data.counterbore(screw, head or "socket")
        if cbore is not None:  # a head the standard has no size for keeps the typed values
            out["cbore_diameter"], out["cbore_depth"] = cbore
        if hole_type == "counterdrill":  # TR144 (D1506): a drill's point at the floor
            out["cdrill_angle"] = math.radians(118.0)
    elif hole_type == "countersink":
        from fdcad.core.features.hole_heads import recessed_csk

        recessed = recessed_csk(screw.name) if head == "recessed" else None
        if head != "recessed" or recessed is not None:
            out["csk_diameter"] = recessed if recessed is not None else screw.csk_diameter
            out["csk_angle"] = math.radians(hole_data.CSK_ANGLE.get(standard, 90.0))
    elif hole_type in ("nut_trap", "nut_slot"):
        out["nut_flats"] = screw.nut_flats
        out["nut_height"] = screw.nut_height
        if hole_type == "nut_slot":
            out["slot_offset"] = round(screw.diameter, 4)
            out["slot_length"] = round(2.0 * screw.nut_flats, 4)
    return out


def sketch_points_used(feature: Feature, sketch: Sketch) -> int:
    """How many holes the feature makes from ``sketch`` (for the panel)."""
    return len(position_points(feature, sketch))
