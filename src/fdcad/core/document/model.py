"""The part document: what a `.fdef` file holds, as plain typed objects (`FDEF_SPEC.md`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fdcad.core.units import Kind, UnitSystem

if TYPE_CHECKING:
    from fdcad.core.graph.model import Graph

#: Newest schema this version reads and writes. Files are written with the lowest
#: schema that holds their data: parts without graphs (D370) or configured values
#: (D391) stay schema 1, so they open and save unchanged (FDEF_SPEC 12A, 15).
SCHEMA_VERSION = 2
BASE_SCHEMA_VERSION = 1
DEFAULT_PART_COLOR = "#B4BCC4"

# Built in feature ids (FDEF_SPEC 5.2).
ORIGIN_ID = "f1"
FRONT_PLANE_ID = "f2"
TOP_PLANE_ID = "f3"
RIGHT_PLANE_ID = "f4"


@dataclass
class Param:
    """A user editable value: the typed text and its evaluated internal value."""

    expr: str
    value: float


#: A list or object is a value from a newer FDCAD, kept as it is (D726).
ParamValue = Param | str | bool | int | float | list[Any] | dict[str, Any] | None


@dataclass
class Variable:
    """A global variable (FDEF_SPEC 4). ``comment`` is the equations manager note."""

    name: str
    kind: Kind
    expr: str
    value: float
    comment: str = ""
    #: Allowed values (TR274, D906), or None for any: ``{"choices": [numbers]}`` or
    #: ``{"min": number, "max": number}`` (either may be left out), in mm or radians.
    allowed: dict[str, Any] | None = None
    #: Read from a CSV file (TR198 item 2, D2102), or None: ``{"file", "row",
    #: "column"}``; see ``core.equations.csv_lookup``.
    lookup: dict[str, Any] | None = None
    #: "" for a number, "text" or "yes_no" (TR417, D2104); see
    #: ``core.equations.variable_types``.
    type: str = ""
    #: The group the equations manager shows it in (TR417), or "".
    group: str = ""


@dataclass
class Feature:
    """One entry in the feature tree (FDEF_SPEC 5.1).

    ``data`` holds keys that only some feature types use, such as a sketch's
    entities, plus unknown keys from newer files, so they survive a save.
    """

    id: str
    type: str
    name: str
    suppressed: bool = False
    params: dict[str, ParamValue] = field(default_factory=dict)
    refs: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    """A part. Lengths are millimetres and angles radians; ``units`` is for display only."""

    units: UnitSystem = UnitSystem.MM
    next_id: int = 1
    variables: list[Variable] = field(default_factory=list)
    configurations: dict[str, Any] = field(default_factory=dict)
    features: list[Feature] = field(default_factory=list)
    rollback: str | None = None
    appearance: dict[str, Any] = field(default_factory=dict)
    print_setup: dict[str, Any] = field(default_factory=dict)
    #: Saved camera views (TR14, FDEF_SPEC 2 item 14): see ``core.document.saved_views``.
    views: list[dict[str, Any]] = field(default_factory=list)
    #: Tree folders and feature comments (TR23, FDEF_SPEC 2 item 15).
    tree: dict[str, Any] = field(default_factory=dict)
    #: A linked equations text file, read on open and on Rebuild (TR25, D749). Empty: none.
    equations_file: str = ""
    embedded: dict[str, Any] = field(default_factory=dict)
    # Version that last saved the file. Informational, so it is not part of equality.
    app_version: str = field(default="", compare=False)
    #: The finished solid saved with the part (FDEF_SPEC 13A, D1102), so a part shows at
    #: once on its first open anywhere. Written by Save from the last rebuild, used on
    #: open only while its key matches the document. Not part of equality or the cache key.
    solid: dict[str, Any] = field(default_factory=dict, compare=False)
    extra: dict[str, Any] = field(default_factory=dict)
    #: Node graphs (Phase 7, FDEF_SPEC 12A). At most one per part in the editor.
    graphs: list[Graph] = field(default_factory=list)
    #: The part's material (TR78, D803): see ``core.materials``. Empty: none chosen.
    material: dict[str, Any] = field(default_factory=dict)
    #: Custom properties (TR82, D810): see ``core.properties``. Empty: none.
    properties: list[dict[str, Any]] = field(default_factory=list)
    #: Typed mass properties (TR80, D1021): see ``core.mass.MassOverride``. Empty: none.
    mass_override: dict[str, Any] = field(default_factory=dict)
    #: Values features measured on the last rebuild, by feature id, such as a Fill
    #: Pattern's ``count`` (TR57). Formulas read them; never saved, not part of equality.
    measured: dict[str, dict[str, float]] = field(default_factory=dict, compare=False, repr=False)
    #: What opening the file left out or changed, as sentences for the user, such as a
    #: damaged configuration entry or a repeated folder name (audit D3 item 21, D5 item
    #: 4, D2678). Filled by the reader; never saved, not part of equality.
    load_warnings: list[str] = field(default_factory=list, compare=False, repr=False)

    def new_feature_id(self) -> str:
        """Return the next feature id. Ids are never reused."""
        fid = f"f{self.next_id}"
        self.next_id += 1
        return fid

    def feature(self, fid: str) -> Feature:
        """Return the feature with id ``fid``. Raises KeyError if there is none."""
        for f in self.features:
            if f.id == fid:
                return f
        raise KeyError(fid)


def default_configurations() -> dict[str, Any]:
    """Configurations block of a new part: one configuration named Default.

    In memory the block has the schema 2 form (no ``suppressed`` lists, D391).
    """
    return {
        "active": "Default",
        "items": [{"name": "Default", "overrides": {}}],
        "design_table": None,
    }


def new_document(units: UnitSystem = UnitSystem.MM) -> Document:
    """A new part with the origin and the three default planes (FDEF_SPEC 5.2).

    The mm and inch templates differ only in ``units``; stored values are mm either way.
    """
    doc = Document(
        units=units,
        configurations=default_configurations(),
        appearance={"part_color": DEFAULT_PART_COLOR, "faces": {}},
        print_setup={"down_face": None},
    )
    builtins = [
        ("origin", "Origin", {}),
        ("plane", "Front Plane", {"basis": "xy"}),
        ("plane", "Top Plane", {"basis": "xz"}),
        ("plane", "Right Plane", {"basis": "yz"}),
    ]
    for ftype, name, params in builtins:
        doc.features.append(Feature(doc.new_feature_id(), ftype, name, params=dict(params)))
    return doc
