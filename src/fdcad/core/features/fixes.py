"""One click fixes that change a feature's data (PLAN 5A item 6, CLAUDE.md rule 12).

A fix is offered by a feature as a button; nothing here runs unless the user
clicks it. ``fixed_feature`` returns the edited copy, which the UI applies as
one undoable command.

Actions:

- ``skip_items``: remove the picks named in ``data["items"]`` from the
  reference lists in ``data["keys"]`` (fillet and chamfer edges that fail).
- ``set_param``: set ``data["param"]`` to the length or angle ``data["value"]``
  (for example a radius reduced to the largest one the edges allow).
- ``add_refs``: add the references ``data["refs"]`` to the list ``data["key"]``
  (a shell face to leave open, TR278, D1406).
- ``set_ref``: put the one reference in ``data["refs"]`` in place of the pick
  ``data["key"]`` (a hinge moved to the edge where its bodies meet, D2627).

``tied_values`` handles ``tie_values``, which changes two features and adds a
variable: two depths that made one face, tied so the face is whole again (D2628).
"""

from __future__ import annotations

import copy

from fdcad.core.document.model import Document, Feature, Param, Variable
from fdcad.core.features.base import Fix
from fdcad.core.units import UnitSystem

ACTIONS = ("skip_items", "set_param", "add_refs", "set_ref")


def _typed(value: float, units: UnitSystem, angle: bool) -> str:
    if angle:
        import math

        return f"{math.degrees(value):.4g}"
    shown = value / 25.4 if units is UnitSystem.IN else value
    return f"{shown:.4g}"


def _renumber_edge_params(feature: Feature, gone: list[int]) -> None:
    """Per edge values (``radius_<k>``, ``vr_<k>_...``) follow their edge (D609).

    Removing picked edge ``k`` drops its values and moves those of later edges
    up one place, so every remaining edge keeps its own radius.
    """
    params: dict[str, object] = {}
    for name, value in feature.params.items():
        head, sep, rest = name.partition("_")
        number, sep2, tail = rest.partition("_")
        if head not in ("radius", "vr") or not sep or not number.isdigit():
            params[name] = value
            continue
        k = int(number)
        if k in gone:
            continue
        k -= sum(1 for g in gone if g < k)
        params[f"{head}_{k}{sep2}{tail}"] = value
    feature.params.clear()
    feature.params.update(params)  # type: ignore[arg-type]


def fixed_feature(doc: Document, fid: str, fix: Fix) -> Feature | None:
    """The feature after ``fix``, or None when the fix does not change data."""
    if fix.action not in ACTIONS:
        return None
    try:
        feature = copy.deepcopy(doc.feature(str(fix.data.get("feature", fid))))
    except KeyError:
        return None
    if fix.action == "add_refs":  # TR278 (D1406)
        key = str(fix.data.get("key", ""))
        current = feature.refs.get(key)
        listed = list(current) if isinstance(current, list) else []
        names = {r.get("name") for r in listed if isinstance(r, dict)}
        for ref in fix.data.get("refs", []):
            if isinstance(ref, dict) and ref.get("name") not in names:
                listed.append(copy.deepcopy(ref))
        feature.refs[key] = listed
        return feature
    if fix.action == "set_ref":  # D2627
        key = str(fix.data.get("key", ""))
        given = [r for r in fix.data.get("refs", []) if isinstance(r, dict)]
        if not key or len(given) != 1:
            return None
        ref = copy.deepcopy(given[0])
        feature.refs[key] = [ref] if isinstance(feature.refs.get(key), list) else ref
        return feature
    if fix.action == "skip_items":
        from fdcad.core.features.modify import piece_base

        items = {piece_base(str(n)) for n in fix.data.get("items", [])}
        places = fix.data.get("positions")
        for key in fix.data.get("keys", ["edges"]):
            refs = feature.refs.get(str(key))
            if isinstance(refs, list):
                if key == "edges" and isinstance(places, list) and places:
                    # By place in the picked list: two picks can share a name (D1043).
                    picked = [k for k, r in enumerate(refs) if isinstance(r, dict)]
                    drop = {picked[int(p) - 1] for p in places if 0 < int(p) <= len(picked)}
                    gone = sorted(int(p) for p in places if 0 < int(p) <= len(picked))
                    feature.refs[str(key)] = [r for k, r in enumerate(refs) if k not in drop]
                else:
                    gone = [
                        k
                        for k, r in enumerate(refs, start=1)
                        if isinstance(r, dict) and r.get("name") in items
                    ]
                    feature.refs[str(key)] = [
                        r for r in refs if not (isinstance(r, dict) and r.get("name") in items)
                    ]
                if key == "edges" and gone:
                    _renumber_edge_params(feature, gone)
        return feature
    name = str(fix.data["param"])
    value = float(fix.data["value"])
    angle = bool(fix.data.get("angle", False))
    feature.params[name] = Param(_typed(value, doc.units, angle), value)
    return feature


def tied_values(doc: Document, fix: Fix) -> tuple[dict[str, Feature], list[Variable]] | None:
    """The features and variables after a ``tie_values`` fix (D2628), or None.

    A new length variable takes ``data["expr"]`` (the leading value as typed), and each
    value in ``data["params"]`` becomes ``=<head><variable><tail>``, where the tail (such
    as `` + 2``) keeps a face that started elsewhere lined up, and a head (such as
    ``14mm - ``) keeps a face that moves the other way lined up (D2656). Nothing is changed in
    ``doc``: the caller applies the result as one undoable step.
    """
    from fdcad.core.rebuild.split_faces import TIE_VALUES, variable_name
    from fdcad.core.units import Kind

    if fix.action != TIE_VALUES:
        return None
    try:
        lead = doc.feature(str(fix.data["params"][0]["feature"]))
    except (KeyError, IndexError, TypeError):
        return None
    name = str(fix.data.get("variable", ""))
    if not name or any(v.name.lower() == name.lower() for v in doc.variables):
        name = variable_name(doc, lead, str(fix.data["params"][0]["param"]))
    variables = [
        *copy.deepcopy(doc.variables),
        Variable(name, Kind.LENGTH, str(fix.data["expr"]), float(fix.data["value"])),
    ]
    features: dict[str, Feature] = {}
    for item in fix.data["params"]:
        fid = str(item["feature"])
        try:
            feature = features.get(fid) or copy.deepcopy(doc.feature(fid))
        except KeyError:
            return None
        text = f"={item.get('head', '')}{name}{item.get('tail', '')}"
        feature.params[str(item["param"])] = Param(text, float(item["value"]))
        features[fid] = feature
    return features, variables
