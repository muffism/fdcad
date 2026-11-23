"""Sketch entities, relations and dimensions as stored in `.fdef` (FDEF_SPEC section 6).

Coordinates are millimetres in the sketch plane's local system and hold the
last solved position. Entity ids are ``e`` plus a number and are never reused.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fdcad.core.document.model import Param
from fdcad.core.sketch.picture import Picture, picture_from_json, picture_to_json

if TYPE_CHECKING:
    from fdcad.core.sketch.text import SketchText

RELATION_TYPES = (
    "horizontal",
    "vertical",
    "coincident",
    "collinear",
    "parallel",
    "perpendicular",
    "tangent",
    "concentric",
    "equal",
    "midpoint",
    "symmetric",
    "coradial",
    "intersection",
    "fixed",
    "offset",
    # TR342 (D1311): a point on a line between its ends.
    "on_segment",
    # TR226 (D870): value relations between lengths, and equal angle or distance.
    "length_ratio",
    "length_difference",
    "equal_angle",
    "equal_distance",
)
#: Relations that carry a value in ``Relation.value`` set by the user (TR226).
VALUE_RELATIONS = ("length_ratio", "length_difference")
DIMENSION_TYPES = (
    "distance",
    "horizontal_distance",
    "vertical_distance",
    "angle",
    "radius",
    "diameter",
    "doubled_distance",
    "arc_length",  # Phase 2 addition (DECISIONS D515)
    "path_length",  # TR45 (D1307): the total length of a chain of lines and arcs
)
#: Limit dimensions (TR342, D1311).
LIMITS = ("min", "max")
#: Where a distance meets a circle or arc picked with it (TOOL_SPEC T4.3): the default,
#: the centre, needs no entry.
MEASURE_TO = ("nearest", "farthest")


@dataclass
class Point:
    """A sketch point. Lines, circles and arcs refer to points by id."""

    id: str
    x: float
    y: float
    construction: bool = False
    #: Part geometry this fixed copy was made from (FDEF_SPEC 6 item 9), or None.
    source: dict[str, Any] | None = None


@dataclass
class Line:
    """A straight segment between two points."""

    id: str
    p1: str
    p2: str
    construction: bool = False
    #: Part geometry this fixed copy was made from (FDEF_SPEC 6 item 9), or None.
    source: dict[str, Any] | None = None


@dataclass
class Circle:
    """A full circle around a center point."""

    id: str
    center: str
    radius: float
    construction: bool = False
    #: Part geometry this fixed copy was made from (FDEF_SPEC 6 item 9), or None.
    source: dict[str, Any] | None = None


@dataclass
class Arc:
    """A circular arc. ``ccw`` is True when it runs counter clockwise from start to end."""

    id: str
    center: str
    start: str
    end: str
    ccw: bool = True
    construction: bool = False


@dataclass
class Ellipse:
    """A full ellipse: its centre, the end of its major axis and the end of its minor
    axis, all point ids (PHASE2_SPEC P2.8 item 13, DECISIONS D278)."""

    id: str
    center: str
    major: str
    minor: str
    construction: bool = False


@dataclass
class EllipseArc:
    """A partial ellipse: an ellipse as above, run counter clockwise from ``start`` to
    ``end`` (point ids on the ellipse)."""

    id: str
    center: str
    major: str
    minor: str
    start: str
    end: str
    construction: bool = False


@dataclass
class Spline:
    """A smooth curve through ``points`` (PHASE2_SPEC P2.8 item 10, D278).

    ``handles`` holds one point per through point: the tangent handle's end. The
    curve leaves each point toward its handle and arrives from the mirrored side.
    """

    id: str
    points: list[str]
    handles: list[str]
    construction: bool = False


Entity = Point | Line | Circle | Arc | Ellipse | EllipseArc | Spline
Curve = Line | Circle | Arc | Ellipse | EllipseArc | Spline
#: Curves the Phase 1 code works on (exact line and circle formulas).
Basic = Line | Circle | Arc
#: Curves added in Phase 2 that the solver and kernel handle, but not Trim and regions.
Freeform = Ellipse | EllipseArc | Spline


@dataclass
class Relation:
    """A geometric relation, such as horizontal or tangent, between entities.

    ``value`` is used by ``offset`` (the offset distance in mm, or None when a
    dimension sets it, DECISIONS D272), ``length_ratio`` (A over B) and
    ``length_difference`` (A minus B, in mm) (TR226, D870).
    """

    type: str
    entities: list[str]
    value: float | None = None
    #: Switched off (TR109, D829): kept and drawn greyed, but the solver ignores it.
    off: bool = False
    #: Added automatically while drawing (TR362, D1310): a relation the user adds
    #: later that conflicts with it replaces it instead of over defining the sketch.
    weak: bool = False


@dataclass
class Dimension:
    """A dimension. Driving dimensions control geometry; driven ones only measure it.

    ``measure_to`` maps a circle or arc of a distance to ``nearest`` or ``farthest``
    (a distance to a circle's centre names the centre point instead). For angles,
    ``supplement`` says which of the angles between two lines is measured: False for
    the angle between their directions, True for the one beside it, None for
    dimensions saved before this was stored (either, whichever is closer).
    ``label`` is where the user put the dimension text: an offset in millimetres
    from the dimension's anchor (FDEF_SPEC 6 item 5), or None to place it
    automatically.
    """

    id: str
    type: str
    entities: list[str]
    param: Param
    driving: bool = True
    measure_to: dict[str, str] = field(default_factory=dict)
    supplement: bool | None = None
    label: tuple[float, float] | None = None
    #: The user's name for the dimension in formulas (TR32), or None for ``d<n>``.
    name: str | None = None
    #: Which side a horizontal or vertical distance keeps (TR337, D770): +1 or -1 along
    #: the axis from the first item to the second, taken from the geometry the first
    #: time it is solved. A negative value flips it on purpose. None until then.
    side: int | None = None
    #: Switched off (TR109, D829): kept and drawn greyed, but it drives nothing.
    off: bool = False
    #: How the label shows (TR46, D901), or None for the plain value: ``tolerance``
    #: (none, bilateral, limit, symmetric), ``plus`` and ``minus`` (mm or radians),
    #: ``decimals``, and ``show`` (radius or diameter) for a round dimension.
    display: dict[str, Any] | None = None
    #: A shared name: dimensions with the same link always have the same value, and
    #: changing any one changes the others (TR193, D978). None when not linked.
    link: str | None = None
    #: A limit instead of an exact value (TR342, D1311): "min" keeps the size at the
    #: value or more, "max" at the value or less. None for an exact dimension.
    limit: str | None = None
    #: A symmetric angle (TR111, D2200): an angle dimension between a line and a
    #: centerline whose value is the full angle, twice the line's angle to the
    #: centerline (the angle between the line and its mirror image).
    symmetric: bool = False


@dataclass
class Sketch:
    """The contents of a sketch feature."""

    entities: dict[str, Entity] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    dimensions: list[Dimension] = field(default_factory=list)
    next_entity: int = 1
    next_dimension: int = 1
    #: Sketch pictures (PHASE2_SPEC P2.9); not entities, so nothing snaps to them.
    pictures: list[Picture] = field(default_factory=list)
    #: Text items (PHASE4_SPEC P4.8), see ``sketch.text``.
    texts: list[SketchText] = field(default_factory=list)
    #: Sketch layers (TR389, D982): each a dict with ``name``, ``colour`` (#RRGGBB or
    #: ""), ``style`` (solid or dashed) and ``visible``; ``layer_of`` maps a curve id to
    #: its layer's name. See ``sketch.layers``.
    layers: list[dict[str, Any]] = field(default_factory=list)
    layer_of: dict[str, str] = field(default_factory=dict)
    #: Keep This Side locks (TR338, D1302): a ``sides.signature`` key, such as
    #: ``corner:e3:e7`` or ``arc:e9``, mapped to the side (+1 or -1) it must keep.
    keep_sides: dict[str, int] = field(default_factory=dict)
    #: Sketch blocks (TR34, D1717): each a dict with ``id``, ``name``, ``sketch`` (the
    #: block's own geometry as sketch data, in its own axes) and ``copies`` (each a
    #: ``map`` from the block's entity ids to this sketch's). See ``sketch.blocks``.
    blocks: list[dict[str, Any]] = field(default_factory=list)

    # Building -----------------------------------------------------------------

    def new_id(self) -> str:
        """Return the next entity id. Ids are never reused, even after deletion."""
        eid = f"e{self.next_entity}"
        self.next_entity += 1
        return eid

    def add_point(self, x: float, y: float, construction: bool = False) -> str:
        """Add a point and return its id."""
        eid = self.new_id()
        self.entities[eid] = Point(eid, x, y, construction)
        return eid

    def add_line(
        self, x1: float, y1: float, x2: float, y2: float, construction: bool = False
    ) -> str:
        """Add a line with two new end points and return the line id."""
        p1 = self.add_point(x1, y1, construction)
        p2 = self.add_point(x2, y2, construction)
        eid = self.new_id()
        self.entities[eid] = Line(eid, p1, p2, construction)
        return eid

    def add_circle(self, cx: float, cy: float, radius: float, construction: bool = False) -> str:
        """Add a circle with a new center point and return the circle id."""
        center = self.add_point(cx, cy, construction)
        eid = self.new_id()
        self.entities[eid] = Circle(eid, center, radius, construction)
        return eid

    def add_arc(
        self,
        cx: float,
        cy: float,
        radius: float,
        start_angle: float,
        end_angle: float,
        construction: bool = False,
    ) -> str:
        """Add a counter clockwise arc from ``start_angle`` to ``end_angle`` (radians)."""
        center = self.add_point(cx, cy, construction)
        start = self.add_point(
            cx + radius * math.cos(start_angle), cy + radius * math.sin(start_angle), construction
        )
        end = self.add_point(
            cx + radius * math.cos(end_angle), cy + radius * math.sin(end_angle), construction
        )
        eid = self.new_id()
        self.entities[eid] = Arc(eid, center, start, end, True, construction)
        return eid

    def relate(self, rtype: str, *entities: str) -> Relation:
        """Add a relation and return it."""
        if rtype not in RELATION_TYPES:
            raise ValueError(f"Unknown relation '{rtype}'.")
        rel = Relation(rtype, list(entities))
        self.relations.append(rel)
        return rel

    def dimension(
        self, dtype: str, entities: list[str], param: Param, driving: bool = True
    ) -> Dimension:
        """Add a dimension and return it."""
        if dtype not in DIMENSION_TYPES:
            raise ValueError(f"Unknown dimension type '{dtype}'.")
        dim = Dimension(f"d{self.next_dimension}", dtype, list(entities), param, driving)
        self.next_dimension += 1
        self.dimensions.append(dim)
        return dim

    # Lookup -------------------------------------------------------------------

    def point(self, eid: str) -> Point:
        """Return point ``eid``. Raises KeyError or TypeError when it is not a point."""
        ent = self.entities[eid]
        if not isinstance(ent, Point):
            raise TypeError(f"{eid} is not a point.")
        return ent

    def xy(self, eid: str) -> tuple[float, float]:
        """Coordinates of point ``eid``."""
        p = self.point(eid)
        return p.x, p.y

    def radius(self, eid: str) -> float:
        """Radius of a circle or arc."""
        ent = self.entities[eid]
        if isinstance(ent, Circle):
            return ent.radius
        if isinstance(ent, Arc):
            cx, cy = self.xy(ent.center)
            sx, sy = self.xy(ent.start)
            return math.hypot(sx - cx, sy - cy)
        raise TypeError(f"{eid} has no radius.")

    def curves(self, include_construction: bool = False) -> list[Curve]:
        """Lines, circles and arcs, in entity order."""
        return [
            e
            for e in self.entities.values()
            if not isinstance(e, Point) and (include_construction or not e.construction)
        ]


def entity_points(e: Entity) -> list[str]:
    """Point ids an entity uses (a point uses itself)."""
    if isinstance(e, Point):
        return [e.id]
    if isinstance(e, Line):
        return [e.p1, e.p2]
    if isinstance(e, Circle):
        return [e.center]
    if isinstance(e, Arc):
        return [e.center, e.start, e.end]
    if isinstance(e, Ellipse):
        return [e.center, e.major, e.minor]
    if isinstance(e, EllipseArc):
        return [e.center, e.major, e.minor, e.start, e.end]
    return [*e.points, *e.handles]


def remap(e: Curve, new_id: str, twin: Callable[[str], str]) -> Curve:
    """A copy of curve ``e`` with id ``new_id`` and each point id passed through
    ``twin``."""
    if isinstance(e, Line):
        return Line(new_id, twin(e.p1), twin(e.p2), e.construction)
    if isinstance(e, Circle):
        return Circle(new_id, twin(e.center), e.radius, e.construction)
    if isinstance(e, Arc):
        return Arc(new_id, twin(e.center), twin(e.start), twin(e.end), e.ccw, e.construction)
    if isinstance(e, Ellipse):
        return Ellipse(new_id, twin(e.center), twin(e.major), twin(e.minor), e.construction)
    if isinstance(e, EllipseArc):
        return EllipseArc(
            new_id,
            twin(e.center),
            twin(e.major),
            twin(e.minor),
            twin(e.start),
            twin(e.end),
            e.construction,
        )
    return Spline(new_id, [twin(p) for p in e.points], [twin(h) for h in e.handles], e.construction)


def curve_ends(e: Curve) -> tuple[str, str] | None:
    """The start and end point ids of an open curve, or None for closed ones."""
    if isinstance(e, Line):
        return e.p1, e.p2
    if isinstance(e, Arc | EllipseArc):
        return e.start, e.end
    if isinstance(e, Spline):
        return e.points[0], e.points[-1]
    return None


# File format ------------------------------------------------------------------


def _entity_to_json(e: Entity) -> dict[str, Any]:
    if isinstance(e, Ellipse):
        return {
            "id": e.id,
            "type": "ellipse",
            "center": e.center,
            "major": e.major,
            "minor": e.minor,
            "construction": e.construction,
        }
    if isinstance(e, EllipseArc):
        return {
            "id": e.id,
            "type": "ellipse_arc",
            "center": e.center,
            "major": e.major,
            "minor": e.minor,
            "start": e.start,
            "end": e.end,
            "construction": e.construction,
        }
    if isinstance(e, Spline):
        return {
            "id": e.id,
            "type": "spline",
            "points": list(e.points),
            "handles": list(e.handles),
            "construction": e.construction,
        }
    out: dict[str, Any]
    if isinstance(e, Point):
        out = {"id": e.id, "type": "point", "x": e.x, "y": e.y, "construction": e.construction}
    elif isinstance(e, Line):
        out = {"id": e.id, "type": "line", "p1": e.p1, "p2": e.p2, "construction": e.construction}
    elif isinstance(e, Circle):
        out = {
            "id": e.id,
            "type": "circle",
            "center": e.center,
            "radius": e.radius,
            "construction": e.construction,
        }
    else:
        return _arc_to_json(e)
    # Optional, written only for copies of part geometry, so older sketches save unchanged.
    if e.source is not None:
        out["source"] = dict(e.source)
    return out


def _arc_to_json(e: Arc) -> dict[str, Any]:
    return {
        "id": e.id,
        "type": "arc",
        "center": e.center,
        "start": e.start,
        "end": e.end,
        "ccw": e.ccw,
        "construction": e.construction,
    }


def _entity_from_json(raw: dict[str, Any]) -> Entity:
    kind = raw.get("type")
    eid = str(raw["id"])
    cons = bool(raw.get("construction", False))
    source = _source_from_json(raw.get("source"), eid)
    if kind == "point":
        return Point(eid, float(raw["x"]), float(raw["y"]), cons, source)
    if kind == "line":
        return Line(eid, str(raw["p1"]), str(raw["p2"]), cons, source)
    if kind == "circle":
        return Circle(eid, str(raw["center"]), float(raw["radius"]), cons, source)
    if kind == "arc":
        return Arc(
            eid,
            str(raw["center"]),
            str(raw["start"]),
            str(raw["end"]),
            bool(raw.get("ccw", True)),
            cons,
        )
    if kind == "ellipse":
        return Ellipse(eid, str(raw["center"]), str(raw["major"]), str(raw["minor"]), cons)
    if kind == "ellipse_arc":
        return EllipseArc(
            eid,
            str(raw["center"]),
            str(raw["major"]),
            str(raw["minor"]),
            str(raw["start"]),
            str(raw["end"]),
            cons,
        )
    if kind == "spline":
        points = [str(p) for p in raw["points"]]
        handles = [str(h) for h in raw["handles"]]
        if len(points) < 2 or len(handles) != len(points):
            raise ValueError(f"Spline {eid} needs two or more points, each with a handle.")
        return Spline(eid, points, handles, cons)
    raise ValueError(f"Unknown sketch entity type '{kind}'.")


#: Kinds of part geometry a fixed copy can come from (FDEF_SPEC 6 item 9).
SOURCE_KINDS = ("vertex", "edge", "origin")


def _source_from_json(raw: Any, eid: str) -> dict[str, Any] | None:
    """A stored ``source`` of a part geometry copy, or None when the key is absent."""
    if raw is None:
        return None
    if not isinstance(raw, dict) or raw.get("kind") not in SOURCE_KINDS:
        raise ValueError(f"The source of sketch entity {eid} is damaged.")
    if raw["kind"] != "origin" and not isinstance(raw.get("name"), str):
        raise ValueError(f"The source of sketch entity {eid} has no name.")
    return dict(raw)


def sketch_to_data(sketch: Sketch) -> dict[str, Any]:
    """Sketch contents as the keys of a sketch feature (FDEF_SPEC 6)."""
    out: dict[str, Any] = {
        "next_entity": sketch.next_entity,
        "entities": [_entity_to_json(e) for e in sketch.entities.values()],
        "relations": [_relation_to_json(r) for r in sketch.relations],
        "dimensions": [_dimension_to_json(d) for d in sketch.dimensions],
    }
    if sketch.pictures:  # optional key, so sketches without pictures save as before
        out["pictures"] = [picture_to_json(p) for p in sketch.pictures]
    if sketch.layers:  # TR389: written only when the sketch has layers
        out["layers"] = [dict(layer) for layer in sketch.layers]
        known = {str(layer.get("name")) for layer in sketch.layers}
        out["layer_of"] = {
            eid: name
            for eid, name in sketch.layer_of.items()
            if eid in sketch.entities and name in known
        }
    if sketch.keep_sides:  # TR338: written only when a side is locked
        out["keep_sides"] = dict(sketch.keep_sides)
    if sketch.blocks:  # TR34: written only when the sketch has blocks
        import copy as _copy

        out["blocks"] = _copy.deepcopy(sketch.blocks)
    if sketch.texts:  # written only when there are texts, so older sketches save unchanged
        from fdcad.core.sketch.text import text_to_json

        out["texts"] = [text_to_json(t) for t in sketch.texts]
    return out


def _relation_to_json(r: Relation) -> dict[str, Any]:
    out: dict[str, Any] = {"type": r.type, "entities": list(r.entities)}
    if r.value is not None:  # optional key, so older sketches save unchanged
        out["value"] = r.value
    if r.off:
        out["off"] = True
    if r.weak:  # TR362: written only when set
        out["weak"] = True
    return out


def _dimension_to_json(d: Dimension) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": d.id,
        "type": d.type,
        "entities": list(d.entities),
        "driving": d.driving,
        "param": d.param,
    }
    # Optional keys, written only when set, so older sketches save unchanged.
    if d.measure_to:
        out["measure_to"] = {k: d.measure_to[k] for k in d.entities if k in d.measure_to}
    if d.supplement is not None:
        out["supplement"] = d.supplement
    if d.label is not None:
        out["label"] = [d.label[0], d.label[1]]
    if d.name:
        out["name"] = d.name
    if d.side is not None:
        out["side"] = d.side
    if d.off:
        out["off"] = True
    if d.display:
        out["display"] = dict(d.display)
    if d.link:
        out["link"] = d.link
    if d.limit:  # TR342
        out["limit"] = d.limit
    if d.symmetric:  # TR111 (D2200)
        out["symmetric"] = True
    return out


def sketch_from_data(data: dict[str, Any]) -> Sketch:
    """Build a sketch from a sketch feature's keys. Raises ValueError on bad data."""
    try:
        entities: dict[str, Entity] = {}
        for raw in data.get("entities", []):
            ent = _entity_from_json(raw)
            entities[ent.id] = ent
        relations = [
            Relation(
                str(r["type"]),
                [str(x) for x in r["entities"]],
                None if r.get("value") is None else float(r["value"]),
                r.get("off") is True,
                r.get("weak") is True,
            )
            for r in data.get("relations", [])
        ]
        dimensions = []
        for raw in data.get("dimensions", []):
            p = raw["param"]
            param = p if isinstance(p, Param) else Param(str(p["expr"]), float(p["value"]))
            measure_to = {str(k): str(v) for k, v in dict(raw.get("measure_to") or {}).items()}
            if any(v not in MEASURE_TO for v in measure_to.values()):
                raise ValueError(f"Unknown measure to value in dimension {raw['id']}.")
            supplement = raw.get("supplement")
            label = _label_from_json(raw.get("label"), str(raw["id"]))
            side = raw.get("side")
            if side is not None and (isinstance(side, bool) or side not in (1, -1)):
                raise ValueError(f"Dimension {raw['id']} has a side that is not 1 or -1.")
            dimensions.append(
                Dimension(
                    str(raw["id"]),
                    str(raw["type"]),
                    [str(x) for x in raw["entities"]],
                    param,
                    bool(raw.get("driving", True)),
                    measure_to,
                    None if supplement is None else bool(supplement),
                    label,
                    str(raw["name"]) if isinstance(raw.get("name"), str) else None,
                    side,
                    raw.get("off") is True,
                    dict(raw["display"]) if isinstance(raw.get("display"), dict) else None,
                    str(raw["link"]) if isinstance(raw.get("link"), str) and raw["link"] else None,
                    raw["limit"] if raw.get("limit") in LIMITS else None,
                    raw.get("symmetric") is True,
                )
            )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"The sketch data is damaged: {exc}.") from exc
    numbers = [int(d.id[1:]) for d in dimensions if d.id[1:].isdigit()]
    pictures = [picture_from_json(raw) for raw in data.get("pictures", []) or []]
    texts = []
    if data.get("texts"):
        from fdcad.core.sketch.text import text_from_json

        texts = [text_from_json(raw) for raw in data["texts"]]
    return Sketch(
        entities=entities,
        relations=relations,
        dimensions=dimensions,
        next_entity=int(data.get("next_entity", len(entities) + 1)),
        next_dimension=max(numbers, default=0) + 1,
        pictures=pictures,
        texts=texts,
        layers=[dict(x) for x in data.get("layers", []) or [] if isinstance(x, dict)],
        layer_of={
            str(k): str(v)
            for k, v in dict(data.get("layer_of") or {}).items()
            if isinstance(v, str)
        },
        keep_sides={
            str(k): int(v)
            for k, v in dict(data.get("keep_sides") or {}).items()
            if v in (1, -1) and not isinstance(v, bool)
        },
        blocks=[_block_from_json(b) for b in data.get("blocks", []) or [] if isinstance(b, dict)],
    )


def _block_from_json(raw: dict[str, Any]) -> dict[str, Any]:
    """A stored sketch block (TR34), checked enough to use."""
    import copy as _copy

    if not isinstance(raw.get("sketch"), dict) or not isinstance(raw.get("copies"), list):
        raise ValueError("A sketch block is damaged: it needs its geometry and its copies.")
    return {
        "id": str(raw.get("id", "")),
        "name": str(raw.get("name", "")),
        "sketch": _copy.deepcopy(raw["sketch"]),
        "copies": [
            {"map": {str(k): str(v) for k, v in dict(c.get("map") or {}).items()}}
            for c in raw["copies"]
            if isinstance(c, dict)
        ],
    }


def _label_from_json(raw: Any, did: str) -> tuple[float, float] | None:
    """A stored label offset ``[dx, dy]``, or None when the key is absent."""
    if raw is None:
        return None
    if not isinstance(raw, list | tuple) or len(raw) != 2:
        raise ValueError(f"The label of dimension {did} must be two numbers.")
    x, y = float(raw[0]), float(raw[1])
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError(f"The label of dimension {did} must be two numbers.")
    return x, y
