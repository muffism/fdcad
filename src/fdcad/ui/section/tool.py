"""Section view command (PHASE2_SPEC P2.13, D253): a view state of each open part.

The command opens the panel and turns the section on. OK keeps it on while you
keep modelling; Cancel, or the command again, turns it off. It is never saved
in the file and never changes the part, so it is not an undo step (like the
display style, D120 item 3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject

from fdcad.core.section import BASIS, DEFAULT_CAP, AxisSetting, Reference, SectionState
from fdcad.ui import strings
from fdcad.ui.commands.document import DocumentCommand
from fdcad.ui.section import strings_section

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.section.panel import SectionPanel


def references(tab: DocumentTab) -> dict[str, tuple[str, Reference]]:
    """Front, Top, Right, every plane of the part, and the selected flat face."""
    from fdcad.core.features.datum import PLANE_TYPES

    out: dict[str, tuple[str, Reference]] = {
        "front": (strings.SECTION_FRONT, Reference(*BASIS["front"])),
        "top": (strings.SECTION_TOP, Reference(*BASIS["top"])),
        "right": (strings.SECTION_RIGHT, Reference(*BASIS["right"])),
    }
    report = tab.session.report
    for f in tab.session.document.features:
        if f.type not in PLANE_TYPES or f.id in ("f2", "f3", "f4") or report is None:
            continue
        result = report.results.get(f.id)
        if result is not None and result.plane is not None:
            p = result.plane
            out[f.id] = (f.name, Reference(p.origin, p.normal, p.x_dir))
    face = _selected_face(tab)
    if face is not None:
        out["face"] = (strings.SECTION_FACE, face)
    return out


def part_centre(tab: DocumentTab) -> tuple[float, float, float] | None:
    """The middle of the shown bodies' bounding box, where a new section cuts (D75, D580)."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    shown = tab.shown_part()  # hidden bodies left out: cut through what is drawn
    if shown is None:
        return None
    box = Bnd_Box()
    BRepBndLib.Add_s(shown, box)
    if box.IsVoid():
        return None
    lo, hi = box.CornerMin(), box.CornerMax()
    return ((lo.X() + hi.X()) / 2, (lo.Y() + hi.Y()) / 2, (lo.Z() + hi.Z()) / 2)


def _selected_face(tab: DocumentTab) -> Reference | None:
    """The flat face selected when the section opened (tiny kernel work, like D75)."""
    from fdcad.core.features.datum import face_geo

    for shape in tab.selection:
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopoDS import TopoDS

        if shape.ShapeType() == TopAbs_FACE:
            geo = face_geo(TopoDS.Face(shape))
            if geo.kind == "plane" and geo.direction is not None and geo.x_dir is not None:
                return Reference(geo.point, geo.direction, geo.x_dir)
    return None


def axes(tab: DocumentTab) -> dict[str, tuple[str, AxisSetting]]:
    """Reference axes, and the selected round face or straight edge, for Section 1."""
    from fdcad.core.features.datum import edge_geo, face_geo

    out: dict[str, tuple[str, AxisSetting]] = {}
    report = tab.session.report
    for f in tab.session.document.features:
        if f.type != "ref_axis" or report is None:
            continue
        result = report.results.get(f.id)
        datum = result.datum if result is not None else None
        if datum is not None and datum.direction is not None:
            out[f.id] = (f.name, AxisSetting(datum.origin, datum.direction))
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopoDS import TopoDS

    for shape in tab.selection:
        kind = shape.ShapeType()
        geo = None
        if kind == TopAbs_FACE:
            geo = face_geo(TopoDS.Face(shape))
        elif kind == TopAbs_EDGE:
            geo = edge_geo(TopoDS.Edge(shape))
        if geo is not None and geo.kind in ("cylinder", "line", "circle") and geo.direction:
            out["selection"] = (
                strings.SECTION_SELECTED_AXIS,
                AxisSetting(geo.point, geo.direction),
            )
            break
    return out


def _body_count(tab: DocumentTab) -> int:
    """How many bodies the part has, for the see through list (TR355)."""
    from fdcad.core.features.solids import solids

    report = tab.session.report
    body = report.body if report is not None else None
    return len(solids(body.shape)) if body is not None else 0


def mesh_lines(tab: DocumentTab, state: SectionState) -> list[str]:
    """Where Section 1 cuts each reference mesh of the part (P3.9, D412).

    The 3D view's clipping cuts the drawn mesh like the part; a mesh has no
    solid to cap, so the panel gives the cut's size instead. Numpy only.
    """
    from fdcad.core.measure import Value
    from fdcad.core.mesh_tools import section_mesh
    from fdcad.ui.measure.box import format_value
    from fdcad.ui.strings_import import SECTION_MESH, SECTION_MESH_OPEN

    report = tab.session.report
    planes = state.cut_planes()
    if report is None or not planes:
        return []
    plane = planes[0]
    units = tab.session.document.units
    lines = []
    for feature in tab.session.document.features:
        result = report.results.get(feature.id)
        if result is None or "reference" not in result.extras or "mesh" not in result.extras:
            continue
        cut = section_mesh(result.extras["mesh"], plane.origin, plane.normal)
        if cut.segments == 0:
            continue
        length = format_value(Value("length", "length", cut.length), units, 2)
        if cut.area is None:
            lines.append(SECTION_MESH_OPEN.format(name=feature.name, length=length))
        else:
            area = format_value(Value("area", "area", cut.area), units, 2)
            lines.append(SECTION_MESH.format(name=feature.name, area=area, length=length))
    return lines


class SetSavedSection(DocumentCommand):
    """Save the section with the part, or remove it (TR213, D1604). View state only:
    no rebuild."""

    def __init__(self, session: Any, data: dict[str, Any] | None, text: str) -> None:
        super().__init__(session, text)
        from fdcad.core.section_store import KEY

        self.before = session.document.appearance.get(KEY)
        self.after = data

    def apply(self) -> None:
        """Store the new saved section."""
        from fdcad.core.section_store import set_saved

        set_saved(self.session.document, self.after)

    def revert(self) -> None:
        """Store the old one."""
        from fdcad.core.section_store import set_saved

        set_saved(self.session.document, self.before)

    def redo(self) -> None:
        """Nothing is redrawn: the section on screen stays as it is."""
        self.apply()

    def undo(self) -> None:
        """Put the old saved section back."""
        self.revert()


class SectionTool(QObject):
    """Turns the section view of the current part on and off."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        #: Section of each open part, by tab; absent means off.
        self.states: dict[int, SectionState] = {}
        self.panel: SectionPanel | None = None
        self.tab: DocumentTab | None = None
        from fdcad.ui.section.handle import SectionHandle

        #: The drag arrow and rings of the active plane in the 3D view.
        self.handle = SectionHandle(lambda: self.panel, self)
        #: The plane whose arrow and rings show: picked in the Section Planes folder.
        self.active_plane = 0
        from fdcad.ui.section.cut_faces import CutFaces

        #: Pickable cut faces for Measure (TR213, D2502).
        self.cut_faces = CutFaces(self)
        tree = getattr(window, "tree", None)
        if tree is not None and hasattr(tree, "section_requested"):
            tree.section_requested.connect(self.tree_request)

    def state_of(self, tab: DocumentTab) -> SectionState | None:
        """The section of ``tab``, or None when it is off."""
        return self.states.get(id(tab))

    def toggle(self) -> None:
        """The Section View command: on (with the panel), or off."""
        tab = self.window.current
        if tab is None:
            return
        if self.panel is not None or self.state_of(tab) is not None:
            self.turn_off(tab)
        else:
            self.open(tab)

    def open(self, tab: DocumentTab) -> None:
        """Show the panel and turn the section on."""
        from fdcad.core.rebuild.engine import document_variables
        from fdcad.ui.section.panel import SectionPanel

        doc = tab.session.document
        try:
            variables = document_variables(doc)
        except Exception:
            variables = {}
        state = self.state_of(tab)
        fresh = state is None
        panel = SectionPanel(
            state or SectionState(),
            references(tab),
            axes(tab),
            doc.units,
            variables,
            centre=part_centre(tab) if fresh else None,
            bodies=_body_count(tab),
            saved=tab.session.document.appearance.get("section") is not None,
        )
        panel.changed.connect(lambda s: self.apply(tab, s))
        panel.accepted.connect(self.accept)
        panel.rejected.connect(lambda: self.turn_off(tab))
        panel.cut_requested.connect(lambda: self.add_cut(tab))
        self.panel, self.tab = panel, tab
        self.window.show_side_panel(panel)
        self.apply(tab, panel.current())

    def apply(self, tab: DocumentTab, state: SectionState) -> None:
        """Show ``state`` in the 3D view of ``tab``."""
        from fdcad.ui.viewport.section_view import clip_chain, clip_chains

        self.states[id(tab)] = state
        show = getattr(tab.viewport, "set_section", None)
        if show is not None:
            zones = state.cut_zones()
            if len(zones) > 1:
                show(clip_chains(zones, state.show_cap, state.cap_color))  # TR355
            else:
                show(clip_chain(state.cut_planes(), state.show_cap, state.cap_color))
        self._see_through(tab, state)
        self.cut_faces.update(tab, state)
        if self.panel is not None and self.tab is tab:
            self.panel.set_mesh_info(mesh_lines(tab, state))
            if self.active_plane >= len(state.planes):
                self.active_plane = 0
            self.handle.show(tab, state, self.active_plane)
        self._check()
        self.window.status.setText(strings.SECTION_ON)

    def add_cut(self, tab: DocumentTab) -> str | None:
        """Add a Section Cut feature for the section shown (TR151 item 2, D2205) as one
        undo step, then turn the section off. Returns the new feature id."""
        from fdcad.core.document.model import Feature
        from fdcad.core.features.names import default_name
        from fdcad.core.features.section_cut import zones_data
        from fdcad.ui.commands.document import AddFeature
        from fdcad.ui.section import strings_section

        state = self.panel.current() if self.panel is not None else self.state_of(tab)
        if state is None:
            return None
        zones = [[(p.origin, p.normal) for p in zone] for zone in state.cut_zones()]
        if not zones:
            return None
        doc = tab.session.document
        feature = Feature(
            doc.new_feature_id(),
            "section_cut",
            default_name(doc, "section_cut"),
            data=zones_data(zones),
        )
        tab.session.undo.push(AddFeature(tab.session, feature))
        self.turn_off(tab)
        self.window.status.setText(strings_section.CUT_FEATURE_DONE.format(name=feature.name))
        return feature.id

    def accept(self) -> None:
        """OK: close the panel, the section stays on."""
        tab = self.tab
        if tab is not None and self.panel is not None:
            self._store(tab, self.panel.save_box.isChecked())
        self._close_panel()
        state = self.state_of(tab) if tab is not None else None
        if tab is not None and state is not None and not state.keep_cap_color:
            state.cap_color = DEFAULT_CAP
            for p in state.planes:
                p.color = DEFAULT_CAP
            self.apply(tab, state)

    def tab_changed(self) -> None:
        """Another part is shown: close the panel as OK does, so the section of the part
        left behind stays on and the panel never edits a part that is not shown."""
        if self.panel is not None and self.tab is not self.window.current:
            self.accept()
        self._check()

    def tree_request(self, what: str, plane: int) -> None:
        """A Section Planes row of the tree (TR213, D2501): "pick" shows that plane's
        arrow and rings (opening the panel), "edit" opens the panel, "off" turns the
        section off."""
        tab = self.window.current
        if tab is None or self.state_of(tab) is None:
            return
        if what == "off":
            self.turn_off(tab)
            return
        self.active_plane = max(0, plane)
        if self.panel is None:
            self.open(tab)
        else:
            state = self.state_of(tab)
            if state is not None:
                self.apply(tab, state)

    def turn_off(self, tab: DocumentTab | None = None) -> None:
        """Remove the section of ``tab`` (the current part by default)."""
        tab = tab or self.window.current
        self._close_panel()
        if tab is None:
            return
        self.states.pop(id(tab), None)
        show = getattr(tab.viewport, "set_section", None)
        if show is not None:
            show(None)
        self._see_through(tab, None)
        self.cut_faces.update(tab, None)
        self._check()
        self.window.status.setText(strings.SECTION_OFF)

    def _store(self, tab: DocumentTab, keep: bool) -> bool:
        """Save the section with the part, or remove the saved one (TR213). True when
        the file changed."""
        from fdcad.core.section_store import KEY, to_json

        state = self.state_of(tab)
        data = to_json(state) if keep and state is not None else None
        if tab.session.document.appearance.get(KEY) == data:
            return False
        text = strings_section.SAVE_UNDO if data is not None else strings_section.UNSAVE_UNDO
        tab.session.undo.push(SetSavedSection(tab.session, data, text))
        return True

    def restore_saved(self, tab: DocumentTab) -> bool:
        """Turn on the section saved with a part that just opened (TR213)."""
        from fdcad.core.section_store import saved

        state = saved(tab.session.document)
        if state is None:
            return False
        self.apply(tab, state)
        if state.see_through or state.whole:  # the bodies are known after the first rebuild
            tab.session.rebuilt.connect(lambda _r: self._see_through(tab, self.state_of(tab)))
        return True

    def show_state(self, tab: DocumentTab, state: SectionState | None) -> None:
        """Show a section kept in a saved view, or turn it off with None (TR213)."""
        if self.panel is not None:
            self.accept()
        if state is None:
            self.turn_off(tab)
        else:
            self.apply(tab, state)

    def _see_through(self, tab: DocumentTab, state: SectionState | None) -> None:
        """Draw the bodies chosen in the section see through, or none (TR355 item 2),
        and keep the bodies left whole uncut (TR213, D2500)."""
        from fdcad.core.features.solids import solids

        self._whole(tab, state)
        fn = getattr(tab.viewport, "set_section_see_through", None)
        if fn is None:
            return
        report = tab.session.report
        body = report.body if report is not None else None
        shape = getattr(body, "shape", None)
        if state is None or not state.see_through or shape is None:
            fn([], 0.0)
            return
        found = solids(shape)
        fn([found[i] for i in state.see_through if 0 <= i < len(found)], state.see_through_level)

    def _whole(self, tab: DocumentTab, state: SectionState | None) -> None:
        """Tell the 3D view which bodies the section leaves whole (TR213, D2500)."""
        from fdcad.core.features.solids import solids

        fn = getattr(tab.viewport, "set_section_whole", None)
        if fn is None:
            return
        report = tab.session.report
        shape = getattr(report.body if report is not None else None, "shape", None)
        if state is None or not state.whole or shape is None:
            fn([])
            return
        found = solids(shape)
        fn([found[i] for i in state.whole if 0 <= i < len(found)])

    def _close_panel(self) -> None:
        self.handle.clear()
        self.active_plane = 0
        if self.panel is not None:
            self.window.hide_side_panel()
            self.panel.deleteLater()
        self.panel, self.tab = None, None

    def plane_names(self, tab: DocumentTab) -> list[str]:
        """The rows of the Section Planes folder for ``tab``: [] when the section is off."""
        state = self.state_of(tab)
        if state is None:
            return []
        refs = references(tab)
        out = []
        for i, plane in enumerate(state.planes[:3]):
            name = strings.SECTION_PLANE.format(number=i + 1)
            if i == 0 and state.axis is not None:
                where = strings.SECTION_AXIS.rstrip(":")
            else:
                where = refs.get(plane.source, ("", None))[0] or plane.source
            out.append(f"{name} ({where})" if where else name)
        return out

    def _check(self) -> None:
        action: Any = self.window.commands.actions.get("view.section")
        tab = self.window.current
        tree = getattr(self.window, "tree", None)
        if tree is not None and hasattr(tree, "set_section_planes"):
            tree.set_section_planes(self.plane_names(tab) if tab is not None else [])
        if action is not None:
            action.blockSignals(True)
            action.setChecked(tab is not None and self.state_of(tab) is not None)
            action.blockSignals(False)
