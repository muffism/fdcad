"""Cosmetic thread panel (PHASE4_SPEC P4.2, DECISIONS D314).

Groups: Thread (the round edge, standard and size), Values (major diameter and
pitch, filled from the standard table when the size changes) and End (Blind
with a length, or the full face, and Reverse).
"""

from __future__ import annotations

from typing import Any

from fdcad.core.features import hole_data
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings_phase4 as text
from fdcad.ui.preferences import phase4_settings as prefs
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import F, G, SpecForm, number_text

T = text.THREAD_TIPS


def _sizes() -> tuple[tuple[str, str], ...]:
    names = hole_data.size_names("iso") + hole_data.size_names("ansi")
    return tuple((n, n) for n in names)


#: How close a round edge must be to a size's diameter (or tap drill) to pick it, mm.
SIZE_MATCH = 0.15


def matching_size(shape: Any) -> str | None:
    """The standard size that fits a round edge, or None (D589).

    A shaft fits the size whose major diameter it has (6 mm: M6); a hole the
    size whose tap drill it has (5 mm: M6). Metric sizes are tried first.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS

    if shape.ShapeType() != TopAbs_EDGE:
        return None
    curve = BRepAdaptor_Curve(TopoDS.Edge(shape))
    if curve.GetType() != GeomAbs_Circle:
        return None
    diameter = 2.0 * curve.Circle().Radius()
    for key in ("diameter", "tap_drill"):
        for standard in hole_data.STANDARDS:
            for size in hole_data.sizes(standard):
                if abs(getattr(size, key) - diameter) <= SIZE_MATCH:
                    return size.name
    return None


class SizedForm(SpecForm):
    """A form whose ``diameter`` and ``pitch`` follow a ``size`` box."""

    def build(self) -> None:
        """Build, then follow the size box."""
        prefs.apply_user_holes()  # TR327 (D1920): the user's sizes join the list
        super().build()
        box = self.choice_boxes["size"]
        for row in hole_data.USER_SIZES:
            if box.findData(row.name) < 0:
                box.addItem(row.name, row.name)
        from PySide6.QtWidgets import QPushButton

        self.user_sizes_button = QPushButton(text.LOAD_USER_SIZES)
        self.user_sizes_button.setToolTip(text.LOAD_USER_SIZES_TIP)
        self.user_sizes_button.clicked.connect(lambda: self.load_user_sizes())
        first = next(iter(self.spec_groups.values()))
        first.form.addRow(self.user_sizes_button)
        stored = self.feature.params.get("size")
        if isinstance(stored, str) and box.findData(stored) < 0:
            # A size that is not in the table stays as it was (D609).
            box.blockSignals(True)
            box.addItem(stored or text.LABEL_CUSTOM_SIZE, stored)
            box.setCurrentIndex(box.count() - 1)
            box.blockSignals(False)
        self._size = box.currentData()
        box.currentIndexChanged.connect(self._size_changed)

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Picks as usual; a round edge also picks the size that fits it (D589)."""
        problem = super().take_shapes(body, shapes)
        for shape in shapes:
            size = matching_size(shape)
            if size is not None:
                box = self.choice_boxes["size"]
                index = box.findData(size)
                if index >= 0:
                    box.setCurrentIndex(index)
        return problem

    def _size_changed(self) -> None:
        size = self.choice_boxes["size"].currentData()
        if size == self._size:
            return
        self._size = size
        found = hole_data.find("user", str(size))  # TR327 (D1920): user sizes first
        if found is None:
            found = hole_data.find("ansi" if not str(size).startswith("M") else "iso", str(size))
        if found is None:
            return
        for name, value in (("diameter", found.diameter), ("pitch", found.pitch)):
            fld = self.fields.get(name)
            if fld is not None:
                fld.edit.setText(number_text(value, Kind.LENGTH, self.doc.units))
        grade = self.choice_boxes.get("thread_class")
        if found.thread_class and grade is not None and grade.findData(found.thread_class) >= 0:
            grade.setCurrentIndex(grade.findData(found.thread_class))

    def load_user_sizes(self, path: str | None = None) -> str:
        """Read a user size file (TR327, D1920): the same file as the Hole Tool's, so
        both share one table. Returns the message shown, empty when nothing was chosen."""
        from fdcad.ui.property_panel.forms.hole_form import read_user_sizes

        message = read_user_sizes(self.panel, path)
        if message:
            box = self.choice_boxes["size"]
            for row in hole_data.USER_SIZES:
                if box.findData(row.name) < 0:
                    box.addItem(row.name, row.name)
            self.user_sizes_button.setToolTip(message)
        return message


@form("cosmetic_thread")
class CosmeticThreadForm(SizedForm):
    """Edits a cosmetic thread."""

    first_param = "length"
    remembered_keys = ("size", "end_condition")
    layout = (
        G(
            "thread",
            text.GROUP_THREAD,
            T["edge"],
            (
                F("edge", text.LABEL_EDGE, "edges", T["edge"], single=True),
                F("size", text.LABEL_SIZE, "choice", T["size"], "M5", _sizes()),
            ),
        ),
        G(
            "values",
            text.GROUP_THREAD_VALUES,
            T["diameter"],
            (
                F("diameter", text.LABEL_THREAD_DIAMETER, "length", T["diameter"], 5.0),
                F("pitch", text.LABEL_PITCH, "length", T["pitch"], 0.8),
            ),
        ),
        G(
            "end",
            text.LABEL_END,
            T["end"],
            (
                F(
                    "end_condition",
                    text.LABEL_END,
                    "choice",
                    T["end"],
                    "blind",
                    tuple(text.THREAD_ENDS.items()),
                ),
                F(
                    "length",
                    text.LABEL_LENGTH,
                    "length",
                    T["length"],
                    10.0,
                    when=lambda v: v.get("end_condition") == "blind",
                ),
                F("reverse", text.LABEL_REVERSE, "bool", T["reverse"]),
            ),
        ),
    )


def thread_defaults(units: UnitSystem) -> dict[str, Any]:
    """A new cosmetic thread: M5 (or 1/4-20 in inch parts), 10 mm long."""
    from fdcad.core.document.model import Param

    inch = units is UnitSystem.IN
    size = hole_data.find("ansi", "1/4-20") if inch else hole_data.find("iso", "M5")
    assert size is not None
    length = 12.7 if inch else 10.0
    out: dict[str, Any] = {"size": size.name, "end_condition": "blind"}
    for name, value in (("diameter", size.diameter), ("pitch", size.pitch), ("length", length)):
        out[name] = Param(number_text(value, Kind.LENGTH, units), value)
    return out


def _end_is(*ends: str) -> Any:
    return lambda v: v.get("end_condition") in ends


@form("modeled_thread")
class ModeledThreadForm(SizedForm):
    """Edits a modelled thread (PHASE4_SPEC P4.3, DECISIONS D315)."""

    first_param = "length"
    remembered_keys = ("size", "method", "hand", "end_condition")
    layout = (
        G(
            "thread",
            text.GROUP_THREAD,
            T["edge"],
            (
                F("edge", text.LABEL_EDGE, "edges", T["edge"], single=True),
                F("offset", text.LABEL_OFFSET, "length", T["offset"], 0.0),
                F("reverse", text.LABEL_REVERSE, "bool", T["reverse"]),
                F("start_angle", text.LABEL_START_ANGLE, "angle", T["start_angle"], 0.0),
            ),
        ),
        G(
            "end",
            text.LABEL_END,
            T["end"],
            (
                F(
                    "end_condition",
                    text.LABEL_END,
                    "choice",
                    T["end"],
                    "blind",
                    tuple(text.MODELED_ENDS.items()),
                ),
                F("length", text.LABEL_LENGTH, "length", T["length"], 10.0, when=_end_is("blind")),
                F(
                    "revolutions",
                    text.LABEL_REVOLUTIONS,
                    "number",
                    T["revolutions"],
                    5.0,
                    when=_end_is("revolutions"),
                ),
                F(
                    "up_to",
                    text.LABEL_UP_TO_ITEM,
                    "any",
                    T["up_to"],
                    single=True,
                    when=_end_is("up_to"),
                ),
                F(
                    "keep_length",
                    text.LABEL_KEEP_LENGTH,
                    "bool",
                    T["keep_length"],
                    True,
                    always=True,
                ),
            ),
        ),
        G(
            "spec",
            text.GROUP_THREAD_VALUES,
            T["size"],
            (
                F("size", text.LABEL_SIZE, "choice", T["size"], "M5", _sizes()),
                F("diameter", text.LABEL_THREAD_DIAMETER, "length", T["diameter"], 5.0),
                F("pitch", text.LABEL_PITCH, "length", T["pitch"], 0.8),
                F(
                    "method",
                    text.LABEL_METHOD,
                    "choice",
                    T["method"],
                    "cut",
                    tuple(text.METHODS.items()),
                ),
                F("hand", text.LABEL_HAND, "choice", T["hand"], "right", tuple(text.HANDS.items())),
                F("starts", text.LABEL_STARTS, "number", T["starts"], 1.0),
            ),
        ),
        # TR178 (D782): a profile, fit and lead in for printing.
        G(
            "printing",
            text.GROUP_THREAD_PRINT,
            T["form"],
            (
                F("form", text.LABEL_FORM, "choice", T["form"], "iso", tuple(text.FORMS.items())),
                F(  # TR254 (D1918): the user's own section
                    "profile_sketch",
                    text.LABEL_PROFILE_SKETCH,
                    "sketch",
                    T["profile_sketch"],
                    when=lambda v: v.get("form") == "sketch",
                ),
                F(
                    "end_finish",
                    text.LABEL_END_FINISH,
                    "choice",
                    T["end_finish"],
                    "square",
                    tuple(text.END_FINISHES.items()),
                ),
                F(
                    "print_fit",
                    text.LABEL_PRINT_FIT,
                    "choice",
                    T["thread_fit"],
                    "none",
                    tuple(text.PRINT_FITS.items()),
                ),
                F(
                    "fit_tolerance",
                    text.LABEL_FIT_TOLERANCE,
                    "length",
                    T["thread_fit"],
                    hole_data.DEFAULT_FIT_TOLERANCE,
                    when=lambda v: v.get("print_fit") not in (None, "none"),
                ),
                F("lead_in", text.LABEL_LEAD_IN, "bool", T["lead_in"]),
                F("relief", text.OPT_THREAD_RELIEF, "bool", T["thread_relief"]),  # TR256
                F("taper_angle", text.LABEL_TAPER_ANGLE, "angle", T["taper_angle"], 0.0),  # TR145
                F(  # TR393 (D1507)
                    "thread_class",
                    text.LABEL_THREAD_CLASS,
                    "choice",
                    T["thread_class"],
                    "none",
                    text.thread_class_choices(internal=None),
                ),
            ),
        ),
    )

    def after_groups(self) -> None:
        """The note that profiles are nominal (P4.3 item 4)."""
        from PySide6.QtWidgets import QLabel

        note = QLabel(text.NOMINAL_NOTE)
        note.setWordWrap(True)
        note.setObjectName("field_info")
        self.spec_groups["spec"].form.addRow(note)
        self.nominal_note = note


def modeled_defaults(units: UnitSystem) -> dict[str, Any]:
    """A new modelled thread: M5 (or 1/4-20), cut, right hand, one start."""
    out = thread_defaults(units)
    out.update({"method": "cut", "hand": "right", "keep_length": True})
    from fdcad.core.document.model import Param

    out["starts"] = Param("1", 1.0)
    return out
