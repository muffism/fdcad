"""Manufacturing check (TR295, TR296; DECISIONS D790).

One advisory list per process. It never changes the part; the fixes it offers
are buttons the user confirms (CLAUDE.md 5.12). Each finding names the faces or
edges it is about, so the window can highlight them.

Profiles: a manufacturing profile per process holds the rule values. FDCAD ships
general values of its own (not any service's tables); the user edits them and
saves a profile as a small JSON file to share (``profile_to_text`` and
``profile_from_text``). Every length is in mm.

Milling checks (TR296):

- ``sharp_corner``: a straight inside edge between two flat faces running along a
  setup direction, which a round tool cannot cut (fix: Corner Relief, TR244); floor
  corners across the tool are cut square by a flat end mill and are left alone.
- ``small_round``: an inside round (part of a cylinder, not a whole hole) with a
  radius under the smallest tool radius, or deeper than the tool reach allows.
- ``deep_hole``: a hole deeper than ``hole_depth_ratio`` times its diameter.
- ``narrow_slot``: two flat walls facing each other closer than the smallest tool.
- ``thin_wall``: two flat faces back to back closer than ``min_wall``.
- ``unreachable``: faces no tool direction in ``setups`` can reach, with the
  number of setups the six main directions would need. Only the face's own
  direction is checked, not other material in the way.
- ``long_thread``: a tapped hole whose thread is longer than ``thread_ratio``
  times its diameter; ``tap_room``: a blind tapped hole with less than
  ``tap_room_pitches`` pitches below the thread.
- ``drill_size``: a hole whose diameter is not a stock drill (fix: Snap to the
  nearest stock size, which changes the hole feature's diameter).
- ``small_text``: sketch text lower than ``min_text``.

Sheet metal and laser checks read the flat pattern (``manufacturing_sheet``,
TR297). The other processes have their profiles; their checks follow (the print
processes have their own Evaluate tools). Geometry
work, so ``check`` runs in a kernel job. No Qt.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.naming.names import NamedShape

PROCESSES = ("milling", "turning", "sheet_metal", "moulding", "fdm", "resin", "powder")

#: General starting values per process, in mm or plain ratios.
DEFAULTS: dict[str, dict[str, float | str]] = {
    "milling": {
        "tool_diameter": 6.0,
        "min_tool_diameter": 3.0,
        "tool_reach_ratio": 4.0,
        "hole_depth_ratio": 8.0,
        "min_wall": 1.0,
        "thread_ratio": 3.0,
        "tap_room_pitches": 2.0,
        "min_text": 2.0,
        "setups": "+Z",
        "pocket_depth_ratio": 4.0,  # D801
        "wall_height_ratio": 10.0,
    },
    "turning": {"min_wall": 1.0, "min_groove": 1.5},
    "sheet_metal": {
        "hole_to_edge": 1.5,
        "hole_to_bend": 2.5,
        "hole_to_hole": 2.0,
        "min_hole": 1.0,
        "min_flange": 4.0,
        "kerf": 0.2,
        "min_tab": 2.0,  # D802
    },
    "moulding": {"min_wall": 1.0, "max_wall": 4.0, "min_draft_deg": 1.0},
    "fdm": {
        "min_wall": 0.8,
        "max_overhang_deg": 45.0,
        "nozzle": 0.4,
        "layer_height": 0.2,
        "min_round_hole": 1.0,
        "max_bridge": 10.0,
    },
    "resin": {
        "min_wall": 0.6,
        "drain_hole": 3.0,
        "nozzle": 0.1,
        "layer_height": 0.05,
        "min_round_hole": 0.5,
        "max_bridge": 5.0,
    },
    "powder": {
        "min_wall": 0.8,
        "escape_hole": 2.0,
        "nozzle": 0.2,
        "layer_height": 0.1,
        "min_round_hole": 1.0,
        "max_bridge": 50.0,
    },
}

CORNER_RELIEF = "corner_relief"
SNAP_DRILL = "snap_drill"

#: Stock metric drills: 0.1 mm steps to 13 mm, then 0.5 mm steps to 50 mm.
STOCK_METRIC = tuple(
    [round(0.5 + 0.1 * k, 1) for k in range(int((13.0 - 0.5) / 0.1) + 1)]
    + [13.0 + 0.5 * k for k in range(1, int((50.0 - 13.0) / 0.5) + 1)]
)


@dataclass
class Finding:
    """One row: its kind, what it says, the shapes it is about, and a fix."""

    kind: str
    message: str
    faces: list[str] = field(default_factory=list)
    edges: list[Any] = field(default_factory=list)  # edges, for highlighting
    fid: str | None = None
    fix: str | None = None  # CORNER_RELIEF, SNAP_DRILL or None
    extra: dict[str, Any] = field(default_factory=dict)


# Profiles -----------------------------------------------------------------------------


def default_profile(process: str) -> dict[str, float | str]:
    """A copy of FDCAD's starting values for ``process``."""
    if process not in DEFAULTS:
        raise ValueError(f"unknown process {process!r}. Choose one of the listed processes.")
    from fdcad.core import manufacturing_print as mp

    out: dict[str, float | str] = dict(DEFAULTS[process])
    if process in mp.PRINT_PROCESSES:
        out.update(mp.PRINT_EXTRA)
    elif process == "moulding":
        out.update(mp.MOULD_EXTRA)
    return out


def profile_to_text(process: str, values: dict[str, float | str]) -> str:
    """A profile as a JSON text to save and share."""
    return json.dumps({"fdcad_manufacturing_profile": 1, "process": process, "values": values},
                      indent=2, sort_keys=True)  # fmt: skip


def profile_from_text(text: str) -> tuple[str, dict[str, float | str]]:
    """The process and values of a saved profile, starting from the defaults so a
    profile from an older FDCAD gets new rules. Raises ValueError for a bad file."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError("the file is not a manufacturing profile. Pick a saved profile.") from exc
    if not isinstance(data, dict) or data.get("fdcad_manufacturing_profile") != 1:
        raise ValueError("the file is not a manufacturing profile. Pick a saved profile.")
    process = data.get("process")
    if process not in DEFAULTS:
        raise ValueError("the profile names an unknown process. Pick another profile.")
    values = default_profile(str(process))
    given = data.get("values")
    if isinstance(given, dict):
        for key, value in given.items():
            if key not in values:
                continue
            if isinstance(values[key], str):
                if isinstance(value, str):
                    values[key] = value
            elif isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                values[key] = float(value)
    return str(process), values


def _num(profile: dict[str, float | str], key: str) -> float:
    value = profile.get(key, DEFAULTS["milling"].get(key, 0.0))
    return float(value) if isinstance(value, (int, float)) else 0.0


# Geometry helpers ---------------------------------------------------------------------


def _faces(shape: Any) -> list[Any]:
    from fdcad.core.naming.names import faces_of

    return list(faces_of(shape))


def _cylinder(face: Any) -> tuple[float, float, bool, float] | None:
    """(radius, length along the axis, whole round, angle covered) of a concave cylinder
    face, else None (a shaft's outside is convex and is left alone)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder

    from fdcad.core.features.direct import radius_after

    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Cylinder:
        return None
    r = surface.Cylinder().Radius()
    grown = radius_after(face, 1.0)
    if grown is None or grown >= r:  # offsetting out of the material must shrink a hole
        return None
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    angle = u1 - u0
    return r, v1 - v0, angle >= 2 * math.pi - 1e-6, angle


def _hole_diameters(body: NamedShape) -> list[tuple[str, Any, float, float]]:
    """Whole round concave faces: (name, face, diameter, depth)."""
    out = []
    for name, face in body.faces:
        found = _cylinder(face)
        if found is not None and found[2]:
            out.append((name, face, 2 * found[0], found[1]))
    return out


def _sample_normals(face: Any) -> list[tuple[float, float, float]]:
    """Outward normals at a 3 by 3 grid over the face's parameters."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepTools import BRepTools

    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    adaptor = BRepAdaptor_Surface(face)
    out = []
    reversed_ = face.Orientation().name == "TopAbs_REVERSED"
    for i in range(3):
        for j in range(3):
            u = u0 + (u1 - u0) * (i + 0.5) / 3
            v = v0 + (v1 - v0) * (j + 0.5) / 3
            props = BRepLProp_SLProps(adaptor, u, v, 1, 1e-6)
            if not props.IsNormalDefined():
                continue
            n = props.Normal()
            vec = (n.X(), n.Y(), n.Z())
            out.append((-vec[0], -vec[1], -vec[2]) if reversed_ else vec)
    return out


AXES: dict[str, tuple[float, float, float]] = {
    "+X": (1.0, 0.0, 0.0),
    "-X": (-1.0, 0.0, 0.0),
    "+Y": (0.0, 1.0, 0.0),
    "-Y": (0.0, -1.0, 0.0),
    "+Z": (0.0, 0.0, 1.0),
    "-Z": (0.0, 0.0, -1.0),
}


def setup_directions(text: str) -> list[tuple[float, float, float]]:
    """Setup directions from text such as "+Z, -Z": the side the tool comes from."""
    out = []
    for word in text.replace(",", " ").split():
        if word.upper() in AXES:
            out.append(AXES[word.upper()])
    return out or [AXES["+Z"]]


def _reachable(normals: list[tuple[float, float, float]], d: tuple[float, float, float]) -> bool:
    """A tool coming from ``d`` reaches a face whose normals never point away from it."""
    return bool(normals) and all(n[0] * d[0] + n[1] * d[1] + n[2] * d[2] > -1e-6 for n in normals)


def setups_needed(face_normals: list[list[tuple[float, float, float]]]) -> int:
    """The fewest of the six main directions that together reach every face (each face
    needs one direction that reaches it), or 0 when some face no main direction reaches."""
    from itertools import combinations

    keys = list(AXES)
    for count in range(1, 7):
        for combo in combinations(keys, count):
            if all(any(_reachable(ns, AXES[k]) for k in combo) for ns in face_normals):
                return count
    return 0


def _flat(face: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    from fdcad.core.features.face_picks import outward_normal
    from fdcad.core.naming.names import centroid

    n = outward_normal(face)
    return None if n is None else (n, centroid(face))


def _on_face(face: Any, point: tuple[float, float, float]) -> bool:
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON

    state = BRepClass_FaceClassifier(face, gp_Pnt(*point), 1e-6).State()
    return state in (TopAbs_IN, TopAbs_ON)


def _facing_pairs(body: NamedShape) -> list[tuple[str, str, float, bool]]:
    """Pairs of parallel flat faces that overlap: (name, name, gap, facing). ``facing``:
    the faces look at each other across air (a slot); else back to back (a wall)."""
    flats = [(n, f, x) for n, f in body.faces if (x := _flat(f)) is not None]
    out = []
    for i, (na, fa, (a_n, a_c)) in enumerate(flats):
        for nb, fb, (b_n, b_c) in flats[i + 1 :]:
            if a_n[0] * b_n[0] + a_n[1] * b_n[1] + a_n[2] * b_n[2] > -0.9999:
                continue
            rel = (b_c[0] - a_c[0], b_c[1] - a_c[1], b_c[2] - a_c[2])
            gap = rel[0] * a_n[0] + rel[1] * a_n[1] + rel[2] * a_n[2]
            if abs(gap) < 1e-6:
                continue
            # Overlap: each centroid, dropped onto the other face's plane, lies on it.
            on_b = (a_c[0] + a_n[0] * gap, a_c[1] + a_n[1] * gap, a_c[2] + a_n[2] * gap)
            on_a = (b_c[0] - a_n[0] * gap, b_c[1] - a_n[1] * gap, b_c[2] - a_n[2] * gap)
            if not (_on_face(fb, on_b) or _on_face(fa, on_a)):
                continue
            out.append((na, nb, abs(gap), gap > 0))
    return out


def _extent(face: Any, d: tuple[float, float, float]) -> float:
    """How far ``face`` reaches along ``d`` (from its bounding box corners)."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(face, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    xs, ys, zs = (lo.X(), hi.X()), (lo.Y(), hi.Y()), (lo.Z(), hi.Z())
    along = [x * d[0] + y * d[1] + z * d[2] for x in xs for y in ys for z in zs]
    return float(max(along) - min(along))


def nearest_stock(diameter: float) -> float:
    """The nearest stock metric drill."""
    return min(STOCK_METRIC, key=lambda d: abs(d - diameter))


def is_stock(diameter: float) -> bool:
    """A stock metric drill, or a named inch drill (number, letter or fraction)."""
    from fdcad.core.features.hole_heads import drill_names

    return abs(nearest_stock(diameter) - diameter) < 0.005 or bool(drill_names(diameter))


# Checks -------------------------------------------------------------------------------


def _owner(name: str) -> str | None:
    head = name.split("/", 1)[0]
    return head if head.startswith("f") and head[1:].isdigit() else None


def milling(doc: Document, body: NamedShape, profile: dict[str, float | str]) -> list[Finding]:
    """The milling findings for ``body`` (see the module notes)."""
    from fdcad.core.features.corner_relief import faces_at, inside_corner

    out: list[Finding] = []
    tool_r = _num(profile, "tool_diameter") / 2
    small_r = _num(profile, "min_tool_diameter") / 2
    reach = _num(profile, "tool_reach_ratio")
    directions = setup_directions(str(profile.get("setups", "+Z")))
    # Sharp inside corners.
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    seen: list[Any] = []
    ex = TopExp_Explorer(body.shape, TopAbs_EDGE)
    while ex.More():
        edge = TopoDS.Edge(ex.Current())
        ex.Next()
        if any(edge.IsSame(e) for e in seen):
            continue
        seen.append(edge)
        corner = inside_corner(body, edge)
        if corner is None:
            continue
        # A flat end mill cuts a floor corner square: only edges along the tool are a problem.
        start, end = corner[0], corner[1]
        along = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
        size = math.sqrt(sum(c * c for c in along)) or 1.0
        if not any(abs(sum(a * b for a, b in zip(along, d, strict=True))) / size > 0.999
                   for d in directions):  # fmt: skip
            continue
        names = [n for n, f in body.faces if any(f.IsSame(x) for x in faces_at(body, edge))]
        out.append(
            Finding(
                "sharp_corner",
                f"Sharp inside corner between {' and '.join(names)}: a round tool leaves a "
                f"{tool_r:g} mm radius. Add a Corner Relief, or round the corner.",
                faces=names,
                edges=[edge],
                fix=CORNER_RELIEF,
            )
        )
    for name, face in body.faces:
        found = _cylinder(face)
        if found is None or found[2]:
            continue
        r, length, _whole, _angle = found
        if r < small_r - 1e-9:
            out.append(
                Finding(
                    "small_round",
                    f"Inside round {name} is {r:g} mm, under the smallest tool radius "
                    f"{small_r:g} mm. Make the round larger.",
                    faces=[name],
                    fid=_owner(name),
                )
            )
        elif length > reach * 2 * r + 1e-9:
            out.append(
                Finding(
                    "small_round",
                    f"Inside round {name} runs {length:g} mm deep, more than {reach:g} times "
                    "a tool that fits it can reach. Make the round larger or the wall lower.",
                    faces=[name],
                    fid=_owner(name),
                )
            )
    # Holes.
    ratio = _num(profile, "hole_depth_ratio")
    for name, _face, diameter, depth in _hole_diameters(body):
        if depth > ratio * diameter + 1e-9:
            out.append(
                Finding(
                    "deep_hole",
                    f"Hole {name} is {depth:g} mm deep, more than {ratio:g} times its "
                    f"{diameter:g} mm diameter. Make it shallower or wider.",
                    faces=[name],
                    fid=_owner(name),
                )
            )
        if not is_stock(diameter):
            stock = nearest_stock(diameter)
            out.append(
                Finding(
                    "drill_size",
                    f"Hole {name} is {diameter:g} mm, not a stock drill size. Snap it to "
                    f"{stock:g} mm, or keep it for a reamed or milled hole.",
                    faces=[name],
                    fid=_owner(name),
                    fix=SNAP_DRILL,
                    extra={"diameter": stock},
                )
            )
    # Slots and walls.
    min_tool = _num(profile, "min_tool_diameter")
    min_wall = _num(profile, "min_wall")
    pocket_ratio = _num(profile, "pocket_depth_ratio")
    wall_ratio = _num(profile, "wall_height_ratio")
    faces_by_name = dict(body.faces)
    for a, b, gap, facing in _facing_pairs(body):
        height = min(
            _extent(faces_by_name[a], directions[0]), _extent(faces_by_name[b], directions[0])
        )
        if facing and pocket_ratio > 0 and height > pocket_ratio * gap + 1e-9:
            out.append(
                Finding(
                    "deep_pocket",
                    f"The pocket between {a} and {b} is {height:g} mm deep and {gap:g} mm "
                    f"wide, more than {pocket_ratio:g} times its width: a long tool chatters. "
                    "Make it wider or shallower.",
                    faces=[a, b],
                )
            )
        if not facing and wall_ratio > 0 and height > wall_ratio * gap + 1e-9:
            out.append(
                Finding(
                    "tall_wall",
                    f"The wall between {a} and {b} is {height:g} mm tall and {gap:g} mm thick, "
                    f"more than {wall_ratio:g} times its thickness: it bends while cut. "
                    "Make it thicker or lower.",
                    faces=[a, b],
                )
            )
        if facing and gap < min_tool - 1e-9:
            out.append(
                Finding(
                    "narrow_slot",
                    f"The gap between {a} and {b} is {gap:g} mm, narrower than the smallest "
                    f"tool ({min_tool:g} mm). Widen it.",
                    faces=[a, b],
                )
            )
        elif not facing and gap < min_wall - 1e-9:
            out.append(
                Finding(
                    "thin_wall",
                    f"The wall between {a} and {b} is {gap:g} mm thick, under {min_wall:g} mm. "
                    "Make it thicker.",
                    faces=[a, b],
                )
            )
    # Reach.
    normals = {name: _sample_normals(face) for name, face in body.faces}
    missed = [n for n, ns in normals.items() if not any(_reachable(ns, d) for d in directions)]
    if missed:
        needed = setups_needed(list(normals.values()))
        more = f" The six main directions need {needed} setups." if needed else ""
        out.append(
            Finding(
                "unreachable",
                f"{len(missed)} faces cannot be reached from the setups "
                f"({profile.get('setups', '+Z')}).{more} Add setups or change the part.",
                faces=missed,
            )
        )
    # Tapped holes and text, from the features.
    from fdcad.core.document.model import Param

    def value(params: dict[str, Any], key: str) -> float:
        v = params.get(key)
        return v.value if isinstance(v, Param) else 0.0

    raised = {
        str(f.refs["sketch"].get("feature")): f.name
        for f in doc.features
        if f.type == "extrude"
        and not f.suppressed
        and f.params.get("operation", "boss") == "boss"
        and isinstance(f.refs.get("sketch"), dict)
    }
    thread_ratio = _num(profile, "thread_ratio")
    room = _num(profile, "tap_room_pitches")
    min_text = _num(profile, "min_text")
    for feature in doc.features:
        if feature.suppressed:
            continue
        p = feature.params
        if feature.type == "hole" and p.get("hole_type") == "tapped":
            thread, major, pitch = (
                value(p, "thread_depth"),
                value(p, "thread_diameter"),
                value(p, "pitch"),
            )
            if major > 0 and thread > thread_ratio * major + 1e-9:
                out.append(
                    Finding(
                        "long_thread",
                        f"{feature.name}: the thread is {thread:g} mm, more than "
                        f"{thread_ratio:g} times its {major:g} mm size. A shorter thread holds "
                        "as well. Shorten the thread depth.",
                        fid=feature.id,
                    )
                )
            blind = p.get("end_condition", "blind") == "blind"
            if blind and pitch > 0 and value(p, "depth") - thread < room * pitch - 1e-9:
                out.append(
                    Finding(
                        "tap_room",
                        f"{feature.name}: less than {room:g} pitches below the thread for the "
                        "tap's lead. Make the hole deeper or the thread shorter.",
                        fid=feature.id,
                    )
                )
        if feature.type == "sketch" and isinstance(feature.data, dict):
            from fdcad.core.sketch.model import sketch_from_data

            try:
                sketch = sketch_from_data(feature.data)
            except Exception:
                continue
            if sketch.texts and feature.id in raised:
                out.append(
                    Finding(
                        "raised_text",
                        f"{raised[feature.id]} raises the text of {feature.name}: every bit of "
                        "floor around the letters has to be milled away. Engrave the text "
                        "(cut it) instead.",
                        fid=feature.id,
                    )
                )
            small = [t for t in sketch.texts if t.height < min_text - 1e-9]
            if small:
                out.append(
                    Finding(
                        "small_text",
                        f"{feature.name}: text {small[0].height:g} mm high, under "
                        f"{min_text:g} mm, is too small to mill. Make the text larger.",
                        fid=feature.id,
                    )
                )
    return out


def check(
    process: str,
    doc: Document,
    body: NamedShape | None,
    profile: dict[str, float | str],
    results: dict[str, Any] | None = None,
) -> list[Finding]:
    """The findings for ``process``; an empty part gives none. Sheet metal reads the Flat
    Pattern's result from ``results`` (the rebuild's results by feature id)."""
    if body is None:
        return []
    if process == "milling":
        return milling(doc, body, profile)
    if process == "sheet_metal":
        return _sheet(doc, profile, results or {})
    if process == "turning":
        return turning(body, profile)
    from fdcad.core import manufacturing_print as mp

    if process in mp.PRINT_PROCESSES:  # TR299 (D805)
        return mp.printing(doc, body, profile)
    if process == "moulding":  # TR298 (D805)
        return mp.moulding(body, profile)
    return []


def _sheet(
    doc: Document, profile: dict[str, float | str], results: dict[str, Any]
) -> list[Finding]:
    from fdcad.core.features.sheetmetal.export import flat_drawing
    from fdcad.core.features.sheetmetal.flat_pattern import flat_pattern_of
    from fdcad.core.io.export import ExportError
    from fdcad.core.manufacturing_sheet import sheet_checks

    flat = flat_pattern_of(doc)
    result = results.get(flat.id) if flat is not None else None
    if flat is None or result is None or getattr(result, "sheet", None) is None:
        return [
            Finding(
                "no_flat",
                "The part has no flat pattern to check. Make a sheet metal part with a Flat "
                "Pattern, then check again.",
            )
        ]
    try:
        drawing = flat_drawing(result, bounding_box=False)
    except ExportError as exc:
        return [Finding("no_flat", str(exc))]
    found = sheet_checks(drawing, result.sheet.thickness, dict(profile))
    found += tab_checks(doc, result.sheet.thickness, profile)
    return found + bend_checks(doc, result.sheet)


def has_checks(process: str) -> bool:
    """True for the processes this version checks."""
    return process in PROCESSES


# Turning (TR295, D801) -------------------------------------------------------------------


def _turning_axis(body: NamedShape) -> tuple[Any, Any] | None:
    """The axis of the biggest round face: the lathe's axis, as (point, direction)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    best = None
    for _name, face in body.faces:
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        cyl = surface.Cylinder()
        if best is None or cyl.Radius() > best[0]:
            best = (cyl.Radius(), cyl.Axis())
    if best is None:
        return None
    ax = best[1]
    p, d = ax.Location(), ax.Direction()
    return (p.X(), p.Y(), p.Z()), (d.X(), d.Y(), d.Z())


def _turned(face: Any, axis: tuple[Any, Any]) -> bool:
    """True when ``face`` is round about ``axis`` or square to it, so a lathe makes it."""
    from fdcad.core.features.face_rules import _axis, _same_axis

    flat = _flat(face)
    if flat is not None:
        n = flat[0]
        return bool(abs(abs(n[0] * axis[1][0] + n[1] * axis[1][1] + n[2] * axis[1][2]) - 1) < 1e-6)
    own = _axis(face)
    return own is not None and bool(_same_axis(own, axis))


def turning(body: NamedShape, profile: dict[str, float | str]) -> list[Finding]:
    """Lathe checks: faces not round about the turning axis (they need milling or a second
    setup), grooves narrower than ``min_groove`` and walls thinner than ``min_wall``."""
    axis = _turning_axis(body)
    if axis is None:
        return [
            Finding(
                "no_axis",
                "The part has no round face to turn about. Turning makes round parts; "
                "choose another process.",
            )
        ]
    out: list[Finding] = []
    off = [name for name, face in body.faces if not _turned(face, axis)]
    if off:
        out.append(
            Finding(
                "not_turned",
                f"{len(off)} faces are not round about the turning axis or square to it: a "
                "lathe cannot make them. They need milling or another setup.",
                faces=off,
            )
        )
    groove = float(profile.get("min_groove", 1.5) or 0)
    wall = float(profile.get("min_wall", 1.0) or 0)
    for a, b, gap, facing in _square_pairs(body, axis):
        if facing and gap < groove - 1e-9:
            out.append(
                Finding(
                    "narrow_groove",
                    f"The groove between {a} and {b} is {gap:g} mm wide, narrower than "
                    f"{groove:g} mm. Widen it for a standard grooving tool.",
                    faces=[a, b],
                )
            )
        elif not facing and gap < wall - 1e-9:
            out.append(
                Finding(
                    "thin_wall",
                    f"The wall between {a} and {b} is {gap:g} mm thick, under {wall:g} mm. "
                    "Make it thicker.",
                    faces=[a, b],
                )
            )
    return out


def _radial_range(face: Any, axis: tuple[Any, Any]) -> tuple[float, float]:
    """The smallest and largest distance from the axis of ``face``'s edges (sampled)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    (p, d) = axis
    dists = []
    ex = TopExp_Explorer(face, TopAbs_EDGE)
    while ex.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(ex.Current()))
        ex.Next()
        a, b = curve.FirstParameter(), curve.LastParameter()
        for k in range(9):
            q = curve.Value(a + (b - a) * k / 8)
            rel = (q.X() - p[0], q.Y() - p[1], q.Z() - p[2])
            along = rel[0] * d[0] + rel[1] * d[1] + rel[2] * d[2]
            dists.append(math.sqrt(max(sum(c * c for c in rel) - along * along, 0.0)))
    return (min(dists), max(dists)) if dists else (0.0, 0.0)


def _square_pairs(body: NamedShape, axis: tuple[Any, Any]) -> list[tuple[str, str, float, bool]]:
    """Flat faces square to the turning axis that face each other or stand back to back and
    overlap radially: (name, name, gap, facing). Rings included."""
    (p, d) = axis
    flats = []
    for name, face in body.faces:
        flat = _flat(face)
        if flat is None:
            continue
        n, c = flat
        k = n[0] * d[0] + n[1] * d[1] + n[2] * d[2]
        if abs(abs(k) - 1) > 1e-6:
            continue
        where = (c[0] - p[0]) * d[0] + (c[1] - p[1]) * d[1] + (c[2] - p[2]) * d[2]
        flats.append((name, k, where, _radial_range(face, axis)))
    out = []
    for i, (na, ka, wa, ra) in enumerate(flats):
        for nb, kb, wb, rb in flats[i + 1 :]:
            if ka * kb > 0 or abs(wa - wb) < 1e-6:
                continue
            if min(ra[1], rb[1]) - max(ra[0], rb[0]) <= 1e-6:
                continue  # no radial overlap
            low, high = (ka, wa), (kb, wb)
            if wa > wb:
                low, high = (kb, wb), (ka, wa)
            # Facing: the lower face looks up the axis and the higher looks down (air between).
            facing = low[0] > 0 and high[0] < 0
            out.append((na, nb, abs(wa - wb), facing))
    return out


def tab_checks(doc: Document, thickness: float, profile: dict[str, float | str]) -> list[Finding]:
    """Tab and Slot minimums (TR297 item 1, D802): a tab shorter than ``min_tab`` times
    the thickness tears out; one shallower than the thickness does not pass through."""
    from fdcad.core.document.model import Param

    out: list[Finding] = []
    least = float(profile.get("min_tab", 2.0) or 0) * thickness
    for feature in doc.features:
        if feature.type != "tab_slot" or feature.suppressed:
            continue
        length = feature.params.get("tab_length")
        depth = feature.params.get("depth")
        if isinstance(length, Param) and least > 0 and length.value < least - 1e-9:
            out.append(
                Finding(
                    "short_tab",
                    f"{feature.name}: tabs {length.value:g} mm long are under {least:g} mm "
                    "(the shortest tab for this sheet) and may break off. Make them longer.",
                    fid=feature.id,
                )
            )
        if isinstance(depth, Param) and depth.value < thickness - 1e-9:
            out.append(
                Finding(
                    "shallow_tab",
                    f"{feature.name}: tabs {depth.value:g} mm deep do not pass through a "
                    f"{thickness:g} mm wall. Make them at least as deep as the sheet is thick.",
                    fid=feature.id,
                )
            )
    return out


def bend_checks(doc: Document, sheet: Any) -> list[Finding]:
    """Bends tighter than the part's material allows (TR297 item 1, D803): an inside
    radius under the material's smallest bend ratio times the thickness may crack."""
    from fdcad.core.materials import min_bend_of, part_material

    material = part_material(doc)
    if material is None:
        return []
    ratio = material.min_bend or min_bend_of(material.name)
    if ratio <= 0:
        return []
    least = ratio * sheet.thickness
    tight = sorted({round(b.radius, 6) for b in sheet.bends.values() if b.radius < least - 1e-9})
    if not tight:
        return []
    return [
        Finding(
            "tight_bend",
            f"Bends with an inside radius of {tight[0]:g} mm are tighter than {material.name} "
            f"allows ({least:g} mm for this thickness) and may crack. Use a larger bend radius.",
        )
    ]
