"""Property panels for the deformation features (PHASE4_SPEC P4.9, D393).

Built with the Phase 3 form tables, so picks, live preview and drag handles
work the same way: the preview shows the deformed bodies and the two trim
planes, with arrows that move the triad (origin) and each trim plane.
Importing this module adds the forms and their text.
"""

from __future__ import annotations

from fdcad.ui import strings_phase3 as text
from fdcad.ui.body_tools.forms import Field, Form, FormGroup, _angle, _count, _flag, _is, _length

DEFORM_TYPES = ("bend", "twist", "taper", "stretch", "flow")
#: Local deform modes without a triad (TR67, D2412).
LOCAL_TYPES = ("deform_point", "deform_curve", "surface_push")
GROUP_TRIAD = "Triad and Trim Planes"
GROUP_DEFORM = {
    "bend": "Bend",
    "twist": "Twist",
    "taper": "Taper",
    "stretch": "Stretch",
    "flow": "Flow Along Curve",
    "deform_point": "Deform Point",
    "deform_curve": "Curve to Curve",
    "surface_push": "Surface Push",
}

LABELS = {
    "spin": "Turn first axis",
    "ox": "Origin X",
    "oy": "Origin Y",
    "oz": "Origin Z",
    "start": "Start plane",
    "end": "End plane",
    "tolerance": "Tolerance",
    "bend_by": "Set",
    "radius": "Radius",
    "factor": "Taper factor",
    "fit": "Fit to curve length",
    "path": "Curve",
    "distance": "Distance",
    "stiffness": "Stiffness",
    "fixed": "Fixed faces and edges",
    "initial": "Initial curve",
    "target": "Target curve",
    "tool": "Tool",
    "depth": "Depth",
    "tool_x": "Tool size across",
    "tool_y": "Tool size along",
    "reach": "Reach into the body",
    "point": "Point",
    "direction": "Direction",
}
TIPS = {
    "spin": "Turns the triad's first and second axes about the third axis.",
    "ox": "Origin X: where the triad sits. Drag the red arrow in the view.",
    "oy": "Origin Y: where the triad sits. Drag the green arrow in the view.",
    "oz": "Origin Z: where the triad sits. Drag the blue arrow in the view.",
    "start": "Start plane: where the deformation starts, along the third axis from the origin.",
    "end": "End plane: where the deformation stops, along the third axis from the origin.",
    "tolerance": (
        "Tolerance: the largest distance allowed from the exact shape. A result that cannot "
        "meet it shows a warning."
    ),
    "bend_by": "Set the bend angle, or the radius. The bent length stays the same.",
    "radius": "Radius: the bend radius at the triad's origin.",
    "factor": "Taper factor: the size at the end plane compared to the start plane.",
    "fit": "Spreads the region between the trim planes over the whole curve.",
    "path": "Curve: a sketch whose curves join end to end, or a curve feature.",
    "stiffness": "Stiffness: 0 to just under 1, the part of the radius that moves the whole "
    "distance; the rest fades out smoothly.",
    "fixed": "Fixed faces and edges: they stay where they are; the movement fades out near them.",
    "initial": "Initial curve: a sketch or curve on or near the body.",
    "target": "Target curve: where the initial curve goes. Points match by length along "
    "each curve.",
    "tool": "Tool: the shape that presses into the face.",
    "tool_x": "Tool size across: a sphere's radius, or the half width of an ellipsoid or "
    "rectangle.",
    "tool_y": "Tool size along: the half length of an ellipsoid or rectangle.",
    "reach": "Reach into the body: how deep below the face the dent fades out. Empty: three "
    "times the depth.",
}
CHOICES = {
    "x": "X",
    "y": "Y",
    "z": "Z",
    "angle": "Angle",
    "radius": "Radius",
    "sphere": "Sphere",
    "ellipsoid": "Ellipsoid",
    "rectangle": "Rectangle",
}
TYPE_NAMES = {
    "bend": "Bend",
    "twist": "Twist",
    "taper": "Taper",
    "stretch": "Stretch",
    "flow": "Flow",
    "deform_point": "Deform Point",
    "deform_curve": "Curve to Curve",
    "surface_push": "Surface Push",
}
TOOLTIPS = {
    "feature.bend": "Bends bodies about the first axis of the triad, between two trim planes.",
    "feature.twist": "Twists bodies about the third axis of the triad, between two trim planes.",
    "feature.taper": "Tapers bodies along the third axis of the triad, between two trim planes.",
    "feature.stretch": (
        "Stretches bodies along the third axis of the triad, between two trim planes."
    ),
    "feature.flow": "Lays bodies along a curve.",
    "feature.deform_point": "Pulls a body round a point along a direction, fading over a radius.",
    "feature.deform_curve": "Moves a body near one curve onto another curve.",
    "feature.surface_push": "Presses a sphere, ellipsoid or rectangle into a face as a dent.",
}


def _triad() -> FormGroup:
    return FormGroup(
        GROUP_TRIAD,
        (
            Field("axis", "choice", choices=("z", "x", "y"), default="z"),
            _angle("spin"),
            *(_length(k) for k in ("ox", "oy", "oz")),
            _length("start"),
            _length("end"),
        ),
    )


BODIES = FormGroup(
    text.GROUP_BODIES_PANEL, (Field("bodies", "picks", accept=("body",), multiple=True),)
)
OPTIONS = FormGroup(text.GROUP_OPTIONS, (_length("tolerance"),))
_COMMON_DEFAULTS = {"axis": "z", "spin": ("0", 0.0), "tolerance": ("0.01", 0.01)}

DEFORM_FORMS: dict[str, Form] = {
    "bend": Form(
        (
            BODIES,
            FormGroup(
                GROUP_DEFORM["bend"],
                (
                    Field("bend_by", "choice", choices=("angle", "radius"), default="angle"),
                    _angle("angle", _is("bend_by", "angle")),
                    _length("radius", _is("bend_by", "radius")),
                ),
            ),
            _triad(),
            OPTIONS,
        ),
        {
            **_COMMON_DEFAULTS,
            "bend_by": "angle",
            "angle": ("90", 1.5707963267948966),
            "radius": ("50", 50.0),
        },
    ),
    "twist": Form(
        (BODIES, FormGroup(GROUP_DEFORM["twist"], (_angle("angle"),)), _triad(), OPTIONS),
        {**_COMMON_DEFAULTS, "angle": ("90", 1.5707963267948966)},
    ),
    "taper": Form(
        (BODIES, FormGroup(GROUP_DEFORM["taper"], (_count("factor"),)), _triad(), OPTIONS),
        {**_COMMON_DEFAULTS, "factor": ("0.5", 0.5)},
    ),
    "stretch": Form(
        (BODIES, FormGroup(GROUP_DEFORM["stretch"], (_length("distance"),)), _triad(), OPTIONS),
        {**_COMMON_DEFAULTS, "distance": ("10", 10.0)},
    ),
    "flow": Form(
        (
            BODIES,
            FormGroup(
                GROUP_DEFORM["flow"],
                (Field("path", "picks", accept=("sketch", "curve")), _flag("fit")),
            ),
            _triad(),
            OPTIONS,
        ),
        dict(_COMMON_DEFAULTS),
    ),
    "deform_point": Form(  # TR67 (D2412)
        (
            BODIES,
            FormGroup(
                GROUP_DEFORM["deform_point"],
                (
                    Field("point", "picks", accept=("vertex",)),
                    Field("direction", "picks", accept=("edge", "face", "axis")),
                    _length("distance"),
                    _length("radius"),
                    _count("stiffness"),
                    Field("fixed", "picks", accept=("face", "edge"), multiple=True),
                ),
            ),
            OPTIONS,
        ),
        {
            "tolerance": ("0.01", 0.01),
            "distance": ("2", 2.0),
            "radius": ("10", 10.0),
            "stiffness": ("0", 0.0),
        },
    ),
    "deform_curve": Form(
        (
            BODIES,
            FormGroup(
                GROUP_DEFORM["deform_curve"],
                (
                    Field("initial", "picks", accept=("sketch", "curve")),
                    Field("target", "picks", accept=("sketch", "curve")),
                    _length("radius"),
                    Field("fixed", "picks", accept=("face", "edge"), multiple=True),
                ),
            ),
            OPTIONS,
        ),
        {"tolerance": ("0.01", 0.01), "radius": ("10", 10.0)},
    ),
    "surface_push": Form(
        (
            BODIES,
            FormGroup(
                GROUP_DEFORM["surface_push"],
                (
                    Field("point", "picks", accept=("vertex",)),
                    Field("direction", "picks", accept=("edge", "face", "axis")),
                    Field(
                        "tool",
                        "choice",
                        choices=("sphere", "ellipsoid", "rectangle"),
                        default="sphere",
                    ),
                    _length("depth"),
                    _length("tool_x"),
                    _length("tool_y", _is("tool", "ellipsoid", "rectangle")),
                    _length("reach"),
                ),
            ),
            OPTIONS,
        ),
        {
            "tolerance": ("0.01", 0.01),
            "tool": "sphere",
            "depth": ("1", 1.0),
            "tool_x": ("5", 5.0),
            "tool_y": ("5", 5.0),
            "reach": ("3", 3.0),
        },
    ),
}

from fdcad.ui import strings as _strings  # noqa: E402

_strings.TOOLTIP_TEXT.update(TOOLTIPS)
for _table, _new in (
    (text.LABELS, LABELS),
    (text.TIPS, TIPS),
    (text.CHOICES, CHOICES),
    (text.TYPE_NAMES, TYPE_NAMES),
    (text.TOOLTIP_TEXT, TOOLTIPS),
    (text.TYPE_COMMANDS, {t: f"feature.{t}" for t in (*DEFORM_TYPES, *LOCAL_TYPES)}),
):
    for _key, _value in _new.items():
        _table.setdefault(_key, _value)
