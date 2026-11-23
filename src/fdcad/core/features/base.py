"""The shared feature interface (PLAN section 5 item 2, CLAUDE.md rule 4).

Every feature type takes the incoming named solid plus resolved inputs and
returns the new named solid. Kernel exceptions never escape: the rebuild
engine turns them into a feature error (CLAUDE.md rule 7).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.profiles import Profile, SketchPlane
from fdcad.core.sketch.regions import Regions, compute
from fdcad.core.sketch.solver import SolveResult
from fdcad.core.units import Kind


class FeatureState(Enum):
    """OK, warning (yellow) or error (red), as shown in the feature tree."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Fix:
    """A one click fix offered to the user (PLAN 5A item 6). Never applied automatically.

    ``action`` names what to do, for example ``"add_to_param"``; ``data`` holds its
    arguments, for example ``{"param": "depth", "delta": 0.01}``.
    """

    label: str
    action: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Issue:
    """A warning or error on a feature, with optional fixes and geometry to highlight."""

    state: FeatureState
    message: str
    fixes: list[Fix] = field(default_factory=list)
    highlight: list[str] = field(default_factory=list)  # face, edge or entity names
    code: str = ""  # short kind, such as "zero_thickness", so the UI can recognise it


class FeatureError(Exception):
    """Raised by a feature when it cannot build. The message is shown to the user."""

    def __init__(
        self, message: str, fixes: list[Fix] | None = None, highlight: list[str] | None = None
    ) -> None:
        super().__init__(message)
        self.fixes = fixes or []
        self.highlight = highlight or []


@dataclass
class SketchOutput:
    """What a sketch feature produces for later features."""

    plane: SketchPlane
    model: Sketch
    solve: SolveResult
    profile: Profile | None
    profile_error: str | None = None
    _regions: Regions | None = field(default=None, repr=False, compare=False)

    def regions(self) -> Regions:
        """The sketch's regions (T5.3.1), computed on first use and then kept.

        Call it on a worker thread: features call it during the rebuild and the
        Selected Regions box from a background job (CLAUDE.md rule 2).
        """
        if self._regions is None:
            self._regions = compute(self.model)
        return self._regions


@dataclass(frozen=True)
class Datum:
    """Reference geometry made by a reference feature (PHASE2_SPEC P2.10).

    ``kind`` is ``plane``, ``axis``, ``point`` or ``frame`` (coordinate system).
    ``origin`` is a point on it. ``direction`` is the plane normal, the axis
    direction or the frame's Z axis; ``x_dir`` is the plane's or frame's X axis.
    ``size`` is a length to draw an axis with, or 0 to size it to the part.
    """

    kind: str
    origin: Vec3
    direction: Vec3 | None = None
    x_dir: Vec3 | None = None
    size: float = 0.0


@dataclass(frozen=True)
class ThreadMark:
    """A cosmetic thread (PHASE4_SPEC P4.2): shown on a round face, never modelled.

    ``origin`` is the centre where the thread starts, ``direction`` the unit axis
    along the thread. ``diameter`` is the major diameter, ``surface`` the diameter
    of the face it is drawn on; ``internal`` is True for a hole.
    """

    origin: tuple[float, float, float]
    direction: tuple[float, float, float]
    diameter: float
    pitch: float
    length: float
    surface: float
    internal: bool
    label: str = ""


@dataclass
class FeatureResult:
    """What a feature produced.

    ``body`` is the part after this feature (None while the part is still empty).
    ``plane`` and ``sketch`` are set by reference features and sketches.
    ``extras`` holds display data some types add (DECISIONS D290): ``face_colors``
    (face name to colour), ``reference`` (a curve or mesh shape drawn in the view
    but not part of the body) and ``report`` (lines of text for the user).
    """

    body: NamedShape | None
    issues: list[Issue] = field(default_factory=list)
    plane: SketchPlane | None = None
    sketch: SketchOutput | None = None
    key: str = ""
    #: Reference geometry of reference features (P2.10); planes also set ``plane``.
    datum: Datum | None = None
    seconds: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)
    #: Cosmetic threads this feature adds (P4.2).
    threads: list[ThreadMark] = field(default_factory=list)

    @property
    def state(self) -> FeatureState:
        """The worst state among the issues."""
        if any(i.state is FeatureState.ERROR for i in self.issues):
            return FeatureState.ERROR
        if any(i.state is FeatureState.WARNING for i in self.issues):
            return FeatureState.WARNING
        return FeatureState.OK


#: Optional common feature key (FDEF_SPEC 5.1, DECISIONS D527): the user kept the
#: separate body this feature made, so its ``separate_body`` warning is not shown.
KEEP_SEPARATE_BODY = "keep_separate_body"


def keeps_separate_body(feature: Feature) -> bool:
    """True when the user chose to keep the separate body this feature makes (D527)."""
    return feature.data.get(KEEP_SEPARATE_BODY) is True


def without_kept_body_warning(feature: Feature, result: FeatureResult) -> FeatureResult:
    """``result`` without its separate body warning when the feature keeps it (D527)."""
    if not keeps_separate_body(feature):
        return result
    issues = [i for i in result.issues if i.code != "separate_body"]
    if len(issues) == len(result.issues):
        return result
    from dataclasses import replace

    return replace(result, issues=issues)


@dataclass
class BuildContext:
    """Everything a feature may read while it builds."""

    document: Document
    body: NamedShape | None
    results: dict[str, FeatureResult]
    variables: dict[str, tuple[Kind, float]] = field(default_factory=dict)
    cancelled: Callable[[], bool] = lambda: False
    #: Name of the feature being built, for messages. Empty in previews and helpers.
    owner: str = ""
    #: Modelled threads show as cosmetic marks while editing (TR347, D1921).
    simplify_threads: bool = False
    #: The pattern copy being built (TR121 item 3, D2203): sketch text fields
    #: ``{copy}`` show it. 1 outside patterns and for the seed.
    copy_number: int = 1

    def result(self, fid: str) -> FeatureResult:
        """Result of an earlier feature. Raises FeatureError when it is missing or failed."""
        res = self.results.get(fid)
        if res is None:
            raise FeatureError(self._missing(fid))
        if res.state is FeatureState.ERROR:
            name = self._name(fid)
            raise FeatureError(f"{name} has an error. Fix {name} first.")
        return res

    def _missing(self, fid: str) -> str:
        """Why the earlier feature ``fid`` has no result, naming it (D431)."""
        prefix = f"{self.owner}: " if self.owner else ""
        try:
            feature = self.document.feature(fid)
        except KeyError:
            return f"{prefix}a reference points at a deleted feature. Choose another reference."
        name = feature.name
        if feature.suppressed:
            return f"{prefix}{name} is suppressed. Unsuppress {name} or choose another reference."
        return (
            f"{prefix}{name} is below this feature in the tree. "
            f"Move {name} above it or choose another reference."
        )

    def missing_message(self, fid: str) -> str:
        """Why the earlier feature ``fid`` gives nothing to refer to, naming it (D431)."""
        return self._missing(fid)

    def _name(self, fid: str) -> str:
        try:
            return self.document.feature(fid).name
        except KeyError:
            return fid


Vec3 = tuple[float, float, float]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 0 else (0.0, 0.0, 0.0)


def value_label(name: str) -> str:
    """A parameter name in words for messages: "count1" is "count 1", "end_condition" is
    "end condition"."""
    return re.sub(r"(\d+)$", r" \1", name).replace("_", " ")


@dataclass(frozen=True)
class PreviewHandle:
    """A drag handle on a feature preview that changes one parameter.

    A length handle (``centre`` is None) is an arrow: dragging it to a point
    ``t`` mm from ``base`` along ``direction`` sets the parameter to ``t * scale``.

    An angle handle (``centre`` set) is a curved arrow: ``base`` turns about the
    axis through ``centre`` along ``direction`` (right hand rule). Turning it by
    ``t`` radians sets the parameter to ``t * scale``.

    The arrow sits at ``tip`` and points along ``pointing``.

    ``step`` is the ruler tick step shown while dragging (mm, or radians for
    angle handles; 0 for no ruler). ``flips`` is True when dragging the handle
    back past its start flips the feature's direction (TOOL_SPEC T5.2.5).
    ``style`` is "arrow", "box" for a scale handle (a small cube, D411), or
    "flat" for a flat arrow drawn facing ``facing``, a direction toward the
    viewer (the section view's arrow, D586).
    ``snaps`` is True when Alt while dragging snaps the end to a part vertex or
    face (TOOL_SPEC T5.2.4, D525).
    """

    param: str
    base: Vec3
    direction: Vec3
    value: float
    scale: float = 1.0
    centre: Vec3 | None = None
    step: float = 0.0
    flips: bool = False
    style: str = "arrow"
    snaps: bool = False
    facing: Vec3 | None = None

    @property
    def is_angle(self) -> bool:
        """True for a handle that turns about an axis."""
        return self.centre is not None

    @property
    def radius(self) -> float:
        """Distance from the axis to ``base`` (0 for length handles)."""
        if self.centre is None:
            return 0.0
        return math.sqrt(_dot(self._arm, self._arm))

    @property
    def _arm(self) -> Vec3:
        """``base`` relative to its foot on the axis (angle handles)."""
        assert self.centre is not None
        c, d = self.centre, _unit(self.direction)
        rel = (self.base[0] - c[0], self.base[1] - c[1], self.base[2] - c[2])
        along = _dot(rel, d)
        return (rel[0] - d[0] * along, rel[1] - d[1] * along, rel[2] - d[2] * along)

    def point(self, t: float) -> Vec3:
        """The point ``t`` mm (or radians) from ``base``."""
        b, d = self.base, self.direction
        if self.centre is None:
            return (b[0] + d[0] * t, b[1] + d[1] * t, b[2] + d[2] * t)
        arm, axis = self._arm, _unit(d)
        side = _cross(axis, arm)
        foot = (b[0] - arm[0], b[1] - arm[1], b[2] - arm[2])
        cos, sin = math.cos(t), math.sin(t)
        return (
            foot[0] + arm[0] * cos + side[0] * sin,
            foot[1] + arm[1] * cos + side[1] * sin,
            foot[2] + arm[2] * cos + side[2] * sin,
        )

    def pointing_at(self, t: float) -> Vec3:
        """Unit direction of travel at ``point(t)``."""
        if self.centre is None:
            return _unit(self.direction)
        p, axis, arm = self.point(t), _unit(self.direction), self._arm
        foot = (self.base[0] - arm[0], self.base[1] - arm[1], self.base[2] - arm[2])
        return _unit(_cross(axis, (p[0] - foot[0], p[1] - foot[1], p[2] - foot[2])))

    @property
    def travel(self) -> float:
        """How far the tip is from ``base``: mm, or radians for angle handles."""
        return self.value / self.scale

    @property
    def tip(self) -> Vec3:
        """Where the arrow is drawn."""
        return self.point(self.travel)

    @property
    def pointing(self) -> Vec3:
        """Unit direction the arrow points at its tip."""
        return self.pointing_at(self.travel)

    def beyond(self, value: float, gap: float) -> Vec3:
        """A point ``gap`` mm past where the tip would be for ``value`` (for the callout)."""
        t = value / self.scale
        if self.centre is None:
            return self.point(t + gap)
        radius = self.radius
        return self.point(t + (gap / radius if radius > 0 else 0.0))

    def value_at(self, distance: float) -> float:
        """The parameter value for a drag point ``distance`` mm (or radians) from the base."""
        return distance * self.scale


#: Angle ruler ticks (TOOL_SPEC T6.3.1).
ANGLE_RULER_STEP = math.radians(5.0)


def ruler_step(size: float, inch: bool = False) -> float:
    """A round ruler tick step in mm for a part feature about ``size`` mm across.

    About a tenth of the size, rounded to 1, 2 or 5 times a power of ten in the
    part's unit (millimetres, or inches when ``inch`` is True), so ticks fall on
    round values (DECISIONS D146).
    """
    factor = 25.4 if inch else 1.0
    target = size / factor / 10.0
    if not math.isfinite(target) or target <= 0:
        return factor
    power = 10.0 ** math.floor(math.log10(target))
    for multiple in (1.0, 2.0, 5.0, 10.0):
        if target <= multiple * power * 1.0000001:
            return multiple * power * factor
    return 10.0 * power * factor


@dataclass(frozen=True)
class ParamSpec:
    """One parameter of a feature type.

    ``kind`` is set for typed values stored as ``{"expr", "value"}``. ``choices``
    is set for plain string settings. Booleans have neither.
    """

    name: str
    kind: Kind | None = None
    choices: tuple[str, ...] = ()
    default: Any = None
    optional: bool = False


class FeatureType:
    """Base class for feature types. Subclasses set ``type_name`` and ``params``."""

    type_name: ClassVar[str]
    params: ClassVar[tuple[ParamSpec, ...]] = ()
    makes_solid: ClassVar[bool] = False
    #: The fixed operation ("boss" or "cut") of a feature with no operation setting
    #: whose ``tool`` is its whole solid, so a feature pattern can copy it.
    pattern_operation: ClassVar[str | None] = None

    def validate(self, feature: Feature) -> None:
        """Check parameters before any kernel call. Raises FeatureError."""
        for spec in self.params:
            value = feature.params.get(spec.name, spec.default)
            if spec.optional and spec.name not in feature.params:
                continue
            if spec.kind is not None and not isinstance(value, Param):
                raise FeatureError(
                    f"{feature.name}: the {value_label(spec.name)} value is missing. Enter a value."
                )
            if spec.choices and value not in spec.choices:
                raise FeatureError(
                    f"{feature.name}: the chosen {value_label(spec.name)} does not work for this "
                    "feature. Choose another in the property panel."
                )

    def kind_of(self, name: str) -> Kind | None:
        """The unit kind of parameter ``name``, for re-evaluating its expression.

        Types with numbered parameters (per edge radii) override this.
        """
        for spec in self.params:
            if spec.name == name:
                return spec.kind
        return None

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Build the feature. Raises FeatureError on failure."""
        raise NotImplementedError

    def reads_body(self, feature: Feature) -> bool:
        """True when the feature reads the part without a face, edge or vertex in ``refs``.

        The rebuild then keys its result on the part (D250).
        """
        return False

    def key_data(self, feature: Feature, doc: Document, results: dict[str, FeatureResult]) -> Any:
        """Data outside the feature's own entry that its result depends on, such as
        the graph a graph body reads. None for most types."""
        return None

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape | None:
        """The feature's own solid, for the live preview. None when it has none."""
        return None

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """Drag arrows shown on the live preview. None by default."""
        return []

    def preview_info(self, feature: Feature, ctx: BuildContext) -> dict[str, float]:
        """Values the panel shows while the preview is open (vent areas, P4.4). None by default."""
        return {}

    # Helpers for subclasses ---------------------------------------------------

    @staticmethod
    def number(feature: Feature, name: str) -> float:
        """Internal value of a typed parameter."""
        value = feature.params.get(name)
        if not isinstance(value, Param):
            raise FeatureError(
                f"{feature.name}: the {value_label(name)} value is missing. Enter a value."
            )
        return value.value

    @staticmethod
    def setting(feature: Feature, name: str, default: Any) -> Any:
        """A plain parameter (string or boolean), or ``default``."""
        return feature.params.get(name, default)


REGISTRY: dict[str, FeatureType] = {}


def register(cls: type[FeatureType]) -> type[FeatureType]:
    """Class decorator: make a feature type available by its ``type_name``."""
    REGISTRY[cls.type_name] = cls()
    return cls
