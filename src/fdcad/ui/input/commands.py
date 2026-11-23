"""Commands, their default shortcuts, gestures and the shortcut bar (SHORTCUTS.md).

Pure Python, no Qt, so the maps are tested on their own. Key text uses Qt's
portable form: on macOS Qt shows "Ctrl" as Cmd and "Meta" as Control, which
gives the Mac conversion rules in SHORTCUTS.md section 1 for free. The few
commands that keep the Control key on a Mac list a ``mac`` shortcut.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandDef:
    """A command the user can bind to keys, gestures and the shortcut bar."""

    id: str
    label: str
    keys: tuple[str, ...] = ()
    mac: tuple[str, ...] | None = None
    group: str = "General"


def _c(
    cid: str, label: str, *keys: str, mac: tuple[str, ...] | None = None, group: str
) -> CommandDef:
    return CommandDef(cid, label, tuple(keys), mac, group)


#: Phase 4 commands (PHASE4_SPEC), kept together so parallel work does not clash.
PHASE4_COMMANDS: tuple[CommandDef, ...] = (
    _c("feature.hole", "Hole Tool", group="Features"),
    _c("feature.cosmetic_thread", "Cosmetic Thread", group="Features"),
    _c("feature.modeled_thread", "Thread", group="Features"),
    _c("feature.mounting_boss", "Mounting Boss", group="Features"),
    _c("feature.snap_hook", "Snap Hook", group="Features"),
    _c("feature.snap_groove", "Snap Hook Groove", group="Features"),
    _c("feature.lip_groove", "Lip and Groove", group="Features"),
    _c("feature.vent", "Vent", group="Features"),
    _c("feature.inlay", "Inlay", group="Features"),  # TR184 (D867)
    _c("feature.cable_tie", "Cable Tie", group="Features"),  # TR363 (D879)
    _c("feature.half_lap", "Half Lap", group="Features"),  # TR364 (D882)
    _c("feature.twist_lock", "Twist Lock", group="Features"),  # TR357 (D1024)
    _c("feature.indent", "Indent", group="Features"),  # TR68 (D1026)
    _c("feature.finger_joint", "Finger Joint", group="Features"),  # TR246 (D883)
    _c("feature.crush_ribs", "Crush Ribs", group="Features"),  # TR403 (D891)
    _c("feature.corner_ears", "Corner Ears", group="Features"),  # TR189 (D1005)
    _c("feature.drain_holes", "Drain Holes", group="Features"),  # TR189 (D1006)
    _c("feature.polygon_holes", "Polygon Holes", group="Features"),  # TR189 (D1007)
    _c("feature.base_pad", "Base Pad", group="Features"),  # TR414 (D1009)
    _c("feature.interlock", "Material Interlock", group="Features"),  # TR414 (D1216)
    _c("feature.lattice_fill", "Lattice Fill", group="Features"),  # TR390 (D2004)
    _c("feature.mark", "Mark", group="Features"),  # TR330 (D2006)
    _c("feature.hinge", "Hinge", group="Features"),  # TR404 (D2008)
    _c("feature.face_seats", "Face Seats", group="Features"),  # TR405 (D2009)
    _c("feature.stone_setting", "Stone Setting", group="Features"),  # TR408 (D2410)
    _c("feature.roof", "Roof", group="Features"),  # TR258 (D2414)
    _c("feature.sprue_tree", "Sprue Tree", group="Features"),  # TR408 (D2411)
    _c("feature.transition_spiral", "Transition Spiral", group="Features"),  # TR408 (D2010)
    _c("feature.edge_profile", "Edge Profile", group="Features"),  # TR243 (D2011)
    _c("feature.lightening_pockets", "Lightening Pockets", group="Features"),  # TR245 (D2012)
    _c("feature.landing_pad", "Landing Pad", group="Features"),  # TR325 (D2013)
    _c("feature.joint_helper", "Joint", group="Features"),  # TR401 (D2014)
    _c("feature.knurl", "Knurl", group="Features"),  # TR163 (D2015)
    _c("feature.hose_fitting", "Hose Fitting", group="Features"),  # TR406 (D914)
    _c("feature.living_hinge", "Living Hinge", group="Features"),  # TR402 (D908)
    _c("feature.rib", "Rib", group="Features"),
    _c("feature.dome", "Dome", group="Features"),
    _c("feature.corner_relief", "Corner Relief", group="Features"),  # TR244 (D785)
    _c("feature.wrap", "Wrap", group="Features"),
    _c("sketch.text", "Text", group="Sketch"),
)

#: Every command built so far. A shortcut becomes active when its command exists.
COMMANDS: tuple[CommandDef, ...] = (
    _c("file.new", "New Part", "Ctrl+N", group="File"),
    _c("file.open", "Open", "Ctrl+O", group="File"),
    _c("file.close", "Close", "Ctrl+W", group="File"),
    _c("file.save", "Save", "Ctrl+S", group="File"),
    _c("file.save_as", "Save As", "Ctrl+Shift+S", group="File"),
    _c("file.save_increment", "Save Increment", group="File"),  # TR305 (D923)
    _c("file.save_all", "Save All", group="File"),  # TR218 (D961): no default keys
    _c("file.close_all", "Close All", group="File"),
    _c("file.revert", "Revert to Saved", group="File"),
    _c("file.open_view_only", "Open for Viewing", group="File"),  # TR356 (D971)
    _c("file.save_copy", "Save a Copy", group="File"),  # TR97 (D806)
    _c("file.export_configs", "Export Configurations", group="File"),  # TR196 (D827)
    _c("file.mirror_part", "Mirror Part", group="File"),  # TR73 (D899)
    _c("file.batch_export", "Batch Export", group="File"),  # TR368 (D904)
    _c("file.save_template", "Save as Template", group="File"),  # TR217 (D833)
    _c("sketch.cut_away", "Cut Away in Front", group="Sketch"),  # TR113 (D844)
    _c("sketch.hide_construction", "Hide Construction Geometry", group="Sketch"),  # TR419
    _c("sketch.show_construction", "Show Construction in Part", group="Sketch"),  # TR339
    _c("print.scale_to_fit", "Scale to Fit Printer", group="Print"),  # TR185 (D828)
    _c("print.clear_fit", "Clear Print Scale", group="Print"),
    _c("print.save_fit", "Save Print Scale as Feature", group="Print"),
    _c("file.save_copy_open", "Save a Copy and Open", group="File"),
    _c("file.save_image", "Save Image", group="File"),  # TR24 (D689)
    _c("edit.undo", "Undo", "Ctrl+Z", group="Edit"),
    # Mac Redo is Command+Shift+Z, as on every Mac app (TR375, D767); Command+Y stays.
    _c("edit.redo", "Redo", "Ctrl+Y", mac=("Ctrl+Shift+Z", "Ctrl+Y"), group="Edit"),
    _c("edit.repeat", "Repeat Last Command", "Return", "Z", group="Edit"),
    _c("edit.delete", "Delete", "Delete", group="Edit"),
    # TR3, TR9 (D685): sketches, sketch based features, and sketch entities in a sketch.
    _c("edit.copy", "Copy", "Ctrl+C", group="Edit"),
    _c("edit.paste", "Paste", "Ctrl+V", group="Edit"),
    _c("edit.rebuild", "Rebuild", "Ctrl+B", group="Edit"),
    _c("edit.pause_rebuilds", "Pause Rebuilds", group="Edit"),  # TR276 (D835)
    _c("edit.rebuild_stay", "Rebuild and Stay Paused", group="Edit"),
    _c("edit.discard_paused", "Discard Paused Edits", group="Edit"),
    _c("edit.continue_rebuild", "Continue Rebuild", group="Edit"),
    _c("edit.force_rebuild", "Force Rebuild", "Ctrl+Q", mac=("Meta+Q",), group="Edit"),
    _c("tree.find", "Find in Feature Tree", "Ctrl+F", group="Feature tree"),
    _c("tree.top", "Scroll Feature Tree to Top", "Home", group="Feature tree"),
    _c("tree.bottom", "Scroll Feature Tree to Bottom", "End", group="Feature tree"),
    _c("tree.flat", "Flat Tree View", "Ctrl+T", group="Feature tree"),
    _c("tree.collapse_all", "Collapse All", group="Feature tree"),  # TR221 (D1611)
    _c("tree.roll_back", "Roll Back One Feature", group="Feature tree"),
    _c("tree.roll_forward", "Roll Forward", group="Feature tree"),
    _c("tree.roll_previous", "Roll to Previous", group="Feature tree"),
    _c("tree.roll_end", "Roll to End", group="Feature tree"),
    _c("tree.purge_unused", "Purge Unused", group="Feature tree"),  # TR159 (D956)
    _c("edit.edit_by_rule", "Edit by Rule", group="Feature tree"),  # TR160 (D957)
    _c("tree.delete_below_bar", "Delete Below Rollback Bar", group="Feature tree"),
    _c("tree.remove_history", "Remove History", group="Feature tree"),  # TR158 (D983)
    _c("view.front", "Front", "Ctrl+1", group="View"),
    _c("view.back", "Back", "Ctrl+2", group="View"),
    _c("view.left", "Left", "Ctrl+3", group="View"),
    _c("view.right", "Right", "Ctrl+4", group="View"),
    _c("view.top", "Top", "Ctrl+5", group="View"),
    _c("view.bottom", "Bottom", "Ctrl+6", group="View"),
    _c("view.iso", "Isometric", "Ctrl+7", group="View"),
    # TR14 (D690): no default keys.
    _c("view.dimetric", "Dimetric", group="View"),
    _c("view.trimetric", "Trimetric", group="View"),
    _c("view.save_view", "Save View", group="View"),
    _c("view.home", "Home", group="View"),  # TR333 (D955): no default keys
    _c("help.tool", "Help for This Tool", group="View"),  # TR380 (D1002): F1 is an owner item
    _c("view.set_view_as", "Set Current View As", group="View"),
    _c("view.reset_views", "Reset Standard Views", group="View"),
    _c("view.temporary_axes", "Temporary Axes", group="View"),  # TR17 (D693)
    _c("view.mirror_image", "Mirror Image", group="View"),  # TR309 (D926)
    _c("view.all_dimensions", "Show All Dimensions", group="View"),  # TR32 (D698)
    # TR16 (D699): no default keys.
    _c("view.split_one", "One View", group="View"),
    _c("view.split_side", "Two Views Side by Side", group="View"),
    _c("view.split_stacked", "Two Views Stacked", group="View"),
    _c("view.split_four", "Four Views", group="View"),
    _c("view.normal_to", "Normal To", "Ctrl+8", "N", group="View"),
    _c("view.fit", "Zoom to Fit", "F", group="View"),
    _c("view.describe_part", "Describe Part", group="View"),  # TR294 item 2 (D2017)
    _c("view.before_after", "Before and After", group="View"),  # TR289 (D2019)
    _c("view.zoom_in", "Zoom In", "Shift+Z", group="View"),
    _c("view.zoom_out", "Zoom Out", group="View"),  # TR211 (D1607): owner sets the key
    _c("view.zoom_area", "Zoom to Area", group="View"),
    _c("view.zoom_selection", "Zoom to Selection", group="View"),
    # On a Mac Previous View moves to Control+Shift+Z, giving Redo its key (D767).
    _c("view.previous", "Previous View", "Ctrl+Shift+Z", mac=("Meta+Shift+Z",), group="View"),
    _c("view.redraw", "Redraw", "Ctrl+R", group="View"),
    _c("view.shaded_edges", "Shaded With Edges", group="View"),
    _c("view.shaded", "Shaded", group="View"),
    _c("view.hidden_lines", "Hidden Lines Removed", "Shift+Q", group="View"),
    _c("view.hidden_lines_visible", "Hidden Lines Visible", "Shift+H", group="View"),
    _c("view.wireframe", "Wireframe", "Shift+W", group="View"),
    _c("view.transparency", "Toggle Transparency", "Shift+T", group="View"),
    _c("view.perspective", "Perspective", group="View"),  # TR15 (D747)
    _c("view.sketch_relations", "Sketch Relations", group="View"),
    _c("view.show_planes", "Planes", group="View"),
    _c("view.show_origins", "Origins", group="View"),
    _c("view.show_sketches", "Sketches", group="View"),
    _c("view.selector", "View Selector", "Ctrl+Space", mac=("Meta+Space",), group="View"),
    _c("view.orientation", "Orientation", group="View"),  # TR210 (D1601): owner sets the key
    _c("view.display_quality", "Display Quality", group="View"),  # TR214 (D1605)
    _c("view.display_states", "Display States", group="View"),  # TR88 (D1608)
    _c("view.hide_show", "Hide or Show", "H", group="View"),
    # Body visibility (PHASE3_SPEC P3.4 item 6, D116 item 4, D410).
    _c("view.isolate", "Isolate", "I", group="View"),
    _c("view.show_hovered", "Show Hovered Body", "Shift+Tab", group="View"),
    _c(
        "view.show_all_bodies",
        "Show All Hidden Bodies",
        "Ctrl+Shift+Tab",
        mac=("Meta+Shift+Tab",),
        group="View",
    ),
    _c(
        "view.hide_reference",
        "Hide All Reference Geometry",
        "Ctrl+H",
        mac=("Meta+H",),
        group="View",
    ),
    _c("select.filter_bar", "Selection Filter Bar", "F5", group="Selection"),
    _c("select.filters_toggle", "Turn Selection Filters On or Off", "F6", group="Selection"),
    _c("select.filter_edges", "Filter Edges", "E", group="Selection"),
    _c("select.filter_faces", "Filter Faces", "X", group="Selection"),
    _c("select.filter_vertices", "Filter Vertices", "V", group="Selection"),
    _c("select.other", "Select Other", group="Selection"),
    _c("select.lasso", "Lasso Selection", group="Selection"),  # TR19 (D755)
    # TR329 (D2208): one pick type at once, paint pick and pick by volume.
    _c("select.only_bodies", "Pick Bodies Only", group="Selection"),
    _c("select.only_faces", "Pick Faces Only", group="Selection"),
    _c("select.only_edges", "Pick Edges Only", group="Selection"),
    _c("select.paint", "Paint Selection", group="Selection"),
    _c("select.in_volume", "Pick in Volume", group="Selection"),
    _c("select.previous", "Select Previous", group="Selection"),  # TR93 (D915)
    _c("select.invert", "Invert Selection", group="Selection"),
    _c("select.all", "Select All", group="Selection"),  # TR380, TR224 (D934)
    _c("select.similar", "Select Similar", group="Selection"),  # TR303 (D943)
    _c("select.to_edges", "Select Their Edges", group="Selection"),
    _c("select.to_faces", "Select Their Faces", group="Selection"),
    _c("select.to_bodies", "Select Their Bodies", group="Selection"),
    _c("select.save_set", "Save Selection Set", group="Selection"),  # TR94 (D944)
    _c("select.sets", "Selection Sets", group="Selection"),
    _c("ui.toggle_left", "Toggle Left Panel", "F9", group="Interface"),
    _c("ui.toggle_toolbars", "Toggle Command Tabs", "F10", group="Interface"),
    _c("ui.fullscreen", "Full Screen", "F11", mac=("F11", "Ctrl+Meta+F"), group="Interface"),
    _c("ui.next_tab", "Next Command Tab", "Ctrl+PgDown", group="Interface"),
    _c("ui.previous_tab", "Previous Command Tab", "Ctrl+PgUp", group="Interface"),
    # TR22 (D683): Control+Tab on a Mac; the previous part has no default key.
    _c("ui.next_part", "Next Part", "Ctrl+Tab", mac=("Meta+Tab",), group="Interface"),
    _c("ui.previous_part", "Previous Part", group="Interface"),
    _c("ui.shortcut_bar", "Shortcut Bar", "Q", group="Interface"),
    _c("ui.preferences", "Preferences", "Ctrl+,", group="Interface"),
    _c("tools.stats", "Rebuild Statistics", group="Interface"),
    _c("evaluate.measure", "Measure", group="Evaluate"),
    _c("view.section", "Section View", group="View"),
    _c("edit.appearance", "Appearance", group="Edit"),
    _c("edit.copy_appearance", "Copy Appearance", group="Edit"),
    _c("edit.paste_appearance", "Paste Appearance", group="Edit"),
    _c("ui.confirm_corner", "Move Confirmation Corner to Cursor", "A", group="Interface"),
    #: T9.12: the right click menu of the selection from the keyboard.
    _c("ui.context_menu", "Context Menu", "Shift+F10", "Menu", group="Interface"),
    _c("sketch.sketch", "Sketch", "S", group="Sketch"),
    _c("sketch.select", "Select", group="Sketch"),
    _c("sketch.line", "Line", "L", group="Sketch"),
    _c("sketch.centerline", "Centerline", "Alt+C", group="Sketch"),
    _c("sketch.corner_rectangle", "Corner Rectangle", "R", group="Sketch"),
    _c("sketch.center_rectangle", "Center Rectangle", group="Sketch"),
    _c("sketch.circle", "Circle", "C", group="Sketch"),
    _c("sketch.center_arc", "Centerpoint Arc", group="Sketch"),
    _c("sketch.tangent_arc", "Tangent Arc", group="Sketch"),
    _c("sketch.three_point_arc", "3 Point Arc", group="Sketch"),
    _c("sketch.point", "Point", "P", group="Sketch"),
    _c("sketch.dimension", "Smart Dimension", "D", group="Sketch"),
    _c("sketch.construction", "Construction Geometry", group="Sketch"),
    _c("sketch.relations", "Relations", group="Sketch"),
    _c("sketch.exit", "Exit Sketch", group="Sketch"),
    _c("sketch.discard", "Exit Without Saving", group="Sketch"),  # TR120 (D941)
    _c("sketch.snap_options", "Snap Options", "F3", group="Sketch"),
    #: T12.5: no default key, because A moves the confirmation corner.
    _c("sketch.line_arc", "Switch Line and Arc", group="Sketch"),
    _c("sketch.edit_plane", "Edit Sketch Plane", group="Sketch"),
    # Phase 2 sketch tools (PHASE2_SPEC P2.8, P2.9): no default keys, so none clash.
    _c("sketch.trim", "Trim", group="Sketch"),
    _c("sketch.extend", "Extend", group="Sketch"),
    _c("sketch.offset", "Offset", group="Sketch"),
    _c("sketch.mirror", "Mirror", group="Sketch"),
    _c("sketch.fillet", "Sketch Fillet", group="Sketch"),
    _c("sketch.chamfer", "Sketch Chamfer", group="Sketch"),
    _c("sketch.convert", "Convert Entities", group="Sketch"),
    _c("sketch.linear_pattern", "Linear Sketch Pattern", group="Sketch"),
    _c("sketch.circular_pattern", "Circular Sketch Pattern", group="Sketch"),
    _c("sketch.slot", "Slot", group="Sketch"),
    _c("sketch.polygon", "Polygon", group="Sketch"),
    _c("sketch.spline", "Spline", group="Sketch"),
    _c("sketch.ellipse", "Ellipse", group="Sketch"),
    _c("sketch.partial_ellipse", "Partial Ellipse", group="Sketch"),
    _c("sketch.picture", "Sketch Picture", group="Sketch"),
    # Round 9t sketch shapes (D511 to D514): no default keys.
    _c("sketch.three_point_corner_rectangle", "3 Point Corner Rectangle", group="Sketch"),
    _c("sketch.three_point_center_rectangle", "3 Point Center Rectangle", group="Sketch"),
    _c("sketch.parallelogram", "Parallelogram", group="Sketch"),
    _c("sketch.perimeter_circle", "Perimeter Circle", group="Sketch"),
    _c("sketch.two_point_circle", "2 Point Circle", group="Sketch"),  # TR317 (D877)
    _c("sketch.tangent_circle", "Tangent Circle", group="Sketch"),  # TR317 (D877)
    _c("sketch.blend_curve", "Blend Curve", group="Sketch"),  # TR318 (D884)
    _c("sketch.jog_line", "Jog Line", group="Sketch"),  # TR52 (D902)
    _c("sketch.parabola", "Parabola", group="Sketch"),  # TR52 (D902)
    _c("sketch.hyperbola", "Partial Hyperbola", group="Sketch"),  # TR374 (D985)
    _c("sketch.dynamic_mirror", "Dynamic Mirror", group="Sketch"),
    # TR1 (D684): no default keys.
    _c("sketch.move_entities", "Move Entities", group="Sketch"),
    _c("sketch.copy_entities", "Copy Entities", group="Sketch"),
    _c("sketch.rotate_entities", "Rotate Entities", group="Sketch"),
    _c("sketch.scale_entities", "Scale Entities", group="Sketch"),
    _c("sketch.stretch_entities", "Stretch Entities", group="Sketch"),
    _c("sketch.midpoint_line", "Midpoint Line", group="Sketch"),  # TR4 (D688)
    _c("sketch.infinite_line", "Infinite Construction Line", group="Sketch"),  # TR115
    _c("sketch.conic", "Conic", group="Sketch"),  # TR28 (D757)
    _c("sketch.equation_curve", "Equation Curve", group="Sketch"),
    _c("sketch.intersection_curves", "Intersection Curves", group="Sketch"),  # TR6 (D759)
    _c("sketch.silhouette", "Silhouette", group="Sketch"),
    _c("sketch.turned_outline", "Turned Outline", group="Sketch"),  # TR319 (D888)
    _c("sketch.close_to_model", "Close Sketch to Model", group="Sketch"),  # TR106 (D1704)
    _c("sketch.fully_define", "Fully Define Sketch", group="Sketch"),  # TR35 (D762)
    _c("sketch.check_sketch", "Check Sketch", group="Sketch"),  # TR36 (D763)
    _c("sketch.repair_sketch", "Repair Sketch", group="Sketch"),  # TR37 (D1300)
    _c("sketch.insert_spline_point", "Insert Spline Point", group="Sketch"),  # TR42 (D1306)
    _c("sketch.fit_spline", "Fit Spline", group="Sketch"),
    _c("sketch.simplify_spline", "Simplify Spline", group="Sketch"),
    _c("sketch.baseline_dimension", "Baseline Dimension", group="Sketch"),  # TR45 (D1307)
    _c("sketch.ordinate_dimension", "Ordinate Dimension", group="Sketch"),
    _c("sketch.split", "Split Entities", group="Sketch"),  # TR2 (D691)
    _c("sketch.insert_dxf", "Insert DXF", group="Sketch"),  # TR5 (D695)
    _c("sketch.insert_svg", "Insert SVG", group="Sketch"),  # TR117 (D863)
    _c("evaluate.undercut", "Undercut Analysis", group="Evaluate"),  # TR83 (D864)
    _c("evaluate.edge_angles", "Edge Angle Analysis", group="Evaluate"),  # TR420 (D929)
    _c("evaluate.layer_preview", "Layer Preview", group="Evaluate"),  # TR315 (D993)
    _c("view.curvature_combs", "Curvature Combs", group="View"),
    _c("feature.extrude", "Extruded Boss", "Shift+E", group="Features"),
    _c("feature.extruded_cut", "Extruded Cut", "Shift+C", group="Features"),
    _c("feature.revolve", "Revolved Boss", "Shift+R", group="Features"),
    _c("feature.revolved_cut", "Revolved Cut", "Ctrl+Shift+R", group="Features"),
    _c("feature.sweep", "Swept Boss", "Shift+S", group="Features"),
    #: SHORTCUTS.md gives Ctrl+Shift+S, which Save As already uses (D216): no default key.
    _c("feature.swept_cut", "Swept Cut", group="Features"),
    _c("feature.loft", "Lofted Boss", group="Features"),
    _c("feature.lofted_cut", "Lofted Cut", "Shift+L", group="Features"),
    _c("feature.fillet", "Fillet", "Shift+F", group="Features"),
    _c("feature.chamfer", "Chamfer", "Ctrl+Shift+F", group="Features"),
    _c("feature.shell", "Shell", group="Features"),
    _c("feature.draft", "Draft", "Shift+D", group="Features"),
    # Phase 3 (PHASE3_SPEC P3.1 to P3.4, P3.8): no default keys, users can bind them.
    _c("feature.move_face", "Move Face", group="Features"),
    _c("feature.face_relation", "Face Relation", group="Features"),  # TR266 (D2418)
    _c("feature.offset_face", "Offset Face", group="Features"),
    _c("feature.delete_face", "Delete Face", group="Features"),
    _c("feature.merge_faces", "Merge Faces", group="Features"),  # TR261 (D787)
    _c("feature.linear_pattern", "Linear Pattern", group="Features"),
    _c("feature.circular_pattern", "Circular Pattern", group="Features"),
    _c("feature.pattern_chain", "Pattern Chain", group="Features"),  # TR141 (D1901)
    _c("feature.sketch_pattern", "Sketch Driven Pattern", group="Features"),
    _c("feature.point_pattern", "Point Pattern", group="Features"),  # TR365 (D887)
    _c("feature.table_pattern", "Table Driven Pattern", group="Features"),  # TR58 (D821)
    _c("feature.fill_pattern", "Fill Pattern", group="Features"),  # TR57 (D792)
    _c("feature.bounding_box", "Bounding Box", group="Evaluate"),  # TR69 (D809)
    _c("feature.sensor", "Sensor", group="Evaluate"),  # TR86 (D1022)
    _c("feature.primitive", "Primitive Solid", group="Features"),  # TR127 (D813)
    _c("feature.mirror", "Mirror", group="Features"),
    _c("feature.combine", "Combine", group="Features"),
    _c("feature.intersect", "Intersect", group="Features"),
    _c("feature.split", "Split", group="Features"),
    _c("feature.move_copy_body", "Move and Copy Body", group="Features"),
    _c("feature.linked_copy", "Linked Body Copy", group="Features"),  # TR154 (D2417)
    _c("feature.insert_part", "Insert Part", group="Features"),  # TR71 (D2420)
    _c("feature.transform_handles", "Transform Handles", group="Features"),
    _c("feature.delete_body", "Delete and Keep Body", group="Features"),
    _c("feature.scale", "Scale", group="Features"),
    _c("feature.mould_cavity", "Mould Cavity", group="Features"),  # TR85 (D2111)
    _c("feature.offset_body", "Offset Body", group="Features"),  # TR129 (D825)
    _c("feature.shaft_shape", "Shaft Shape", group="Features"),  # TR247 (D841)
    _c("feature.ring_groove", "Ring Groove", group="Features"),  # TR249 (D874)
    _c("feature.oring_groove", "O Ring Groove", group="Features"),  # TR250 (D886)
    _c("feature.import_step", "Import STEP Body", group="Features"),
    _c("feature.helix", "Helix and Spiral", group="Features"),
    _c("feature.projected_curve", "Projected Curve", group="Features"),
    _c("feature.composite_curve", "Composite Curve", group="Features"),
    _c("feature.point_curve", "Curve Through Points", group="Features"),  # TR61 (D817)
    _c("feature.sketch3d", "3D Sketch", group="Features"),  # TR7 (D1719)
    _c("feature.pipe", "Pipe", group="Features"),
    _c("feature.curve_array", "Array Along Curve", group="Features"),
    _c("feature.contour", "Contour Curves", group="Features"),
    _c("evaluate.curvature_graph", "Curvature Graph", group="Evaluate"),
    _c("evaluate.zebra", "Zebra Stripes", group="Evaluate"),  # TR18 (D754)
    _c("evaluate.curvature_colors", "Curvature Colors", group="Evaluate"),  # TR199 (D2503)
    _c("evaluate.compare_bodies", "Compare Bodies", group="Evaluate"),  # TR27 (D758)
    _c("evaluate.mass_properties", "Mass Properties", group="Evaluate"),  # TR79 (D764)
    _c("evaluate.interference", "Interference Check", group="Evaluate"),  # TR150 (D771)
    _c("evaluate.cavities", "Enclosed Cavities", group="Evaluate"),  # TR284 (D772)
    _c("evaluate.change_test", "Change Test", group="Evaluate"),  # TR287 (D774)
    _c("evaluate.model_health", "Model Health", group="Evaluate"),  # TR286 (D775)
    _c("evaluate.repair_references", "Repair Lost References", group="Evaluate"),  # TR125
    _c("evaluate.manufacturing", "Manufacturing Check", group="Evaluate"),  # TR295 (D790)
    _c("feature.import_mesh", "Import Mesh", group="Features"),
    _c("feature.split_for_print", "Split for Printing", group="Features"),
    _c("feature.ref_plane", "Plane", group="Features"),
    _c("feature.ref_axis", "Axis", group="Features"),
    _c("feature.ref_point", "Point", group="Features"),
    _c("feature.coord_system", "Coordinate System", group="Features"),
    *PHASE4_COMMANDS,
    _c("feature.base_flange", "Base Flange", group="Sheet Metal"),
    _c("feature.edge_flange", "Edge Flange", group="Sheet Metal"),
    _c("feature.sketched_bend", "Sketched Bend", group="Sheet Metal"),
    _c("feature.sheet_metal", "Sheet Metal Parameters", group="Sheet Metal"),
    _c("feature.bend_table", "Load Bend Table", group="Sheet Metal"),
    _c("feature.flatten", "Flatten", group="Sheet Metal"),
    _c("file.export_flat", "Export Flat Pattern", group="Sheet Metal"),
    # Later sheet metal tools (D547): no default keys.
    _c("feature.hem", "Hem", group="Sheet Metal"),
    _c("feature.miter_flange", "Miter Flange", group="Sheet Metal"),
    _c("feature.jog", "Jog", group="Sheet Metal"),
    _c("feature.closed_corner", "Closed Corner", group="Sheet Metal"),
    _c("feature.break_corner", "Break Corner", group="Sheet Metal"),
    _c("feature.rip", "Rip", group="Sheet Metal"),
    _c("feature.gusset", "Gusset", group="Sheet Metal"),  # TR12 (D700)
    _c("feature.tab_slot", "Tab and Slot", group="Sheet Metal"),
    _c("feature.convert_sheet", "Convert to Sheet Metal", group="Sheet Metal"),
    _c("feature.insert_bends", "Insert Bends", group="Sheet Metal"),
    _c("feature.cross_break", "Cross Break", group="Sheet Metal"),
    _c("feature.unfold", "Unfold", group="Sheet Metal"),
    _c("feature.fold", "Fold", group="Sheet Metal"),
    _c("feature.form_tool", "Forming Tool", group="Sheet Metal"),
    _c("feature.gauge_table", "Load Gauge Table", group="Sheet Metal"),
    _c("feature.flat_marks", "Flat Marks", group="Sheet Metal"),
    _c("feature.stamp", "Stamp", group="Sheet Metal"),  # TR77 (D1816)
    _c("feature.bend_list", "Bend Table", group="Sheet Metal"),
    _c("feature.sheet_rules", "Sheet Metal Rules", group="Sheet Metal"),
    _c("feature.perforation", "Perforated Fold Line", group="Sheet Metal"),
    _c("feature.extend_wall", "Extend Wall", group="Sheet Metal"),
    _c("feature.sheet_corner_relief", "Corner Relief", group="Sheet Metal"),
    _c("feature.edit_bends", "Edit Bends", group="Sheet Metal"),
    _c("feature.sheet_tab", "Tab", group="Sheet Metal"),
    # Phase 2 print and evaluate tools (D350 to D357): no default keys, users can bind them.
    _c("file.export_dxf", "Export DXF", group="File"),
    _c("file.export_svg", "Export SVG", group="File"),
    _c("file.export_section", "Export Section and Outline", group="File"),  # TR300 (D1204)
    _c("file.export_bodies", "Export Bodies", group="File"),  # spec 2 section 20 item 13
    _c("print.open_slicer", "Open in Slicer", group="Print"),
    _c("print.lay_flat", "Lay Face Flat", group="Print"),
    _c("print.bed_chamfer", "Bed Edge Chamfer", group="Print"),  # TR177 (D779)
    _c("print.fix_overhangs", "Fix Overhangs", group="Print"),  # TR410 (D909)
    _c("print.height_changes", "Settings by Height", group="Print"),  # TR384 (D1208)
    _c("evaluate.layer_fit", "Layer Fit Check", group="Evaluate"),  # TR187 (D1209)
    _c("print.suggest_orientation", "Suggest Orientation", group="Print"),  # TR301 (D1210)
    _c("print.arrange", "Arrange on Bed", group="Print"),
    _c("evaluate.cups_islands", "Suction Cups and Islands", group="Evaluate"),  # TR409
    _c("print.coating", "Coating Allowance", group="Print"),  # TR307 (D1214)
    _c("print.fit_calibration", "Fit Calibration", group="Print"),  # TR358 (D2000)
    _c("print.keep_fit", "Keep Measured Fit", group="Print"),
    _c("print.clear_orientation", "Clear Print Orientation", group="Print"),
    _c("evaluate.build_volume", "Build Volume", group="Evaluate"),
    _c("evaluate.overhang", "Overhang Analysis", group="Evaluate"),
    _c("evaluate.wall_thickness", "Wall Thickness Analysis", group="Evaluate"),
    _c("evaluate.draft_analysis", "Draft Analysis", group="Evaluate"),
    _c("evaluate.print_estimate", "Print Estimate", group="Evaluate"),
    _c("evaluate.geometry_check", "Geometry Check", group="Evaluate"),
    # Node editor (PLAN Phase 7). Keys other than the editor's own apply inside it only.
    _c("graph.editor", "Node Editor", group="Graph"),
    _c("graph.add_node", "Add Node", "Shift+A", group="Graph"),
    _c("graph.delete", "Delete Nodes", "Backspace", group="Graph"),
    # Ctrl+C and Ctrl+V reach the node editor through Edit Copy and Paste (D685).
    _c("graph.copy", "Copy Nodes", group="Graph"),
    _c("graph.paste", "Paste Nodes", group="Graph"),
    _c("graph.group", "Group Nodes", "Ctrl+G", group="Graph"),
    _c("graph.ungroup", "Ungroup Nodes", "Ctrl+Shift+G", group="Graph"),
    _c("graph.comment", "Add Comment", group="Graph"),
    _c("graph.fit", "Fit Graph", group="Graph"),
    _c("graph.set_position", "Set Graph Position", group="Graph"),
    # Phase 4 deformation features (PHASE4_SPEC P4.9): no default keys.
    _c("feature.bend", "Bend", group="Features"),
    _c("feature.twist", "Twist", group="Features"),
    _c("feature.taper", "Taper", group="Features"),
    _c("feature.stretch", "Stretch", group="Features"),
    _c("feature.flow", "Flow Along Curve", group="Features"),
    _c("feature.deform_point", "Deform Point", group="Features"),  # TR67 (D2412)
    _c("feature.deform_curve", "Deform Curve to Curve", group="Features"),
    _c("feature.surface_push", "Surface Push", group="Features"),
    # Phase 4 equations, configurations and design tables (PHASE4_SPEC P4.10).
    _c("tools.equations", "Equations", group="Tools"),
    _c("tools.material", "Material", group="Tools"),  # TR78 (D803)
    _c("tools.properties", "Custom Properties", group="Tools"),  # TR82 (D810)
    _c("tools.configurations", "Configurations", group="Tools"),
    _c("tools.design_table", "Design Table", group="Tools"),
    _c("tools.expected_values", "Expected Values", group="Tools"),  # TR359 (D889)
    _c("tools.bodies_by_size", "Select Bodies by Size", group="Tools"),  # TR70 (D894)
    _c("tools.slice", "Slice Body", group="Tools"),  # TR151 (D1718)
    _c("tools.hole_table", "Hole Table", group="Tools"),  # TR316 (D924)
    _c("tools.named_items", "Named Items", group="Tools"),  # TR152 (D2105)
    _c("tools.insert_library", "Insert Library Feature", group="Tools"),  # TR72 (D2115)
    _c("tools.bodies_to_files", "Bodies to Part Files", group="Tools"),  # TR280 (D2421)
    _c("tools.part_notes", "Part Notes", group="Tools"),  # TR392 (D931)
    _c("tools.goal_seek", "Goal Seek and Sweep", group="Tools"),  # TR273 (D1020)
)
BY_ID: dict[str, CommandDef] = {c.id: c for c in COMMANDS}

#: Default search words (TOOL_SPEC T14.7.2): extra words the shortcut bar search
#: matches besides the command name. Plain English words only.
DEFAULT_WORDS: dict[str, str] = {
    "edit.delete": "remove erase",
    "edit.copy": "duplicate clipboard",
    "edit.paste": "duplicate clipboard",
    "edit.rebuild": "update regenerate",
    "view.fit": "zoom all whole",
    "view.normal_to": "face look square",
    "view.previous": "back undo view",
    "view.selector": "cube orientation",
    "view.orientation": "popup views saved split new view",
    "view.hide_show": "visibility body bodies",
    "view.isolate": "solo only body bodies alone",
    "view.show_hovered": "unhide body under cursor",
    "view.show_all_bodies": "unhide every body bodies reveal",
    "feature.extrude": "pull add material prism",
    "feature.extruded_cut": "remove material hole",
    "feature.revolve": "turn spin lathe",
    "feature.revolved_cut": "turn spin groove",
    "feature.helix": "coil spring thread spiral",
    "feature.projected_curve": "project wrap curve onto face",
    "feature.composite_curve": "join chain path curves",
    "feature.point_curve": "xyz table points file spline path through points",
    "feature.sketch3d": "3d sketch space path planes lines spline",
    "feature.pipe": "tube rod wire frame",
    "feature.curve_array": "pattern copy along path chain",
    "feature.contour": "section slice level lines",
    "evaluate.curvature_graph": "comb smoothness analysis",
    "evaluate.zebra": "reflection smoothness stripes surface join analysis",
    "evaluate.curvature_colors": "curvature map colour color radius gaussian mean faces",
    "evaluate.compare_bodies": "difference diff versus step changes volume",
    "evaluate.mass_properties": "weight mass inertia centre of gravity density volume area",
    "evaluate.interference": "clash overlap collision gap clearance print in place fit",
    "evaluate.cavities": "void hollow trapped resin powder drain cup volume capacity",
    "evaluate.change_test": "robust flex vary values sensitivity rebuild safe range",
    "evaluate.model_health": "advice best practice check tree untidy design review",
    "evaluate.repair_references": "missing reference lost face edge broken reselect fix",
    "evaluate.manufacturing": "dfm machining milling cnc sheet metal moulding process rules",
    "feature.import_mesh": "stl 3mf obj scan reference",
    "feature.import_step": "stp open model base body",
    "feature.transform_handles": "move rotate turn drag arrows rings gizmo triad body",
    "feature.split_for_print": "printer pieces divide pins dovetail build volume",
    "file.export_dxf": "laser cnc drawing flat face sketch outline",
    "file.export_svg": "laser vector drawing flat face sketch outline",
    "file.export_section": "laser engrave kerf slice shadow silhouette dxf svg layers",
    "file.export_bodies": "split pieces separate files stl 3mf each body",
    "print.open_slicer": "3d print printer send 3mf slice",
    "print.lay_flat": "orientation bed down face rotate print",
    "print.bed_chamfer": "elephant foot first layer bottom edge chamfer print",
    "print.suggest_orientation": "best orientation overhang support face down rank lay flat",
    "print.fit_calibration": "tolerance test print clearance gap calibrate holes pins",
    "print.keep_fit": "tolerance measured clearance gap calibrate printer profile",
    "print.coating": "paint powder anodise plating thickness allowance shrink holes",
    "evaluate.cups_islands": "resin trapped air suction hollow drain island support start",
    "print.arrange": "arrange pack bed layout spacing several bodies plate",
    "evaluate.layer_fit": "layer height line width wall thickness rounding slicer",
    "print.height_changes": "pause magnet nut insert colour color change layer height z",
    "feature.corner_relief": "dogbone t bone relief milling cnc inside corner tool",
    "feature.merge_faces": "join unify remove edge seam imported faces heal",
    "feature.fill_pattern": "grille vent perforate holes array weight reduction fill face",
    "feature.bounding_box": "stock size envelope extents box cylinder quote",
    "feature.sensor": "watch alert limit warning monitor volume mass",
    "feature.primitive": "box cylinder sphere cone torus wedge prism tube block ball",
    "print.clear_orientation": "orientation reset bed print as modelled",
    "evaluate.build_volume": "printer bed fit size check",
    "evaluate.overhang": "support bridge angle print steep colour",
    "evaluate.wall_thickness": "thin wall minimum print strength colour check",
    "evaluate.draft_analysis": "mould pull taper parting colour check",
    "evaluate.print_estimate": "volume weight mass material density filament grams",
    "evaluate.geometry_check": "validate invalid sliver tiny edge gap heal problems",
    "sketch.dimension": "measure size length",
    "sketch.corner_rectangle": "box square",
    "sketch.construction": "reference helper",
    "sketch.relations": "constraints",
    "sketch.fully_define": "auto dimension constrain all define",
    "sketch.check_sketch": "validate profile open gap contour problems",
    "sketch.repair_sketch": "fix heal gap overlap tiny duplicate dxf close",
    "sketch.insert_spline_point": "add point knot curve",
    "sketch.fit_spline": "convert curve smooth polyline",
    "sketch.simplify_spline": "reduce points smooth curve",
    "sketch.baseline_dimension": "datum stacked dimension",
    "sketch.ordinate_dimension": "datum coordinate dimension",
    "select.other": "behind hidden pick",
    "select.lasso": "free loop freehand drag select",
    "select.only_bodies": "filter priority solid body",
    "select.only_faces": "filter priority surface",
    "select.only_edges": "filter priority line",
    "select.paint": "brush drag faces select",
    "select.in_volume": "box cylinder sphere inside outside touching select",
    "ui.preferences": "settings options",
    "graph.editor": "nodes visual programming algorithm generative",
    "graph.add_node": "insert node search",
    "graph.set_position": "graph order tree place",
}


def search_words(cid: str, overrides: dict[str, str] | None = None) -> str:
    """The search words of a command: the user's, else the defaults."""
    if overrides is not None and cid in overrides:
        return overrides[cid]
    return DEFAULT_WORDS.get(cid, "")


def key_text(key: str) -> str:
    """Key text with letters in upper case ("ctrl+l" gives "Ctrl+L", T14.7.4)."""
    parts = key.split("+")
    out = []
    for part in parts:
        if len(part) == 1:
            out.append(part.upper())
        else:
            out.append(part[:1].upper() + part[1:])
    return "+".join(out)


def normalize(key: str) -> str:
    """Compare key text without caring about case or spaces."""
    return key.replace(" ", "").lower()


@dataclass
class ShortcutMap:
    """Shortcuts per command: the defaults with the user's changes on top."""

    overrides: dict[str, list[str]] = field(default_factory=dict)
    mac: bool = False

    def default(self, cid: str) -> list[str]:
        """The default shortcuts of ``cid`` on this platform."""
        cmd = BY_ID[cid]
        keys = cmd.mac if self.mac and cmd.mac is not None else cmd.keys
        return list(keys)

    def keys(self, cid: str) -> list[str]:
        """Current shortcuts of ``cid``."""
        if cid in self.overrides:
            return list(self.overrides[cid])
        return self.default(cid)

    def owners(self, key: str) -> list[str]:
        """Commands that currently use ``key``."""
        k = normalize(key)
        return [c.id for c in COMMANDS if any(normalize(x) == k for x in self.keys(c.id))]

    def set(self, cid: str, keys: list[str]) -> dict[str, str]:
        """Give ``cid`` these shortcuts. Other commands lose them.

        Returns the commands that lost a shortcut and the key they lost, so the
        editor can say which command loses it (SHORTCUTS.md 9.2).
        """
        lost: dict[str, str] = {}
        clean = [k for k in keys if k.strip()]
        for key in clean:
            for other in self.owners(key):
                if other != cid:
                    remaining = [x for x in self.keys(other) if normalize(x) != normalize(key)]
                    self.overrides[other] = remaining
                    lost[other] = key
        self.overrides[cid] = clean
        if self.overrides[cid] == self.default(cid):
            del self.overrides[cid]
        return lost

    def reset(self) -> None:
        """Go back to the default shortcuts."""
        self.overrides.clear()


# Gestures ---------------------------------------------------------------------------------

DIRECTIONS_4 = ("right", "up", "left", "down")
DIRECTIONS_8 = ("right", "up_right", "up", "up_left", "left", "down_left", "down", "down_right")
#: A right drag shorter than this (pixels) is a normal right click.
GESTURE_MIN_PX = 40.0

DEFAULT_GESTURES: dict[str, dict[str, str]] = {
    "part": {"up": "view.top", "left": "view.left", "right": "view.right", "down": "view.bottom"},
    "sketch": {
        "up": "sketch.dimension",
        "left": "sketch.line",
        "right": "sketch.circle",
        "down": "sketch.corner_rectangle",
    },
}


def gesture_direction(dx: float, dy: float, sectors: int = 4) -> str | None:
    """Direction of a drag in screen pixels (y down), or None when it is too short."""
    if math.hypot(dx, dy) < GESTURE_MIN_PX:
        return None
    names = DIRECTIONS_8 if sectors == 8 else DIRECTIONS_4
    angle = math.atan2(-dy, dx) % (2 * math.pi)
    step = 2 * math.pi / len(names)
    return names[round(angle / step) % len(names)]


@dataclass
class GestureMap:
    """Command for each direction, per context (part or sketch)."""

    mapping: dict[str, dict[str, str]] = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_GESTURES.items()}
    )
    sectors: int = 4

    def command(self, context: str, direction: str | None) -> str | None:
        """Command for a gesture, or None."""
        if direction is None:
            return None
        cid = self.mapping.get(context, {}).get(direction)
        return cid if cid in BY_ID else None


# Shortcut bar ---------------------------------------------------------------------------------

DEFAULT_BAR: dict[str, list[str]] = {
    "part": [
        "sketch.sketch",
        "feature.extrude",
        "feature.extruded_cut",
        "feature.revolve",
        "feature.revolved_cut",
        "view.normal_to",
        "view.fit",
        "view.iso",
        "view.transparency",
    ],
    "sketch": [
        "sketch.line",
        "sketch.centerline",
        "sketch.corner_rectangle",
        "sketch.center_rectangle",
        "sketch.circle",
        "sketch.center_arc",
        "sketch.tangent_arc",
        "sketch.three_point_arc",
        "sketch.point",
        "sketch.dimension",
        "sketch.construction",
        "sketch.relations",
        "sketch.exit",
    ],
}
