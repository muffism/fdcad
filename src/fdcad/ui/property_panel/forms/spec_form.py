"""A panel form built from a list of field definitions (Phase 4 panels).

Each Phase 4 feature lists its groups and fields; this base class makes the
widgets, shows and hides rows as other values change, writes the values into
the edited copy and sends picks from the view to the right pick list. Every
fastening feature panel adds the Favourites box (PHASE4_SPEC common rules).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QLineEdit, QWidget

from fdcad.core.document.model import Feature, Param
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings
from fdcad.ui import strings_phase4 as text
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList
from fdcad.ui.property_panel.groups import Group, with_icon

Values = dict[str, Any]

#: Field kinds: typed numbers, plain settings, picks from the view and sketches.
NUMBER_KINDS = {"length": Kind.LENGTH, "angle": Kind.ANGLE, "number": Kind.NUMBER}
PICK_KINDS = ("faces", "edges", "vertices", "any")


@dataclass(frozen=True)
class F:
    """One field. ``when`` decides from the current values whether it shows.

    Numbers: ``default`` is the value in mm, radians or a plain number. Choices:
    ``choices`` are (stored value, label) pairs. Booleans: written only when
    ticked unless ``always``. Picks: ``single`` keeps one item, stored in
    ``refs[name]`` as a list. Sketch: ``refs[name] = {"feature": id}``.
    """

    name: str
    label: str
    kind: str
    tip: str = ""
    default: Any = None
    choices: tuple[tuple[str, str], ...] = ()
    when: Callable[[Values], bool] | None = None
    single: bool = False
    always: bool = False
    optional: bool = False


@dataclass(frozen=True)
class G:
    """One group of fields."""

    key: str
    title: str
    tip: str
    fields: tuple[F, ...]
    when: Callable[[Values], bool] | None = None


def number_text(value: float, kind: Kind, units: UnitSystem) -> str:
    """Text for a default value in the part's units."""
    import math

    if kind is Kind.ANGLE:
        return f"{math.degrees(value):.6g}"
    if kind is Kind.LENGTH and units is UnitSystem.IN:
        # The shortest inch text that reads back as the same length; a metric table
        # value (an M5 tap drill of 4.2 mm) has none, so it keeps its millimetres
        # (D2643). Four digits gave 0.1654 in, which read back as 4.2012 mm.
        for digits in range(4, 7):
            inches = f"{value / 25.4:.{digits}g}"
            if abs(float(inches) * 25.4 - value) <= 1e-9 * max(1.0, abs(value)):
                return inches
        return f"{value:.6g} mm"
    return f"{value:.6g}"


class SpecForm(FeatureForm):
    """A form described by ``layout``. Subclasses set ``layout`` and ``favourites``."""

    layout: ClassVar[tuple[G, ...]] = ()
    #: True for the fastening features: the panel has the Favourites box.
    favourites: ClassVar[bool] = False

    def build(self) -> None:
        """Make every group and field."""
        self.rows: dict[str, tuple[QFormLayout, QWidget]] = {}
        self.choice_boxes: dict[str, QComboBox] = {}
        self.checks: dict[str, QCheckBox] = {}
        self.picks: dict[str, PickList] = {}
        self.sketch_boxes: dict[str, QComboBox] = {}
        self.texts: dict[str, QLineEdit] = {}
        self.spec_groups: dict[str, Group] = {}
        self.defs: dict[str, F] = {}
        self.active_pick: str | None = None
        self.before_groups()
        for g in self.layout:
            group = self.group(g.key, g.title, g.tip)
            self.spec_groups[g.key] = group
            for f in g.fields:
                self.defs[f.name] = f
                self._make(group, f)
        if self.favourites:
            from fdcad.ui.property_panel.favourites import FavouritesBox

            group = self.group("favourites", text.GROUP_FAVOURITES, text.FAVOURITES_TIP)
            self.favourites_box = FavouritesBox(self.panel, self.feature.type, self._report)
            group.form.addRow(self.favourites_box)
        self.after_groups()
        self.update_visibility()

    # Hooks for subclasses ---------------------------------------------------------

    def before_groups(self) -> None:
        """Add widgets above the listed groups."""

    def after_groups(self) -> None:
        """Add widgets below the listed groups."""

    def extra_apply(self, feature: Feature) -> str | None:
        """Write anything the layout does not cover."""
        return None

    # Building -----------------------------------------------------------------------

    def _report(self, message: str) -> None:
        self.panel.message.setText(message)

    def _make(self, group: Group, f: F) -> None:
        feature = self.feature
        widget: QWidget
        if f.kind in NUMBER_KINDS:
            kind = NUMBER_KINDS[f.kind]
            current = feature.params.get(f.name)
            if not isinstance(current, Param):
                value = float(f.default if f.default is not None else 0.0)
                current = Param(number_text(value, kind, self.doc.units), value)
            field = self.panel.make_field(kind, current)
            field.setToolTip(f.tip)
            field.edit.textChanged.connect(lambda _t: self._changed())
            field.edit.returnPressed.connect(self.panel.accept)
            field.edit.setProperty("param_name", f.name)
            field.edit.installEventFilter(self.panel)
            self.fields[f.name] = field
            icon = "field.angle" if kind is Kind.ANGLE else "field.depth"
            widget = with_icon(icon, f.tip, field)
        elif f.kind == "choice":
            box = QComboBox()
            box.setToolTip(f.tip)
            for choice_value, choice_label in f.choices:
                box.addItem(choice_label, choice_value)
            stored = feature.params.get(f.name, f.default)
            box.setCurrentIndex(max(box.findData(stored), 0))
            box.currentIndexChanged.connect(lambda _i: self._changed())
            self.choice_boxes[f.name] = box
            widget = box
        elif f.kind == "bool":
            check = QCheckBox(f.label)
            check.setToolTip(f.tip)
            stored = feature.params.get(f.name, f.default)
            check.setChecked(stored is True)
            check.toggled.connect(lambda _on: self._changed())
            self.checks[f.name] = check
            group.form.addRow(check)
            self.rows[f.name] = (group.form, check)
            return
        elif f.kind == "text":
            edit = QLineEdit(str(feature.params.get(f.name, f.default or "")))
            edit.setToolTip(f.tip)
            edit.textChanged.connect(lambda _t: self._changed())
            self.texts[f.name] = edit
            widget = edit
        elif f.kind in ("sketch", "feature"):
            box = QComboBox()
            box.setToolTip(f.tip)
            self._fill_sketches(box, f, "sketch" if f.kind == "sketch" else str(f.default))
            box.currentIndexChanged.connect(lambda _i: self._changed())
            self.sketch_boxes[f.name] = box
            widget = box
        elif f.kind in PICK_KINDS:
            picks = PickList(self.doc, f.tip)
            refs = feature.refs.get(f.name, [])
            picks.set_refs(refs if isinstance(refs, list) else [])
            picks.changed.connect(self._changed)
            picks.list.itemPressed.connect(lambda _i, n=f.name: self._activate(n))
            self.picks[f.name] = picks
            widget = picks
        else:
            raise ValueError(f"unknown field kind {f.kind}")
        row_label = QLabel(f.label)
        row_label.setToolTip(f.tip)
        group.form.addRow(row_label, widget)
        self.rows[f.name] = (group.form, widget)

    def _fill_sketches(self, box: QComboBox, f: F, ftype: str = "sketch") -> None:
        """Features of ``ftype`` above the edited one (sketches, or for example snap hooks)."""
        order = [x.id for x in self.doc.features]
        mine = order.index(self.feature.id) if self.feature.id in order else len(order)
        if f.optional:
            box.addItem(f.label if not f.default or ftype != "sketch" else str(f.default), None)
        for x in self.doc.features[:mine]:
            if x.type == ftype:
                box.addItem(x.name, x.id)
        ref = self.feature.refs.get(f.name)
        if isinstance(ref, dict) and "feature" in ref:
            box.setCurrentIndex(max(box.findData(ref["feature"]), 0))

    def _activate(self, name: str) -> None:
        self.active_pick = name

    def _changed(self) -> None:
        self.update_visibility()
        self.changed.emit()

    # Values -------------------------------------------------------------------------

    def values(self) -> Values:
        """The current settings by name, for the ``when`` rules."""
        out: Values = {}
        for name, box in self.choice_boxes.items():
            out[name] = box.currentData()
        for name, check in self.checks.items():
            out[name] = check.isChecked()
        for name, fld in self.fields.items():
            param = fld.param()
            out[name] = param.value if param is not None else None
        for name, picks in self.picks.items():
            out[name] = picks.refs()
        for name, box in self.sketch_boxes.items():
            out[name] = box.currentData()
        for name, edit in self.texts.items():
            out[name] = edit.text()
        return out

    def shown(self, name: str, values: Values | None = None) -> bool:
        """True when field ``name`` and its group show for the current values."""
        values = self.values() if values is None else values
        f = self.defs.get(name)
        if f is None:
            return name in self.fields
        if f.when is not None and not f.when(values):
            return False
        for g in self.layout:
            if f in g.fields and g.when is not None and not g.when(values):
                return False
        return True

    def update_visibility(self) -> None:
        """Show and hide rows and groups from the current values."""
        values = self.values()
        for g in self.layout:
            group = self.spec_groups.get(g.key)
            if group is not None:
                group.setVisible(g.when is None or g.when(values))
        for name, (layout, widget) in self.rows.items():
            layout.setRowVisible(widget, self.shown(name, values))

    def apply(self, feature: Feature) -> str | None:
        """Write the shown fields; hidden ones are removed from the copy."""
        values = self.values()
        values.pop("_tab", None)  # a closed tab still holds values
        for name, f in self.defs.items():
            visible = self.shown(name, values)
            if f.kind in NUMBER_KINDS:
                if not visible:
                    feature.params.pop(name, None)
                    continue
                param = self.fields[name].param()
                if param is None:
                    return strings.FIX_ERRORS
                feature.params[name] = param
            elif f.kind == "choice":
                if visible:
                    feature.params[name] = self.choice_boxes[name].currentData()
                else:
                    feature.params.pop(name, None)
            elif f.kind == "bool":
                on = visible and self.checks[name].isChecked()
                if on or (visible and f.always):
                    feature.params[name] = on
                else:
                    feature.params.pop(name, None)
            elif f.kind == "text":
                if visible:
                    feature.params[name] = self.texts[name].text()
                else:
                    feature.params.pop(name, None)
            elif f.kind in ("sketch", "feature"):
                sid = self.sketch_boxes[name].currentData()
                if visible and isinstance(sid, str):
                    feature.refs[name] = {"feature": sid}
                else:
                    feature.refs.pop(name, None)
                    if visible and not f.optional:
                        return strings.CHOOSE_SKETCH
            elif f.kind in PICK_KINDS:
                refs = self.picks[name].refs()
                if visible and refs:
                    feature.refs[name] = refs[:1] if f.single else refs
                else:
                    feature.refs.pop(name, None)
                    if visible and not f.optional:
                        if f.kind == "vertices":
                            return strings.PICK_VERTEX
                        return text.HOLE_PICK_FACE if f.kind == "faces" else strings.PICK_FACES
        return self.extra_apply(feature)

    def settings_params(self) -> dict[str, Any] | None:
        """The shown settings without picks, for the Favourites box (None when a value
        is wrong)."""
        from fdcad.core.document.model import ParamValue

        values = self.values()
        values.pop("_tab", None)
        out: dict[str, ParamValue] = {}
        for name, f in self.defs.items():
            if not self.shown(name, values):
                continue
            if f.kind in NUMBER_KINDS:
                param = self.fields[name].param()
                if param is None:
                    return None
                out[name] = param
            elif f.kind == "choice":
                out[name] = self.choice_boxes[name].currentData()
            elif f.kind == "bool":
                out[name] = self.checks[name].isChecked()
            elif f.kind == "text":
                out[name] = self.texts[name].text()
        return out

    # Picks --------------------------------------------------------------------------

    def _accepts(self, f: F, shape: Any) -> bool:
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX

        kind = shape.ShapeType()
        wanted = {
            "faces": (TopAbs_FACE,),
            "edges": (TopAbs_EDGE,),
            "vertices": (TopAbs_VERTEX,),
            "any": (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX),
        }[f.kind]
        return kind in wanted

    def pick_target(self, shape: Any) -> str | None:
        """The pick list a picked shape goes to: the active one, else the first that
        is shown, takes the shape and still has room."""
        values = self.values()
        order = list(self.picks)
        if self.active_pick in order:
            order.remove(self.active_pick)
            order.insert(0, self.active_pick)
        for name in order:
            f = self.defs[name]
            if not self.shown(name, values) or not self._accepts(f, shape):
                continue
            if f.single and self.picks[name].refs() and name != self.active_pick:
                continue
            return name
        return None

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Picks go to the pick lists (see ``pick_target``)."""
        from fdcad.core.naming.select import reference_for

        problem = None
        for shape in shapes:
            target = self.pick_target(shape)
            if target is None:
                problem = strings.PICK_FACES
                continue
            ref = reference_for(body, shape)
            if ref is None:
                continue
            refused = self.own_ref(ref)
            if refused:
                problem = refused
                continue
            picks = self.picks[target]
            if self.defs[target].single:
                picks.set_refs([ref])
                picks.changed.emit()
            else:
                picks.add(ref)
        return problem


class ClickPlacement:
    """A click on a face sets the feature's face and its typed position (P4.4).

    Mixed into forms with a single ``face`` pick and ``pos_x``, ``pos_y``, ``pos_z``
    fields. Picked vertices and round edges still go to the ``position`` list.
    """

    def take_point(self, body: NamedShape, shapes: list[Any], point: Any) -> bool:
        """Use a face click as the position. True when it was used."""
        from OCP.TopAbs import TopAbs_FACE

        from fdcad.core.naming.select import reference_for

        form_ = self  # SpecForm
        assert isinstance(form_, SpecForm)
        faces = [s for s in shapes if s.ShapeType() == TopAbs_FACE]
        if point is None or len(faces) != 1 or len(shapes) != 1:
            return False
        if form_.active_pick not in (None, "face"):
            return False
        ref = reference_for(body, faces[0])
        if ref is None or form_.own_ref(ref):
            return False
        form_.picks["face"].set_refs([ref])
        form_.picks["position"].set_refs([])
        for axis, value in zip("xyz", point, strict=True):
            form_.fields[f"pos_{axis}"].edit.setText(
                number_text(float(value), Kind.LENGTH, form_.doc.units)
            )
        form_._changed()
        return True
