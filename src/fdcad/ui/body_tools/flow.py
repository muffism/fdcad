"""Phase 3 commands in the main window: starting the tools, view picks, fixes and the
face menu (PHASE3_SPEC P3.1 to P3.4, P3.8; TOOL_SPEC T9 face menu).

The main window calls this module from a few small hooks, so the window code
stays as it is: ``register`` adds the commands, ``picked`` routes view picks
into the open panel, ``apply_fix`` runs the Phase 3 fixes and ``face_menu``
builds the right click menu of a face.
"""

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.units import UnitSystem
from fdcad.ui import strings_phase3 as text
from fdcad.ui.body_tools.forms import form_for

if TYPE_CHECKING:
    from fdcad.ui.body_tools.form_widget import FeatureForm
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

#: Command id to (feature type, preset parameters).
COMMAND_TYPES: dict[str, tuple[str, dict[str, Any]]] = {
    "feature.move_face": ("move_face", {"mode": "translate"}),
    "feature.face_relation": ("face_relation", {}),  # TR266 (D2418)
    "feature.offset_face": ("move_face", {"mode": "offset"}),
    "feature.delete_face": ("delete_face", {}),
    "feature.merge_faces": ("merge_faces", {}),  # TR261
    "feature.linear_pattern": ("linear_pattern", {}),
    "feature.circular_pattern": ("circular_pattern", {}),
    "feature.pattern_chain": ("pattern_chain", {}),  # TR141 (D1901)
    "feature.sketch_pattern": ("sketch_pattern", {}),
    "feature.table_pattern": ("table_pattern", {}),
    "feature.point_pattern": ("point_pattern", {}),  # TR365
    "feature.fill_pattern": ("fill_pattern", {}),  # TR57
    "feature.bounding_box": ("bounding_box", {}),  # TR69
    "feature.sensor": ("sensor", {}),  # TR86
    "feature.primitive": ("primitive", {}),  # TR127
    "feature.mirror": ("mirror", {}),
    "feature.combine": ("combine", {}),
    "feature.intersect": ("intersect", {}),
    "feature.split": ("split", {}),
    "feature.move_copy_body": ("move_copy_body", {}),
    "feature.linked_copy": ("linked_copy", {}),  # TR154 (D2417)
    "feature.insert_part": ("insert_part", {}),  # TR71 (D2420)
    # Transform handles (PLAN Phase 3, D411): Move and Copy Body with arrows and rings.
    "feature.transform_handles": ("move_copy_body", {"mode": "translate"}),
    "feature.delete_body": ("delete_body", {}),
    "feature.scale": ("scale", {}),
    "feature.mould_cavity": ("mould_cavity", {}),  # TR85 (D2111)
    "feature.offset_body": ("offset_body", {}),  # TR129
    "feature.shaft_shape": ("shaft_shape", {}),  # TR247
    "feature.inlay": ("inlay", {}),  # TR184
    "feature.cable_tie": ("cable_tie", {}),  # TR363
    "feature.half_lap": ("half_lap", {}),  # TR364
    "feature.twist_lock": ("twist_lock", {}),  # TR357
    "feature.indent": ("indent", {}),  # TR68
    "feature.finger_joint": ("finger_joint", {}),  # TR246
    "feature.crush_ribs": ("crush_ribs", {}),  # TR403
    "feature.corner_ears": ("corner_ears", {}),  # TR189 (D1005)
    "feature.drain_holes": ("drain_holes", {}),  # TR189 (D1006)
    "feature.polygon_holes": ("polygon_holes", {}),  # TR189 (D1007)
    "feature.base_pad": ("base_pad", {}),  # TR414 (D1009)
    "feature.interlock": ("interlock", {}),  # TR414 (D1216)
    "feature.lattice_fill": ("lattice_fill", {}),  # TR390 (D2004)
    "feature.mark": ("mark", {}),  # TR330 (D2006)
    "feature.hinge": ("hinge", {}),  # TR404 (D2008)
    "feature.face_seats": ("face_seats", {}),  # TR405 (D2009)
    "feature.stone_setting": ("stone_setting", {}),  # TR408 item 2 (D2410)
    "feature.roof": ("roof", {}),  # TR258 item 1 (D2414)
    "feature.sprue_tree": ("sprue_tree", {}),  # TR408 item 3 (D2411)
    "feature.transition_spiral": ("transition_spiral", {}),  # TR408 item 1 (D2010)
    "feature.edge_profile": ("edge_profile", {}),  # TR243 (D2011)
    "feature.lightening_pockets": ("lightening_pockets", {}),  # TR245 (D2012)
    "feature.landing_pad": ("landing_pad", {}),  # TR325 (D2013)
    "feature.joint_helper": ("joint_helper", {}),  # TR401 (D2014)
    "feature.knurl": ("knurl", {}),  # TR163 (D2015)
    "feature.living_hinge": ("living_hinge", {}),  # TR402
    "feature.hose_fitting": ("hose_fitting", {}),  # TR406
    "feature.ring_groove": ("ring_groove", {}),  # TR249
    "feature.oring_groove": ("oring_groove", {}),  # TR250
    # Phase 4 deformation features (PHASE4_SPEC P4.9).
    "feature.bend": ("bend", {}),
    "feature.twist": ("twist", {}),
    "feature.taper": ("taper", {}),
    "feature.stretch": ("stretch", {}),
    "feature.flow": ("flow", {}),
    "feature.deform_point": ("deform_point", {}),  # TR67 (D2412)
    "feature.deform_curve": ("deform_curve", {}),
    "feature.surface_push": ("surface_push", {}),
}

#: Types that start with the faces selected in the view, and those that take bodies.
_FACE_SEEDED = {
    "move_face",
    "delete_face",
    "merge_faces",
    "shaft_shape",
    "ring_groove",
    "oring_groove",
    "crush_ribs",
    "corner_ears",
    "polygon_holes",
    "base_pad",
    "interlock",
    "hose_fitting",
}
_BODY_SEEDED = {"combine", "move_copy_body", "delete_body", "scale", "intersect", "split"}
_BODY_SEEDED |= {"offset_body", "lattice_fill", "linked_copy"}
_BODY_SEEDED |= {"bend", "twist", "taper", "stretch", "flow"}
_BODY_SEEDED |= {"deform_point", "deform_curve", "surface_push"}  # TR67 (D2412)


def default_name(doc: Document, ftype: str) -> str:
    """The next free name, such as "Move Face 2" (D110 item 4)."""
    prefix = text.TYPE_NAMES.get(ftype, ftype.replace("_", " ").title())
    pattern = re.compile(rf"^{re.escape(prefix)} (\d+)$")
    used = [int(m.group(1)) for f in doc.features if (m := pattern.match(f.name))]
    return f"{prefix} {max(used, default=0) + 1}"


def new_feature(
    doc: Document, ftype: str, preset: dict[str, Any], refs: dict[str, Any] | None = None
) -> Feature:
    """A new Phase 3 feature with the form's defaults, the preset and any picks."""
    form = form_for(ftype)
    params: dict[str, Any] = {}
    if form is not None:
        for name, value in form.defaults.items():
            params[name] = Param(*value) if isinstance(value, tuple) else value
    params.update(preset)
    return Feature(
        doc.new_feature_id(), ftype, default_name(doc, ftype), params=params, refs=refs or {}
    )


def register(window: MainWindow) -> None:
    """Add the Phase 3 commands to the window (before the command tabs are built)."""
    from functools import partial

    for cid in COMMAND_TYPES:
        if cid not in window.commands.actions:
            window.commands.add(cid, partial(start, window, cid), repeatable=True)


def start(window: MainWindow, cid: str, face: Any = None, body_index: int | None = None) -> bool:
    """Open the panel for a new Phase 3 feature.

    ``face`` is a face to start with; ``body_index`` a body (from the Solid Bodies
    folder) for the tools that take bodies.
    """
    tab, panel = window.current, window.panel
    if tab is None or panel is None:
        return False
    if window.sketch_mode is not None and window.sketch_mode.is_open:
        window.status.setText("Exit the sketch first.")
        return False
    if panel.is_editing:
        panel.reject()
    ftype, preset = COMMAND_TYPES[cid]
    session = tab.session
    report = session.report
    body = report.body if report is not None else None
    label = text.TYPE_NAMES.get(ftype, ftype)
    if ftype == "insert_part":  # TR71 (D2420): pick the part file first; an empty part is fine
        from PySide6.QtWidgets import QFileDialog

        path, _filter = QFileDialog.getOpenFileName(window, label, "", text.INSERT_PART_FILTER)
        if not path:
            return False
        preset = {**preset, "part_file": path}
    elif body is None:
        window.status.setText(text.NEEDS_BODY.format(tool=label))
        return False
    refs: dict[str, Any] = {}
    shapes = [face] if face is not None else list(tab.selection)
    picked = _face_refs(body, shapes)
    if picked and ftype in _FACE_SEEDED:
        refs["faces"] = picked
    elif picked and ftype == "fill_pattern":
        refs["face"] = picked[:1]  # the face to fill (TR57)
    elif ftype in _BODY_SEEDED:
        if body_index is not None:  # a body row of the tree wins over the view selection
            picked = _body_refs(window, body, [], body_index)
        else:
            picked = picked or _body_refs(window, body, shapes, body_index)
        if picked:
            refs["bodies"] = picked
    feature = new_feature(session.document, ftype, preset, refs)
    if session.document.units is UnitSystem.IN:
        inch_defaults(feature, preset)
    if ftype == "move_face":  # the fit preset's tolerance (D413), written once a fit is chosen
        from fdcad.core.units import Kind
        from fdcad.ui.preferences import phase4_settings
        from fdcad.ui.property_panel.forms.spec_form import number_text

        tol = phase4_settings.fit_tolerance()
        units = session.document.units
        feature.params["fit_tolerance"] = Param(number_text(tol, Kind.LENGTH, units), tol)
    if ftype in ("bend", "twist", "taper", "stretch", "flow"):
        _deform_defaults(feature, body, session.document)
    panel.begin(session, feature, is_new=True, preset=True)  # TR326
    window._left_tab(1)
    _connect_form(window, tab)
    return True


def inch_defaults(feature: Feature, preset: dict[str, Any]) -> None:
    """Give the form's length defaults round inch values in an inch part (D2645).

    The defaults are written in millimetres ("1" for a 1 mm Move Face, "10" for a
    pattern spacing), and a length field reads a bare number in the part's unit, so
    an inch part got 1 in and 10 in. Each default becomes its millimetres in inches
    to one significant digit (1 mm is 0.04 in, 10 mm is 0.4 in), as the deform
    tools (``INCH_DEFAULTS``) and Extrude (bug hunt E5) already do. Values the command
    preset gives are left as they are.
    """
    import math

    from fdcad.core.units import Kind

    form = form_for(feature.type)
    if form is None:
        return
    for spec in form.fields():
        if spec.kind != "value" or spec.value_kind is not Kind.LENGTH or spec.name in preset:
            continue
        param = feature.params.get(spec.name)
        if not isinstance(param, Param) or param.value == 0:
            continue
        inches = abs(param.value) / 25.4
        rounded = round(inches, -math.floor(math.log10(inches)))
        inches = math.copysign(rounded, param.value)
        feature.params[spec.name] = Param(f"{inches:g}", inches * 25.4)


def _deform_defaults(feature: Feature, body: Any, doc: Document) -> None:
    """Centre the triad on the picked bodies and put the trim planes at their ends."""
    from fdcad.core.deform.feature import default_params

    target = _picked_bodies(feature.name, feature.refs.get("bodies", []), body, doc)
    feature.params.update(default_params(target, "z", doc.units))
    if doc.units is UnitSystem.IN:
        # The form's lengths are typed in mm; read in inches, "0.01" would be a
        # 0.254 mm tolerance. Round inch values instead, as Dome does.
        for name, inches in INCH_DEFAULTS.items():
            if name in feature.params:
                feature.params[name] = Param(f"{inches:g}", inches * 25.4)


#: Deformation lengths for a new feature in an inch part (the form gives mm values).
INCH_DEFAULTS = {"tolerance": 0.0004, "distance": 0.4, "radius": 2.0}


def _picked_bodies(name: str, refs: list[dict[str, Any]], body: Any, doc: Document) -> Any:
    """The picked bodies as one shape, or every body when none is picked."""
    from fdcad.core.features.base import BuildContext
    from fdcad.core.features.bodies import body_index
    from fdcad.core.features.solids import compound, solids

    shapes = solids(body.shape)
    picked = []
    ctx = BuildContext(doc, body, {})
    for ref in refs:
        try:
            index, _issues = body_index(ctx, ref, name)
        except Exception:  # a pick that does not resolve: use every body
            continue
        picked.append(shapes[index])
    return compound(picked) if picked else body.shape


def _connect_deform(window: MainWindow, tab: DocumentTab, form: FeatureForm) -> None:
    """Keep the trim planes at the ends of the bodies when Axis or the picks change.

    Start and End are measured along the axis, so the values fitted to one axis
    put the planes far from the bodies along another. A new Axis refits Start and
    End about the triad where it is; new body picks on a new feature also move the
    triad to their centre. A box query on the UI thread, as at the start (D75).
    """
    from PySide6.QtWidgets import QComboBox

    from fdcad.ui.body_tools.form_widget import PickBox

    if form.feature.type not in ("bend", "twist", "taper", "stretch", "flow"):
        return
    axis, bodies = form.widgets.get("axis"), form.widgets.get("bodies")
    if isinstance(axis, QComboBox):
        axis.currentIndexChanged.connect(lambda _i: _refit_triad(window, tab, form, False))
    panel = window.panel
    if isinstance(bodies, PickBox) and panel is not None and panel.is_new:
        bodies.changed.connect(lambda: _refit_triad(window, tab, form, True))


def _refit_triad(
    window: MainWindow, tab: DocumentTab, form: FeatureForm, move_origin: bool
) -> None:
    """Write fitted triad and trim plane values into the open deformation panel."""
    from fdcad.core.deform.feature import default_params
    from fdcad.core.features.preview import body_before

    panel, report = window.panel, tab.session.report
    if panel is None or panel.body_form is not form or report is None:
        return
    doc = tab.session.document
    body = body_before(doc, form.feature, report.results)
    if body is None:
        return
    values = form.values()
    params = {}
    for key in ("ox", "oy", "oz", "spin"):
        param = form.widgets[key].param()
        if param is None:
            return  # a field the user is still typing: leave the planes alone
        params[key] = param.value
    origin = None if move_origin else (params["ox"], params["oy"], params["oz"])
    try:
        target = _picked_bodies(form.feature.name, values.get("bodies") or [], body, doc)
        fitted = default_params(target, str(values["axis"]), doc.units, origin, params["spin"])
    except Exception:  # a kernel failure never stops the panel; the values stay
        return
    for key, param in fitted.items():
        edit = form.widgets[key].edit
        if edit.text() != param.expr:
            edit.setText(param.expr)


def _body_refs(
    window: MainWindow, body: Any, shapes: list[Any], body_index: int | None
) -> list[dict[str, Any]]:
    """Body picks from picked edges or vertices, or from a body row of the tree (D411)."""
    from fdcad.core.body_visibility import bodies_of
    from fdcad.core.features.solids import solids
    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.select import reference_for

    indices = bodies_of(body.shape, shapes)
    if not indices and body_index is None and window.tree is not None:
        body_index = window.tree.selected_body()
    if not indices and body_index is not None:
        indices = [body_index]
    parts = solids(body.shape)
    out = []
    for index in indices:
        if 0 <= index < len(parts):
            ref = reference_for(body, faces_of(parts[index])[0])
            if ref is not None:
                out.append(ref)
    return out


def _face_refs(body: Any, shapes: list[Any]) -> list[dict[str, Any]]:
    from OCP.TopAbs import TopAbs_FACE

    from fdcad.core.naming.select import reference_for

    out = []
    for shape in shapes:
        if shape.ShapeType() == TopAbs_FACE:
            ref = reference_for(body, shape)
            if ref is not None:
                out.append(ref)
    return out


def edit(window: MainWindow, fid: str) -> bool:
    """Open an existing Phase 3 feature in the panel. False for other types."""
    tab, panel = window.current, window.panel
    if tab is None or panel is None:
        return False
    feature = tab.session.document.feature(fid)
    if form_for(feature.type) is None:
        return False
    panel.begin(tab.session, feature, is_new=False)
    window._left_tab(1)
    _connect_form(window, tab)
    return True


def _connect_form(window: MainWindow, tab: DocumentTab) -> None:
    """Show helper bars and highlights for the open form."""
    panel = window.panel
    form = getattr(panel, "body_form", None)
    if form is None:
        return
    form.highlight.connect(window.highlight_names)
    form.face_added.connect(lambda face: _offer_helpers(window, tab, face))
    _connect_deform(window, tab, form)


def picked(window: MainWindow, tab: DocumentTab, shapes: list[Any]) -> bool:
    """A click in the view while a Phase 3 panel is open goes into its active pick box."""
    panel = window.panel
    form = getattr(panel, "body_form", None) if panel is not None else None
    if form is None or not shapes:
        return False
    problem = form.take_pick(shapes)
    if problem:
        window.status.setText(problem)
    clear = getattr(tab.viewport, "clear_selection", None)
    if clear is not None:
        clear()  # the pick box holds the picks; the view selection starts fresh
    return True


def _offer_helpers(window: MainWindow, tab: DocumentTab, face: Any) -> None:
    from fdcad.ui.body_tools.helper_bar import HelperBar

    bar = getattr(window, "face_helper_bar", None)
    if bar is None:
        bar = HelperBar(window)
        window.face_helper_bar = bar  # type: ignore[attr-defined]
    report = tab.session.report
    if report is None or report.body is None:
        return
    panel = window.panel

    def add(faces: list[Any]) -> None:
        form = getattr(panel, "body_form", None)
        if form is not None:
            form.add_faces(faces)

    def highlight(faces: list[Any]) -> None:
        show = getattr(tab.viewport, "highlight", None)
        if show is not None:
            show(faces)

    bar.offer(report.body.shape, face, add, highlight, QCursor.pos())


#: Fix actions of the Phase 3 features (``delete_face.DROP_REFS``, ``patterns.SKIP_INSTANCES``).
DROP_REFS = "drop_refs"
SKIP_INSTANCES = "skip_instances"
SKIP_POINTS = "skip_points"  # TR400 (D2109)


def apply_fix(window: MainWindow, fid: str, fix: Any) -> bool:
    """Run a Phase 3 fix the user clicked (never automatically, CLAUDE.md rule 12).

    ``drop_refs`` removes failed picks from a pick list; ``skip_instances``
    adds failed pattern copies to the skip list. Both are one undoable step.
    """
    from fdcad.ui.commands.document import ReplaceFeature

    tab = window.current
    if tab is None or fix.action not in (DROP_REFS, SKIP_INSTANCES, SKIP_POINTS):
        return False
    session = tab.session
    target = str(fix.data.get("feature", fid))
    edited = copy.deepcopy(session.document.feature(target))
    if fix.action == SKIP_POINTS:  # TR400 (D2109): holes that fail are skipped
        from fdcad.core.features.partial import with_skipped
        from fdcad.ui.strings_config import FIX_HOLES_SKIPPED

        points = [str(p) for p in fix.data.get("points", [])]
        edited = with_skipped(edited, points)
        message = FIX_HOLES_SKIPPED.format(count=len(points))
    elif fix.action == DROP_REFS:
        key = str(fix.data.get("ref", "faces"))
        names = set(fix.data.get("names", []))
        refs = edited.refs.get(key, [])
        kept = [r for r in refs if not (isinstance(r, dict) and r.get("name") in names)]
        edited.refs[key] = kept
        message = text.FIX_DROPPED.format(count=len(refs) - len(kept))
    else:
        skip = list(edited.data.get("skip", []))
        added = 0
        for item in fix.data.get("instances", []):
            if list(item) not in skip:
                skip.append(list(item))
                added += 1
        edited.data["skip"] = skip
        message = text.FIX_SKIPPED.format(count=added)
    session.undo.push(ReplaceFeature(session, edited, f"{fix.label} ({edited.name})"))
    window.status.setText(message)
    return True


def face_menu(window: MainWindow, tab: DocumentTab, face: Any) -> QMenu:
    """The right click menu of a face: Move Face and Delete Face with it picked (T9)."""
    menu = QMenu(window)
    menu.setObjectName("face_menu")
    from fdcad.ui.input.commands import BY_ID

    for cid in ("feature.move_face", "feature.offset_face", "feature.delete_face"):
        action = menu.addAction(BY_ID[cid].label)
        action.setObjectName(cid)
        action.triggered.connect(lambda _c=False, c=cid: start(window, c, face))
    if window.isVisible():
        menu.popup(QCursor.pos())
    return menu


__all__ = ["COMMAND_TYPES", "apply_fix", "edit", "face_menu", "picked", "register", "start"]
