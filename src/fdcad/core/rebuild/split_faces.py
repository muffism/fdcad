"""Say when a picked face has split because two features no longer line up (D2628).

A face can be one face only because two features end at the same number: two
plates 10 mm thick side by side have one top, which carries the names of both.
A pick on it stores one of the names and the face's snapshot. When one of the
numbers changes, the top splits into two faces at different heights; the stored
name now gives only its own piece, so what was picked lies over the wrong piece
or is lost (IDEAS 70, found by the edit storm of D2602). The feature's own error
is right, but does not say why.

After a rebuild, each face reference of a feature with an error or a warning is
checked: when the face its name gives no longer matches the snapshot, and
faces parallel to it and near its plane, from two or more features, add up to the
picked face's area and centre, the face has split. The feature's message then
says which features' faces it was made of and how far apart they are now. When
both pieces are the end faces of blind extrudes, two fixes are offered, one for
each feature's depth: tie both depths to one new variable so the faces line up
again and stay together (``tie_values``, applied only when the user clicks).
"""

from __future__ import annotations

import itertools
import math
import re
from dataclasses import dataclass, replace
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureResult, FeatureState, Fix, Issue
from fdcad.core.naming.names import NamedShape

#: The fix action that ties two feature values to one new variable.
TIE_VALUES = "tie_values"
#: The issue code of the explanation.
SPLIT_FACE = "split_face"
_FEATURE = re.compile(r"^(f\d+)/")
#: Most faces tried as pieces of one picked face.
_MOST_CANDIDATES = 12
#: Most pieces one picked face is looked for in.
_MOST_PIECES = 4
_AREA_SHARE = 1e-3


@dataclass(frozen=True)
class Piece:
    """One of the faces a picked face split into."""

    names: tuple[str, ...]
    #: Where the face's plane is along the picked face's normal (mm).
    level: float
    area: float


@dataclass(frozen=True)
class Split:
    """A picked face that is now several faces of different features."""

    name: str
    pieces: tuple[Piece, ...]
    #: The features whose faces made the picked face, in tree order.
    owners: tuple[str, ...]

    @property
    def gap(self) -> float:
        """How far apart the pieces' planes are now (mm)."""
        levels = [p.level for p in self.pieces]
        return max(levels) - min(levels)


def owners_of(names: tuple[str, ...] | list[str]) -> list[str]:
    """The ids of the features that made faces with these names, in name order."""
    out: list[str] = []
    for name in names:
        match = _FEATURE.match(name)
        if match is not None and match.group(1) not in out:
            out.append(match.group(1))
    return out


def face_refs(refs: Any) -> list[dict[str, Any]]:
    """Every stored face reference with a flat face's snapshot in ``refs``."""
    out: list[dict[str, Any]] = []
    if isinstance(refs, dict):
        snap = refs.get("snapshot")
        if (
            isinstance(refs.get("name"), str)
            and refs.get("kind", "face") == "face"
            and isinstance(snap, dict)
            and all(key in snap for key in ("normal", "area", "point"))
        ):
            out.append(refs)
        for value in refs.values():
            if isinstance(value, dict | list):
                out += face_refs(value)
    elif isinstance(refs, list):
        for value in refs:
            out += face_refs(value)
    return out


def split_of(body: NamedShape, ref: dict[str, Any]) -> Split | None:
    """The split of the picked flat face ``ref`` in ``body``, or None when its name still
    gives the face as picked, or no faces of two or more features make it up."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.resolve import _matches, face_snapshot
    from fdcad.core.plane_normal import plane_normal

    name = str(ref["name"])
    snap = ref["snapshot"]
    normal = [float(v) for v in snap["normal"]]
    point = [float(v) for v in snap["point"]]
    area = float(snap["area"])
    if area <= 0:
        return None
    named = body.face(name)
    if named is None:
        return None  # a split keeps each name on its own piece
    now = face_snapshot(named)
    # A piece of a split face is smaller than the face that was picked.
    if _matches(snap, now) or float(now["area"]) >= area * (1 - _AREA_SHARE):
        return None
    within = _outer_region(named)
    level = _dot(point, normal)
    reach = math.sqrt(area)
    near: list[tuple[float, Any, dict[str, Any]]] = []
    for face in faces_of(body.shape):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        n = plane_normal(face)
        if n is None or _dot(n, normal) < 1 - 1e-6:
            continue
        on = surface.Plane().Location()
        if abs(_dot((on.X(), on.Y(), on.Z()), normal) - level) > reach:
            continue
        current = face_snapshot(face)
        if not face.IsSame(named) and _inside(within, current["point"], now["point"], normal):
            continue  # in a hole of the named piece (a hole's floor), not beside it
        across = _in_plane(current["point"], point, normal)
        near.append((across, face, current))
    near.sort(key=lambda item: item[0])
    near = near[:_MOST_CANDIDATES]
    must = [k for k, (_d, face, _s) in enumerate(near) if face.IsSame(named)]
    for size in range(2, _MOST_PIECES + 1):
        for chosen in itertools.combinations(range(len(near)), size):
            if must and must[0] not in chosen:
                continue
            snaps = [near[k][2] for k in chosen]
            total = sum(float(s["area"]) for s in snaps)
            if abs(total - area) > max(_AREA_SHARE * area, 1e-6):
                continue
            middle = [
                sum(float(s["area"]) * s["point"][i] for s in snaps) / total for i in range(3)
            ]
            if _in_plane(middle, point, normal) > 1e-3 * reach + 1e-3:
                continue
            pieces = tuple(
                Piece(
                    tuple(body.names_of(near[k][1])),
                    _dot(near[k][2]["point"], normal),
                    float(near[k][2]["area"]),
                )
                for k in chosen
            )
            owners = owners_of([n for p in pieces for n in p.names])
            if (
                len(owners) < 2
                or max(p.level for p in pieces) - min(p.level for p in pieces) < 1e-6
            ):
                return None
            return Split(name, pieces, tuple(owners))
    return None


def _outer_region(face: Any) -> Any:
    """``face`` with its holes filled: the face made from its outer edge only."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepTools import BRepTools

    return BRepBuilderAPI_MakeFace(
        BRep_Tool.Surface_s(face), BRepTools.OuterWire_s(face), True
    ).Face()


def _inside(region: Any, at: Any, on: Any, normal: list[float]) -> bool:
    """True when ``at``, moved along ``normal`` onto the plane through ``on``, lies in
    ``region``."""
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    lift = _dot([float(at[i]) - float(on[i]) for i in range(3)], normal)
    p = gp_Pnt(*(float(at[i]) - lift * normal[i] for i in range(3)))
    return bool(BRepClass_FaceClassifier(region, p, 1e-6).State() == TopAbs_IN)


def _dot(a: Any, b: Any) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b, strict=False))


def _in_plane(a: Any, b: Any, normal: list[float]) -> float:
    """The distance from ``a`` to ``b`` across ``normal``."""
    d = [float(a[i]) - float(b[i]) for i in range(3)]
    along = _dot(d, normal)
    return math.sqrt(max(sum(c * c for c in d) - along * along, 0.0))


def _names(doc: Document, fids: list[str] | tuple[str, ...]) -> str:
    names = [doc.feature(f).name for f in fids]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _mm(value: float) -> str:
    return f"{value:.4g} mm"


def message_for(doc: Document, split: Split) -> str:
    """What happened to the picked face, in words."""
    known = [f for f in split.owners if any(g.id == f for g in doc.features)]
    return (
        f"The picked face {split.name} was one face of {_names(doc, known)}, which no longer "
        f"line up: their faces are now {_mm(split.gap)} apart. Change the values so the faces "
        "meet again, or pick the face again."
    )


def _blind_end(doc: Document, piece: Piece) -> tuple[Feature, float] | None:
    """The blind extrude whose end face ``piece`` is, and how its face moves along the
    picked face's normal when its depth grows (+1 for a boss, -1 for a cut)."""
    from fdcad.core.features.extrude import direction1

    for name in piece.names:
        match = re.fullmatch(r"(f\d+)/cap/end", name)
        if match is None:
            continue
        try:
            feature = doc.feature(match.group(1))
        except KeyError:
            continue
        if feature.type != "extrude" or direction1(feature) != "blind":
            continue
        if not isinstance(feature.params.get("depth"), Param):
            continue
        cut = str(feature.params.get("operation", "boss")) == "cut"
        return feature, -1.0 if cut else 1.0
    return None


def variable_name(doc: Document, feature: Feature, param: str) -> str:
    """A new variable name for ``param`` of ``feature``, not used by the part yet."""
    from fdcad.core.equations.edit import value_names

    base = re.sub(r"[^A-Za-z0-9_]+", "_", f"{feature.name}_{param}").strip("_")
    if not base or not base[0].isalpha():
        base = f"V_{base}".strip("_")
    taken = {v.name.lower() for v in doc.variables} | {n.lower() for n in value_names(doc)}
    name, k = base, 2
    while name.lower() in taken:
        name, k = f"{base}_{k}", k + 1
    return name


def tie_fixes(doc: Document, split: Split) -> list[Fix]:
    """One fix for each of two blind extrude ends: both depths from one new variable at
    that extrude's depth, the other's set so its face lines up again."""
    if len(split.pieces) != 2:
        return []
    ends = [_blind_end(doc, p) for p in split.pieces]
    if ends[0] is None or ends[1] is None or ends[0][0].id == ends[1][0].id:
        return []
    from fdcad.core.equations.edit import plain_text
    from fdcad.core.units import Kind

    fixes = []
    for lead, follow in ((0, 1), (1, 0)):
        (first, lead_slope), (second, slope) = ends[lead], ends[follow]  # type: ignore[misc]
        depth, other = first.params["depth"], second.params["depth"]
        assert isinstance(depth, Param) and isinstance(other, Param)
        lined_up = other.value + slope * (split.pieces[lead].level - split.pieces[follow].level)
        if lined_up <= 0:
            continue
        head, tail = "", ""
        if lead_slope == slope:  # both faces move the same way: an offset keeps them level
            offset = lined_up - depth.value
            sign = "+" if offset >= 0 else "-"
            step = plain_text(abs(offset), Kind.LENGTH, doc) + doc.units.value  # "6mm"
            tail = "" if abs(offset) < 1e-9 else f" {sign} {step}"
        else:
            # A boss end rises with its depth where a cut floor sinks with its own, so the
            # two depths keep a fixed sum: "=14mm - Plate_depth" (D2656). An offset made
            # them line up only at today's value and split again at the next change.
            total = lined_up + depth.value
            head = plain_text(total, Kind.LENGTH, doc) + doc.units.value + " - "
        fixes.append(
            Fix(
                f"Use {first.name}'s Depth for Both",
                TIE_VALUES,
                {
                    "variable": variable_name(doc, first, "depth"),
                    "expr": depth.expr,
                    "value": depth.value,
                    "params": [
                        {"feature": first.id, "param": "depth", "tail": "", "value": depth.value},
                        {
                            "feature": second.id,
                            "param": "depth",
                            "head": head,
                            "tail": tail,
                            "value": lined_up,
                        },
                    ],
                },
            )
        )
    return fixes


def _body_before(active: list[Feature], index: int, results: dict[str, FeatureResult]) -> Any:
    for feature in reversed(active[:index]):
        result = results.get(feature.id)
        if (
            result is not None
            and result.body is not None
            and result.state is not FeatureState.ERROR
        ):
            return result.body
    return None


def add_split_faces(
    doc: Document, active: list[Feature], results: dict[str, FeatureResult]
) -> None:
    """Explain every error or warning whose picked face has split, with tie fixes."""
    for index, feature in enumerate(active):
        result = results.get(feature.id)
        if result is None or not result.issues:
            continue
        refs = face_refs(feature.refs)
        if not refs:
            continue
        body = _body_before(active, index, results)
        if body is None:
            continue
        found: list[Split] = []
        for ref in refs:
            try:
                split = split_of(body, ref)
            except Exception:  # an explanation only: never break the rebuild (CLAUDE.md 5.7)
                split = None
            if split is not None and all(s.name != split.name for s in found):
                found.append(split)
        if found:
            results[feature.id] = replace(result, issues=_explained(doc, result, found))


def _explained(doc: Document, result: FeatureResult, found: list[Split]) -> list[Issue]:
    issues = list(result.issues)
    highlight = [n for s in found for p in s.pieces for n in p.names[:1]]
    text = " ".join(message_for(doc, s) for s in found)
    fixes = [f for s in found for f in tie_fixes(doc, s)]
    at = next((k for k, i in enumerate(issues) if i.state is FeatureState.ERROR), None)
    if at is None:
        issues.append(Issue(FeatureState.WARNING, text, fixes, highlight, SPLIT_FACE))
        return issues
    error = issues[at]
    issues[at] = replace(
        error,
        message=f"{error.message} {text}",
        fixes=[*error.fixes, *fixes],
        highlight=[*error.highlight, *highlight],
        code=error.code or SPLIT_FACE,
    )
    return issues
