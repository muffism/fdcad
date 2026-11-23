"""Part, body, feature and face colours (PHASE2_SPEC P2.11, FDEF_SPEC 10, D254).

``appearance`` in the file holds ``part_color`` and ``faces`` (face name to
colour) since schema 1; ``features`` (feature id to colour) and ``bodies``
(body number, from 1 in the Solid Bodies order, to colour) are optional and left
out while empty. The most specific colour wins: face, then feature, then body,
then part. Pure Python apart from listing faces of bodies.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import ShapeMap

PART_COLOR = "#B4BCC4"
KINDS = ("part", "body", "feature", "face")
#: ``sketch`` colours a finished sketch's lines in the 3D view (TR233, D928); it is
#: not offered among the part colour targets.
_KEYS = {"face": "faces", "feature": "features", "body": "bodies", "sketch": "sketches"}
#: Canonical key order of ``appearance`` (FDEF_SPEC 10 item 6, 14).
ORDER = ("part_color", "faces", "features", "bodies", "sketches", "hidden", "shown")
_OPTIONAL = ("features", "bodies", "sketches")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


@dataclass(frozen=True)
class Target:
    """What a colour is set on: the part, body ``key`` ("1", "2"), a feature id or a face name."""

    kind: str
    key: str = ""


def valid_color(text: str) -> bool:
    """True for ``#RRGGBB`` or ``#RRGGBBAA``."""
    return bool(_HEX.match(text))


def _map(appearance: dict[str, Any], key: str) -> dict[str, str]:
    value = appearance.get(key)
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items() if isinstance(v, str)}


def part_color(appearance: dict[str, Any]) -> str:
    """The part colour."""
    value = appearance.get("part_color")
    return value if isinstance(value, str) and valid_color(value) else PART_COLOR


def ordered(appearance: dict[str, Any]) -> dict[str, Any]:
    """``appearance`` in canonical key order; empty optional maps are left out.

    ``faces`` is always written, as schema 1 files have it.
    """
    out: dict[str, Any] = {}
    for key in ORDER:
        if key not in appearance:
            continue
        value = appearance[key]
        if key in _OPTIONAL and not value:
            continue
        if isinstance(value, dict):
            value = {k: value[k] for k in sorted(value, key=_sort_key)}
        out[key] = value
    for key, value in appearance.items():  # keys a newer version wrote: keep them
        if key not in out and key not in _OPTIONAL:
            out[key] = value
    return out


def _sort_key(key: str) -> tuple[int, str]:
    return len(key), key


def with_color(appearance: dict[str, Any], target: Target, color: str | None) -> dict[str, Any]:
    """A copy of ``appearance`` with ``color`` on ``target`` (None removes it).

    Removing the part colour sets the default. Raises ValueError on a bad colour.
    """
    if color is not None and not valid_color(color):
        raise ValueError(f"Invalid colour '{color}'. Use #RRGGBB.")
    out = copy.deepcopy(appearance)
    if target.kind == "part":
        out["part_color"] = color.upper() if color else PART_COLOR
        out.setdefault("faces", {})
        return ordered(out)
    key = _KEYS[target.kind]
    colors = _map(out, key)
    if color is None:
        colors.pop(target.key, None)
    else:
        colors[target.key] = color.upper()
    out[key] = colors
    out.setdefault("faces", {})
    return ordered(out)


def sketch_color(appearance: dict[str, Any], sketch_id: str) -> str | None:
    """The display colour set on a sketch (TR233), or None for the usual colour."""
    return _map(appearance, "sketches").get(sketch_id)


def color_of(appearance: dict[str, Any], target: Target) -> str | None:
    """The colour set on ``target`` itself, or None."""
    if target.kind == "part":
        return part_color(appearance)
    return _map(appearance, _KEYS[target.kind]).get(target.key)


_COPY = re.compile(r"^([^/]+)/(?:instance\d+\.\d+|mirror\d+)/(.+)$")


def propagating(doc: Any) -> frozenset[str]:
    """Ids of the patterns and mirrors with Propagate Colours on (audit B item 2, D717)."""
    return frozenset(
        f.id for f in getattr(doc, "features", []) if f.params.get("propagate_colours") is True
    )


def seed_name(name: str, propagate: Collection[str]) -> str | None:
    """The seed face a copy's face came from, when its pattern propagates colours:
    ``f9/instance2.1/f6/side/e3`` gives ``f6/side/e3``. Copies of copies follow back."""
    found = None
    while True:
        match = _COPY.match(name)
        if match is None or match.group(1) not in propagate:
            return found
        name = found = match.group(2)


def _feature_of(name: str) -> str:
    """The feature id that made a face, from its name (FDEF_SPEC 8.1)."""
    return name.split("/", 1)[0]


def body_faces(shape: TopoDS_Shape) -> list[ShapeMap]:
    """A face map per body, in Solid Bodies order."""
    from fdcad.core.features.solids import solids

    maps = []
    for body in solids(shape) or [shape]:
        fmap = ShapeMap()
        TopExp.MapShapes_s(body, TopAbs_FACE, fmap)
        maps.append(fmap)
    return maps


def face_colors(
    named: NamedShape, appearance: dict[str, Any], propagate: Collection[str] = ()
) -> list[tuple[TopoDS_Face, str]]:
    """Every face that is not in the part colour, with its colour (face, feature, body).

    Copies made by a pattern or mirror in ``propagate`` take their seed face's colour."""
    faces = _map(appearance, "faces")
    features = _map(appearance, "features")
    bodies = _map(appearance, "bodies")
    if not (faces or features or bodies):
        return []
    maps = body_faces(named.shape) if bodies else []
    fmap = ShapeMap()
    TopExp.MapShapes_s(named.shape, TopAbs_FACE, fmap)
    groups: dict[int, list[str]] = {}
    for name, face in named.faces:
        index = fmap.FindIndex(face)
        if index:
            groups.setdefault(index, []).append(name)
            seed = seed_name(name, propagate) if propagate else None
            if seed is not None:
                groups[index].append(seed)
    out: list[tuple[TopoDS_Face, str]] = []
    for index, names in groups.items():
        face = TopoDS.Face(fmap.FindKey(index))
        color = next((faces[n] for n in names if n in faces), None)
        if color is None:
            owners = [_feature_of(n) for n in names]
            color = next((features[o] for o in owners if o in features), None)
        if color is None and maps:
            body = next((i for i, m in enumerate(maps) if m.Contains(face)), None)
            if body is not None:
                color = bodies.get(str(body + 1))
        if color is not None:
            out.append((face, color))
    return out


def appearance_entries(
    appearance: dict[str, Any], names: dict[str, str]
) -> list[tuple[str, str, list[Target]]]:
    """One (colour, label, targets) entry per item that carries a colour (D584).

    The part comes first, then bodies, features, and the coloured faces of each
    feature as one entry. ``names`` maps feature ids to their tree names.
    """
    out: list[tuple[str, str, list[Target]]] = [(part_color(appearance), "Part", [Target("part")])]
    for k, color in _map(appearance, "bodies").items():
        out.append((color, f"Body {k}", [Target("body", k)]))
    for k, color in _map(appearance, "features").items():
        out.append((color, names.get(k, k), [Target("feature", k)]))
    groups: dict[tuple[str, str], list[str]] = {}
    for k, color in _map(appearance, "faces").items():
        groups.setdefault((color, _feature_of(k)), []).append(k)
    for (color, owner), keys in groups.items():
        feature = names.get(owner, owner)
        label = f"Face of {feature}" if len(keys) == 1 else f"{len(keys)} faces of {feature}"
        out.append((color, label, [Target("face", k) for k in keys]))
    return out


def colors_in_use(appearance: dict[str, Any], names: dict[str, str]) -> list[tuple[str, list[str]]]:
    """Each colour in use with what carries it, for the tree (P2.11 item 1).

    ``names`` maps feature ids to their tree names.
    """
    found: dict[str, list[str]] = {part_color(appearance): ["Part"]}
    for key, label in (("bodies", "Body {}"), ("features", "{}")):
        for k, color in _map(appearance, key).items():
            text = label.format(names.get(k, k) if key == "features" else k)
            found.setdefault(color, []).append(text)
    # Faces by the feature that made them: face names are internal (FDEF_SPEC 8.1).
    counts: dict[tuple[str, str], int] = {}
    for k, color in _map(appearance, "faces").items():
        owner = _feature_of(k)
        pair = (color, names.get(owner, owner))
        counts[pair] = counts.get(pair, 0) + 1
    for (color, feature), count in counts.items():
        text = f"Face of {feature}" if count == 1 else f"{count} faces of {feature}"
        found.setdefault(color, []).append(text)
    return list(found.items())
