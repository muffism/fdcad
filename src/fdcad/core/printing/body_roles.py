"""Body roles for printing (TR382, DECISIONS D796).

A body can be a Part (the default), a Modifier, a Negative Volume, a Support
Enforcer or a Support Blocker. Roles are kept in the part's print setup under
``body_roles``: a face name of the body (its mark, as for hidden bodies, D410)
to the role, so a role survives rebuilds that renumber the bodies. Export 3MF
writes them in the forms the slicers read (``core.io.export``); this module
holds the role names, the values each slicer family uses and the status line.
No Qt and no kernel calls beyond small topology queries.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from fdcad.core.document.model import Document
from fdcad.core.naming.names import NamedShape

BODY_ROLES = "body_roles"
PART, MODIFIER, NEGATIVE = "part", "modifier", "negative"
ENFORCER, BLOCKER = "support_enforcer", "support_blocker"
ROLES = (PART, MODIFIER, NEGATIVE, ENFORCER, BLOCKER)

#: Export 3MF "Slicer" choice: the assembly form (Bambu Studio, OrcaSlicer, Cura) or the
#: one object form PrusaSlicer reads (spec TR382 file forms item 2).
SLICER_DEFAULT, SLICER_PRUSA = "default", "prusa"
SLICER_FORMS = (SLICER_DEFAULT, SLICER_PRUSA)
#: Slicer targets (TR385, D1206): the two forms, Cura alone, and plain 3MF with no slicer
#: settings at all, for any program.
SLICER_CURA, SLICER_PLAIN = "cura", "plain"
SLICER_TARGETS = (SLICER_DEFAULT, SLICER_PRUSA, SLICER_CURA, SLICER_PLAIN)
#: What each target keeps, shown in the export options (TR385).
TARGET_SUPPORT = {
    SLICER_DEFAULT: "Bambu Studio and OrcaSlicer: body names, all print roles, per body "
    "settings, pauses, colour changes and settings by height. Cura: modifier and support "
    "roles and per body walls, infill and supports.",
    SLICER_PRUSA: "PrusaSlicer: body names, all print roles, per body settings, pauses, "
    "colour changes and settings by height. Other slicers load one object.",
    SLICER_CURA: "Cura: modifier and support roles and per body walls, infill, supports "
    "and extruder. No negative volumes and nothing by height.",
    SLICER_PLAIN: "Any program: bodies, colours and names only. Print roles and print "
    "settings are not written.",
}

#: ``subtype`` of a ``<part>`` in ``Metadata/model_settings.config`` (family B).
BAMBU_SUBTYPES = {
    PART: "normal_part",
    MODIFIER: "modifier_part",
    NEGATIVE: "negative_part",
    ENFORCER: "support_enforcer",
    BLOCKER: "support_blocker",
}
#: ``volume_type`` of a ``<volume>`` in ``Metadata/Slic3r_PE_model.config`` (family P).
PRUSA_TYPES = {
    PART: "ModelPart",
    MODIFIER: "ParameterModifier",
    NEGATIVE: "NegativeVolume",
    ENFORCER: "SupportEnforcer",
    BLOCKER: "SupportBlocker",
}
CURA_NAMESPACE = "http://software.ultimaker.com/xml/cura/3mf/2015/10"
#: The Cura setting a role turns on; Cura has no negative volume, so a negative body is
#: an anti overhang mesh: not printed, but nothing is cut (item 10).
CURA_SETTINGS = {
    MODIFIER: "cura:infill_mesh",
    ENFORCER: "cura:support_mesh",
    BLOCKER: "cura:anti_overhang_mesh",
    NEGATIVE: "cura:anti_overhang_mesh",
}


def stored(doc: Document) -> dict[str, str]:
    """The saved marks and roles; anything damaged is left out."""
    raw = (doc.print_setup or {}).get(BODY_ROLES)
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and v in ROLES and v != PART}


def stored_all(doc: Document) -> dict[str, str]:
    """The saved marks and roles, Part included (it overrides a role from the file)."""
    raw = (doc.print_setup or {}).get(BODY_ROLES)
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and v in ROLES}


def roles_of(
    doc: Document, named: NamedShape | None, defaults: dict[str, str] | None = None
) -> list[str]:
    """The role of every body of ``named``, in Solid Bodies order. ``defaults`` (roles a
    feature gave its bodies, TR386) apply where the user set none; a body set back to
    Part keeps a stored "part"."""
    from fdcad.core.body_visibility import body_names

    marks = {k: v for k, v in (defaults or {}).items() if v in ROLES}
    marks.update(stored_all(doc))
    out = []
    for names in body_names(named):
        out.append(next((marks[n] for n in sorted(names) if n in marks), PART))
    return out


def with_roles(
    doc: Document,
    named: NamedShape | None,
    indices: Iterable[int],
    role: str,
    defaults: dict[str, str] | None = None,
) -> dict[str, str]:
    """The ``body_roles`` value after giving the bodies at ``indices`` ``role``. A body
    whose role came from its feature (``defaults``, TR386) keeps a stored Part."""
    from fdcad.core.body_visibility import body_names, mark_of

    if role not in ROLES:
        raise ValueError(f"Unknown body role {role}.")
    all_names = body_names(named)
    out = dict(stored_all(doc))
    for i in indices:
        if not 0 <= i < len(all_names):
            continue
        for name in all_names[i]:
            out.pop(name, None)
        mark = mark_of(all_names[i])
        from_feature = bool(all_names[i] & set(defaults or {}))
        if mark is not None and (role != PART or from_feature):
            out[mark] = role
    return out


def any_role(roles: Sequence[str]) -> bool:
    """True when a body has a role other than Part."""
    return any(r != PART for r in roles)


def printed_count(roles: Sequence[str]) -> int:
    """How many bodies print as parts."""
    return sum(1 for r in roles if r == PART)


def status_line(form: str, roles: Sequence[str]) -> str:
    """What each slicer family keeps (spec TR382 file forms item 24), or "" with no roles."""
    if not any_role(roles):
        return ""
    if form == SLICER_PLAIN:
        return "Plain 3MF: print roles not written, every body prints."
    if form == SLICER_CURA:
        line = "Cura: modifier, support enforcer and support blocker kept"
        if NEGATIVE in roles:
            line += "; negative volume not cut, body not printed"
        return line + ". Other slicers: roles dropped."
    if form == SLICER_PRUSA:
        return (
            "PrusaSlicer: all roles kept. Bambu Studio, OrcaSlicer, Cura: roles dropped, "
            "all bodies merged and printed."
        )
    cura = "Cura: modifier, support enforcer and support blocker kept"
    if NEGATIVE in roles:
        cura += "; negative volume not cut, body not printed"
    return (
        f"Bambu Studio, OrcaSlicer: all roles kept. {cura}. PrusaSlicer: roles dropped, "
        "bodies load as separate objects and all print; export with Slicer set to PrusaSlicer."
    )
