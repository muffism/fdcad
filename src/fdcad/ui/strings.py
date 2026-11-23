"""Every user facing string of the shell, in one place so translation can be added later
(PLAN section 8 item 14). Command labels use title case, messages sentence case.
"""

APP = "FDCAD"


def clause(reason: object) -> str:
    """An error from outside FDCAD as a clause to wrap in a message (D550).

    Operating system errors give their short text. A final full stop is dropped,
    so a template can add its own next step after the clause without "..".
    """
    text = ""
    if isinstance(reason, OSError) and reason.strerror:
        text = reason.strerror
    text = (text or str(reason)).strip().rstrip(".").strip()
    return text or type(reason).__name__


# Menus
MENU_FILE = "&File"
MENU_EDIT = "&Edit"
MENU_VIEW = "&View"
MENU_INSERT = "&Insert"
MENU_TOOLS = "&Tools"
MENU_HELP = "&Help"
MENU_WINDOW = "&Window"  # Mac only (TR376)
WINDOW_MINIMIZE = "Minimize"
WINDOW_ZOOM = "Zoom"
WINDOW_FRONT = "Bring All to Front"
MENU_RECENT = "Open &Recent"
MENU_EXPORT = "&Export"

# Commands
NEW = "&New Part..."
OPEN = "&Open..."
SAVE = "&Save"
SAVE_AS = "Save &As..."
CLOSE = "&Close"
CLOSE_TAB = "Close this part"
QUIT = "&Quit"
CLEAR_RECENT = "Clear Recent Files"
EXPORT_STEP = "STEP..."
EXPORT_STL = "STL..."
EXPORT_3MF = "3MF..."
UNDO = "&Undo"
REDO = "&Redo"
REBUILD = "Re&build"
ZOOM_TO_FIT = "Zoom to Fit"
VIEW_ISOMETRIC = "Isometric"
VIEW_FRONT = "Front"
VIEW_TOP = "Top"
VIEW_RIGHT = "Right"
PREFERENCES = "&Preferences..."
SKETCH = "Sketch"
EXTRUDED_BOSS = "Extruded Boss"
EXTRUDED_CUT = "Extruded Cut"
REVOLVED_BOSS = "Revolved Boss"
REVOLVED_CUT = "Revolved Cut"
RENAME = "Rename"
SUPPRESS = "Suppress"
UNSUPPRESS = "Unsuppress"
DELETE = "Delete"
ROLLBACK_HERE = "Roll Back to Here"
TREE_MOVE_UP = "Move Up"  # TR293 (D2209)
TREE_MOVE_DOWN = "Move Down"
ROLL_FORWARD = "Roll to End"
EDIT_FEATURE = "Edit Feature"
SHOW = "Show"
NORMAL_TO = "Normal To"
HIDE = "Hide"

# Command tabs: group captions and tooltips. A tooltip shows the bold command
# name, one sentence on what it does, and the shortcut when there is one.
GROUP_BOSS = "Add Material"
GROUP_CUT = "Remove Material"
GROUP_SKETCH = "Sketch"
GROUP_DRAW = "Draw"
GROUP_SKETCH_TOOLS = "Tools"
TOOLTIP = "<b>{name}</b><br>{text}"
TOOLTIP_SHORTCUT = "<br><span style='color:gray'>Shortcut: {keys}</span>"
TOOLTIP_TEXT = {
    "feature.extrude": "Extends a sketch in one or two directions to make a solid.",
    "feature.extruded_cut": "Removes material by extending a sketch through the part.",
    "feature.revolve": "Turns a sketch around a centerline to make a solid.",
    "feature.revolved_cut": "Removes material by turning a sketch around a centerline.",
    "sketch.sketch": "Starts a new sketch on a plane or flat face.",
    "sketch.exit": "Saves the sketch and goes back to the 3D view.",
    "sketch.discard": "Drops the changes made since the sketch was opened, after asking, "
    "and goes back to the 3D view.",
    "sketch.line": "Draws straight lines. Click to start each new segment.",
    "sketch.centerline": "Draws construction lines used as axes and for symmetry.",
    "sketch.corner_rectangle": "Draws a rectangle from two opposite corners.",
    "sketch.center_rectangle": "Draws a rectangle from its center and one corner.",
    "sketch.circle": "Draws a circle from its center and a point on the edge.",
    "sketch.center_arc": "Draws an arc from its center, a start point and an end point.",
    "sketch.tangent_arc": "Draws an arc that continues smoothly from the end of a line or arc.",
    "sketch.three_point_arc": "Draws an arc through a start point, an end point and a midpoint.",
    "sketch.point": "Places a sketch point, for example to mark a hole center.",
    "sketch.dimension": "Adds a size to the selected items. The size drives the sketch.",
    "sketch.construction": "Turns the selected items into construction geometry or back.",
    "sketch.relations": "Lists every relation in the sketch so you can find and delete them.",
    "sketch.select": "Ends the current sketch tool so you can pick and drag items.",
    "edit.rebuild": "Rebuilds the features that changed.",
    "edit.force_rebuild": "Rebuilds every feature from scratch, ignoring saved results.",
    "tools.stats": "Shows how long each feature took to rebuild.",
    "file.new": "Starts a new part.",
    "file.open": "Opens a part file.",
    "file.save": "Saves the active part.",
    "file.save_as": "Saves the active part under a new name, or a copy as STEP, STL or 3MF.",
    "file.close": "Closes the active part.",
    "edit.undo": "Takes back the last change.",
    "edit.redo": "Makes the change you took back again.",
    "edit.repeat": "Runs the last command again.",
    "edit.delete": "Deletes the selected feature.",
    "file.save_image": "Saves the 3D view as a PNG picture.",
    "edit.copy": "Copies the selected sketch, or feature with its sketch, or sketch entities.",
    "edit.paste": "Pastes a copied sketch or feature onto a plane or flat face.",
    "view.fit": "Zooms so the whole part fits in the view.",
    "view.zoom_area": "Zooms in on a box you drag in the view.",
    "view.zoom_in": "Zooms in one step.",
    "tree.collapse_all": "Closes every folder and feature in the feature tree.",
    "view.zoom_out": "Zooms out one step.",
    "view.orientation": "Opens a list of the standard views, saved views and split layouts.",
    "view.display_quality": "Sets how finely this part's curved faces are drawn.",
    "view.display_states": "Saves and shows named sets of hidden bodies, colours and modes.",
    "view.previous": "Goes back to the view before the last view change.",
    "view.normal_to": "Turns the view to look straight at the selected face or plane.",
    "view.iso": "Shows the part from an angle that shows three sides.",
    "view.dimetric": "Shows three sides, two of them alike and the top smaller.",
    "view.trimetric": "Shows three sides, each at its own angle.",
    "view.split_one": "Shows one view of the part.",
    "view.split_side": "Shows two views of the part side by side.",
    "view.split_stacked": "Shows two views of the part, one above the other.",
    "view.split_four": "Shows four views: Front, Top, Right and Isometric.",
    "view.all_dimensions": "Shows every sketch dimension and feature value on the model.",
    "view.temporary_axes": "Shows an axis through every round face, to pick or snap to.",
    "view.save_view": "Saves the current view under a name in the part file.",
    "view.shaded_edges": "Shows the part shaded, with its edges drawn.",
    "view.shaded": "Shows the part shaded, without edges.",
    "view.hidden_lines": "Shows only the edges you can see.",
    "view.hidden_lines_visible": "Shows the edges you can see, and hidden edges as dashed lines.",
    "view.wireframe": "Shows every edge, also the hidden ones.",
    "view.transparency": "Makes the part see through, or solid again.",
    "view.perspective": "Shows the part in perspective, or in the parallel view again.",
    "select.lasso": "Drag a free loop to select. Clockwise takes what is inside it.",
    "select.previous": "Picks again what was picked before the selection was cleared.",
    "view.mirror_image": "Shows a see through mirror image of the part about a plane.",
    "select.invert": "Picks every face, edge or vertex that is not picked now.",
    "select.all": "Picks every face, or every edge when an edge is picked.",
    "select.similar": "Picks the faces like the picked face: same kind and size, parallel, "
    "or same area.",
    "select.to_edges": "Picks the edges of the picked faces, with the picked edges.",
    "select.to_faces": "Picks the faces next to the picked edges and vertices, with the "
    "picked faces.",
    "select.to_bodies": "Picks every face of each body that holds a pick.",
    "select.save_set": "Keeps the picked items under a name, to pick them again later.",
    "file.open_view_only": "Opens a part to turn, zoom and measure without changing it. Click "
    "Edit on the bar above the view to change it.",
    "file.save_all": "Saves every open part that has unsaved changes.",
    "file.close_all": "Closes every open part, asking about unsaved changes first.",
    "file.revert": "Throws away the changes since the last save and opens the saved part again.",
    "edit.edit_by_rule": "Finds the features of one kind whose value passes a test, such as "
    "fillets under 2 mm, and sets a new value on all of them.",
    "tree.remove_history": "Turns the part into one plain body with no feature history, "
    "after asking. Used to share a simple part.",
    "tree.purge_unused": "Lists the sketches nothing uses, suppressed features and unused "
    "variables, and deletes the ones you tick.",
    "tree.delete_below_bar": "Deletes every feature below the rollback bar, after asking.",
    "view.home": "Turns the view to this part's Home direction and fits the part.",
    "help.tool": "Opens the user guide at the open panel's, the sketch tool's or the last "
    "command's section.",
    "view.set_view_as": "Makes the way you look at the part now its Front, another standard "
    "view, or Home. The part does not move.",
    "view.reset_views": "Puts the standard views and Home of this part back as they were.",
    "select.sets": "Lists the saved selection sets: pick one, make one by a rule, or combine two.",
    "evaluate.compare_bodies": "Compares two bodies, or a body and a STEP file.",
    "evaluate.mass_properties": "Shows mass, volume, area, centre of mass and inertia.",
    "evaluate.interference": "Finds bodies that overlap, touch or are closer than a gap.",
    "evaluate.cavities": "Finds closed voids that trap resin or powder, and measures cups.",
    "print.bed_chamfer": "Chamfers the edges on the bed so the first layers do not spread.",
    "print.fix_overhangs": "Chamfers the edges of flat faces that hang over thin air.",
    "evaluate.change_test": "Steps each value up and down to find which ones break the part.",
    "evaluate.model_health": "Advice on the tree: loose sketches, early fillets, unused cuts.",
    "evaluate.repair_references": "Lists lost picks with a match to use, or removes them.",
    "feature.bounding_box": "A box or cylinder around the part, with its sizes for stock.",
    "feature.sensor": "Watches a value and warns in the tree when it leaves your limits.",
    "feature.primitive": "A box, cylinder, sphere, cone or other solid from typed sizes.",
    "file.save_copy": "Writes the part to a new file; the open part keeps its name.",
    "file.export_configs": "Writes each chosen configuration to its own file in a folder.",
    "file.mirror_part": "Saves the opposite hand of the part as a new part file and opens it.",
    "file.batch_export": "Exports the part once for every combination of variable values.",
    "edit.pause_rebuilds": "Collects edits without rebuilding. Rebuild applies them.",
    "edit.rebuild_stay": "Applies the collected edits and keeps rebuilds paused.",
    "edit.discard_paused": "Undoes the edits made while rebuilds were paused.",
    "edit.continue_rebuild": "Rebuilds past every checkpoint once.",
    "sketch.insert_svg": "Reads lines, arcs and curves from an SVG file into the sketch.",
    "evaluate.undercut": "Colours faces by what a mould pulled along a direction can reach.",
    "evaluate.layer_preview": "Draws lines on the part at every layer of the printer profile, "
    "to judge small details against the layers.",
    "evaluate.edge_angles": "Colours sharp edges and edges that are nearly but not quite smooth.",
    "tools.expected_values": "Target results with a tolerance, checked after every rebuild.",
    "tools.bodies_by_size": "Selects, deletes or keeps the bodies smaller or larger than a "
    "size limit.",
    "tools.hole_table": "Lists every hole and thread with its size, depth and position.",
    "tools.named_items": "Lists the named faces and edges and picks each one in the view.",
    "tools.insert_library": "Inserts a saved library feature onto a plane or flat face.",
    "tools.bodies_to_files": "Saves each body to its own file: linked parts that follow this "
    "part, FDCAD parts, STEP, STL or 3MF.",
    "tools.part_notes": "Plain text notes kept in the part, such as how to drive it.",
    "tools.slice": "Cuts the part with parallel planes into section sketches in a folder.",
    "sketch.cut_away": "Hides the part in front of the sketch plane while sketching.",
    "sketch.hide_construction": "Hides or shows the open sketch's construction curves.",
    "sketch.show_construction": "Shows this sketch's construction lines and points in the part "
    "after it is closed, for later sketches and features to pick.",
    "file.save_template": "Saves this part's units, variables, colour and settings as a template.",
    "file.save_copy_open": "Writes the part to a new file and opens that file in a new tab.",
    "tools.material": "The part's material and density, for mass and print estimates.",
    "tools.properties": "Named values kept with the part: part number, revision, mass.",
    "evaluate.manufacturing": "Checks the part against the rules of a process, such as milling.",
    "evaluate.zebra": "Shows stripes reflected in the faces, to check that joins are smooth.",
    "ui.preferences": "Changes units, theme, shortcuts and other settings.",
}
GROUP_REBUILD = "Rebuild"
GROUP_DEFORM = "Deform"
GROUP_IMPORT = "Import"
GROUP_PRINT_FEATURES = "Print Features"
STANDARD_VIEWS = "Standard Views"
SAVED_VIEWS = "Saved Views"
DISPLAY_STYLE = "Display Style"
# View toolbar dropdowns say what they hold on hover (D1089).
STANDARD_VIEWS_TIP = "Look at the part from the front, top, a side or an angle."
DISPLAY_STYLE_TIP = "Draw the part shaded, with edges, as lines, or see through."
VISIBILITY = "Hide or Show Items"
VISIBILITY_TIP = (
    "Click to hide planes, axes, points, sketches, origins and dimensions at once, and "
    "again to show them. The arrow lists each kind to show or hide."
)
CORNER_OK_SKETCH = "Exits the sketch and keeps the changes."
CORNER_OK_FEATURE = "Accepts the feature."
CORNER_CANCEL_SKETCH = "Exits the sketch and discards the changes."
CORNER_CANCEL_FEATURE = "Closes the feature without changing the part."
ZOOM_AREA_HINT = "Drag a box around the area to zoom to."
UNIT_SELECTOR_TIP = "<b>Units</b><br>Units used to show and type sizes in this part."
UNIT_NAMES = {"mm": "Millimeters (mm)", "in": "Inches (in)"}

# Panels and tabs
TAB_FEATURES = "Features"
TAB_SKETCH = "Sketch"
TAB_EVALUATE = "Evaluate"
TAB_BODIES = "Bodies"
TAB_PRINT = "3D Print"
#: Command tab row: the show or hide button and its menu (D582).
TABS_BUTTON_TIP = "Show or hide tabs. Hold a tab and drag it to move it."
TABS_SHOW_ALL = "Show All Tabs"
TABS_RESET_ORDER = "Reset Tab Order"
TAB_TREE = "Feature Tree"
TAB_PROPERTIES = "Properties"
TAB_VARIABLES = "Variables"
ROLLBACK_BAR = "Rollback bar"
OK = "OK"
CANCEL = "Cancel"

# File dialog filters
FILTER_FDEF = "FDCAD parts (*.fdprt)"
FILTER_IGES = "IGES (*.igs *.iges)"  # TR369 (D989)
FILTER_BREP = "OpenCascade BREP (*.brep)"
FILTER_PLY = "PLY mesh (*.ply)"
FILTER_GLB = "glTF binary (*.glb)"
FILTER_OBJ = "Wavefront OBJ mesh (*.obj)"  # TR336 (D995)
FILTER_DXF3D = "3D DXF wireframe (*.dxf)"  # TR369 (D1010)
FILTER_PARTS_OPEN = "FDCAD parts (*.fdprt *.fdef)"
FILTER_STEP = "STEP files (*.step *.stp)"
FILTER_STL = "STL files (*.stl)"
FILTER_3MF = "3MF files (*.3mf)"

# Messages
READY = "Ready"
REBUILDING = "Rebuilding {name} ({index} of {total})"
REBUILT = "Rebuilt in {seconds:.2f} s"
#: The opened part is its saved solid, not rebuilt (D1106).
SHOWN_SAVED = (
    "Opened the saved shape without rebuilding. Sketches and planes appear after a "
    "rebuild: press Ctrl+B."
)
#: Autosave could not write its copy (audit D3 item 10, D724).
AUTOSAVE_FAILED = "Autosave failed: {reason}. Save the part now, and check the free disk space."
#: Save As onto a file another tab has open (audit D3 item 14, D723).
SAVE_AS_OPEN = "{name} is open in another tab. Close that tab first, or save under another name."
#: A rebuild stopped before the end (audit D3 item 4, D710).
REBUILD_STOPPED = (
    "Rebuild stopped: the part shows only the features built so far. Press Ctrl+B to rebuild it."
)
UNSAVED_TITLE = "Unsaved Changes"
UNSAVED = "Save changes to {name} before closing?"
OPEN_FAILED = "Could not open {name}: {reason}"
OPEN_FAILED_SYSTEM = (
    "Could not open {name}: {reason}. Check that the file exists and that you can read it."
)
#: What opening a part left out or changed (audit D3 item 21, D2678); {notes} are the
#: reader's sentences.
LOAD_WARNINGS_BAR = (
    "{name} opened, but parts of the file were damaged: {notes} Check the part, then "
    "save it to keep it this way, or open another copy of the file."
)
SAVE_AS_TITLE = "Save As"
FILE_EXISTS = "{name} already exists. Replace it?"
SAVE_FAILED = "Could not save {name}: {reason}. Choose another folder and try again."
#: For a part value FDCAD cannot write; the reason already says what to fix.
SAVE_REFUSED = "Could not save {name}: {reason}"
EXPORT_DONE = "Exported {name}"
EXPORT_FAILED = "Export failed: {reason}. Check the folder and file name, then export again."
EXPORT_REFUSED = "Export failed: {reason}"
NO_3D_VIEW = (
    "3D view is not available on this display. Update the graphics driver, then start FDCAD again."
)
EXPORT_WAIT = "The part is still rebuilding. Wait for the rebuild to finish, then export again."
EXPORT_STOPPED = (
    "The last rebuild was stopped, so the part is not complete. "
    "Press Ctrl+B to rebuild it, then export again."
)
EXPORT_ERRORS = (
    "Note: {n} feature{s} with errors {are} not in the file. "
    "Fix them and export again to include them."
)
EXPORT_ROLLED_BACK = (
    "Note: the part is rolled back, so the features below the bar are not in the file."
)
EXPORT_SIMPLIFIED = (  # TR347 (D1921)
    "Note: modelled threads are shown as cosmetic while editing, so they are not in the "
    "file. Use Force Rebuild first to export them modelled."
)
NOTHING_TO_EXPORT = "The part is empty. Add a feature before exporting."
EXPORT_REPLACE = "{name} already exists. Replace it?"
EXPORT_WAIT = "Finishing the export before FDCAD closes."
EXPORT_STILL_RUNNING = "The export is still being written. Wait for it to finish, then quit again."
EXPORT_MESH_ONLY = (
    "{name} is a reference mesh, so the part has no solid to export. "
    "Edit {name}, tick Convert to Solid, then export again."
)
RECOVERY_TITLE = "Recover Parts"
RECOVERY = (
    "FDCAD closed unexpectedly. {count} part(s) with unsaved changes can be recovered. "
    "Yes opens them, Discard deletes the copies, Cancel keeps them for the next start."
)
RECOVERY_NEWER = (
    "A recovered part's file was saved again after the autosave, so the copy opened "
    "without a name. Use Save As to keep it beside the newer file."
)
DELETE_WITH_CHILDREN = "{name} is used by {children}. Delete it anyway? They will show errors."
SELECT_SKETCH = "Select a sketch in the feature tree first."
SKETCH_FOR_FEATURE = "Sketch the profile, then exit the sketch to set up the feature."
NO_AXIS = (
    "The sketch has no centerline to revolve around. Add one in the sketch, or choose "
    "an origin axis or a reference axis in the Axis list."
)
VARIABLE_ERROR = "Variables: {reason}"
# Property panel
FIELD_OPERATION = "Operation"
FIELD_END_CONDITION = "End condition"
FIELD_DIRECTION = "Direction"
FIELD_DEPTH = "Depth"
FIELD_DEPTH2 = "Depth 2"
FIELD_ANGLE = "Angle"
FIELD_ANGLE2 = "Angle 2"
FIELD_REVERSE = "Reverse direction"
FIELD_SKETCH = "Sketch"
FIELD_AXIS = "Axis"
CHOICES = {
    "boss": "Boss",
    "cut": "Cut",
    "blind": "Blind",
    "through_all": "Through All",
    "mid_plane": "Mid Plane",
    "two_directions": "Two Directions",
    "one_direction": "One Direction",
}
FIELD_MERGE = "Merge result"
FIELD_AXIS_REVOLUTION = "Axis of revolution"
GROUP_FROM = "From"
GROUP_AXIS = "Axis of Revolution"
GROUP_DIRECTION1 = "Direction 1"
GROUP_DIRECTION2 = "Direction 2"
GROUP_THIN = "Thin Feature"
SKETCH_LINE = "Line {id}"
SKETCH_CENTERLINE = "Centerline {id}"
PANEL_TIPS = {
    "end_twist": "End twist: how far the profile turns from the start to the end. 0: no turn.",
    "end_scale": "End scale: how big the profile is at the end, as a factor. 1: the same.",
    "profile_offset": "Profile offset: grow the profile by this much on every side, or shrink "
    "it with a negative value. Use a fit variable to make mating parts from one sketch.",
    "ok": "OK: apply the feature and close the panel (Enter).",
    "cancel": "Cancel: close the panel without changes (Esc).",
    "sketch": "Sketch: the sketch whose closed profile this feature uses.",
    "from": "From: where the feature starts. It starts on the sketch plane.",
    "axis": (
        "Axis of revolution: the sketch line or straight part edge the profile turns around. "
        "Click a line or an edge in the view to choose it."
    ),
    "direction1": "Direction 1: how far the feature goes from the sketch.",
    "direction2": "Direction 2: also extend the feature the other way from the sketch.",
    "reverse": "Reverse direction: flip the feature to the other side of the sketch.",
    "end_condition": "End condition: how the feature ends in this direction.",
    "direction": "End condition: how the feature ends in this direction.",
    "depth": "Depth: distance from the sketch. Type a value, a unit or a formula.",
    "depth2": "Depth: distance in direction 2. Type a value, a unit or a formula.",
    "angle": "Angle: how far the profile turns. Type a value, a unit or a formula.",
    "angle2": "Angle: how far the profile turns in direction 2.",
    "merge": "Merge result: join this feature with the part. Untick to keep a separate body.",
}
FIX_ERRORS = "Fix the highlighted values, then press OK."
FEATURE_UNDONE = (
    "{name} is no longer in the part because of Undo. Press Cancel, then use Redo to get it back."
)
CHOOSE_SKETCH = "Choose a sketch."
CHOOSE_AXIS = (
    "Pick the axis of revolution: a line or centerline in the sketch, "
    "or a straight edge of the part."
)
AXIS_EDGE = "Edge of {feature}"
#: A round face whose axis is the revolve axis (a temporary axis, TR17, D712).
AXIS_FACE = "Axis of a round face of {feature}"
PREF_REDUCE_MOTION = "Reduce motion"
PREF_REDUCE_MOTION_TIP = (
    "Turn off animation. The view jumps to a new direction instead of turning, "
    "and menus open without effects."
)
MODEL_CURSOR = "X {x}  Y {y}  Z {z}"
AXIS_EDGE_NOT_STRAIGHT = (
    "Only a straight edge or a round face can be the axis. Click a straight edge, "
    "a cylinder, or pick an axis in the list."
)
AXIS_EDGE_TOO_LATE = (
    "{feature} cannot use an edge or face made by itself or a later feature. Click another one."
)
AXIS_CENTERLINE = "Centerline {id}"
AXIS_LINE = "Line {id}"

# Feature panel completion (WP10, TOOL_SPEC T5.1, T6.1)
START_CHOICES = {
    "sketch_plane": "Sketch Plane",
    "surface": "Surface/Face/Plane",
    "vertex": "Vertex",
    "offset": "Offset",
}
START_PICK_HINT = "Click a face, plane or vertex"
START_SKETCH_POINT = "Point {id} of {sketch}"
START_FACE = "Face of {feature}"
START_VERTEX = "Vertex of {feature}"
THE_PART = "the part"
START_PICK_FACE = "Pick a face of the part or a plane for From."
START_PICK_VERTEX = "Pick a vertex of the part or a sketch point for From."
START_PICK_NOT_ASKED = "From does not take a pick. Choose Surface/Face/Plane or Vertex first."
START_PICK_TOO_LATE = (
    "{feature} cannot start on geometry made by itself or a later feature. Pick another one."
)
FIELD_CUT_OUTSIDE = "Cut outside"
FIELD_FLIP_SIDE = "Flip side"  # TR157 (D1023)
FIELD_MERGE_ENDS = "Merge ends"  # TR272 (D1025)
FIELD_LINK_THICKNESS = "Link to thickness"
FIELD_NORMAL_CUT = "Normal cut"
PANEL_TIPS.update(
    {
        "from": "From: where the feature starts. Depth is measured from the start.",
        "start_condition": (
            "Start: the sketch plane, a face or plane, a vertex, or an offset from the sketch."
        ),
        "start_pick": "Start at: click a face, plane or vertex in the view, or choose one here.",
        "start_offset": "Offset: distance from the sketch plane to the start. Type a value.",
        "start_reverse": "Reverse direction: put the start on the other side of the sketch.",
        "end_condition2": "End condition: how the feature ends in direction 2.",
        "cut_outside": "Cut outside: remove the material outside the profile instead of inside.",
        "flip_side": "Flip side: with an open line as the sketch, cut the material on its "
        "other side.",
        "thin_merge_ends": "Merge ends: an open wall's ends carry on until they meet the part, "
        "and stop there.",
        "link_thickness": "The depth follows the sheet thickness: a cut goes exactly through "
        "the sheet and a boss is one sheet thick.",
        "normal_cut": "Cut square to the sheet, so the cut faces stand straight folded and flat.",
    }
)

# Phase 2 extrude additions (PHASE2_SPEC P2.1)
CHOICES.update(
    {
        "up_to_vertex": "Up to Vertex",
        "up_to_face": "Up to Face",
        "offset_from_face": "Offset from Face",
        "two_direction": "Two Direction",
    }
)
# More end conditions (TOOL_SPEC T16)
CHOICES.update(
    {
        "through_all_both": "Through All Both",
        "up_to_next": "Up to Next",
        "up_to_body": "Up to Body",
    }
)
END_BODY = "Body with a face of {feature}"
END_PICK_BODY = "Pick a face of the body to end at."
END_PICK_HINT = "Click a face, plane or vertex"
END_PICK_FACE = "Pick a face of the part or a plane for the end."
END_PICK_VERTEX = "Pick a vertex of the part or a sketch point for the end."
END_PICK_TOO_LATE = (
    "{feature} cannot end on geometry made by itself or a later feature. Pick another one."
)
FIELD_END_REVERSE_OFFSET = "Reverse offset"
FIELD_TRANSLATE_SURFACE = "Translate surface"
FIELD_DRAFT = "Draft"
FIELD_DRAFT_OUTWARD = "Draft outward"
FIELD_THIN_TYPE = "Type"
FIELD_CAP_ENDS = "Cap ends"
PANEL_TIPS.update(
    {
        "end_pick": "End at: click a face, plane or vertex in the view, or choose one here.",
        "end_offset": "Offset: distance between the end and the face. Type a value.",
        "end_offset2": "Offset: distance between the end and the face. Type a value.",
        "end_offset_angle": "Offset: angle the end stops short of the face. Type a value.",
        "end_offset_reverse": "Reverse offset: put the end beyond the face instead of before it.",
        "end_translate": (
            "Translate surface: move the face along the direction instead of offsetting it."
        ),
        "draft": "Draft: lean the side faces of this direction by an angle.",
        "draft_angle": "Draft angle: measured from the extrude direction. Type a value.",
        "draft_angle2": "Draft angle: measured from the extrude direction. Type a value.",
        "draft_outward": "Draft outward: the side faces lean out instead of in.",
        "thin": "Thin Feature: make a wall around the sketch curves. Open sketches need it.",
        "thin_type": "Type: the wall on one side, centred on the curves, or two thicknesses.",
        "thin_thickness": "Thickness: wall thickness. Type a value, a unit or a formula.",
        "thin_thickness2": "Thickness 2: wall thickness on the other side.",
        "thin_reverse": "Reverse direction: put the wall on the other side of the curves.",
        "thin_cap": "Cap ends: close both ends of a closed thin wall with a lid.",
        "thin_cap_thickness": "Cap thickness: thickness of each lid.",
        "thin_fillet": "Auto fillet corners: round the corners of a wall made from an open "
        "sketch. The outside radius is the inside radius plus the wall.",
        "thin_fillet_radius": "Corner radius: the inside radius of each rounded corner.",
    }
)

# Phase 2 feature panels (PHASE2_SPEC P2.2 to P2.7)
GROUP_MODIFY = "Modify"
TOOLTIP_TEXT.update(
    {
        "feature.fillet": "Rounds the picked edges with a constant or varying radius.",
        "feature.chamfer": "Bevels the picked edges or a corner with a flat face.",
        "feature.shell": "Hollows the part, leaving walls of a set thickness.",
        "feature.draft": "Tilts faces by an angle from a neutral plane, for moulding.",
        "feature.sweep": "Moves a profile along a path to make a solid.",
        "feature.swept_cut": "Removes material by moving a profile along a path.",
        "feature.loft": "Joins two or more profiles with a smooth solid.",
        "feature.lofted_cut": "Removes material between two or more profiles.",
    }
)
PICK_LABELS = {
    "edge": "Edge of {feature}",
    "face": "Face of {feature}",
    "vertex": "Vertex of {feature}",
    "loop": "Edge loop of {feature}",  # TR138 (D1908)
}
PICK_REMOVE = "Remove"
PICK_REMOVE_TIP = "Remove the selected items from the list."
PICK_UP = "Move Up"
PICK_DOWN = "Move Down"
PICK_UP_TIP = "Move the selected item up the list."
PICK_DOWN_TIP = "Move the selected item down the list."
PICK_LOST = "Lost: {item}. Select it and pick the new item, or remove it."
PICK_CLEAR_GONE = "Clear All Missing"
PICK_CLEAR_GONE_TIP = "Removes every lost item from the list."
PICK_TOO_LATE = "{feature} cannot use geometry made by itself or a later feature. Pick another one."
PICK_EDGES_OR_FACES = "Pick edges or faces of the part."
PICK_FACES = "Pick faces of the part."
PICK_ADD_FEATURE = "Add Feature"
PREVIEW_MODES = {"full": "Full preview", "partial": "Partial preview", "none": "No preview"}
SET_ALL = "Set All"
GROUP_FILLET_TYPE = "Fillet Type"
FILLET_TYPES = {"constant": "Constant Size", "variable": "Variable Size"}
GROUP_ITEMS_FILLET = "Items to Fillet"
FILLET_PICK_HINT = "Click edges or faces in the view. A face adds all its edges."
GROUP_FILLET_PARAMS = "Fillet Parameters"
FIELD_MULTIPLE_RADIUS = "Multiple radius"
GROUP_VARIABLE = "Variable Radii"
TRANSITIONS = {"smooth": "Smooth transition", "straight": "Straight transition"}
EDGE_RADIUS = "Edge {k}"
EDGE_START = "Edge {k} start"
EDGE_END = "Edge {k} end"
EDGE_POINT = "Edge {k} point {j}"
FILLET_NEEDS_ITEMS = "Pick edges, faces or features to fillet."
PANEL_TIPS.update(
    {
        "fillet_type": "Fillet type: one radius, or a radius that changes along each edge.",
        "fillet_items": "Items to fillet: click edges or faces in the view. Remove takes them out.",
        "item_feature": "Add every edge of an earlier feature.",
        "preview_mode": (
            "Preview: Full shows the finished part. Partial draws only the outline "
            "of the new faces. None is fastest."
        ),
        "radius": "Radius: size of the round. Type a value, a unit or a formula.",
        "multiple_radius": "Multiple radius: give each picked edge its own radius.",
        "variable": "Radius at each end and control point of the edge.",
        "control_points": "Control points: evenly spaced points along each edge with a radius.",
        "transition": "Transition: how the radius changes between points.",
        "set_all": "Copy the radius above to every point.",
    }
)

# Chamfer panel (PHASE2_SPEC P2.5)
GROUP_CHAMFER_TYPE = "Chamfer Type"
CHAMFER_TYPES = {
    "angle_distance": "Angle Distance",
    "distance_distance": "Distance Distance",
    "vertex": "Vertex",
}
CHAMFER_METHODS = {"symmetric": "Symmetric", "asymmetric": "Asymmetric"}
GROUP_ITEMS_CHAMFER = "Items to Chamfer"
GROUP_CHAMFER_PARAMS = "Chamfer Parameters"
CHAMFER_PICK_HINT = "Click edges or faces in the view. A face adds all its edges."
CHAMFER_VERTEX_HINT = "Click a corner where three straight edges meet."
CHAMFER_NEEDS_ITEMS = "Pick edges or faces to chamfer."
CHAMFER_NEEDS_VERTEX = "Pick a vertex to chamfer."
PICK_VERTEX = "Pick a vertex of the part."
FIELD_FLIP = "Flip direction"
FIELD_EQUAL_DISTANCE = "Equal distance"
PANEL_TIPS.update(
    {
        "chamfer_type": "Chamfer type: an angle and a distance, two distances, or a corner.",
        "chamfer_items": "Items to chamfer: click edges, faces or a vertex in the view.",
        "chamfer_method": "Symmetric: one distance on both faces. Asymmetric: two distances.",
        "flip": "Flip direction: measure the first distance on the other face of each edge.",
        "distance": "Distance: size of the chamfer. Type a value, a unit or a formula.",
        "distance2": "Distance 2: the second distance.",
        "distance3": "Distance 3: the distance along the third edge at the corner.",
        "chamfer_angle": "Angle: measured from the face the distance is on.",
        "equal": "Equal distance: one distance along all three edges at the corner.",
    }
)

# Fillet and chamfer options (round 9t, DECISIONS D518 to D520)
FILLET_TYPES.update({"face": "Face", "full_round": "Full Round"})
CHAMFER_TYPES.update({"offset_face": "Offset Face", "face_face": "Face to Face"})
CHAMFER_METHODS.update({"width": "Width"})
GROUP_FACE_SETS = "Face Sets"
FACE_SET_1 = "Face Set 1"
FACE_SET_2 = "Face Set 2"
SIDE_SET_1 = "Side Face Set 1"
CENTRE_SET = "Centre Face Set"
SIDE_SET_2 = "Side Face Set 2"
FILLET_NEEDS_FACE_SETS = "Pick faces for Face Set 1 and Face Set 2."
FILLET_NEEDS_FULL_ROUND = "Pick a side face, the centre face and the other side face."
CHAMFER_NEEDS_FACE_SETS = "Pick faces for Face Set 1 and Face Set 2."
FULL_ROUND_HINT = "The radius is half the distance between the two side faces."
ASSISTANT_WHOLE_PART = "Whole Part"
ASSISTANT_CONVEX = "Add Convex Edges"
ASSISTANT_CONCAVE = "Add Concave Edges"
GROUP_PARTIAL = "Partial Edges"
# Tabs of a long panel (Fillet, Chamfer), so it stays as narrow as the tree (D2790).
PANEL_TAB_MAIN = "Main"
PANEL_TAB_MAIN_TIP = "What to round or bevel, and its size."
PANEL_TAB_MORE = "More"
PANEL_TAB_MORE_TIP = "Ways to add many edges at once, partial edges and limits."
PANEL_TAB_FAVOURITES = "Favourites"
PANEL_TAB_FAVOURITES_TIP = "Save these settings under a name, or use saved ones."
GROUP_ADD_EDGES = "Add Edges"
PARTIAL_KINDS = {"distance": "Distance", "percent": "Percent", "reference": "Reference"}
AUTO_EDGE_LABELS = {
    "convex": "Convex edges of {feature}",
    "concave": "Concave edges of {feature}",
}
PANEL_TIPS.update(
    {
        "face_sets": "Face sets: click faces in the view. They go to the set chosen above.",
        "face_set_target": "Pick into: the face set that takes the next faces you click.",
        "assistant": (
            "Fillet assistant: add every convex or concave edge of the whole part or of one "
            "feature. The edges are found again when the part changes."
        ),
        "assistant_scope": "Where the assistant looks: the whole part or one earlier feature.",
        "width": "Width: the width of the chamfer face. Type a value, a unit or a formula.",
        "partial": (
            "Partial edges: round only part of each edge, from a start to an end measured "
            "along the edge as a distance or a percent of its length."
        ),
        "partial_flip": "Flip direction: measure the start and end from the other end.",
        "partial_start": "Start: where the round begins along each edge.",
        "partial_end": "End: where the round stops along each edge.",
        "fillet_type": (
            "Fillet type: one radius, a radius that changes along each edge, a round "
            "between two face sets, or a full round over the face between two sides."
        ),
        "chamfer_type": (
            "Chamfer type: an angle and a distance, two distances, a corner, offsets "
            "square to the faces, or the edges between two face sets."
        ),
    }
)

# Shell panel (PHASE2_SPEC P2.6)
GROUP_PARAMETERS = "Parameters"
GROUP_MULTI_THICKNESS = "Multi Thickness"
GROUP_BODY = "Body to Shell"
FIELD_FACES_TO_REMOVE = "Faces to remove"
FIELD_SHELL_OUTWARD = "Shell outward"
FIELD_SHOW_PREVIEW = "Show preview"
FACE_THICKNESS = "Face {k}"
SHELL_NEEDS_BODY = "The part has several bodies. Pick a face of the body to shell."
PANEL_TIPS.update(
    {
        "shell_thickness": "Thickness: wall thickness. Type a value, a unit or a formula.",
        "shell_faces": "Faces to remove: click faces in the view. None gives a closed hollow part.",
        "shell_outward": "Shell outward: the wall grows outside the part instead of inside.",
        "show_preview": "Show preview: build the preview while you edit.",
        "multi": "Multi thickness: click faces that need their own thickness, then type it.",
        "shell_body": "Body to shell: click a face of the body to shell.",
    }
)

# Draft panel (PHASE2_SPEC P2.7)
GROUP_DRAFT_ANGLE = "Draft Angle"
GROUP_NEUTRAL = "Neutral Plane"
GROUP_FACES_TO_DRAFT = "Faces to Draft"
NEUTRAL_HINT = "Choose a plane or click a flat face"
PICK_NEUTRAL = "Pick Neutral Face"
PROPAGATIONS = {
    "none": "None",
    "tangent": "Along tangent",
    "all": "All faces",
    "inner": "Inner faces",
    "outer": "Outer faces",
}
FIELD_SHOW_CHANGED = "Show changed faces"
DRAFT_NEEDS_NEUTRAL = "Choose a neutral plane or click a flat face."
DRAFT_NEEDS_FACES = "Pick faces to draft, or choose All, Inner or Outer faces."
PANEL_TIPS.update(
    {
        "draft_angle_main": "Draft angle: measured from the pull direction. Type a value.",
        "neutral": "Neutral plane: faces turn about where they meet it. Its normal is the pull.",
        "draft_reverse": "Reverse direction: flip the pull, so the faces tilt the other way.",
        "pick_neutral": "Pick Neutral Face: the next flat face clicked becomes the neutral plane.",
        "draft_faces": "Faces to draft: click faces in the view.",
        "propagation": "Propagation: also draft faces joined smoothly, all side faces, "
        "only the inside ones (holes) or only the outside ones.",
        "show_changed": "Show changed faces: the preview shows only the drafted faces. "
        "Untick to see the whole part.",
    }
)

# Sweep and loft panels (PHASE2_SPEC P2.2, P2.3)
GROUP_PROFILE_PATH = "Profile and Path"
GROUP_OPTIONS = "Options"
GROUP_PROFILES = "Profiles"
GROUP_START_END = "Start and End Constraints"
PROFILE_TYPES = {
    "sketch": "Sketch profile",
    "circular": "Circular profile",
    "face": "Face profile",  # TR138 (D1516)
    "body": "Tool body",  # TR138 item 3 (D2405)
}
SWEEP_TOOL_BODY_TIP = (
    "Click a face of the body to move along the path, such as a cutter. Place it at one end "
    "of the path; it does not turn as it moves."
)
SWEEP_GROUND_ENDS = "Ground ends"  # TR162 item 2 (D2408)
SWEEP_GROUND_ENDS_TIP = (
    "Cut the sweep flat at both ends of the path, square to the helix axis, so a spring "
    "stands square."
)
SWEEP_NEEDS_TOOL_BODY = "Click a face of the tool body to move along the path."
SWEEP_PROFILE_FACE_TIP = "Click a flat face of the part to sweep, holes included."
SWEEP_NEEDS_PROFILE_FACE = "Click a flat face for the profile, or choose a sketch profile."
ORIENTATIONS = {
    "follow_path": "Follow Path",
    "keep_normal": "Keep Normal Constant",
    "curvature": "Follow Curvature",  # TR56 (D1504)
    "face": "Normal to Face",  # TR396 (D1514)
    "second_path": "Follow Second Path",
}
SWEEP_ORIENT_FACE_TIP = (
    "Click the face under the path: the section keeps its up direction on the face's normal."
)
SWEEP_X_PATH_TIP = "The second path: the section's X axis points at it all along the path."
SWEEP_NEEDS_ORIENT_FACE = "Click the face under the path, or choose another orientation."
SWEEP_NEEDS_X_PATH = "Choose the second path, or choose another orientation."
SWEEP_CORNERS = {"smooth": "Smooth", "mitre": "Mitre", "round": "Round"}  # TR137 (D1515)
SWEEP_CORNERS_LABEL = "Corners"
SWEEP_TANGENCIES = {"none": "None", "path_tangent": "Path Tangent"}  # TR56 (D1905)
SWEEP_TANGENCY_LABEL = "Start tangency"
SWEEP_TANGENCY_TIP = (
    "Path Tangent turns the profile square to the path where it starts, so a path that "
    "leaves the sketch plane at a slant still gives a full size section. None sweeps "
    "the profile as drawn."
)
SWEEP_MERGE_FACES = "Merge tangent faces"
SWEEP_DIRECTIONS = {"forward": "Along the Path", "backward": "Against the Path", "both": "Both"}
SWEEP_DIRECTION_LABEL = "Direction"  # TR137 (D1906)
SWEEP_DIRECTION_TIP = (
    "When the profile sits part way along the path: sweep along the path, against it, "
    "or both ways. A profile at an end of the path sweeps along it."
)
SHOW_SECTION_TIP = (  # TR139 (D1909)
    "Show section: step through the sections from 1 (the start) to 11 (the end) to find "
    "where the shape goes wrong. It is drawn in the view. 0 shows none."
)
SECTION_VALUES_LABEL = "Section values"  # TR396 (D1910)
SECTION_VALUES_TIP = (
    "Profile dimensions that change along the path, as formulas of t, which runs from 0 "
    "at the start to 1 at the end: d1 = 10 + 10 * t. Separate several with semicolons."
)
GROUP_SECTIONS = "More Profiles"  # TR137 (D1907)
SECTIONS_TIP = (
    "Sketches further along the path that the section changes into, smoothly from one "
    "to the next. Each needs one closed outline, and the path must pass through it."
)
SWEEP_TWIST2_TIP = "The twist of the side swept against the path, from the profile."
SWEEP_MERGE_FACES_TIP = (
    "On a smooth path made of several pieces, each profile edge makes one side face "
    "instead of one per piece."
)
SWEEP_CORNERS_TIP = (
    "How the section passes a sharp corner of the path: Smooth lets the section turn, "
    "Mitre meets in a sharp edge, Round rounds the outside of the corner."
)
TWISTS = {
    "none": "None",
    "minimum": "Minimum Twist",
    "angle": "Specify Twist Angle",
    "turns": "Number of Turns",  # TR56 (D1504)
    "direction": "Specify Direction Vector",
}
FIELD_PATH_EDGES = "Path edges (instead of a sketch)"
DIRECTION_HINT = "Choose a plane or click a face or edge"
SWEEP_NEEDS_PROFILE = "Choose the profile sketch."
SWEEP_NEEDS_PATH = "Choose the path sketch, or click edges of the part for the path."
SWEEP_NEEDS_DIRECTION = "Choose a plane, or click a flat face or straight edge for the direction."
SWEEP_PICK_EDGES = "Click edges of the part for the path."
LOFT_NEEDS_PROFILES = "Add at least two profiles."
LOFT_ADD = "Add Profile"
ADD_LOFT_SECTION = "Add Loft Section"  # TR136 item 3 (D2404)
BREAK_BODY_LINK = "Break Link"  # TR154 (D2417)
MOVE_PART_ORIGIN = "Move Part Origin"  # TR343 (D2419)
BODIES_FILES = "Bodies to Part Files"  # TR280 (D2421)
BODIES_FILES_PROMPT = "Choose how each body is saved."
BODIES_FILES_NONE = "Build a body first, then save the bodies to files."
BODIES_FILES_SAVE_FIRST = "Save this part first, so the linked parts can find it."
BODIES_FILES_DONE = "Saved {count} files to {folder}."
PART_ORIGIN_PROMPT = "Choose where the part origin and its main planes go."
PART_ORIGIN_CHOICES = {
    "box": "To the box centre of the bodies",
    "mass": "To the centre of the bodies' volume",
    "selection": "To the selected vertex or face",
    "reset": "Back to the model origin",
}
PART_ORIGIN_NOTHING = "Select a vertex or face first, or build a body."
BREAK_BODY_LINK_UNDO = "Break Link of {name}"
LOFT_SECTION_PROMPT = "Enter where the section goes: 1.5 is halfway between profiles 1 and 2."
LOFT_SECTION_UNDO = "Add Loft Section to {name}"
LOFT_CONNECTORS = "Connectors"  # TR136 item 1 (D2403)
LOFT_CONNECTORS_TIP = (
    "More connectors for the selected profile: vertex numbers such as 3, 6, counted like the "
    "connection point. Every profile needs as many, and the loft joins them in order."
)
LOFT_RESET_CONNECTORS = "Reset"
LOFT_RESET_TIP = "Clear the connection point and connectors of every profile."
CONSTRAINTS = {
    "default": "Default",
    "none": "None",
    "normal": "Normal to Profile",
    "direction": "Direction Vector",
    "tangent": "Tangent to Faces",  # TR136 (D1924): a face profile's neighbours
    "curvature": "Curvature to Faces",
}
CHOICES_DEFAULT = "Default"
LOFT_PICK_FACES = (
    "Click flat faces of the part, or add sketches from the list. A vertex can be the first or "
    "last profile."
)
FIELD_START = "Start"
FIELD_END = "End"
FIELD_CLOSE_LOFT = "Close loft"
PANEL_TIPS.update(
    {
        "sweep_profile": "Profile: the closed sketch that moves along the path.",
        "profile_type": "Profile: a sketch, or a circle of the diameter below (a round rod).",
        "diameter": "Diameter: of the round profile. Type a value, a unit or a formula.",
        "sweep_path": "Path: a sketch whose curves join end to end, starting on the profile plane.",
        "path_edges": "Path edges: click joined edges of the part to use them as the path.",
        "orientation": "Follow Path keeps the section's angle to the path; Keep Normal Constant "
        "keeps it parallel to the start; Follow Curvature turns it with the path's bend, as "
        "along a helix.",
        "twist": "Twist: how the section turns about the path.",
        "twist_angle": "Twist angle: how far the section turns from start to end.",
        "twist_angle2": "The twist of the side swept against the path, from the profile.",
        "twist_turns2": "The turns of the side swept against the path, from the profile.",
        "twist_turns": "Turns: how many times the section turns from start to end. A closed "
        "path needs a whole number.",
        "twist_direction": "Direction: the section's up direction follows this plane's normal, "
        "face normal or edge.",
        "loft_profiles": "Profiles: sketches in the order they are joined. Move Up and Move "
        "Down change the order.",
        "loft_add": "Add the chosen sketch as the next profile.",
        "constraint": "How the loft leaves the first profile or reaches the last one.",
        "tangent_length": "Tangent length: how far the start or end direction reaches.",
        "close_loft": "Close loft: join the last profile back to the first.",
        "connect": "Connection point: the corner where the selected profile starts. "
        "Change it to untwist the loft.",
    }
)

# Sketcher
EDIT_SKETCH = "Edit Sketch"
EDIT_SKETCH_PLANE = "Edit Sketch Plane"
SKETCH_PLANE_PICK = "Plane or face"
SKETCH_PLANE_HINT = "Select a plane or flat face in the view or the tree, then click OK."
SKETCH_PLANE_FACE = "Face of the part"
SKETCH_PLANE_NONE = "Select a sketch in the feature tree first, then use Edit Sketch Plane."
SKETCH_PLANE_LATER = (
    "{name} cannot go there: the plane or face comes after it in the feature tree. "
    "Pick a plane or a face made before {name}."
)
SKETCH_TOOLS = {
    "line": "Line",
    "centerline": "Centerline",
    "corner_rectangle": "Corner Rectangle",
    "center_rectangle": "Center Rectangle",
    "circle": "Circle",
    "center_arc": "Centerpoint Arc",
    "tangent_arc": "Tangent Arc",
    "three_point_arc": "3 Point Arc",
    "point": "Point",
    "dimension": "Smart Dimension",
}
CONSTRUCTION = "Construction Geometry"
EXIT_SKETCH = "Exit Sketch"
EXIT_SKETCH_TIP = "Exit the sketch and keep the changes"
DISCARD_MARK = "✕"
DISCARD_TIP = "Exit the sketch and discard the changes"
SKETCH_TOOL_HINT = "{tool}: click to place. Right click or Escape to stop."
DIMENSION_HINT = "Smart Dimension: click one or two items, then click where the dimension goes."
DIMENSION_MADE_REFERENCE = (
    "The dimension would over define the sketch, so it was added as a reference dimension."
)
TOOL_OPTIONS = "Options"
FOR_CONSTRUCTION = "For construction"
LINE_ORIENTATION = "Orientation"
LINE_ORIENTATIONS = {
    "as_drawn": "As drawn",
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "angle": "Angle",
}
LINE_ANGLE = "Angle"
LINE_ANGLE_TIP = "The angle of new lines from the sketch X axis, for example 30deg."
TOOL_HINTS = {
    "line": "Move back onto the end point and away again to draw a tangent arc.",
    "corner_rectangle": "Hold Shift while placing the second corner for a square.",
    "center_rectangle": "Hold Shift while placing the corner for a square.",
    "tangent_arc": (
        "Leave the end point along the curve for a tangent arc, or sideways for a normal arc. "
        "Go back to the end point to choose again."
    ),
    "three_point_arc": "Click the start and the end, then move to set the bulge and click.",
}
SHAPE_VALUES = "Parameters"
SHAPE_VALUE_TIP = (
    "Type a value or an expression and press Enter. Relations and dimensions are kept."
)
SHAPE_FIELDS = {
    "x": "X",
    "y": "Y",
    "length": "Length",
    "angle": "Angle",
    "cx": "Center X",
    "cy": "Center Y",
    "radius": "Radius",
    "width": "Width",
    "height": "Height",
}
SHAPE_VALUE_POSITIVE = "A size must be greater than zero. Type a positive value."
SHAPE_VALUE_HELD = (
    "This value is held by relations or dimensions, so nothing moved. "
    "Change or delete the dimension or relation that sets it."
)
OVER_DEFINE_QUESTION = "This dimension over defines the sketch. Make it a reference dimension?"
MAKE_REFERENCE = "Make Reference"
KEEP_DRIVING = "Keep Driving"
DIMENSION_PANEL = "Dimension"
DIMENSION_PANEL_HINT = "Pick one or two items, then click where the dimension goes."
DIMENSION_VALUE = "Value"
DIMENSION_VALUE_TIP = (
    "Type a value or an expression starting with =. Press Enter to apply. "
    "Reference dimensions only measure, so their value cannot be typed."
)
DIMENSION_DRIVING = "Driving"
DIMENSION_REFERENCE = "Reference"
DIMENSION_DRIVING_TIP = "A driving dimension sets the size of the geometry."
DIMENSION_REFERENCE_TIP = "A reference dimension only measures the geometry. It shows in grey."
DIMENSION_STAYS_REFERENCE = (
    "The dimension stays a reference dimension: driving it would over define the sketch. "
    "Delete a relation or dimension first."
)
DIMENSION_TYPES = {
    "distance": "Distance",
    "horizontal_distance": "Horizontal Distance",
    "vertical_distance": "Vertical Distance",
    "angle": "Angle",
    "radius": "Radius",
    "diameter": "Diameter",
    "doubled_distance": "Doubled Distance",
    "arc_length": "Arc Length",
    "path_length": "Path Length",  # TR45 (D1307)
}
DIMENSION_RESET_LABEL = "Place Text Automatically"
DIMENSION_RESET_LABEL_TIP = "Put the dimension text back where FDCAD places it."
DIMENSION_NOT_POSSIBLE = "These items cannot be dimensioned together. Pick other items."
DIMENSION_POSITIVE = "A size must be greater than zero. Type a positive value."
DIMENSION_ANGLE_RANGE = (
    "An angle between two lines must be more than 0 and less than 180 degrees. "
    "Type an angle in that range."
)
VALUE_OK = "\u2713"
VALUE_OK_TIP = "Keep the value (Enter)"
VALUE_CANCEL = "\u2715"
VALUE_CANCEL_TIP = "Cancel (Escape)"
VALUE_REBUILD = "\u21bb"
VALUE_REBUILD_TIP = "Apply the value and keep editing"
VALUE_STEP_TIP = (
    "Spin step. The wheel and the up and down arrows change the value by this step. "
    "Hold Ctrl for ten steps or Alt for a tenth."
)
SELECT_PLANE = "Select a plane or flat face, or a plane in the tree. Press Escape to cancel."
SKETCH_STATUS = {
    "under": "Under defined: {dof} degrees of freedom left",
    "full": "Fully defined",
    "over": "Over defined: {message}",
    # TR38 (D1301): states shown by the sketch editor beside the three above.
    "dangling": "Dangling: {message} Click here to open the problem list.",
    "invalid": "Invalid geometry: click here to open the problem list.",
    "no_solution": "No solution: click here to open the problem list.",
}
#: Skipping automatic relations for one click (TR231, D1309).
SKIP_RELATIONS_ON = (
    "Automatic relations are skipped for the next click. Press Tab again to keep them."
)
SKIP_RELATIONS_OFF = "Automatic relations are back on for the next click."
#: Path Length and Chamfer dimensions (TR45, D1307).
PATH_LENGTH = "Path Length Dimension"
CHAMFER_DIMENSION = "Chamfer Dimension"
CHAMFER_ANGLE = "Length and Angle"
CHAMFER_LENGTHS = "Two Lengths"
#: Limit dimensions (TR342, D1311).
DIM_LIMIT = "Limit"
DIM_LIMITS = {"": "Exact Value", "min": "Minimum", "max": "Maximum"}
#: Angles to an axis through a line end (TR111, D1312).
ANGLE_TO_HORIZONTAL = "Angle to Horizontal"
ANGLE_TO_VERTICAL = "Angle to Vertical"
#: Relax Spline (TR115, D1314).
RELAX_SPLINE = "Relax Spline"
SPLINE_LENGTH = "Spline Length"  # TR115 item 4 (D2201)
#: Weak automatic relations (TR362, D1310).
KEEP_RELATION = "Keep Relation"
#: Spline handles (TR43, D1305).
PIN_HANDLE = "Pin Handle"
RESET_HANDLE = "Reset Handle"
HANDLE_LINE = "Add Handle Line"
#: Solution jumps (TR338, D1302).
KEEP_THIS_SIDE = "Keep This Side"
REMOVE_SIDE_LOCKS = "Remove Side Locks"
SIDE_KEPT = "Change undone. The flipped items now keep the side they had before."
#: The sketch problem list (TR38, D1301).
PROBLEMS_TITLE = "Sketch Problems"
PROBLEMS_TIP = "Click to list the sketch's problems."
PROBLEMS_NONE = "No problems: the sketch solves."
PROBLEMS_KINDS = {
    "dangling": "Dangling",
    "invalid": "Invalid",
    "conflicting": "Conflicting",
    "redundant": "Redundant",
    "no_solution": "No solution",
}
PROBLEMS_ZOOM = "Zoom to Item"
PROBLEMS_PICK = "Pick New Item"
PROBLEMS_DELETE = "Delete"
PROBLEMS_REPAIR = "Repair All Dangling"
PROBLEMS_DIAGNOSE = "Diagnose"
PROBLEMS_APPLY = "Apply Way Out"
PROBLEMS_UNDER = "Select Under Defined"
PROBLEMS_PICK_FIRST = "Select one item in the sketch first, then click Pick New Item."
PROBLEMS_NOT_DANGLING = "Pick a dangling row first."
PROBLEMS_NOT_CONFLICT = "Pick a conflict set first."
PROBLEMS_NO_WAY = "No single change solves this set. Delete or change two of its items."
PROBLEMS_WAY = "Way {n} of {count}: {label} Click Apply Way Out, or Diagnose for the next."
PROBLEMS_REPAIR_ASK = "Use {new} in place of the deleted {old} for {item}?"
PROBLEMS_REPAIRED = (
    "Repaired {n} dangling items. {left} have no clear match: pick a new item or delete them."
)
PROBLEMS_UNDER_NONE = "Nothing is under defined."
SKETCH_RELATIONS = "Add Relation"
SKETCH_EXISTING = "Relations of the selection"
# What the two cards say while they are empty (D2702).
RELATIONS_NONE_PICKED = "Relations that fit what you select show here."
RELATIONS_NONE_FIT = "No relation fits this selection. Select other items."
EXISTING_NONE_PICKED = "Select an item to see its relations."
EXISTING_NONE = "The selection has no relations yet."
DELETE_RELATION = "Delete Relation"
DELETE_ALL = "Delete All"
MEASURE_TO = "Measure To"
MEASURE_SIDES = {"center": "Center", "nearest": "Nearest", "farthest": "Farthest"}
MEASURE_KINDS = {"circle": "Circle", "arc": "Arc"}
RELATIONS_PANEL = "Relations"
RELATIONS_BACK = "Back"
RELATION_FILTER = "Show"
RELATION_FILTERS = {
    "all": "All",
    "problems": "Over defining or not solved",
    "model": "Model references",
}
SELECTION_STATE = {
    "under": "Selection: under defined",
    "full": "Selection: fully defined",
    "over": "Selection: over defined",
}
NOTHING_SELECTED = "Select sketch items to add relations."
SELECTED_COUNT = "{count} item(s) selected"
DISCARD_SKETCH_TITLE = "Discard Sketch Changes"
DISCARD_SKETCH = "Discard the changes to {name}?"
RELATION_NAMES = {
    "merge": "Merge",
    "on_segment": "Point on Segment",  # TR342 (D1311)
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "coincident": "Coincident",
    "collinear": "Collinear",
    "parallel": "Parallel",
    "perpendicular": "Perpendicular",
    "tangent": "Tangent",
    "concentric": "Concentric",
    "equal": "Equal",
    "midpoint": "Midpoint",
    "symmetric": "Symmetric",
    "coradial": "Coradial",
    "intersection": "Intersection",
    "fixed": "Fixed",
}
#: Short text of each relation tag drawn beside the geometry (W3.3).
RELATION_TAGS = {
    "on_segment": "S",  # TR342
    "horizontal": "H",
    "vertical": "V",
    "coincident": "C",
    "collinear": "L",
    "parallel": "//",
    "perpendicular": "\u22a5",
    "tangent": "T",
    "concentric": "O",
    "equal": "=",
    "midpoint": "M",
    "symmetric": "S",
    "coradial": "R",
    "intersection": "X",
    "fixed": "F",
}
SHOW_RELATIONS = "Sketch Relations"
SNAP_LABELS = {
    "point": "Endpoint",
    "center": "Center",
    "midpoint": "Midpoint",
    "quadrant": "Quadrant",
    "intersection": "Intersection",
    "on_curve": "On curve",
    "guide": "Guide",  # TR232 (D1714)
    "parallel": "Parallel",
    "perpendicular": "Perpendicular",
}
SNAP_ORIGIN = "Origin"
SKETCH_CURSOR = "X {x}  Y {y}"

# Feature tree
PARENTS_CHILDREN = "Parents and Children"
RELATIVES = "{name}\n\nUses: {parents}\nUsed by: {children}"
NONE = "nothing"
# TR96 (D942)
RELATION_ARROWS = "Parent and Child Arrows"
RELATIVES_USES = "Uses (parents):"
RELATIVES_USED_BY = "Used by (children):"
RELATIVES_HINT = "Double click a feature to see its own parents and children."
FIND_TITLE = "Find in Feature Tree"
FIND_PROMPT = "Feature name contains:"

# View and selection
SELECTION_FILTER = "Selection Filter"
FILTER_KINDS = {"face": "Faces", "edge": "Edges", "vertex": "Vertices"}
SELECTED = "{items} selected"
SELECT_FACE_FOR_NORMAL = "Select a flat face or a plane first, then use Normal To."

# Preferences: input
TAB_GENERAL = "General"
#: Colour scheme choices in Preferences, General (D437): label and stored value.
THEME_CHOICES = (
    ("Beige", "beige"),
    ("Light Gray", "light"),
    ("Dark Grey", "dark"),
    ("Stealth (black)", "stealth"),
    ("Follow system", "system"),
)
VIEW_SELECTOR_FACES = {
    "back": "Back",
    "left": "Left",
    "bottom": "Bottom",
    "dimetric": "Dimetric",
    "trimetric": "Trimetric",
}
VIEW_SELECTOR_TIP = "Click a face, edge or corner of the cube to look from there."
HIDE_SHOW_NOTHING = "Select a body, sketch or plane to hide or show it."
REFERENCE_HIDDEN = "Reference geometry hidden. Run Hide All Reference Geometry again to show it."
REFERENCE_SHOWN = "Reference geometry shown."
LINE_ARC_NONE = "Draw a line or arc first. The next segment can then switch to an arc."
LINE_ARC_ON = "Line: the next segment is a tangent arc. Switch again for a line."
LINE_ARC_OFF = "Line: the next segment is a line."
SNAP_OPTIONS_TITLE = "Snap options"
TAB_SKETCH = "Sketch"
#: Labels and tooltips of the Sketch preferences page (T11), by option key.
PREF_SKETCH = {
    "normal_to_on_open": (
        "Turn the view normal to the sketch when it opens",
        "Turn the 3D view to face the sketch plane before the sketch editor opens.",
    ),
    "show_centres": (
        "Show circle and arc centres",
        "Draw the centre point of every circle and arc.",
    ),
    "end_point_dots": (
        "Show end points as dots",
        "Draw the end points of lines and arcs as small dots in their state colour.",
    ),
    "snapping": (
        "Snapping",
        "Snap the cursor to points, centres and curves. Hold Ctrl to snap nothing for a move.",
    ),
    "model_snaps": (
        "Snap to model geometry",
        "Snap to centres of round edges of the part.",
    ),
    "auto_relations": (
        "Automatic relations",
        "Add relations such as Coincident or Horizontal where a click lands on a snap.",
    ),
    "auto_horizontal": (  # TR231 (D1309)
        "Automatic Horizontal relations",
        "Add Horizontal relations automatically while drawing. Needs Automatic relations on.",
    ),
    "auto_vertical": (  # TR231 (D1309)
        "Automatic Vertical relations",
        "Add Vertical relations automatically while drawing. Needs Automatic relations on.",
    ),
    "auto_parallel": (  # TR231 (D1309)
        "Automatic Parallel relations",
        "Add Parallel relations automatically while drawing. Needs Automatic relations on.",
    ),
    "auto_perpendicular": (  # TR231 (D1309)
        "Automatic Perpendicular relations",
        "Add Perpendicular relations automatically while drawing. Needs Automatic relations on.",
    ),
    "auto_tangent": (  # TR231 (D1309)
        "Automatic Tangent relations",
        "Add Tangent relations automatically while drawing. Needs Automatic relations on.",
    ),
    "auto_equal": (  # TR231 (D1309)
        "Automatic Equal relations",
        "Add Equal relations automatically while drawing. Needs Automatic relations on.",
    ),
    "auto_midpoint": (  # TR231 (D1309)
        "Automatic Midpoint relations",
        "Add Midpoint relations automatically while drawing. Needs Automatic relations on.",
    ),
    "auto_coincident": (  # TR231 (D1309)
        "Automatic Coincident relations",
        "Add Coincident relations automatically while drawing. Needs Automatic relations on.",
    ),
    "show_grid": (
        "Show the grid",
        "Draw grid lines behind the sketch. Off by default.",
    ),
    "value_input": (
        "On screen value input while drawing",
        "Open the size box at the cursor as soon as a shape starts. Type a size and press "
        "Enter, or keep drawing with the mouse. Off by default.",
    ),
    "drag_changes_dimensions": (  # TR112 item 2 (D1716)
        "Dragging changes dimensions",
        "Dragging geometry that has driving dimensions gives those dimensions the sizes "
        "the drag leaves, instead of holding them. Off by default.",
    ),
    "lock_changed_dimensions": (  # TR238 (D1706)
        "Lock changed dimensions while dragging",
        "While you drag, the curves and points of dimensions whose value you changed since "
        "the sketch opened stay where they are, so the drag moves the rest. Off by default.",
    ),
    "keep_proportions": (  # TR119 (D938)
        "Keep proportions on the first dimension",
        "The first length dimension you give a value scales the whole sketch, so the shape "
        "keeps its proportions. Only when no other dimension or model geometry sizes the "
        "sketch. Off by default.",
    ),
    "double_click_exit": (  # TR120 (D941)
        "Double click empty space to exit the sketch",
        "A double click where there is nothing, with no tool active, saves the sketch and "
        "goes back to the 3D view. Off by default.",
    ),
    "escape_exit": (
        "Esc with nothing to cancel exits the sketch",
        "Esc first stops the tool and clears the picks; one more Esc saves the sketch and goes "
        "back to the 3D view. Off by default.",
    ),
    "dimension_ends": (  # TR418 (D953)
        "Smart Dimension picks end points",
        "Where an end point snap shows, Smart Dimension measures to that point instead of "
        "the curve.",
    ),
    "dimension_middles": (
        "Smart Dimension picks midpoints",
        "Where a midpoint snap shows on a line, an arc or a part edge, Smart Dimension "
        "measures to the midpoint. FDCAD adds a construction point there for it. Off by "
        "default, so a click on the middle of a line gives its length.",
    ),
    "dimension_centres": (
        "Smart Dimension picks centres",
        "Where a centre snap shows, Smart Dimension measures to the centre point instead of "
        "the circle or arc.",
    ),
}
PREF_OVER_DEFINE = "Over defining dimension"
PREF_OVER_DEFINE_TIP = "What happens when a new dimension would over define the sketch."
PREF_OVER_DEFINE_CHOICES = {"ask": "Ask", "reference": "Always make reference"}
TAB_SHORTCUTS = "Shortcuts"
TAB_GESTURES = "Gestures"
TAB_SHORTCUT_BAR = "Shortcut Bar"
CONTEXT_PART = "Part"
CONTEXT_SKETCH = "Sketch"
SEARCH_COMMANDS = "Search commands"
SEARCH_UNAVAILABLE = (
    "{n} more matching command(s) cannot run now. Select what they work on, or open a part, "
    "then search again."
)
SEARCH_COMMANDS_BOX = "Search tools (Ctrl+K)"
SEARCH_COMMANDS_TIP = (
    "Find any tool, feature or command by name or by a word such as spin or thread"
)
SHORTCUT_COLUMNS = ["Command", "Group", "Shortcut"]
ASSIGN = "Assign"
CLEAR_SHORTCUT = "Clear"
RESET_ALL = "Reset All"
SHORTCUT_IN_USE = "{key} is used by {names}. Assigning it here removes it from there."
SHORTCUT_MOVED = "{key} moved here. {names} lost it."
FOUR_DIRECTIONS = "4 directions"
EIGHT_DIRECTIONS = "8 directions"
DIRECTIONS = "Directions"
GESTURE_HINT = (
    "Hold the right mouse button, drag in a direction and release. "
    "On a trackpad, hold Control and drag."
)
NO_COMMAND = "(none)"
DIRECTION_NAMES = {
    "up": "Up",
    "up_right": "Up right",
    "right": "Right",
    "down_right": "Down right",
    "down": "Down",
    "down_left": "Down left",
    "left": "Left",
    "up_left": "Up left",
}

# Errors panel and bodies
TAB_ERRORS = "Errors"
TAB_ERRORS_COUNT = "Errors ({count})"
OPEN_FEATURE = "Open Feature"
NO_PROBLEMS = "No warnings or errors."
ERROR = "Error"
WARNING = "Warning"
BODIES = "Solid Bodies ({count})"
BODY = "Body {index}"
BODY_COUNT = {1: "1 body"}
BODY_COUNT_MANY = "{count} bodies"
FIX_APPLIED = "Applied: {label}"

# Rebuild statistics
STATS_TITLE = "Rebuild Statistics"
STATS_COLUMNS = ["Feature", "Time (ms)", "Last rebuild"]
STATS_REBUILT = "Rebuilt"
STATS_REUSED = "Reused from cache"
STATS_SUMMARY = (
    "Last rebuild: {seconds:.2f} s, {rebuilt} feature(s) rebuilt, {reused} reused. "
    "Memory in use: {memory:.0f} MB."
)
STATS_NONE = "No rebuild yet. Memory in use: {memory:.0f} MB."

# View bar
VIEW_MENU = "View"
STYLE_MENU = "Display"
MENU_SAMPLES = "Open &Sample"

# Selected Regions (WP15, TOOL_SPEC T5.1.6, T5.3)
GROUP_REGIONS = "Selected Regions"
REGION_ITEM = "Region {number}"
REGIONS_EMPTY = "Click in the list, then click regions in the view. Empty uses the whole sketch."
REGIONS_ACTIVE = "Click regions in the view to add or remove them."
REGIONS_CLEAR = "Clear"
REGION_SHARED_SKETCH = "{sketch} (shared)"
PANEL_TIPS.update(
    {
        "regions": (
            "Selected Regions: use only some regions of the sketch. Click in the list, then "
            "click regions in the view; click again to remove one. Empty uses the whole sketch."
        ),
        "regions_clear": "Clear: remove every picked region, so the whole sketch is used.",
    }
)


# Phase 2 sketch tools (PHASE2_SPEC P2.8, P2.9): their text lives in its own module.
from fdcad.ui.sketch_tools.tool_text import RELATION_NAMES as _P2_RELATION_NAMES  # noqa: E402
from fdcad.ui.sketch_tools.tool_text import RELATION_TAGS as _P2_RELATION_TAGS  # noqa: E402
from fdcad.ui.sketch_tools.tool_text import THREE_POINT_HINTS as _P2_HINTS  # noqa: E402
from fdcad.ui.sketch_tools.tool_text import TOOL_NAMES as _P2_TOOL_NAMES  # noqa: E402
from fdcad.ui.sketch_tools.tool_text import TOOLTIPS as _P2_TOOLTIPS  # noqa: E402

TOOLTIP_TEXT.update(_P2_TOOLTIPS)
TOOL_HINTS.update(_P2_HINTS)
SKETCH_TOOLS.update(_P2_TOOL_NAMES)
RELATION_NAMES.update(_P2_RELATION_NAMES)
RELATION_TAGS.update(_P2_RELATION_TAGS)

# Model geometry snapping (WP14, TOOL_SPEC T1.2.2, D250)
LINKS_STALE = (
    "The part changed: {count} part copies no longer match the part. "
    "Press Update to move them onto the part."
)
LINKS_STALE_ONE = (
    "The part changed: 1 part copy no longer matches the part. "
    "Press Update to move it onto the part."
)
LINKS_LOST = (
    "{count} part copies lost their part edge or corner. They stay where they are. "
    "Convert the part edges again if the copies should follow the part."
)
LINKS_UPDATE = "Update"
LINKS_UPDATE_TIP = "Move the copies onto the part. The sketch geometry tied to them follows."
LINKS_UPDATED = "Moved {count} part copies onto the part. Undo puts them back."

# Reference geometry (PHASE2_SPEC P2.10, D251)
GROUP_REFERENCE = "Reference Geometry"
REF_TITLES = {
    "ref_plane": "Plane",
    "ref_axis": "Axis",
    "ref_point": "Point",
    "coord_system": "Coordinate System",
}
REF_METHOD = "Method"
REF_METHODS = {
    "offset": "Offset distance",
    "angle": "At angle",
    "three_points": "Three points",
    "normal_to_curve": "Normal to curve",
    "mid_plane": "Mid plane",
    "parallel_point": "Parallel through a point",
    "project": "Project onto a face",
    "screen": "Parallel to screen",
    "tangent": "Tangent to a cylinder",
    "line_point": "Through a line and a point",
    "line": "Along a line or edge",
    "two_planes": "Two planes",
    "two_points": "Two points",
    "cylinder": "Cylinder or round edge axis",
    "point_normal": "Point and face",
    "arc_centre": "Arc centre",
    "face_centre": "Centre of face",
    "intersection": "Intersection",
    "projection": "Projection",
    "along_curve": "Along curve",
    "sketch_point": "On a point",
    "values": "X, Y and Z values",
    "centre_of_mass": "Centre of mass",  # TR80 (D1021)
    "directions": "Origin and directions",
    "angles": "Rotation angles",
}
REF_PICK_NONE = "Click here, then pick in the view"
REF_PICK_FEATURES = "Choose a plane, axis or point"
REF_PICK_CLEAR = "Clear this reference"
REF_VALUES = {
    "distance": "Distance",
    "angle": "Angle",
    "percent": "Percent of length",
    "x": "X",
    "y": "Y",
    "z": "Z",
    "rx": "Rotation about X",
    "ry": "Rotation about Y",
    "rz": "Rotation about Z",
    "crossing": "Crossing number",  # TR353 (D984): which crossing, along the line
    # TR149 (D980): after the method, in the reference's own axes
    "extra_dx": "Extra offset X",
    "extra_dy": "Extra offset Y",
    "extra_dz": "Extra offset Z",
    "extra_rx": "Extra turn about X",
    "extra_ry": "Extra turn about Y",
    "extra_rz": "Extra turn about Z",
}
REF_CHECKS = {
    "flip": "Flip side",
    "flip_normal": "Flip normal",
    "origin_on_curve": "Set origin on curve",
    "reverse": "Reverse direction",
    "by_percent": "Distance as percent",
    "reverse_x": "Reverse X",
    "reverse_z": "Reverse Z",
    "along_normal": "Along sketch normal",
    "extra_flip": "Flip after the extra offset",
}
REF_USE_VIEW = "Use Current View"
REF_USE_VIEW_TIP = "Take the direction you are looking in as the plane's normal."
REF_NEEDS_VIEW = "Press Use Current View to take the view direction."
REF_FULLY_DEFINED = "Fully defined. Click OK to add it."
REF_NEEDS_PICK = "Pick {what} for reference {index}."
REF_WORKING = "Working out the preview."
REF_PART_ORIGIN = "Origin"
# Sketch items in the reference geometry pick menu (audit B item 3, D718).
REF_SKETCH_POINT = "Point {id}"
REF_SKETCH_LINE = "Line {id}"
REF_SKETCH_ROUND = "Axis of arc or circle {id}"
TOOLTIP_TEXT.update(
    {
        "feature.ref_plane": "Add a reference plane from faces, planes, edges or points.",
        "feature.ref_axis": (
            "Add a reference axis from an edge, two planes, two points or a round face."
        ),
        "feature.ref_point": "Add a reference point at a centre, an intersection or given values.",
        "feature.coord_system": "Add a coordinate system from an origin and directions or angles.",
    }
)

# Measure (PHASE2_SPEC P2.12, D252)
GROUP_MEASURE = "Measure"
MEASURE_TITLE = "Measure"
MEASURE_PIN = "Pin"
MEASURE_PIN_TIP = "Keep the Measure box on top of the window."
MEASURE_PAUSE = "Pause"
MEASURE_PAUSE_TIP = "Stop adding picks, so clicks in the view select as usual."
MEASURE_FREE = "Points on faces"  # TR192 (D925)
MEASURE_FREE_TIP = (
    "Measure from the exact spots you click on faces, not the faces themselves. "
    "One point gives its position; two give the distance between them."
)
MEASURE_CLEAR = "Clear"
MEASURE_PICKS = "Picked items"
MEASURE_HINT = "Click faces, edges or vertices in the view. Click an item again to remove it."
MEASURE_PART_UNITS = "Part units"
MEASURE_UNITS = "Units"
MEASURE_SECOND_UNIT = "Second unit"  # TR26
MEASURE_NO_SECOND_UNIT = "None"
MEASURE_DECIMALS = "Decimals"
MEASURE_ARC = "Circles"
MEASURE_ARC_MODES = {"centre": "Center to center", "minimum": "Minimum", "maximum": "Maximum"}
MEASURE_SHOW_XYZ = "Show dX, dY, dZ"
MEASURE_XYZ_FROM = "XYZ from"
MEASURE_PART_ORIGIN = "Part origin"
MEASURE_PROJECT = "Projected on"
MEASURE_NO_PROJECTION = "None"
MEASURE_HISTORY = "History"
MEASURE_COPY = "Copy"
MEASURE_COPY_TIP = "Copy this value."
MEASURE_LABELS = {
    "point": "Point",
    "length": "Length",
    "radius": "Radius",
    "diameter": "Diameter",
    "centre": "Center",
    "area": "Area",
    "perimeter": "Perimeter",
    "projected_area": "Projected area",
    "thickness": "Thickness here",
    "distance": "Distance",
    "distance_min": "Minimum distance",
    "distance_max": "Maximum distance",
    "centre_distance": "Center distance",
    "delta": "dX, dY, dZ",
    "projected_distance": "Projected distance",
    "normal_distance": "Normal distance",
    "angle": "Angle",
    "total_length": "Total length",
    "total_area": "Total area",
    "deviation_max": "Angle across, largest",  # TR199 (D996)
    "deviation_min": "Angle across, smallest",
    "deviation_avg": "Angle across, average",
    "triangles": "Triangles",
    "size": "Size X, Y, Z",
    "volume": "Volume",
}
TOOLTIP_TEXT.update(
    {"evaluate.measure": "Measure distances, angles, lengths and areas of picked items."}
)

# Section view (PHASE2_SPEC P2.13, D253)
SECTION_TITLE = "Section View"
SECTION_PLANE = "Section {number}"
SECTION_FRONT = "Front"
SECTION_TOP = "Top"
SECTION_RIGHT = "Right"
SECTION_FACE = "Selected face"
SECTION_REFERENCE = "Plane"
SECTION_REVERSE = "Reverse"
SECTION_OFFSET = "Offset"
SECTION_ROT_X = "Rotate X"
SECTION_ROT_Y = "Rotate Y"
SECTION_COLOR = "Cap Color"
SECTION_USE_AXIS = "Turn Section 1 about an axis"
SECTION_AXIS = "Axis"
SECTION_ANGLE = "Angle"
SECTION_SELECTED_AXIS = "Selected edge or face"
SECTION_SHOW_CAP = "Show section cap"
SECTION_KEEP_COLOR = "Keep cap color after closing"
SECTION_OK_TIP = "Keep the section on while you work. Run Section View again to turn it off."
SECTION_CANCEL_TIP = "Turn the section off."
SECTION_ON = "Section view on. The part is not changed."
SECTION_OFF = "Section view off."
TOOLTIP_TEXT.update(
    {"view.section": "Cut the view open along up to three planes. The part is not changed."}
)

# Appearance (PHASE2_SPEC P2.11, D254)
APPEARANCE_TITLE = "Appearance"
APPEARANCE_DONE = "Done"
APPEARANCE_TARGET = "Color of"
APPEARANCE_PART = "Part"
APPEARANCE_FACES = "Selected faces ({count})"
APPEARANCE_MORE = "More Colors..."
APPEARANCE_REMOVE = "Remove Color"
APPEARANCE_REMOVE_TIP = "Remove this color, so the feature, body or part color shows."
APPEARANCE_IN_USE = "Colors in use"
APPEARANCE_IN_USE_TIP = (
    "Double click to change a color. Select one and press Delete to remove it, "
    "or right click for both."
)
APPEARANCE_CHANGE = "Change Color..."
APPEARANCE_CURRENT = "Current: {color}"
APPEARANCE_INHERITED = "none of its own"
APPEARANCE_SET = "Color {item}"
APPEARANCE_CLEARED = "Remove Color of {item}"
APPEARANCE_COPIED = "Copied the color {color}."
APPEARANCE_NOTHING_COPIED = "Nothing to paste. Copy an appearance first."
APPEARANCE_ROW = "Appearances ({count})"
TOOLTIP_TEXT.update(
    {
        "edit.appearance": "Color the part, a body, a feature or the selected faces.",
        "edit.copy_appearance": "Copy the color of the selection.",
        "edit.paste_appearance": "Give the selection the copied color.",
    }
)
# Phase 4 command tooltips live in strings_phase4 (parallel work, PHASE4_SPEC).
from fdcad.ui.strings_phase4 import COMMAND_TIPS as _PHASE4_TIPS  # noqa: E402

TOOLTIP_TEXT.update(_PHASE4_TIPS)

# Extrude drag interactions (TOOL_SPEC T5.2.4, T5.4, D525) ---------------------------------
SNAP_TO_VERTEX = "to vertex"
SNAP_TO_FACE = "to face"
DRAG_BOSS = "Boss"
DRAG_BOSS_TIP = "Add material: make the dragged region a boss."
DRAG_CUT = "Cut"
DRAG_CUT_TIP = "Remove material: make the dragged region a cut."
DRAG_OK_TIP = "Add the feature."
DRAG_CANCEL_TIP = "Drop the arrow without changing the part."
DRAG_PANEL = "Edit in Panel"
DRAG_PANEL_TIP = "Open the full Extrude panel for this feature."
# Draft types and the draft assistant (D521, D522)
GROUP_DRAFT_TYPE = "Type of Draft"
DRAFT_TYPES = {
    "neutral_plane": "Neutral Plane",
    "parting_line": "Parting Line",
    "step": "Step Draft",
    "fixed_edge": "Fixed Edge",  # TR323 (D1804)
}
GROUP_PULL = "Direction of Pull"
PICK_PULL = "Pick Direction Face"
GROUP_PARTING_LINES = "Parting Lines"
FIELD_OTHER_SIDE = "Other side"
FIELD_BOTH_SIDES = "Draft both sides"
FIELD_OTHER_ANGLE = "Other angle"
DRAFT_NEEDS_PULL = "Choose a direction of pull or click a flat face."
DRAFT_NEEDS_PARTING = "Pick the parting line edges in the view."
PICK_EDGES_PARTING = "Pick edges for the parting lines, or a flat face for the direction."
DRAFT_ADD_NEEDED = "Add Faces That Need Draft"
DRAFT_ADDED = "Added {count} that need draft."
DRAFT_NONE_NEEDED = "No other face needs draft from this neutral plane."
DRAFT_ASSIST_WORKING = "Looking for faces that need draft."
DRAFT_ASSIST_FAILED = (
    "Could not find the faces that need draft: {reason}. Pick the faces in the view instead."
)
PANEL_TIPS.update(
    {
        "draft_type": "Type of draft: tilt faces about a neutral plane, or about parting "
        "line edges (Step Draft allows edges at several heights).",
        "pull": "Direction of pull: the normal of a plane or flat face. Faces next to the "
        "parting lines on this side are drafted.",
        "pick_pull": "Pick Direction Face: the next flat face clicked sets the direction of pull.",
        "parting_lines": "Parting lines: click edges in the view. Each must lie square to "
        "the direction of pull.",
        "other_side": "Other side: draft the faces on the other side of the parting lines.",
        "both_sides": "Draft both sides: draft the faces on both sides of the parting lines.",
        "draft_angle2": "Other angle: the draft angle of the other side. Type a value.",
        "add_needed": "Add every face whose draft from the neutral plane is less than the "
        "draft angle.",
    }
)
# Kept separate bodies (D527)
WARN_SEPARATE_BODIES = "Warn About Separate Bodies"

# Named dimensions (TR32) -----------------------------------------------------------

DIMENSION_NAME = "Name"
DIMENSION_NAME_EMPTY = "Automatic"
DIMENSION_NAME_TIP = "A name to use this value in equations, for example wall."
DIMENSION_NAME_BAD = (
    "Type a name that starts with a letter and has only letters, digits and underscores, "
    "for example wall."
)
DIMENSION_NAME_TAKEN = "This sketch already has a dimension called {name}. Choose another name."
NAME_VALUE = "Name This Value..."
NAME_VALUE_TITLE = "Name Value"
NAME_VALUE_PROMPT = "Name for this value in equations (leave empty for the automatic name):"
SHOW_ALL_DIMENSIONS = "Show All Dimensions"

# Split View (TR16) -----------------------------------------------------------------

SPLIT_VIEW = "Split View"
SPLIT_NO_VIEW = "Split View needs the 3D view, which is not available here."

# Zebra stripes (TR18, D754) ---------------------------------------------------------------

ZEBRA_TITLE = "Zebra Stripes"
ZEBRA_COUNT = "Stripes"
ZEBRA_COUNT_TIP = "How many black and white stripes are reflected in the faces."
ZEBRA_DIRECTION = "Direction"
ZEBRA_DIRECTIONS = {"vertical": "Up and down", "horizontal": "Side to side"}

# Compare Bodies (TR27, D758) --------------------------------------------------------------

COMPARE_TITLE = "Compare Bodies"
COMPARE_FIRST = "First"
COMPARE_SECOND = "Second"
COMPARE_BODY = "Body {index}"
COMPARE_STEP = "STEP file..."
COMPARE_STEP_TITLE = "Compare With a STEP File"
COMPARE_STEP_FILTER = "STEP files (*.step *.stp);;All files (*)"
COMPARE_RUN = "Compare"
COMPARE_RUNNING = "Comparing..."
COMPARE_SAME = "The bodies are the same."
COMPARE_DONE = (
    "{faces} faces of the first body differ. Only in the first: {first}. "
    "Only in the second: {second}."
)
COMPARE_NO_BODY = "Nothing to compare: the part has no body. Rebuild the part, then compare."
COMPARE_NO_FILE = "No STEP file chosen. Choose STEP file... in Second, then compare."
COMPARE_SAME_BODY = "First and Second are the same body. Choose another body for Second."
COMPARE_FAILED = "Compare failed: {reason}"

# Use Only Fully Defined Sketches (TR36 item 6, D763) -------------------------------------

PREF_FULL_SKETCHES = "Use only fully defined sketches"
PREF_FULL_SKETCHES_TIP = "Features refuse a sketch that is not fully defined, and name the sketch."

# Mass Properties (TR79, D764) -------------------------------------------------------------

MASS_TITLE = "Mass Properties"
MASS_USE = "Bodies"
MASS_WHOLE_PART = "The whole part"
MASS_PICKED = "The picked bodies"
MASS_HIDDEN = "Include hidden bodies"
MASS_MATERIAL = "Material"
MASS_TYPED = "Typed density"
MASS_DENSITY = "Density"
MASS_ABOUT = "Inertia about"
MASS_ABOUT_CENTRE = "Centre of mass"
MASS_ABOUT_ORIGIN = "Part origin"
MASS_RUN = "Calculate"
MASS_COPY = "Copy"
MASS_COPY_TIP = "Copies every value as text."
MASS_RUNNING = "Calculating..."
MASS_COPIED = "Copied the mass properties."
MASS_NO_BODY = "Nothing to measure: no body is shown. Rebuild the part, or include hidden bodies."
MASS_FAILED = "Mass properties failed: {reason}"
# TR81 (D1019): section properties of a flat face or a closed sketch.
MASS_SECTION = "Section of the picked face or sketch"
MASS_NO_SECTION = (
    "Nothing to measure: pick a flat face in the view, or select a sketch in the feature tree."
)
MASS_SECTION_COPIED = "Copied the section properties."
# TR80 (D1021): typed mass properties.
MASS_OVERRIDE = "Override..."
MASS_OVERRIDE_TIP = "Type the mass, centre of mass and inertia for imported or simplified bodies."
MASS_OVERRIDE_TITLE = "Override Mass Properties"
MASS_OVERRIDE_MASS = "Mass"
MASS_OVERRIDE_CENTRE = "Type the centre of mass"
MASS_OVERRIDE_INERTIA = "Type the inertia about the centre of mass (model axes)"
MASS_OVERRIDE_CLEAR = "Clear Override"
MASS_OVERRIDE_NOTE = (
    "The typed values replace the measured ones for the whole part. Without a typed inertia, "
    "the measured one is scaled to the typed mass."
)
MASS_OVERRIDE_BAD = "These values cannot be used: {reason}"
MASS_OVERRIDE_MARK = "Typed values (Override)"
MASS_OVERRIDE_MARK_TEXT = "mass{centre}{inertia} typed, not measured"

# Drop files on the window (TR377, D765) ---------------------------------------------------

DROP_SKIPPED = (
    "{name} was not opened: FDCAD opens parts, STEP, IGES and mesh files "
    "({count} skipped). Drop one of those files instead."
)

# Colour vision safe colours (TR292, D769) -------------------------------------------------

PREF_COLOUR_SAFE = "Colour vision safe colours"
PREF_COLOUR_SAFE_TIP = (
    "Blue and orange instead of green and red for sketch status and feature states."
)

# Interference Check (TR150, D771) ---------------------------------------------------------

INTERFERE_TITLE = "Interference Check"
INTERFERE_GAP_LABEL = "Report gaps under"
INTERFERE_GAP_TIP = (
    "Pairs of bodies closer than this are listed, for example parts printed in place."
)
INTERFERE_TOUCHING = "Count touching bodies"
INTERFERE_BODIES = "Bodies"
INTERFERE_BODIES_TIP = "Untick a body to leave it out of the check."
INTERFERE_RUN = "Check"
INTERFERE_IGNORE = "Ignore Pair"
INTERFERE_RUNNING = "Checking..."
INTERFERE_PAIR = "Body {a} and Body {b}"
INTERFERE_OVERLAP = "overlap {value}"
INTERFERE_GAP = "gap {value}"
INTERFERE_TOUCH = "touching"
INTERFERE_FAILED = "could not be checked. Check both bodies with Geometry Check."
INTERFERE_NONE = "No bodies overlap, touch or come closer than the gap."
INTERFERE_DONE = "{overlaps} overlaps and {gaps} small gaps found. Click a row to see it."
INTERFERE_ONE_BODY = "The part has fewer than two bodies. Interference needs two or more bodies."
INTERFERE_FAILED_ALL = "Interference check failed: {reason}"


# Enclosed Cavities (TR284, D772) ----------------------------------------------------------

CAVITY_TITLE = "Enclosed Cavities"
CAVITY_FIND = "Find"
CAVITY_DRAIN = "Add Drain Hole"
CAVITY_DRAIN_TIP = "Adds a small hole from the nearest flat outside face into the void."
CAVITY_RUNNING = "Looking for closed voids..."
CAVITY_ROW = "Body {body}: closed void, {volume}"
CAVITY_NONE = "No closed voids: liquid and powder can drain from every space."
CAVITY_DONE = "{count} closed voids found. Click one to see it; Add Drain Hole drains it."
CAVITY_PICK = "Nothing to drain. Click Find, then pick a void in the list."
CAVITY_NO_FACE = (
    "No flat outside face lies straight across from this void. Add a hole by hand with the "
    "Hole Tool."
)
CAVITY_DRAINED = "Added {name}. Click Find again to check that no closed void is left."
CAVITY_FAILED = "Cavity check failed: {reason}"
CAVITY_OPENING = "Opening"
CAVITY_TOP = "The top of the picked faces"
CAVITY_CUP = "Cup Volume"
CAVITY_CUP_TIP = "The volume the picked inside faces hold below the opening."
CAVITY_CUP_PICK = "Pick the inside faces of the cup in the view, then click Cup Volume."
CAVITY_CUP_EMPTY = (
    "The picked faces hold nothing below that opening. Pick the inside faces, or another opening."
)
CAVITY_CUP_DONE = "The picked faces hold {volume}."

# Show the cause of an error (TR288, D773) --------------------------------------------------

SHOW_CAUSE_DONE = "Selected {name}, where the missing face was lost."

# Change Test (TR287, D774) ----------------------------------------------------------------

CHANGE_TITLE = "Change Test"
CHANGE_STEP = "Step"
CHANGE_STEPS = "Steps each way"
CHANGE_RUN = "Run"
CHANGE_STOP = "Stop"
CHANGE_RUNNING = "Rebuilding a copy with each value stepped up and down..."
CHANGE_SAFE = "{name}: fine {reach}% up and down"
CHANGE_BAD = "{name}: safe from -{down}% to +{up}%. {problem}"
CHANGE_DONE = (
    "Tested {count} values: {bad} change the part or make it fail. Click one to select its feature."
)
CHANGE_STOPPED = "Stopped before the end: run it again to test the rest."
CHANGE_FAILED = "Change test failed: {reason}"

# Model Health (TR286, D775) ---------------------------------------------------------------

HEALTH_TITLE = "Model Health"
HEALTH_CHECK = "Check"
HEALTH_MOVE = "Move to End"
HEALTH_MOVE_TIP = "Moves the selected fillet or chamfer to the end of the tree, as one undo step."
HEALTH_RUNNING = "Checking the part..."
HEALTH_DONE = "{count} pieces of advice. Click one to select its feature."
HEALTH_NONE = "No advice: the part is tidy."
HEALTH_MOVED = "Moved {name} to the end. Click Check to look again."
HEALTH_FAILED = "Model health check failed: {reason}"
# Repair Lost References (TR125, D795)
REPAIR_TITLE = "Repair Lost References"
REPAIR_CHECK = "Check"
REPAIR_TICK_ALL = "Tick All"
REPAIR_USE = "Use Offered"
REPAIR_USE_TIP = "Puts the offered match in for every ticked row that has one, as one undo step."
REPAIR_REMOVE = "Remove"
REPAIR_REMOVE_TIP = (
    "Takes every ticked pick out of its feature, as one undo step. Tick All, then Remove, "
    "clears all missing picks."
)
REPAIR_RUNNING = "Looking for lost picks..."
REPAIR_OFFER = "Offered: the {kind} {distance} mm from where it was."
REPAIR_NO_OFFER = "No clear match: edit the feature and pick again, or remove it."
REPAIR_DONE = (
    "{count} lost picks, {offers} with an offered match. Click a row to see where the lost "
    "item was and its match, tick the rows to change, then Use Offered or Remove."
)
REPAIR_NONE = "No lost picks."
REPAIR_NOTHING_TICKED = "Tick the rows to change first."
REPAIR_APPLIED = "Changed {count} picks. Undo puts them back."
REPAIR_UNDO = "Repair Lost References"
REPAIR_UNDO_REMOVE = "Remove Lost References"
REPAIR_FAILED = "Looking for lost picks failed: {reason}"
REPAIR_FEATURE = "Repair Lost References"

# Manufacturing Check (TR295, D790) --------------------------------------------------------

MFG_TITLE = "Manufacturing Check"
MFG_PROCESS = "Process"
MFG_PROCESSES = {
    "milling": "Milling",
    "turning": "Turning",
    "sheet_metal": "Laser and Sheet Metal",
    "moulding": "Moulding",
    "fdm": "FDM Printing",
    "resin": "Resin Printing",
    "powder": "Powder Printing",
}
MFG_RULE = "Rule"
MFG_VALUE = "Value"
MFG_RULES = {
    "tool_diameter": "Tool diameter (mm)",
    "min_tool_diameter": "Smallest tool (mm)",
    "tool_reach_ratio": "Tool reach (times diameter)",
    "hole_depth_ratio": "Hole depth (times diameter)",
    "min_wall": "Thinnest wall (mm)",
    "max_wall": "Thickest wall (mm)",
    "thread_ratio": "Thread length (times diameter)",
    "tap_room_pitches": "Room below a tap (pitches)",
    "min_text": "Smallest text (mm)",
    "setups": "Setups (+Z, -Z, +X...)",
    "min_groove": "Narrowest groove (mm)",
    "hole_to_edge": "Hole to edge (times thickness)",
    "hole_to_bend": "Hole to bend (times thickness)",
    "hole_to_hole": "Hole to hole (times thickness)",
    "min_hole": "Smallest hole (times thickness)",
    "min_flange": "Shortest flange (times thickness)",
    "kerf": "Kerf (mm)",
    "min_draft_deg": "Least draft (degrees)",
    "max_overhang_deg": "Steepest overhang (degrees)",
    "drain_hole": "Drain hole (mm)",
    "escape_hole": "Powder escape hole (mm)",
    "pocket_depth_ratio": "Pocket depth (times width)",  # D801
    "min_tab": "Shortest tab (times thickness)",  # D802
    "pin_ratio": "Tallest post (times its width)",  # D805
    "text_nozzles": "Smallest text (nozzle widths)",
    "thread_layers": "Finest thread (layers per pitch)",
    "wall_change": "Wall change (times thinnest)",
    "rib_ratio": "Rib thickness (of the wall)",
    "wall_height_ratio": "Wall height (times thickness)",
    "nozzle": "Nozzle or smallest detail (mm)",
    "layer_height": "Layer height (mm)",
    "min_round_hole": "Smallest round hole (mm)",
    "max_bridge": "Longest bridge (mm)",
}
MFG_LOAD = "Load Profile"
MFG_SAVE = "Save Profile"
MFG_FILE_FILTER = "Manufacturing profile (*.fdmfg);;All files (*)"
MFG_SAVED = "Saved the profile to {path}."
MFG_LOADED = "Loaded the profile from {path}. Click Check to use it."
MFG_FILE_FAILED = "The profile could not be read or written: {reason}. Pick another file."
MFG_BAD_VALUE = "A rule value must be a number of 0 or more. Type the value again."
MFG_NOT_YET = (
    "This version checks milling and sheet metal only; this process's rules are kept for "
    "later. Choose Milling or Laser and Sheet Metal to check the part."
)
MFG_DONE = "{count} findings. Click one to highlight it."
MFG_NONE = "No findings: the part suits the process."
MFG_FAILED = "Manufacturing check failed: {reason}"
MFG_FIX_RELIEF = "Add Corner Relief"
MFG_FIX_SNAP = "Snap to Stock Size"
MFG_FIXED = "Fix added as one undo step. Click Check to look again."

# Mesh export options (TR182, D776) ---------------------------------------------------------

MESH_EXPORT_TITLE = "{kind} Export Options"
MESH_QUALITY = "Quality"
MESH_PRESETS = {
    "coarse": "Coarse",
    "standard": "Standard",
    "fine": "Fine",
    "custom": "Custom",
}
MESH_DEVIATION = "Chord deviation"
MESH_ANGLE = "Angle"
MESH_FORMAT = "Format"
MESH_BINARY = "Binary"
MESH_TEXT = "Text"
MESH_UNIT = "Unit"
MESH_WHICH = "Bodies"
MESH_SLICER = "Slicer"
MESH_SLICERS = {
    "default": "Bambu Studio, OrcaSlicer or Cura",
    "prusa": "PrusaSlicer",
    "cura": "Cura only",  # TR385 (D1206)
    "plain": "Plain 3MF (any program)",
}
MESH_SLICER_TIP = (
    "The slicer the file is for. Body print roles are written the way that slicer reads "
    "them; the two layouts cannot be mixed in one file."
)
MESH_BODIES = {"all": "All bodies", "shown": "The shown bodies", "picked": "The picked bodies"}
MESH_COUNTING = "Counting triangles..."
MESH_INFO = "{triangles} triangles, {size}"
MESH_ABOUT = "about "
MESH_COUNT_FAILED = "Could not count the triangles: {reason}"
MESH_EXPORT_UNDO = "Change Mesh Export Options"
STEP_EXPORT_TITLE = "STEP Export Options"  # TR302 (D1202)
STEP_UNITS = {"mm": "Millimetres", "in": "Inches", "m": "Metres"}
STEP_Y_UP = "Y up"
STEP_Y_UP_TIP = "Turn the model so its up direction is Y, for programs that use Y up."
STEP_NAMES = "Body names"
STEP_NAMES_TIP = "Write each body with its name (Rename Body) or Body N."
STEP_PER_BODY = "One file per body"
STEP_PER_BODY_TIP = "Write each body to its own file, named after the file and the body."
STEP_HIDDEN = "Include hidden bodies"
STEP_EXPORTED_FILES = "Exported {count} files: {names}"
STEP_UNDO = "Change STEP Export Options"
RENAME_BODY = "Rename Body..."  # TR183 (D1201)
RENAME_BODY_TITLE = "Rename Body"
RENAME_BODY_LABEL = "Name (empty for Body N):"
RENAME_BODY_UNDO = "Rename Body"
MESH_MAX_EDGE = "Largest edge"  # TR336 (D1200)
MESH_MAX_EDGE_OFF = "No limit"
MESH_MAX_ASPECT = "Largest aspect ratio"  # TR336 (D2001)
MESH_MAX_ASPECT_TIP = (
    "Thin triangles are mended until none is thinner than this: 1 is an equilateral "
    "triangle, and limits below 2 count as 2. Flat faces mend fully; triangles along "
    "a curved edge may stay thinner. Some simulation tools need it; slicers do not."
)
MESH_MAX_EDGE_TIP = (
    "Triangles are split until no edge is longer than this. Long edges on flat faces "
    "help some simulation and engraving tools; slicers do not need it."
)
MESH_PREVIEW = "Show the mesh in the view"
MESH_QUALITY_INFO = "Longest edge {longest} mm, worst aspect ratio {worst}, {thin} thin triangles"

# Part material (TR78, D803)
MATERIAL_TITLE = "Material"
MATERIAL_NAME = "Material"
MATERIAL_NONE = "None"
MATERIAL_DENSITY = "Density"
MATERIAL_USE_COLOUR = "Use its colour for the part"
MATERIAL_USE_COLOUR_TIP = "Sets the part colour to the material's colour, in the same undo step."
MATERIAL_UNDO = "Set Material"
MATERIAL_ROW = "Material: {name}"
MATERIAL_ROW_NONE = "Material: none"
MATERIAL_ROW_TIP = "Double click or right click to choose the part's material."
MATERIAL_EDIT = "Edit Material"
# Guide curves and centerline (TR55, D804)
GROUP_GUIDES = "Guide Curves"
GUIDES_TIP = (
    "Curves the section follows. A sweep takes one or two; each loft guide must touch every "
    "profile."
)
GUIDES_ADD = "Add"
GUIDES_ADD_TIP = "Adds the chosen sketch or curve as a guide."
GUIDES_PICK = "Pick edges as guides"
GUIDES_PICK_TIP = "While ticked, edges picked in the view become guides."
CENTERLINE = "Centerline"
CENTERLINE_NONE = "None"
CENTERLINE_TIP = "Middle sections of the loft are kept square to this curve."
SECTIONS_TIP = "How many sections are added between two profiles along the centerline."
# Save a Copy (TR97, D806)
SAVE_COPY = "Save a Copy"
SAVED_COPY = "Saved a copy as {name}. The open part is unchanged."
# Tree filter (TR95, D806)
TREE_FILTER_HINT = "Filter the tree"
TREE_FILTER_TIP = "Shows only the rows whose name holds this text, with the rows above them."
TREE_FILTER_STATE_TIP = "Shows only features with problems, suppressed features or comments."
TREE_FILTER_STATES = {
    "all": "All",
    "problems": "Errors and Warnings",
    "suppressed": "Suppressed",
    "comments": "With Comments",
}
# Undo To (TR208, D807)
UNDO_TO = "Undo To"
UNDO_TO_NONE = "Nothing to undo"
# Delete with dependents (TR201, D807)
DELETE_LIST_INTRO = (
    "{count} features use {name}. The ticked ones are deleted with it; untick a feature "
    "to keep it (it then reports what it lost)."
)
DELETE_TICK_ALL = "Tick All"
DELETE_TICK_NONE = "Tick None"
DELETE_GRAPHS = "These graphs read it and will change: {names}."
# TR91 (D940)
DELETE_NO_USERS = "Delete {name}?"
DELETE_VARIABLES = (
    "Only the deleted features use these variables. Tick the ones to delete too; the others stay."
)
DELETE_VARIABLES_UNDO = "Delete Unused Variables"
DELETE_FEATURE = "Delete Feature ({name})"
DELETE_FACES = "Delete Face ({count} picked)"
# Tree follows the selection (TR200, D808)
PREF_TREE_FOLLOW = "Tree opens to the feature of a picked face or edge"
PREF_TREE_FOLLOW_TIP = (
    "Picking a face, edge or vertex in the view scrolls the tree to the feature that made it. "
    "Clearing the pick scrolls the tree back."
)
PREF_TREE_HOVER = "Hovering a tree row shows its feature in the view"
# TR420 (D929)
EDGE_ANGLE_TITLE = "Edge Angle Analysis"
EDGE_ANGLE_ASK = "Edges whose faces meet at this angle or more are sharp (degrees):"
EDGE_ANGLE_NOTHING = "The part has no solid yet. Add a feature first."
EDGE_ANGLE_FOUND = (
    "{sharp} sharp edges (red, {limit} degrees or more) and {near} nearly smooth edges "
    "(yellow), which can make a fillet or draft fail."
)
EDGE_ANGLE_FAILED = "Edge Angle Analysis failed: {reason}. Rebuild the part and try again."
# TR233 (D928)
SKETCH_COLOR = "Sketch Colour"
#: TR7 (D1719): 3D Sketch panel.
S3D_PARTS = "Plane Sketches"
S3D_PARTS_TIP = "2D sketches, each on its own plane, copied in as parts of the 3D sketch."
S3D_SOURCE = "Sketch"
S3D_ADD_PART = "Add Part"
S3D_REMOVE = "Remove"
S3D_PART_ROW = "Part {k}: {name}"
S3D_LINES = "3D Lines"
S3D_LINES_TIP = "Points in space, one x y z a line, joined by straight lines or a spline."
S3D_KIND = "Join by"
S3D_KIND_LINES = "Lines"
S3D_KIND_SPLINE = "Spline"
S3D_ADD_LINE = "Add 3D Line"
S3D_LINE_ROW = "Line {k}: {kind}, {count} points"
S3D_NO_SKETCH = "No sketch above this one to add. Make a 2D sketch first."
S3D_NEED_TWO = "Type at least two points, one x y z a line."
S3D_EMPTY = "The 3D sketch has no curves. Add a plane sketch or a 3D line."
# TR7 (D2206): relations and 3D lengths between the points of 3D lines.
S3D_RELATIONS = "3D Relations"
S3D_RELATIONS_TIP = (
    "Hold 3D line points along an axis, together, in place, or at a 3D length. A point "
    "can also be tied to a point of a plane sketch part."
)
S3D_REL_TYPE = "Relation"
S3D_REL_TYPES = {
    "along_x": "Along X",
    "along_y": "Along Y",
    "along_z": "Along Z",
    "coincident": "Coincident",
    "fixed": "Fix",
    "length": "3D Length",
}
S3D_REL_FIRST = "First point"
S3D_REL_SECOND = "Second point"
S3D_REL_VALUE = "Length"
S3D_ADD_RELATION = "Add Relation"
S3D_LINE_POINT = "Line {k} point {i}"
S3D_PART_POINT = "Part {k} point {eid}"
S3D_REL_SAME = "Pick two different points for the relation."
#: TR151 item 1 (D1718): Slice Body.
SLICE_TITLE = "Slice Body"
SLICE_BASE = "Base plane"
SLICE_COUNT = "Slices"
SLICE_SPACING = "Spacing"
SLICE_START = "Start offset"
SLICE_WORKING = "Cutting the part into slices..."
SLICE_DONE = "Added {count} slice sketches in a new folder."
SLICE_NO_BODY = "Slice Body needs a part to cut. Make a solid first."
SLICE_NO_PLANE = "The base plane is not built. Pick another plane."
SLICE_FAILED = "The part could not be cut into slices. Change the spacing or the plane."
# TR151 item 1 (D2204): slices round an axis.
SLICE_AXIS = "Around axis"
SLICE_PARALLEL = "None: parallel slices"
SLICE_ANGLE_STEP = "Angle step"
SLICE_START_ANGLE = "Start angle"
SLICE_NO_AXIS_BUILT = "The axis is not built. Pick another axis."
#: TR34 (D1717): sketch blocks.
BLOCK_MAKE = "Make Block"
BLOCK_INSERT = "Insert Copy of {name}"
BLOCK_SELECT = "Select Block Copy"
BLOCK_UPDATE = "Update Block from This Copy"
BLOCK_EXPLODE = "Explode Block Copy"
BLOCK_MADE = "Made {name}. Right click one of its curves to place copies of it."
BLOCK_INSERTED = "Placed a copy of {name}. Move or rotate it with the picked curves."
BLOCK_UPDATED = "Updated {name} from this copy and made {count} other copies again."
BLOCK_EXPLODED = "The copy is plain sketch geometry now. Edit it like any curves."
#: TR112 (D1716): drag without solving.
FREE_DRAG = "Drag Without Solving"
DETACH_DRAG = "Detach Segment on Drag"
FREE_DRAG_TITLE = "Drag Without Solving"
FREE_DRAG_QUESTION = (
    "{count} relations or dimensions no longer hold after the drag. Delete them? "
    "Pick No to keep them; the sketch then shows them as conflicts until you fix them."
)
FREE_DRAG_DELETED = "Deleted {count} relations or dimensions that no longer held."
FREE_DRAG_KEPT = "Kept {count} relations or dimensions that no longer hold. Fix or delete them."
#: TR232 (D1714): temporary guide lines.
GUIDE_STARTED = "Guide started. Rest the cursor on another point to draw the guide."
GUIDE_MADE = "Guide added. Its ends, middle, thirds and quarters snap until the tool ends."
#: TR121 item 1 (D1713): Explode Text.
TEXT_EXPLODE = "Explode Text"
TEXT_EXPLODING = "Turning the text into curves..."
TEXT_EXPLODED = "Turned {count} text items into curves. Edit them like any sketch curves."
TEXT_EXPLODE_FAILED = (
    "A text could not be turned into curves. Change its font or size, then try again."
)
#: TR114 item 2 (D1709): Edit Polygon.
POLYGON_EDIT_TITLE = "Edit Polygon"
POLYGON_SIDES = "Sides"
POLYGON_INSCRIBED = "Corners on the circle (off: sides touch the circle)"
POLYGON_SIZE = "Circle diameter"
POLYGON_ANGLE = "Angle"
#: TR111 item 3 (D1708): hide parts of a linear dimension.
DIM_HIDE_EXTENSION = "Hide extension lines"
DIM_HIDE_LINE = "Hide dimension line"
#: TR111 item 1 (D1707): right click while placing a dimension.
DIMENSION_LOCKED = "Dimension locked to {kind}. Right click again to unlock it."
DIMENSION_UNLOCKED = "Dimension unlocked. Move the cursor to choose its type."
DIMENSION_KINDS = {
    "distance": "aligned",
    "horizontal_distance": "horizontal",
    "vertical_distance": "vertical",
}
#: TR339 (D1703): the tick per sketch.
SHOW_CONSTRUCTION_IN_PART = "Show Construction in Part"
SKETCH_COLOR_CLEAR = "Usual Sketch Colour"
# TR415 (D933)
POINT_FILE_TITLE = "Points from File"
POINT_FILE_FILTER = "Text files (*.txt *.csv *.xyz);;All files (*)"
POINT_FILE_DONE = "{count} points added from the file."
POINT_FILE_SKIPPED = "{count} lines without two numbers were skipped."
POINT_FILE_UNREADABLE = "The file could not be read: {reason}. Choose a plain text file."
# TR228 (D927)
PRESET_TITLE = "Shapes"
PRESET_KIND = "Shape"
PRESET_NOTE = "The shape is centred on the sketch origin. Add dimensions or move it after."
PRESET_KINDS = {
    "triangle_sss": "Triangle by three sides",
    "triangle_sas": "Triangle by two sides and the angle between",
    "triangle_asa": "Triangle by a side and two angles",
    "trapezoid": "Trapezoid",
    "keyhole": "Keyhole",
    "reuleaux": "Constant width triangle",
    "egg": "Egg",
    "superellipse": "Superellipse",
    # TR367 (D991)
    "angle": "Angle (L) section",
    "channel": "Channel (C) section",
    "i_beam": "I beam",
    "rect_tube": "Rectangular tube",
    "round_tube": "Round tube",
    "din_rail": "DIN rail (35 x 7.5 top hat)",
}
PRESET_FIELDS = {
    "side_a": "Side 1 (base)",
    "side_b": "Side 2",
    "side_c": "Side 3",
    "angle_between": "Angle between",
    "angle_1": "Angle at its start",
    "angle_2": "Angle at its end",
    "bottom": "Bottom width",
    "top": "Top width",
    "height": "Height",
    "hole": "Hole diameter",
    "slot": "Slot width",
    "slot_length": "Slot reach below centre",
    "width": "Width",
    "exponent": "Squareness (2 is an ellipse)",
    # TR367 (D991)
    "leg_a": "Leg along X",
    "leg_b": "Leg along Y",
    "thickness": "Thickness",
    "flange_width": "Flange depth",
    "web": "Web thickness",
    "flange": "Flange thickness",
    "wall": "Wall",
    "outside": "Outside diameter",
}
# TR392 (D931)
NOTES_TITLE = "Part Notes"
NOTES_UNDO = "Edit Part Notes"
NOTES_HINT = "Notes about this part, for example which variables to change and why."
NOTES_NOTE = "Plain text, saved in the part. Nothing in the notes runs, and links stay text."
# TR316 (D924)
HOLE_TABLE_TITLE = "Hole Table"
HOLE_TABLE_NOTE = "{count} holes and threads from the last rebuild. Lengths in {unit}."
HOLE_TABLE_EMPTY = "The part has no holes or threads. Add a Hole feature first."
HOLE_TABLE_COPY = "Copy"
HOLE_TABLE_SAVE = "Save CSV"
HOLE_TABLE_CLOSE = "Close"
HOLE_TABLE_FILTER = "CSV files (*.csv)"
HOLE_TABLE_COPIED = "The table is on the clipboard. Paste it into a spreadsheet."
HOLE_TABLE_SAVED = "Saved {name}."
HOLE_TABLE_FAILED = "The file could not be written: {reason}. Choose another folder."
HOLE_TABLE_WAIT = "Wait for the part to finish rebuilding, then open the Hole Table."
# TR236 (D922)
STEP_TITLE = "Step Through Values"
STEP_FROM = "From"
STEP_TO = "To"
STEP_COUNT = "Steps"
STEP_NOTE = "The sketch is solved at each value in turn, then goes back as it was."
STEP_POSITIVE = "Lengths must be above zero. Type larger values."
STEP_AT = "Step {k} of {n}: {value}"
STEP_DONE = "Every value solved. The sketch is back as it was."
STEP_FAILED = (
    "{count} values did not solve; the sketch is back as it was. "
    "Check the relations and dimensions that hold the moving items."
)
# TR235 (D921)
SHOW_FORMULAS = "Show Formulas on Dimensions"
# TR237 (D920)
EXPLAIN_RELATION = "Explain"
# TR204 (D918)
RECENT_SKETCH_TOOLS = "Recent Sketch Tools"
# TR313 (D917)
PREF_PICK_SIZE = "Pick distance"
PREF_PICK_SIZE_TIP = (
    "How close the cursor must be to a point, edge or vertex to pick it, "
    "in the 3D view and in sketches."
)
PICK_SIZES = {"small": "Small", "normal": "Normal", "large": "Large", "extra_large": "Extra large"}
# TR99 (D939)
PREF_ISOLATE_OTHERS = "Other bodies while isolating"
PREF_ISOLATE_OTHERS_TIP = (
    "How Isolate (I) draws the bodies you did not pick: hidden, see through or as edges only. "
    "They cannot be picked. Press I again to show them as normal."
)
ISOLATE_LOOKS = {"hidden": "Hidden", "transparent": "Transparent", "wireframe": "Wireframe"}
PREF_TREE_HOVER_TIP = "Draws the faces of the feature under the mouse in the feature tree."
# Custom properties (TR82, D810)
PROPS_TITLE = "Custom Properties"
PROPS_NAME = "Name"
PROPS_KIND = "Kind"
PROPS_VALUE = "Value"
PROPS_CONFIG = "In {name} only"
PROPS_RESULT = "Result"
PROPS_ADD = "Add"
PROPS_REMOVE = "Remove"
PROPS_WORK = "Work Out"
PROPS_HINT = (
    'A value starting with = is a formula, for example ="mass@Part" or ="volume@Part". '
    'Plain number rows can be used in equations as "Name@Properties".'
)
PROPS_KINDS = {"text": "Text", "number": "Number", "date": "Date", "yes_no": "Yes or No"}
PROPS_SEE_BELOW = "(see below)"
PROPS_UNDO = "Set Custom Properties"
# Esc stops long work (TR126, D814)
STOP_REBUILD = "Stop the rebuild? The part shows the last features that finished."
STOP_PREVIEW = "Stop working out the preview? The panel stays open."
PREVIEW_STOPPED = "Preview stopped. Change a value to see it again."
# Extrude along a direction (TR239, D815)
ALONG = "Along"
ALONG_TIP = (
    "The way the profile goes: square to the sketch, along a plane's normal or an axis, or "
    "along an edge picked in the view."
)
ALONG_NORMAL = "Square to the sketch"
ALONG_PICK = "An edge picked in the view..."
ALONG_EDGE = "Picked edge"
ALONG_PICK_EDGE = "Pick a straight edge for the direction."
DEPTH_MEASURED = "Depth measured"
DEPTH_ALONG = {"direction": "Along the direction", "normal": "Square to the sketch"}
# Sweep scale along the path (TR241, D816)
SWEEP_SCALE_START = "Scale at start"
SWEEP_SCALE_END = "Scale at end"
SWEEP_SCALE_LAW = "Scale change"
SWEEP_SCALE_LAWS = {"linear": "Even", "smooth": "Smooth"}
SWEEP_SCALE_TIP = (
    "The profile's size along the path, as factors of its drawn size. Not with a twist angle."
)
# Curve Through Points (TR61, D817)
GROUP_POINTS = "Points"
POINTS_TIP = (
    "Type X, Y and Z for each point in order, load them from a text file, or click vertices "
    "in the view (picked points win)."
)
POINTS_ADD = "Add"
POINTS_REMOVE = "Remove"
POINTS_LOAD = "Load File"
POINTS_RELOAD = "Reload"
POINTS_RELOAD_TIP = "Reads the same file again; the points are kept in the part."
POINTS_FILTER = "Point files (*.txt *.csv *.xyz);;All files (*)"
POINTS_NO_FILE = "No file was loaded. Click Load File first."
POINTS_FILE_FAILED = "The point file could not be read: {reason} Check the file."
POINTS_FRAME = "Frame"
POINTS_PART_AXES = "Part axes"
POINTS_PICK_TIP = "Vertices picked in the view, in order. Remove them to use the table."
POINTS_CLOSED = "Closed"
POINTS_NOT_NUMBERS = "Every point needs three numbers. Fix the table."
POINTS_NEED_TWO = "A curve needs at least two points. Add points."
POINTS_PICK_VERTICES = "Click vertices for the curve's points."
EDIT_SEED = "Edit Seed"  # TR142 (D1016): the feature a pattern copy came from
COPY_VALUES = "Copy Values"  # TR59 (D1900): the values of one pattern copy
REF_HOW_MANY = "How many"  # TR148 (D1925)
REF_HOW_MANY_TIP = (
    "Make several at once, each its own plane or point: the next ones are spaced by the "
    "same distance, angle or percent as the first, and follow it when it changes."
)
REF_POINT_SPACINGS = {
    "distance": "Spaced by the distance",
    "percent": "Spaced by the percent",
    "even": "Spread evenly over the curve",
}
REF_SERIES_UNDO = "Add {name} and more"
EXPLODE_PATTERN = "Explode Pattern"  # TR270 (D1902): one feature per copy
EXPLODE_PATTERN_UNDO = "Explode {name}"
ADD_TO_PATTERN = "Add to Pattern"  # TR399 (D1904): repeat at every copy
ARRAY_SQUARE_TO_FACE = "Square to face"  # TR373 (D1017)
ARRAY_SQUARE_TIP = (
    "Click the face the curve runs on: each copy keeps the face's normal as its up "
    "direction and the curve as its forward direction."
)
ARRAY_SQUARE_NEEDS_FACE = "Click the face to stay square to, or untick Square to face."
ARRAY_LAW = "Spacing law"  # TR366 (D1500)
ARRAY_LAW_TIP = (
    "Even spaces the copies equally. Growing makes each gap the growth ratio times the one "
    "before. Random moves each copy by up to a share of the gap. List of fractions places "
    "each copy at a typed share of the run."
)
ARRAY_RATIO_TIP = "Growth ratio: each gap is this times the one before, such as 1.2."
ARRAY_JITTER_TIP = "Random move: how far each copy may move, in percent of the gap."
ARRAY_SEED_TIP = "Random seed: the same number always gives the same layout."
ARRAY_FRACTIONS_TIP = (
    "One number per copy, such as 0.1, 0.3, 1: each copy sits at that share of the run."
)
# TR374 (D1011)
POINTS_EXPR = "{axis}(t)"
POINTS_EXPR_TIP = (
    "A formula in t, such as 10*cos(t). Plain numbers are in the part's unit; variables "
    "and functions work as in any value field."
)
POINTS_T_RANGE = "t from, to, points"
POINTS_FILL = "Fill Points"
POINTS_FILL_TIP = "Replaces the table with the points of X(t), Y(t) and Z(t) over the range of t."
POINTS_T_NOT_NUMBERS = "The start and end of t must be numbers. Type two numbers."
POINTS_EXPR_FAILED = "The points could not be made: {reason}"
# Saved measurements (TR190, TR191, D818)
MEASURE_KEEP = "Keep"
MEASURE_KEEP_TIP = (
    "Saves this measurement in the part: it measures again after each change, shows a label, "
    "and formulas can use it."
)
MEASURE_KEEP_PICKS = "Pick one or two items to keep, or none for the whole part."
MEASURE_KEPT = 'Kept as {name}. Formulas can use its values, for example "distance@{name}".'
# Show Types (TR215, D819)
SHOW_TYPES = "Show Types"
SHOW_TYPE_NAMES = {
    "planes": "Planes",
    "axes": "Axes",
    "points": "Points",
    "frames": "Coordinate Systems",
    "curves": "Curves",
}
HIDE_ALL_TYPES = "Hide All Types"
# Errors table (TR202, D820)
ERRORS_KIND = "Kind"
ERRORS_FEATURE = "Feature"
ERRORS_MESSAGE = "Message"
ERRORS_SHOW_ERRORS = "Show Errors"
ERRORS_SHOW_WARNINGS = "Show Warnings"
# Table Driven Pattern (TR58, D821)
TABLE_USE = "Use"
TABLE_PASTE = "Paste"
TABLE_SAVE = "Save File"
TABLE_FILTER = "Table files (*.txt *.csv);;All files (*)"
# Select Loop and Select Tangent (TR92, D823)
SELECT_LOOP = "Select Loop"
START_PARTIAL_LOOP = "Start Partial Loop"
END_PARTIAL_LOOP = "End Partial Loop Here"
SELECT_TANGENT = "Select Tangent"
LOOP_SELECTED = "{n} edges selected. Choose Select Loop again for the loop on the next face."
PARTIAL_LOOP_STARTED = "Right click the last edge and choose End Partial Loop Here."
TANGENT_SELECTED = "{n} items joined smoothly are selected."
# Thin feature auto fillet (TR65, D824)
FIELD_AUTO_FILLET = "Auto fillet corners"
# Offset Body and Shell corners (TR129, D825)
SHELL_CORNERS = "Corners"
SHELL_CORNERS_TIP = (
    "How the wall's corners join. Automatic: sharp, or rounded where sharp corners fail."
)
SHELL_CORNER_CHOICES = {None: "Automatic", "sharp": "Sharp", "rounded": "Rounded"}
# Export Configurations (TR196, D827)
EXPORT_CONFIGS_TITLE = "Export Configurations"
EXPORT_CONFIGS_KINDS = {"step": "STEP", "stl": "STL", "3mf": "3MF", "fdprt": "Part files"}
EXPORT_CONFIGS_KIND = "Files"
EXPORT_CONFIGS_FOLDER = "Folder"
EXPORT_CONFIGS_BROWSE = "Browse"
EXPORT_CONFIGS_NONE = "Tick at least one configuration and choose a folder."
EXPORT_CONFIGS_DONE = "{n} configurations exported to {folder}."
EXPORT_CONFIGS_SOME = (
    "{done} configurations exported; {failed} could not be. See Export log.txt in the folder."
)
# Relations and dimensions switched off (TR109, D829)
TURN_OFF = "Turn Off"
TURN_ON = "Turn On"
SWITCHED_OFF = "(off)"
# Right click to move on (TR207, D831)
NEXT_PICK_BOX = "Now picking: {name}. Right click again for the next box, or OK and Cancel."
# Rotate about a picked item (TR209, D832)
PREF_TURN_STYLE = "Turn style"  # TR415 (D1001)
PREF_TURN_STYLE_TIP = (
    "How dragging with the middle button turns the view. Turntable keeps the model's Z axis "
    "pointing up. Arcball rolls the model like a ball under your pointer."
)
PREF_TURN_STYLES = {"free": "Free", "turntable": "Turntable (Z stays up)", "arcball": "Arcball"}
TURN_CENTRE_SET = "The view now turns about the clicked point. Middle click off the part to undo."
TURN_CENTRE_CLEARED = "The view turns about its centre again."
# Part templates (TR217, D833)
TEMPLATE_NONE = "No template"
TEMPLATE_LABEL = "Or start from a template (its units, variables, colour and settings):"
TEMPLATE_SAVE = "Save as Template"
TEMPLATE_ASK = "Template name:"
TEMPLATE_SAVED = "Template {name} saved. New Part offers it."
TEMPLATE_FAILED = "The template could not be used: {reason}. Choose another name or template."
# Round All Corners (TR227, D834)
ROUND_ALL_TITLE = "Round All Corners"
ROUND_ALL_RADIUS = "Radius"
ROUND_ALL_CORNER = "Corner"
ROUND_ALL_OWN = "Own radius"
ROUND_ALL_HINT = "Leave a corner's own radius empty to use the radius above."
ROUND_ALL_BAD = "A radius is not a length: {reason}. Type a length such as 2 or 2mm."
ROUND_ALL_NONE = "The selected lines have no corners. Select lines that meet end to end."
ROUND_ALL_DONE = "{n} corners rounded."
ROUND_ALL_SKIPPED = "Not rounded: {which}."
# Pause Rebuilds and checkpoints (TR276, D835)
PAUSE_ON = "Rebuilds are paused. Edits are collected until you choose Rebuild."
PAUSE_OUT_OF_DATE = (
    "Out of date: rebuilds are paused. Choose Rebuild, Rebuild and Stay Paused, or Discard "
    "Paused Edits."
)
CHECKPOINT_STOPPED = (
    "The rebuild stopped after checkpoint {name}. Choose Continue Rebuild to go on."
)
CHECKPOINT_SET = "Checkpoint"
CHECKPOINT_UNDO = "Set Checkpoint"
# Replace a reference everywhere (TR277, D838)
REPLACE_EVERYWHERE = "Replace Everywhere"
REPLACE_INSTEAD = "Replace Instead"
REPLACE_INTRO = "Every feature that uses {name} will use this instead:"
REPLACE_DELETE_OLD = "Delete the old one"
REPLACE_UNDO = "Replace {name} Everywhere"
REPLACE_DONE = "{n} features now use {name}."
REPLACE_NO_USERS = "No feature uses {name}. Pick an item that other features use."
REPLACE_NONE = (
    "There is no item of the same kind above the features that use {name}. Make one first."
)
# Airfoil profile (TR257, D839)
AIRFOIL_TITLE = "Airfoil"
AIRFOIL_CODE = "Code or file"
AIRFOIL_LOAD = "Load File"
AIRFOIL_CHORD = "Chord"
AIRFOIL_ANGLE = "Angle"
AIRFOIL_EDGE = "Trailing edge"
AIRFOIL_CLOSED = "Close the trailing edge"
AIRFOIL_FAILED = "The airfoil could not be made: {reason}. Check the values."
# A depth per region (TR242, D842)
REGIONS_OWN_DEPTH = "Own depth per region"
REGIONS_OWN_DEPTH_TIP = (
    "Give each picked region its own depth. Leave a depth empty to use the depth above."
)
REGIONS_COLUMN = "Region"
REGIONS_DEPTH = "Depth"
REGIONS_BAD_DEPTH = "Region {number}: the depth is not a length: {reason} Type a length."
# Pierce (TR101, D843)
PIERCE = "Pierce"
PIERCE_REMOVE = "Remove Pierce"
PIERCE_ASK = "Keep the point where this curve crosses the sketch plane:"
PIERCE_NONE = "There is no curve or other sketch above this sketch. Make the curve first."
PIERCE_SET = "The point follows where {name} crosses the sketch plane after you exit the sketch."
# Cut away while sketching (TR113, D844)
CUT_AWAY_ON = "The part in front of the sketch plane is hidden while you sketch. Display only."
CUT_AWAY_OFF = "The whole part shows behind the sketch again."
# Derived sketch (TR49, D845)
DERIVED_TITLE = "Derived Sketch"
DERIVED_ASK = "Put the linked copy on this plane:"
DERIVED_PLACE = "Edit Placement"
DERIVED_ANGLE = "Angle"
DERIVED_BREAK = "Break Link"
DERIVED_NO_EDIT = (
    "This sketch is a linked copy and cannot change shape. Use Edit Placement to move it, "
    "or Break Link to edit it."
)
# Replace Entity (TR104, D846)
REPLACE_ENTITY = "Replace First with Second"
REPLACE_ENTITY_KEEP = "Replace, Keep First as Construction"
REPLACE_ENTITY_DONE = "Replaced. Features that used the old curve now use the new one."
REPLACE_ENTITY_DROPPED = "These did not fit the new curve and were removed: {which}."
# Segment a curve (TR103, D847)
SEGMENT = "Segment"
SEGMENT_POINTS = "Equally Spaced Points"
SEGMENT_ASK = "Number of equal pieces:"
SEGMENT_POINTS_ASK = "Number of equal spaces (the points go between them):"
SEGMENT_DONE = "Split into {n} equal parts."
# Snap to grid, steps and the snap filter (TR102, D860)
PREF_GRID_SNAP = "Snap to grid"
PREF_GRID_SNAP_CHOICES = {"off": "Off", "shown": "While the grid shows", "always": "Always"}
PREF_LENGTH_STEP = "Length step"
PREF_ANGLE_STEP = "Angle step"
PREF_STEPS_TIP = "Hold Alt while drawing to step the length and angle from the last click."
PREF_GRID_KIND = "Grid"  # TR238 (D1014)
PREF_GRID_KINDS = {"square": "Square", "polar": "Polar (rings and spokes)"}
PREF_POLAR_ANGLE = "Polar grid angle"
PREF_POLAR_ANGLE_TIP = (
    "The angle between the spokes of the polar grid. Its rings follow the grid spacing."
)
SNAP_ONLY = "Snap Next Click To"
SNAP_ONLY_CHOICES = {
    "point": "End Point",
    "midpoint": "Midpoint",
    "center": "Centre",
    "on_curve": "Nearest",
}
GRID_SPACING = "Grid Spacing"
GRID_SPACING_ASK = "Major grid spacing for this part (0 for automatic):"
GRID_MINOR_ASK = "Minor lines between major lines:"
# Property panel behaviour (TR206, D861)
PANEL_PIN = "Pin"
PANEL_PIN_TIP = "Pin: keep making this feature. After OK, the same command starts again."
PICK_DELETE = "Delete"
PICK_CLEAR = "Clear Selections"
# Undercut analysis (TR83, D864)
UNDERCUT_TITLE = "Undercut Analysis"
UNDERCUT_DIRECTION = "Pull direction"
UNDERCUT_REVERSE = "Reverse"
UNDERCUT_GROUPS = {
    "above": "Seen from above",
    "below": "Seen from below",
    "straddle": "Straddle",
    "undercut": "Undercut (hidden from both)",
    "side": "Side wall",
}
UNDERCUT_ZOOM = "Zoom"
UNDERCUT_ZOOM_TIP = "Selects the faces of this group and zooms to them."
UNDERCUT_DONE = "{n} undercut faces for a pull along {direction}."
UNDERCUT_NOTHING = "There is no part to analyse. Build a part first."
UNDERCUT_NO_DIRECTION = "Choose a plane whose normal is the pull direction."
UNDERCUT_NONE_IN_GROUP = "No face is in that group. Choose another group."
UNDERCUT_FAILED = "The undercut analysis failed: {reason}. Try another direction."
# Gear and sprocket profiles (TR161, D866)
GEAR_TITLE = "Gear"
GEAR_KIND = "Kind"
GEAR_KINDS = {
    "spur": "Spur gear",
    "internal": "Internal gear (the hole)",
    "sprocket": "Chain sprocket",
    "pulley": "Timing pulley",  # TR348 (D2007)
}
GEAR_SIZE_BY = "Size by"
GEAR_MODULE = "Module (mm)"
GEAR_DP = "Diametral pitch (teeth per inch)"
GEAR_SIZE = "Module or pitch"
GEAR_TEETH = "Teeth"
GEAR_PRESSURE = "Pressure angle"
GEAR_SHIFT = "Profile shift"
GEAR_FILLET = "Rounded roots"
GEAR_CHAIN = "Chain"
GEAR_FILLET_RADIUS = "Root fillet radius"  # TR348 (D2007)
GEAR_FILLET_AUTO = "Automatic"
GEAR_BELT = "Belt"
# Ratio and difference relations (TR226, D870)
RELATION_NAMES.update(
    {
        "length_ratio": "Length Ratio",
        "length_difference": "Length Difference",
        "equal_angle": "Equal Angle",
        "equal_distance": "Equal Distance",
    }
)
# Result line after each command (TR290, D878)
CHANGE_LINE = "{name} {what}."
CHANGE_ADDED = "added {v:.3g} {unit}"
CHANGE_REMOVED = "removed {v:.3g} {unit}"
CHANGE_FACES_MORE = "{n} more faces"
CHANGE_FACES_LESS = "{n} fewer faces"
CHANGE_AND = ", "
CHANGE_NONE = "{name} built; the solid did not change."
# A failed feature leaves the part as it was. It used to read as CHANGE_NONE (D1041).
CHANGE_ERROR = (
    "{name} failed: the part is unchanged. Open the Errors tab for the reason and what to do."
)
# Results that did not rebuild (TR352, D881)
STALE_RESULTS = (
    "Out of date: {name} failed, so later features built on the part from before it. "
    "Fix {name} to measure the real part."
)
# Expected value checks (TR359, D889)
CHECKS_TITLE = "Expected Values"
CHECKS_UNDO = "Change Expected Values"
CHECKS_COLUMNS = ("Check", "Expected", "Tolerance", "Actual", "Result")
CHECKS_ADD = "Add"
CHECKS_REMOVE = "Remove"
CHECKS_USE_CURRENT = "Use Actual Values"
CHECKS_USE_CURRENT_TIP = "Copy every actual value into its expected value."
CHECKS_BAD_ROW = "Row {row}: the expected value is not a number. Type a number."
CHECKS_STATUS = "Checks: {passed} of {count} pass."
CHECK_PASS = "Pass"
CHECK_FAIL = "Fail"
CHECK_KINDS = {
    "volume": "Volume (mm3)",
    "size_x": "Size X (mm)",
    "size_y": "Size Y (mm)",
    "size_z": "Size Z (mm)",
    "faces": "Face count",
    "holes": "Hole count",
    "measurement": "Measurement",
}
# Switch between boss and cut (TR387, D890)
SWITCH_TO_CUT = "Switch to Cut"
SWITCH_TO_BOSS = "Switch to Boss"
SWITCH_TO_THIN = "Make Thin"
SWITCH_FROM_THIN = "Make Solid"
# Select bodies by size (TR70, D894)
BODY_SIZE_TITLE = "Select Bodies by Size"
BODY_SIZE_LIMIT = "Size limit"
BODY_SIZE_SIDE = "Bodies"
BODY_SIZE_SMALLER = "Smaller than the limit"
BODY_SIZE_LARGER = "Larger than the limit"
BODY_SIZE_WORKING = "Measuring the bodies..."
BODY_SIZE_COUNT = "{n} of {total} bodies (limit: {percent} percent of the largest body)."
BODY_SIZE_BUTTONS = {"select": "Select", "delete": "Delete", "keep": "Keep Only These"}
BODY_SIZE_EMPTY = "The part has no bodies yet. Build the part first."
BODY_SIZE_FAILED = "The bodies could not be measured ({reason}). Rebuild and try again."
# Modify Sketch (TR50, D895)
MODIFY_SKETCH_TITLE = "Modify Sketch"
# Convex Hull (TR229, D912)
HULL_TITLE = "Convex Hull"
# TR147 (D998)
SHELL_CHECK = "Check Walls"
SHELL_CHECK_TIP = (
    "Find the faces that bend too tightly for the wall thickness, and the smallest bend "
    "radius, before building."
)
SHELL_CHECK_WORKING = "Checking the faces."
SHELL_CHECK_NEEDS = "Enter a wall thickness above zero, then check again."
SHELL_CHECK_FAILED = "The check could not run ({reason}). Rebuild the part and check again."
SHELL_CHECK_TIGHT = (
    "{count} faces bend tighter than the {wall} wall (smallest radius {radius}): {names}. "
    "Use a thinner wall, or remove or round those faces."
)
SHELL_CHECK_FITS = "Every face fits the {wall} wall. The tightest bend has a {radius} radius."
SHELL_CHECK_FLAT = "No face bends toward the wall, so a {wall} wall fits everywhere."
# TR64 (D997)
FIELD_OMIT_ATTACH = "Omit attach edges"
FIELD_OMIT_ATTACH_TIP = (
    "For a picked feature: round only its own edges and leave sharp the edges where it "
    "meets the rest of the part."
)
# TR323 (D1419)
DRAFT_ANGLE_MODES = {"absolute": "Angle from the pull", "relative": "Angle added to the lean"}
DRAFT_ANGLE_MODE_TIP = (
    "From the pull: every face ends at the angle. Added to the lean: a flat face that "
    "already leans tilts by the angle more."
)
DRAFT_SPLIT = "Other angle below the neutral plane"
DRAFT_SPLIT_TIP = "Faces below the neutral plane tilt by this angle instead."
DRAFT_SPLIT_BAD = "The angle below the neutral plane is not valid. Enter an angle."
# TR147 (D1418)
FIELD_ALLOW_REDUCED = "Allow reduced angle"
FIELD_ALLOW_REDUCED_TIP = (
    "When the full angle fails, draft at the largest angle that works and say which angle was used."
)
# TR164 (D1417)
FIELD_DETAILED_PREVIEW = "Detailed preview"
FIELD_DETAILED_PREVIEW_TIP = (
    "Show the whole result with the faces the feature adds in one colour and the faces it "
    "changes in another. When it makes new bodies, only those show."
)
# TR87 and TR262 (D1416)
CHECK_CURVE_LABEL = "Bend radius below"
CHECK_KNIFE_LABEL = "Knife edge below"
CHECK_SMOOTH_LABEL = "Nearly smooth within"
CHECK_SQUARE_LABEL = "Nearly square within"  # TR262 (D2303)
CHECK_CLIP = "Clip around each finding"
CHECK_CLIP_TIP = (
    "While you step with Next and Back, hide everything outside a box round the finding, "
    "so a finding inside the part can be seen. Turn it off to see the whole part again."
)
CHECK_TURNED = "{name} turns the face to close the angle. Check Again to see what is left."
CHECK_BACK = "Back"
CHECK_NEXT = "Next"
CHECK_FIX = "Fix"
CHECK_FIX_TIP = (
    "Remove a sliver or duplicate face with a new Delete Face feature, heal an edge "
    "with a gap with a new Heal Edges feature, or turn a flat face with a new Move Face "
    "feature so a nearly smooth or nearly square edge becomes exact. Undo takes it back."
)
CHECK_IGNORE = "Ignore"
CHECK_IGNORE_TIP = "Hide this finding until the part is opened again."
CHECK_NO_FIX = "This finding has no fix. Change the feature that made it."
CHECK_FIXED = "{name} removes the face. Check Again to see what is left."
CHECK_SYMMETRY = "Symmetry Check"
CHECK_SYMMETRY_TIP = (
    "Select a flat face first: tells if the part is the same on both sides of its plane."
)
CHECK_SYMMETRY_PICK = "Select a flat face in the view first, then click Symmetry Check."
CHECK_SYMMETRY_FACE = "Face {k} has no matching face on the other side of the plane."
CHECK_SYMMETRIC = "The part is the same on both sides of the plane."
CHECK_NOT_SYMMETRIC = (
    "{count} faces differ from the other side of the plane. Click one to highlight it."
)
# TR84 (D1415)
PARTING_LINE = "Parting Line"
PARTING_LINE_TIP = (
    "Finds the edges where faces turn from positive to negative draft for the pull direction, "
    "and keeps them as a curve."
)
PARTING_LINE_DIRECTION = "Pull direction"
PARTING_LINE_REVERSE = "Reverse"
# TR60 (D1414)
SPLIT_LINE = "Split Line"
SPLIT_LINE_TIP = "Divide faces into regions with new edges. The volume does not change."
SPLIT_LINE_METHOD = "Method"
SPLIT_LINE_METHODS = {
    "projection": "Projection",
    "intersection": "Intersection",
    "silhouette": "Silhouette",  # TR60 (D1810)
}
SPLIT_LINE_FACES = "Faces to split"
SPLIT_LINE_FACES_TIP = "The faces the new edges divide."
SPLIT_LINE_SKETCH = "Sketch"
SPLIT_LINE_SKETCH_TIP = "Its curves are projected onto the faces along the sketch normal."
SPLIT_LINE_REVERSE = "Reverse"
SPLIT_LINE_BOTH = "Both directions"
SPLIT_LINE_PLANE = "Plane"
SPLIT_LINE_PLANE_TIP = (
    "Click this list, then a flat face: the faces are split where its plane crosses them."
)
# TR267 (D1413)
PUSH_PULL = "Push Pull"
PUSH_PULL_TIP = "A positive distance adds material and a negative one cuts."
PUSH_PULL_FACES = "Faces"
PUSH_PULL_FACES_TIP = "Flat faces to move. Every face takes the same distance."
PUSH_PULL_SKETCH = "Sketch region"
PUSH_PULL_SKETCH_TIP = "A closed sketch on a face: its regions are pushed out or cut in."
PUSH_PULL_DISTANCE = "Distance"
PUSH_PULL_SYMMETRIC = "Symmetric"
PUSH_PULL_SYMMETRIC_TIP = "Push the sketch region half each way from its sketch."
PUSH_PULL_TARGET = "Up to face"
PUSH_PULL_TARGET_TIP = "A parallel face: the distance is measured to it."
PUSH_PULL_NEXT = "Next Parallel Face"
PUSH_PULL_NEXT_TIP = (
    "Make the next face parallel to the first picked face the target, nearest first."
)
PUSH_PULL_PICK_FIRST = "Pick a flat face to push or pull first."
PUSH_PULL_NO_PARALLEL = "No other face is parallel to the picked face. Type a distance instead."
PUSH_PULL_NEEDS = "Pick flat faces, or choose a sketch on a face."
# TR130 (D1412)
REPLACE_FACE = "Replace Face"
REPLACE_FACE_TIP = (
    "Swap faces for a flat target: the body under them is extended or trimmed up to the target."
)
REPLACE_FACE_FACES = "Faces to replace"
REPLACE_FACE_FACES_TIP = "The faces to swap for the target, for example a bumpy imported face."
REPLACE_FACE_TARGET = "Target"
REPLACE_FACE_TARGET_TIP = "A flat face or plane the body should end at."
REPLACE_FACE_NEEDS_TARGET = "Pick a flat face or a plane as the target."
# TR322 (D1411)
FIELD_SHELL_BOTH = "Both sides"
FIELD_SHELL_BOTH_TIP = "Half the wall inside the part and half outside, centred on its faces."
# TR260 (D1410)
REMOVE_FILLETS = "Remove Fillets"
REMOVE_FILLETS_GROUP = "Rounds"
REMOVE_FILLETS_TIP = (
    "Rounds on a body with no history: the picked round faces, or every round in the radius "
    "range. They are removed smallest first, a few at a time."
)
REMOVE_FILLETS_FACES = "Round faces"
REMOVE_FILLETS_FACES_TIP = "Click round faces to treat only those. Leave empty to find them."
REMOVE_FILLETS_RANGE = "Radius range"
REMOVE_FILLETS_RESIZE = "Make again at a new radius"
REMOVE_FILLETS_RESIZE_TIP = "Round the edges again at the new radius after removing the rounds."
REMOVE_FILLETS_ADD = "Add Remove Fillets"
REMOVE_FILLETS_FOUND = "{count} rounds in this range on the part."
# TR29 (D1409)
HOLD_METHODS = {"radius": "Radius", "hold_line": "Hold Line"}
HOLD_METHOD_TIP = (
    "Radius: one radius. Hold Line: the round meets a face set along picked edges, so its "
    "size follows the gap."
)
HOLD_LINES_TIP = "While Pick Hold Lines is pressed, edges you click become the hold line."
HOLD_PICK = "Pick Hold Lines"
HOLD_NEEDED = "Pick the hold line edges the round should follow, or choose the Radius method."
# TR320 (D1408)
RULE_CHOICES = {
    "attach": "Attach Edges",
    "free": "Free Edges",
    "feature": "Feature Edges",
    "parallel": "Edges Parallel to {axis}",
}
RULE_LABELS = {
    "attach": "Attach edges of {feature}",
    "free": "Free edges of {feature}",
    "feature": "Edges of {feature}",
    "parallel": "Edges of {feature} parallel to {axis}",
}
RULE_EXCLUDED = " (less {count})"
RULE_TIP = (
    "A rule finds its edges again after changes: where the feature in the scope list meets "
    "the earlier body, its other edges, all its edges, or straight edges parallel to an axis."
)
RULE_ADD = "Add Rule"
RULE_OWN_RADIUS = "Own radius"
RULE_OWN_RADIUS_TIP = "Give the next rule you add its own radius instead of the fillet radius."
RULE_PICK_EXCLUDE = "Pick Exclusions"
RULE_PICK_EXCLUDE_TIP = (
    "While pressed, edges you click are left out of the rule selected in the list."
)
RULE_NEEDS_FEATURE = "This rule needs a feature. Choose a feature in the scope list first."
RULE_SELECT_FIRST = "Select a rule in the items list first, then click the edges to leave out."
# TR271 (D1407)
GROUP_FILLET_LIMITS = "Limits"
LIMIT_GROUP_TIP = "Edges a round may not swallow, and a plane where the rounds stop."
LIMIT_KEEP_LABEL = "Edges to keep"
LIMIT_KEEP_TIP = (
    "While Pick Kept Edges is pressed, edges you click are protected instead of rounded."
)
LIMIT_PICK_KEEP = "Pick Kept Edges"
LIMIT_PLANE_LABEL = "Limiting plane"
LIMIT_PLANE_TIP = "While Pick Limit is pressed, the flat face you click sets where the rounds stop."
LIMIT_PICK_PLANE = "Pick Limit"
LIMIT_FLIP = "Keep the other side"
LIMIT_FLIP_TIP = "Round the part of each edge in front of the plane instead of behind it."
LIMIT_NOT_FLAT = "The limiting face must be flat. Pick a flat face or a plane."
# TR278 (D1406)
RESET_SKIPPED = "Reset Skipped Faces"
# TR346 (D1405)
SPLIT_FILLET_UNDO = "Split {name}"
SPLIT_FILLET_IN_PANEL = "To split the fillet, click OK, then click the fix in the errors panel."
# TR132 (D1404)
CHANGE_FILLET_EDGE = "Change Fillet Edge"
CHANGE_FILLET_EDGE_INTRO = "Give this edge of {name} its own radius, or remove it from the fillet."
CHANGE_FILLET_RADIUS = "Radius"
CHANGE_FILLET_REMOVE = "Remove from Fillet"
CHANGE_FILLET_REMOVE_TIP = "Take this edge out of the fillet. The edge goes back to sharp."
CHANGE_FILLET_BAD_VALUE = "The value is not valid. Enter a number or an expression."
CHANGE_FILLETS = "Change Fillets"
CHANGE_FILLETS_COLUMNS = ("Fillet", "Radius", "Picked edges")
CHANGE_FILLETS_FROM = "Radius from"
CHANGE_FILLETS_TO = "Radius to"
CHANGE_FILLETS_NEW = "New radius"
CHANGE_FILLETS_APPLY = "Apply to Listed"
CHANGE_FILLETS_NONE = "No fillet has a radius in this range. Change the range."
CHANGE_DRAFTS = "Change Drafts"
CHANGE_DRAFTS_COLUMNS = ("Draft", "Angle", "Pull direction")
CHANGE_DRAFTS_ANGLE = "New angle"
CHANGE_DRAFTS_SET = "Set Angle"
CHANGE_DRAFTS_REMOVE = "Remove Selected"
CHANGE_DRAFTS_PICK = "No draft is selected. Select drafts in the list first."
# TR133 (D1403)
FILLET_POINT_AT = "Point {j} at (%)"
FILLET_POINT_AT_TIP = "Where this control point sits on each edge, in percent of the edge length."
FILLET_ADD_POINT = "Add Point"
FILLET_ADD_POINT_TIP = "Add a control point in the middle of the widest gap between points."
FILLET_DELETE_POINT = "Delete Point"
FILLET_DELETE_POINT_TIP = (
    "Delete the control point with this number. Later points move up one place."
)
# TR62 (D1402)
FILLET_METHODS = {"radius": "Radius", "asymmetric": "Asymmetric", "chord": "Chord Width"}
FILLET_PROFILES = {
    "circular": "Circular",
    "conic": "Conic",
    "curvature": "Curvature Continuous",
    "elliptic": "Elliptic",
}
FILLET_METHOD_TIP = (
    "Radius: one radius. Asymmetric: a distance on each face. Chord Width: the straight "
    "width across the round."
)
FILLET_PROFILE_TIP = (
    "The shape across the round. Conic and Curvature Continuous (and Asymmetric) work on "
    "straight edges between flat faces."
)
FILLET_DISTANCE1_TIP = "The distance the round reaches along the first face."
FILLET_DISTANCE2_TIP = "The distance the round reaches along the second face."
FILLET_CHORD_TIP = (
    "The straight width across the round, between the lines where it meets the faces."
)
FILLET_RHO_TIP = "Conic shape, 0.05 to 0.95: small is flat, large is close to the sharp corner."
FILLET_REVERSE = "Reverse distances"
FILLET_REVERSE_TIP = "Swap which face takes the first distance."
# TR64 item 5 (D1401)
PARTIAL_ENDS_LABEL = "Start and end: click two vertices, or press Pick Ends and click flat faces."
PARTIAL_ENDS_TIP = "The first pick sets the start of the range on each edge, the second the end."
PARTIAL_ENDS_FACES = "Pick Ends"
PARTIAL_ENDS_FACES_TIP = (
    "While pressed, flat faces you click set an end instead of being added as items."
)
PARTIAL_ENDS_FULL = "Start and end are both picked. Remove one to pick another."
PARTIAL_ENDS_NEEDED = "Pick a start and an end for the partial range."
# TR131 (D1400)
FIELD_TANGENT_PROPAGATION = "Tangent propagation"
FIELD_TANGENT_PROPAGATION_TIP = (
    "On: edges joined smoothly to a picked edge are included. Off: only the picked edges, "
    "and each one stops square where a smooth edge joins it."
)
# TR134 (D994)
SWAP_TO_CHAMFER = "Change to Chamfer"
SWAP_TO_FILLET = "Change to Fillet"
SWAP_KIND_UNDO = "Change Kind of {name}"
SWAP_KIND_DONE = "{name} keeps its edges and size. Undo changes it back."
SWAP_KIND_CHILDREN = "Features after it that used its faces may need their picks again."
# TR122 (D986)
MERGE_SKETCH = "Merge Into Sketch..."
MERGE_SKETCH_TITLE = "Merge Sketches"
MERGE_SKETCH_PROMPT = "Merge this sketch into:"
MERGE_SKETCH_USED = (
    "{name} is used by a feature, so it cannot be merged away. Merge the other sketch into "
    "{name} instead."
)
MERGE_SKETCH_NONE = "No other sketch is on the same plane as {name}. Draw one there first."
MERGE_SKETCH_DONE = "{name} was merged into {target}. Undo brings it back."
# TR158 (D983)
REMOVE_HISTORY_TITLE = "Remove History"
REMOVE_HISTORY_PROMPT = (
    "Replace the {count} features of this part with one plain body? The shape stays, but "
    "the features, sketches and their values are gone. Undo brings them back."
)
REMOVE_HISTORY_NOTHING = "There is no built body to keep. Build the part first."
REMOVE_HISTORY_FAILED = (
    "The body could not be written as a plain body. Rebuild the part and try again."
)
REMOVE_HISTORY_DONE = "The part is now one plain body. Undo brings the features back."
REMOVE_HISTORY_NAME = "Body"
# TR389 (D982)
LAYERS = "Layers"
LAYER_NAME_PROMPT = "Name of the new layer:"
LAYER_COLOUR = "Layer Colour"
LAYER_STYLE_PROMPT = "Line style of the layer:"
LAYER_STYLES = {"solid": "Solid", "dashed": "Dashed"}
LAYER_SHOWN = "Show {name}"
LAYER_NEW = "New Layer..."
LAYER_PUT_ON = "Put on {name}"
LAYER_TAKE_OFF = "Take Off Layer"
LAYER_DELETE = "Delete Layer {name}"
LAYER_PICK = "Pick {name}"
LAYER_LOCK = "Lock {name}"
LAYER_LOCKED = (
    "This curve is on a locked layer, so it does not move. Untick Lock in the Layers menu."
)
LAYER_MADE = "Layer {name} made. Right click for Layers to show, hide or fill it."
# TR193 (D978)
LINK_VALUES = "Link Values"
UNLINK_VALUES = "Unlink Values"
LINK_NAME_PROMPT = "Shared name for these values:"
LINKED = "{count} dimensions now share {name}. Change any one and the others follow."
UNLINKED = "{count} dimensions are no longer linked. They keep their values."
# TR123 (D974)
SELECT_PLANE_FOR_TOOL = (
    "Select a plane or flat face to draw a {tool} on. The sketch opens there with the tool "
    "ready; press Esc to cancel."
)
# TR153 (D972)
BODY_HISTORY = "Feature History"
BODY_HISTORY_TITLE = "Feature History of Body {index}"
BODY_HISTORY_HELP = (
    "The features that made this body, in build order. Click one to find it in the tree."
)
BODY_HISTORY_NONE = "No feature history was found for body {index}. Rebuild the part and try again."
# TR356 (D971)
VIEW_ONLY_BAR = (
    "{name} is open for viewing only: turn, zoom and measure as you like. Click Edit to change it."
)
VIEW_ONLY_EDIT = "Edit"
VIEW_ONLY_BLOCKED = (
    "{name} is open for viewing only, so the change was not made. Click Edit on the bar above "
    "the view first."
)
VIEW_ONLY_TAB = "{name} (view only)"
# TR372 (D970)
SHAKE_TITLE = "Shake Sketch"
SHAKE_MOVED = (
    "{count} items can still move: they are picked. Add relations or dimensions to hold them."
)
SHAKE_STILL = "Nothing moved: every point is held. The sketch is fully defined where it counts."
LOCK_POINTS = "Lock All Points"
POINTS_LOCKED = "All points are locked, so dragging moves nothing. Untick Lock All Points to drag."
POINTS_UNLOCKED = "Points can be dragged again."
# TR220 (D968)
LOW_DISK = (
    "Only {mb} MB is free on the disk of {where}. Save your parts now, then free some space "
    "so saves and recovery copies do not fail."
)
LOW_MEMORY = (
    "Only {mb} MB of memory is free. Save your parts now, then close other programs or parts "
    "so FDCAD does not run out."
)
SAVE_ALL_BUTTON = "Save All"
# TR111 (D965)
MADE_REFERENCE = "{count} dimensions are reference dimensions now. They measure only."
MADE_DRIVING = (
    "{count} dimensions drive the sketch now. Any that would over define it stay reference."
)
REFERENCE_MODE = "New Dimensions Are Reference"
REFERENCE_MODE_ON = (
    "New dimensions are reference dimensions: they measure only. Untick New Dimensions Are "
    "Reference in the right click menu to drive the sketch again."
)
REFERENCE_MODE_OFF = "New dimensions drive the sketch again. Type a value to set a size."
# TR341 (D964)
SKETCH_DISPLAY = "Show in Sketch"
SHOW_OPEN_ENDS = "Open Ends"
SHOW_CROSSINGS = "Crossings and Forks"  # TR238 (D987)
SHOW_DRIVING = "Driving Dimensions"
SHOW_REFERENCE = "Reference Dimensions"
SHOW_TAGS_OF = "{kind} Tags"
TAG_SIZES = {1.0: "Normal Tags", 1.3: "Large Tags"}
LINE_WEIGHTS = {  # TR341 (D1013)
    0.75: "Thin Lines",
    1.0: "Normal Lines",
    1.5: "Bold Lines",
    2.0: "Extra Bold Lines",
}
# TR221 (D963)
RECENTLY_EDITED = "Recently Edited"
PREF_NAME_NEW = "Name new features as they are made"
PREF_NAME_NEW_TIP = (
    "After OK on a new feature, its name in the feature tree is ready to type over. Press "
    "Enter to keep the name or Esc to leave it."
)
# TR142 (D962)
LARGE_PATTERN_TITLE = "Large Pattern"
LARGE_PATTERN_PROMPT = (
    "{name} makes {count} copies, which can take a long time to build. Build it anyway? "
    "Press No to change the count."
)
# TR218 (D961)
SAVE_ALL_DONE = "{count} parts saved."
SAVE_ALL_NOTHING = "Every open part is saved already. Nothing to do."
REVERT_TITLE = "Revert to Saved"
REVERT_PROMPT = "Throw away the changes to {name} since it was last saved? This cannot be undone."
REVERT_NOT_SAVED = "{name} was never saved, so there is nothing to go back to. Save it first."
REVERT_CLEAN = "{name} has no changes since it was saved. Nothing to revert."
PREF_REOPEN = "Open the parts from last time at start"
PREF_SIMPLIFY_THREADS = "Simplify threads while editing"  # TR347 (D1921)
PREF_SIMPLIFY_THREADS_TIP = (
    "Modelled threads show as cosmetic threads while you edit, which rebuilds much faster. "
    "Force Rebuild models them for exporting and printing. A part can keep its "
    "own setting."
)
PREF_REOPEN_TIP = (
    "When FDCAD starts without a file to open, it opens the saved parts that were open when "
    "it closed."
)
PREF_BACKUPS = "Older copies to keep"
PREF_BACKUPS_TIP = (
    "Each save first keeps the old file as a numbered copy. 0 keeps none. The oldest copy "
    "past this number is deleted."
)
PREF_BACKUP_FOLDER = "Folder for older copies"
PREF_BACKUP_FOLDER_HINT = "A Backups folder beside each part"
# TR203 (D959)
MESSAGE_NEVER = "Don't Show Again"
MESSAGE_CLOSE = "Close"
MESSAGE_CLOSE_TIP = "Close this message. It comes back the next time it applies."
#: Messages that can be hidden, by key, as Preferences lists them.
MESSAGE_NAMES = {
    "rebuilds_paused": "Rebuilds are paused",
    "low_disk": "Disk space is low",  # TR220
    "low_memory": "Memory is low",
    "view_only": "Open for viewing only",
}
PREF_HIDDEN_MESSAGES = "Hidden messages"
PREF_HIDDEN_MESSAGES_TIP = (
    "Messages you chose not to see again. Pick some and press Show Again to see them again."
)
PREF_SHOW_AGAIN = "Show Again"
# TR308 (D958)
IDENTICAL_BODIES = "Identical Bodies ({count})"
IDENTICAL_BODIES_TIP = (
    "These bodies have the same shape, wherever they sit. Pick one to see it in the view."
)
# TR160 (D957)
COPY_VALUES = "Copy Values to Others"
COPY_VALUES_TITLE = "Copy Values"
COPY_VALUES_PROMPT = "Tick the features that take the values of {name}. Their picks and names stay."
COPY_VALUES_NONE = "No other feature is the same kind as {name}. Make another one first."
COPY_VALUES_DONE = "{count} features now have the values of {name}. Undo puts theirs back."
EDIT_BY_RULE_TITLE = "Edit by Rule"
RULE_TYPE = "Kind of feature"
RULE_VALUE = "Value"
RULE_TEST = "Test"
RULE_LIMIT = "Compared with"
RULE_FOUND = "Features the rule finds:"
RULE_NEW_VALUE = "Set the value to"
RULE_INCOMPLETE = (
    "Nothing was changed: the rule found no features or the new value does not read. "
    "Change the rule or type the new value again."
)
RULE_NOTHING = "No feature in this part has a value to edit. Add a feature first."
RULE_DONE = "{count} features changed. Undo puts their values back."
# TR159 (D956)
PURGE_TITLE = "Purge Unused"
PURGE_PROMPT = (
    "These are not used by anything in the part. Untick what you want to keep, then press OK. "
    "Features built on a suppressed feature are deleted with it."
)
PURGE_SKETCH = "Sketch nothing uses: {name}"
PURGE_SUPPRESSED = "Suppressed feature: {name}"
PURGE_VARIABLE = "Unused variable: {name}"
PURGE_NOTHING = "Nothing unused was found. Every sketch, feature and variable is in use."
PURGE_DONE = "{count} unused items deleted. Undo brings them back."
DELETE_BELOW_TITLE = "Delete Below Rollback Bar"
DELETE_BELOW_PROMPT = (
    "Delete the {count} features below the rollback bar? {names}. Undo brings them back."
)
DELETE_BELOW_NOTHING = "No features are below the rollback bar. Drag the bar up first."
DELETE_BELOW_DONE = "{count} features below the rollback bar deleted. Undo brings them back."
# TR333 (D955)
VIEW_FRAME_NAMES = {
    "front": "Front",
    "back": "Back",
    "left": "Left",
    "right": "Right",
    "top": "Top",
    "bottom": "Bottom",
    "home": "Home",
}
VIEW_SET_AS = "Set Current View As"
VIEW_SET_AS_PROMPT = "Make the current view this part's:"
VIEW_SET_AS_DONE = (
    "The current view is now {view}. Use Reset Standard Views to go back to the usual views."
)
VIEW_RESET = "Reset Standard Views"
VIEW_RESET_DONE = "The standard views and Home are back as they were. Undo brings yours back."
VIEW_FRAME_NOTHING = (
    "This part uses the usual views already. Use Set Current View As to change one."
)
VIEW_FRAME_NO_VIEW = (
    "There is no 3D view to take the direction from. Open the part view and try again."
)
# TR314 (D954)
PANEL_INCOMPLETE = (
    "This feature cannot be built yet. Pick what the panel asks for or change the values."
)
# TR335 (D952)
SHADE_REGIONS = "Shade Closed Regions"
SHOW_POINTS = "Show Sketch Points"
# TR361 (D951)
DIAMETER_MODE_ON = (
    "Diameter mode is on: lines parallel to this centerline get diameters. Press Esc to "
    "turn it off."
)
# TR124 (D950)
SWAP_AXIS_TITLE = "Swap Axis Relations"
SWAP_AXIS_DONE = (
    "{count} Horizontal and Vertical relations swapped for Parallel and Perpendicular. "
    "Drag the shape or add an angle dimension to turn it."
)
# TR350 (D949)
PREF_ROUNDING = "Round shown numbers"
PREF_ROUNDING_TIP = (
    "How shown values are rounded to their last place. Typed values and the model keep every digit."
)
ROUNDING_RULES = {
    "half_away": "Half away from zero",
    "half_even": "Half to even",
    "truncate": "Cut off (truncate)",
}
PREF_SEPARATOR = "Decimal separator"
PREF_SEPARATOR_TIP = (
    "The mark between whole and decimal places in shown values. Value fields still read a point."
)
SEPARATORS = {"system": "Follow the system", ".": "Point (1.5)", ",": "Comma (1,5)"}
PREF_FRACTION = "Inch values as fractions"
PREF_FRACTION_TIP = (
    "Show inch values as fractions to this step, such as 1 3/4. A value that does not "
    "land on a step keeps its decimals."
)
FRACTION_OFF = "Off (decimals)"
# TR379 (D948)
DOCK_NEW_PART = "New Part"
# TR225 (D946)
SLOT_ALONG_TITLE = "Slot Along Curves"
SLOT_ALONG_WIDTH = "Slot width (mm):"
SLOT_ALONG_DONE = "Slot made of {count} curves. Change its width with the width dimension."
HULL_DONE = (
    "Convex outline added: {count} curves. Delete the curves inside if you do not need them."
)
# Mean Dimensions (TR306, D911)
MEAN_DIMS_TITLE = "Mean Dimensions"
MEAN_DIMS_NOMINAL = "Typed Dimensions"
MEAN_DIMS_DONE = (
    "{count} toleranced dimensions set to the middle of their range. "
    "Right click and pick Typed Dimensions to put them back."
)
MEAN_DIMS_BACK = "Toleranced dimensions are back at their typed values."
MODIFY_SKETCH_DX = "Move X"
MODIFY_SKETCH_DY = "Move Y"
MODIFY_SKETCH_ANGLE = "Turn"
MODIFY_SKETCH_SCALE = "Scale"
MODIFY_SKETCH_FLIP = "Flip"
MODIFY_SKETCH_FLIPS = {
    "none": "No flip",
    "x": "Left to right",
    "y": "Top to bottom",
    "both": "Both",
}
MODIFY_SKETCH_NOTE = (
    "Scales, turns and flips about the sketch origin, then moves. Geometry held to the "
    "part stays where it is."
)
MODIFY_SKETCH_BAD_SCALE = "The scale must be larger than zero. Type another scale."
MODIFY_SKETCH_HELD = "Everything in this sketch is held to the part, so nothing can move."
# Add relations to existing geometry (TR416, D896)
FIND_RELATIONS_TITLE = "Add Relations"
FIND_RELATIONS_ROW = "{name}: {ids}"
FIND_RELATIONS_NOTE = (
    "{count} relations fit the geometry within 1 degree and 0.05 mm. Untick any you do "
    "not want, then press OK."
)
FIND_RELATIONS_NONE = "No missing relations found: the geometry has every one that fits."
FIND_RELATIONS_ADDED = "Added {count} relations."
# Sketch from a picked edge (TR51, D898)
SKETCH_NORMAL_TO_EDGE = "Sketch Square to Edge"
SKETCH_NORMAL_NO_REF = "This edge cannot be referenced. Rebuild the part and try again."
# Mirror Part (TR73, D899)
MIRROR_PART_TITLE = "Mirror Part"
MIRROR_PART_EMPTY = "The part has nothing to mirror yet. Build the part first."
MIRROR_PART_WORKING = "Mirroring the part..."
MIRROR_PART_DONE = "Saved the mirrored part to {path}."
MIRROR_PART_FAILED = "The part could not be mirrored ({reason}). Rebuild and try again."
# Dimension tolerance and display (TR46, D901)
DIM_DISPLAY_TITLE = "Display"
DIM_TOLERANCE = "Tolerance"
DIM_TOLERANCES = {
    "none": "None",
    "bilateral": "Plus and minus",
    "limit": "Limits",
    "symmetric": "Plus or minus",
}
DIM_PLUS = "Plus"
DIM_MINUS = "Minus"
DIM_DECIMALS = "Decimals"
DIM_SHOW_AS = "Show as"
DIM_SHOW_AS_IS = "As placed"
DIM_SHOW_RADIUS = "Radius"
DIM_SHOW_DIAMETER = "Diameter"
# Batch export over variable values (TR368, D904)
BATCH_TITLE = "Batch Export"
BATCH_COLUMNS = ("Variable", "Values")
BATCH_TEMPLATE = "File names"
BATCH_TEMPLATE_HINT = "{part} width{width}"
BATCH_NOTE = (
    "Type values for the variables to change: a list such as 10, 20, 30 or a range such "
    "as 10..30 step 5. Every combination is rebuilt and exported."
)
BATCH_NO_VALUES = "Type values for at least one variable."
BATCH_NO_VARIABLES = "The part has no variables. Add variables in Equations first."
BATCH_DONE = "Exported {n} files to {folder}."
BATCH_SOME = "Exported {done} files; {failed} failed. See the export log in the folder."
# Typed values that should be linked (TR351, D905)
HEALTH_LINK = "Link to Variable"
HEALTH_LINKED = "{name} now uses variable {variable}."
# Overlapping bodies on export (TR411, D907)
MESH_OVERLAPS = "Overlapping bodies"
MESH_OVERLAPS_TIP = (
    "Bodies that overlap print the shared part twice. Warn only, join them into one, or "
    "let the earlier body keep the shared part."
)
MESH_OVERLAP_CHOICES = {
    "warn": "Warn only",
    "join": "Join them",
    "first": "First body wins",
}

# Goal Seek and Sweep (TR273, D1020).
GOAL_TITLE = "Goal Seek and Sweep"
GOAL_VARIABLE = "Variable"
GOAL_TARGET = "Measured value"
GOAL_MODE = "Find"
GOAL_MODE_SEEK = "Goal Seek: the value that reaches a target"
GOAL_MODE_SWEEP = "Sweep: the result at each step"
GOAL_FROM = "From"
GOAL_TO = "To"
GOAL_STEPS = "Steps"
GOAL_GOAL = "Target"
GOAL_VALUE = "Variable value"
GOAL_RESULT = "Measured value"
GOAL_RUN = "Run"
GOAL_STOP = "Stop"
GOAL_USE = "Use Value"
GOAL_NOTE = (
    "Each trial rebuilds a copy of the part; the part changes only when you click Use Value. "
    "Measured values are in mm, mm^2, mm^3 and g."
)
GOAL_RUNNING = "Running trials..."
GOAL_NO_VARIABLE = "Goal Seek needs a variable. Add one in the equations manager first."
GOAL_FAILED = "Goal Seek failed: {reason}"
GOAL_SWEEP_DONE = "Sweep done: {good} of {n} steps built. Pick a row, then click Use Value."
GOAL_SEEK_DONE = (
    "Found {value}, which gives {result} ({n} trials). Click Use Value to set the variable."
)
GOAL_USED = "Set {name} to {text}. Use Undo to go back."
