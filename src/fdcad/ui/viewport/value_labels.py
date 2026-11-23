"""Value labels of the open feature panel in the 3D view (TOOL_SPEC T15.2 to T15.4, D441).

Every length, angle or count field of the panel that is shown has a label in
the view. Fields with a drag handle keep the value beside the handle (T5.2.3);
the others are listed here, placed at the feature's anchor (the first pick,
``PreviewGeometry.anchor``). Label text always comes from the panel field, so
the field and the label never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from shiboken6 import isValid

from fdcad.core.units import Kind

#: Characters that open the value box when typed with the view focused (T15.4).
TYPING_KEYS = frozenset("0123456789-.=")
#: Field kinds that get a label: lengths, angles and counts (T15.7).
LABEL_KINDS = (Kind.LENGTH, Kind.ANGLE, Kind.NUMBER)

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class ValueLabel:
    """One label: the panel parameter, where it sits (mm) and what it says."""

    param: str
    point: Vec3
    text: str


def starts_typing(text: str, modifiers: Qt.KeyboardModifier) -> bool:
    """True for a digit, minus, dot or ``=`` typed without Ctrl, Alt or Meta."""
    held = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
    held |= Qt.KeyboardModifier.MetaModifier
    return len(text) == 1 and text in TYPING_KEYS and not modifiers & held


def value_fields(panel: Any) -> dict[str, Any]:
    """The panel's shown length, angle and count fields, in panel order."""
    if panel is None or not isValid(panel):
        return {}
    fields: dict[str, Any] = dict(getattr(panel, "values", {}) or {})
    form = getattr(panel, "form", None)
    if form is not None:
        fields.update(getattr(form, "fields", {}) or {})
    return {
        name: field
        for name, field in fields.items()
        if getattr(field, "kind", None) in LABEL_KINDS
        and isValid(field)
        and field.isVisibleTo(panel)
        and field.isEnabledTo(panel)
    }


def label_text(field: Any) -> str:
    """What the label of ``field`` says: its value in the part's units, or the raw text."""
    from fdcad.ui.property_panel.panel import format_value

    param = field.param()
    if param is None:
        return field.edit.text().strip() or "?"
    if field.kind is Kind.NUMBER:
        return f"{param.value:g}"
    return format_value(param.value, field.kind, field.units)


#: Fields whose label is left out of the view while they keep their plain value (D816):
#: a twist of 0 and a scale of 1 change nothing, so they would only crowd the model.
QUIET_AT = {"end_twist": 0.0, "end_scale": 1.0, "profile_offset": 0.0}


def _quiet(name: str, field: Any) -> bool:
    if name not in QUIET_AT:
        return False
    param = field.param()
    return param is not None and abs(param.value - QUIET_AT[name]) < 1e-12


#: Label params of pattern instance markers start with this (TR59 item 4, D2400).
MARKER_PREFIX = "instance:"


def copy_values_line(panel: Any) -> Any:
    """The Copy values field of the open pattern panel, or None (TR59, D1900)."""
    if panel is None or not isValid(panel):
        return None
    form = getattr(panel, "body_form", None)
    widgets = getattr(form, "widgets", None) or {}
    line = widgets.get("instance_values")
    return line if line is not None and isValid(line) and line.isVisibleTo(panel) else None


def marker_labels(panel: Any, geometry: Any) -> list[ValueLabel]:
    """A numbered marker on each pattern copy while its panel has Copy values (TR59
    item 4, D2400). The text is ``#`` and the instance number, as typed in Skip."""
    if copy_values_line(panel) is None:
        return []
    markers = getattr(geometry, "markers", None) or []
    return [ValueLabel(f"{MARKER_PREFIX}{label}", point, f"#{label}") for label, point in markers]


def pick_marker(panel: Any, param: str) -> bool:
    """Start an entry for the clicked copy in Copy values and put the cursor after it,
    so the user types only the values (TR59 item 4, D2400). True when it was a marker."""
    from fdcad.core.features.pattern_markers import parse_label
    from fdcad.core.features.seed_of import add_instance_values

    if not param.startswith(MARKER_PREFIX):
        return False
    index = parse_label(param[len(MARKER_PREFIX) :])
    line = copy_values_line(panel)
    if index is None or line is None:
        return True
    line.setText(add_instance_values(line.text(), index))
    line.setFocus()
    line.setCursorPosition(len(line.text()))
    return True


def skip_markers(panel: Any, params: list[str], toggle: bool = False) -> bool:
    """Add the copies whose markers were boxed to Instances to Skip (TR270 item 3,
    D2401); with ``toggle`` (Ctrl) copies already skipped are brought back instead.
    True when the skip field was changed."""
    from fdcad.core.features.pattern_markers import parse_label
    from fdcad.ui.body_tools.forms import format_skip, parse_skip

    if panel is None or not isValid(panel):
        return False
    form = getattr(panel, "body_form", None)
    line = (getattr(form, "widgets", None) or {}).get("skip")
    if line is None or not isValid(line):
        return False
    current = parse_skip(line.text()) or []
    boxed = [
        [index[0], index[1]]
        for p in params
        if p.startswith(MARKER_PREFIX) and (index := parse_label(p[len(MARKER_PREFIX) :]))
    ]
    out = list(current)
    for item in boxed:
        if item in out and toggle:
            out.remove(item)
        elif item not in out:
            out.append(item)
    if out == current:
        return False
    line.setText(format_skip(out))
    return True


def feature_labels(panel: Any, geometry: Any) -> list[ValueLabel]:
    """Labels for the fields without a drag handle, at ``geometry.anchor``, then the
    pattern instance markers (D2400).

    ``geometry`` is a ``PreviewGeometry``. No anchor, no value labels.
    """
    anchor = getattr(geometry, "anchor", None)
    if anchor is None:
        return marker_labels(panel, geometry)
    handled = {h.param for h in getattr(geometry, "handles", [])}
    return [
        ValueLabel(name, anchor, label_text(field))
        for name, field in value_fields(panel).items()
        if name not in handled and not _quiet(name, field)
    ] + marker_labels(panel, geometry)
