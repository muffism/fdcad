"""UI text of the Sheet Metal tab and panels (PHASE5_SPEC, CLAUDE.md section 8).

Labels, tips and choices join the Phase 3 tables (``strings_phase3``), which
the shared feature forms read; tooltips join ``strings.TOOLTIP_TEXT``.
"""

from __future__ import annotations

from fdcad.ui import strings as _strings
from fdcad.ui import strings_phase3 as _phase3

TAB_SHEET_METAL = "Sheet Metal"
GROUP_SHEET = "Sheet Metal"
GROUP_FLAT = "Flat Pattern"

GROUP_SHEET_VALUES = "Sheet"
GROUP_BEND = "Bend Allowance"
GROUP_RELIEF = "Relief"
GROUP_PROFILE = "Profile"
GROUP_FROM = "From"
GROUP_DIRECTION1 = "Direction 1"
GROUP_DIRECTION2 = "Direction 2"
GROUP_EDGES = "Flange Edges"
GROUP_ANGLE = "Angle"
GROUP_LENGTH = "Flange Length"
GROUP_POSITION = "Flange Position"
GROUP_OWN_BEND = "Own Bend Values"
GROUP_OWN_RELIEF = "Own Relief"
GROUP_BEND_LINE = "Bend Line"
GROUP_FLAT_OPTIONS = "Flat Pattern"
GROUP_FLANGES = "Flanges"
GROUP_CORNERS = "Corners"
GROUP_CUTS = "Cuts and Marks"
GROUP_CONVERT_TAB = "Convert"
GROUP_FORMS = "Forms"
GROUP_HEM_EDGES = "Hem Edges"
GROUP_HEM = "Hem"
GROUP_MITER_EDGES = "Edge Chain"
GROUP_JOG_LINE = "Jog Line"
GROUP_JOG = "Jog"
GROUP_CORNER = "Corner"
GROUP_RIP = "Rip"
GROUP_GUSSET = "Gusset"
GROUP_TAB = "Tab Sketch"
GROUP_EDIT_BENDS = "Bends to Change"
GROUP_EXTEND = "Extend"
GROUP_PERFORATION = "Slots"
GROUP_CORNERS_PICK = "Corners"
GROUP_CORNER_RELIEF = "Relief"
GROUP_TAB_SLOT = "Tab Edge and Slot Face"
GROUP_TABS = "Tabs"
GROUP_CONVERT = "Fixed Face and Bends"
GROUP_CROSS = "Cross Break"
GROUP_UNFOLD = "Bends to Unfold"
GROUP_FOLD = "Fold"
GROUP_FORM_PLACES = "Form Places"
GROUP_FORM = "Form"

TOOLTIP_TEXT = {
    "feature.base_flange": "Makes the first sheet metal wall from a closed or open sketch.",
    "feature.edge_flange": "Adds a bent wall along each picked edge of the sheet.",
    "feature.sketched_bend": "Bends the sheet along a line sketched on a flat face.",
    "feature.sheet_metal": "Edits the part's thickness, bend radius, bend allowance and relief.",
    "feature.bend_table": "Loads a bend table from a CSV file of thickness, radius, angle "
    "and allowance.",
    "feature.flatten": "Shows the sheet metal part flat or folded.",
    "file.export_flat": "Saves the flat pattern as STEP, DXF or SVG at true scale.",
    "feature.hem": "Folds picked edges back over the sheet: closed, open, teardrop or rolled.",
    "feature.miter_flange": "Runs a sketched profile along a chain of edges, mitred at the "
    "corners.",
    "feature.jog": "Offsets part of a wall with two opposite bends along a sketched line.",
    "feature.closed_corner": "Lengthens two flange walls so they close the corner between them.",
    "feature.break_corner": "Chamfers or rounds outside corners of the flat sheet.",
    "feature.rip": "Cuts narrow slits along sketched lines, or between walls that touch.",
    "feature.gusset": "Presses a stiffening rib into a bend between two walls.",
    "feature.tab_slot": "Adds tabs to an edge and matching slots in the wall they pass through.",
    "feature.convert_sheet": "Turns the faces of a solid into sheet metal walls and bends.",
    "feature.insert_bends": "Turns a thin part of even thickness into sheet metal.",
    "feature.cross_break": "Marks a wall with cosmetic cross break lines.",
    "feature.unfold": "Shows picked bends flat so cuts can be made across them.",
    "feature.fold": "Folds unfolded bends back, keeping the cuts made across them.",
    "feature.form_tool": "Presses a dimple, louvre or rib into a flat wall.",
    "feature.sheet_tab": "Adds a sketched piece of wall, one sheet thickness thick.",
    "feature.edit_bends": "Changes the radius and bend allowance of bends already made.",
    "feature.sheet_corner_relief": "Cuts relief shapes where two or three bends meet.",
    "feature.extend_wall": "Lengthens a wall out of an edge face by a distance or up to a plane.",
    "feature.perforation": "Cuts a row of short slots along sketched lines for bending by hand.",
    "feature.sheet_rules": "Picks, saves and shares named sheet metal rules: thickness, "
    "radius, unfold rule and reliefs.",
    "feature.bend_list": "Lists every bend with its radius, allowance and bending order.",
    "feature.flat_marks": "Copies sketch lines on a wall onto the flat pattern as marks.",
    "feature.stamp": "Presses a closed sketched outline into a flat wall.",
    "feature.gauge_table": "Loads a gauge table from a CSV file of names, thicknesses and radii.",
}

#: Feature type to the command (and icon) that makes it, for the tree rows.
TYPE_COMMANDS = {
    "flat_marks": "feature.flat_marks",
    "stamp": "feature.stamp",
    "perforation": "feature.perforation",
    "extend_wall": "feature.extend_wall",
    "sheet_corner_relief": "feature.sheet_corner_relief",
    "edit_bends": "feature.edit_bends",
    "sheet_metal": "feature.sheet_metal",
    "base_flange": "feature.base_flange",
    "edge_flange": "feature.edge_flange",
    "sketched_bend": "feature.sketched_bend",
    "flatten": "feature.flatten",
    "hem": "feature.hem",
    "miter_flange": "feature.miter_flange",
    "jog": "feature.jog",
    "closed_corner": "feature.closed_corner",
    "break_corner": "feature.break_corner",
    "rip": "feature.rip",
    "gusset": "feature.gusset",
    "tab_slot": "feature.tab_slot",
    "convert_sheet": "feature.convert_sheet",
    "insert_bends": "feature.insert_bends",
    "cross_break": "feature.cross_break",
    "unfold": "feature.unfold",
    "fold": "feature.fold",
    "form_tool": "feature.form_tool",
    "sheet_tab": "feature.sheet_tab",
}

TYPE_NAMES = {
    "flat_marks": "Flat Marks",
    "stamp": "Stamp",
    "perforation": "Perforated Fold Line",
    "extend_wall": "Extend Wall",
    "sheet_corner_relief": "Corner Relief",
    "edit_bends": "Edit Bends",
    "sheet_metal": "Sheet Metal",
    "base_flange": "Base Flange",
    "edge_flange": "Edge Flange",
    "sketched_bend": "Sketched Bend",
    "flatten": "Flat Pattern",
    "hem": "Hem",
    "miter_flange": "Miter Flange",
    "jog": "Jog",
    "closed_corner": "Closed Corner",
    "break_corner": "Break Corner",
    "rip": "Rip",
    "gusset": "Gusset",
    "tab_slot": "Tab and Slot",
    "convert_sheet": "Convert to Sheet Metal",
    "insert_bends": "Insert Bends",
    "cross_break": "Cross Break",
    "unfold": "Unfold",
    "fold": "Fold",
    "form_tool": "Forming Tool",
    "sheet_tab": "Tab",
}

LABELS = {
    "thickness": "Thickness",
    "radius": "Bend radius",
    "method": "Method",
    "k_factor": "K-factor",
    "allowance": "Value",
    "relief": "Relief type",
    "relief_by": "Size by",
    "relief_ratio": "Ratio",
    "relief_width": "Width",
    "relief_depth": "Depth",
    "flip_side": "Reverse thickness",
    "symmetric": "Symmetric",
    "start_condition": "Start",
    "start": "Start at",
    "start_offset": "Offset",
    "start_reverse": "Reverse offset",
    "end_condition": "End",
    "depth": "Depth",
    "reverse": "Reverse direction",
    "end": "End at",
    "end_offset": "Offset",
    "end_condition2": "End",
    "depth2": "Depth",
    "end2": "End at",
    "end_offset2": "Offset",
    "edges": "Edges",
    "angle": "Angle",
    "angle_mode": "Angle from",
    "angle_face": "Face",
    "length": "Length",
    "length_from": "Measure from",
    "vertex_end": "End face",
    "position": "Position",
    "trim_side_bends": "Trim side bends",
    "gap": "Gap",
    "offset_distance": "Offset distance",
    "propagate": "Propagate",
    "walls": "Walls",
    "profile": "Profile",
    "rib_position": "Position along the bend",
    "flat_cutout": "Cut out in the flat pattern",
    "round": "Round",
    "flat": "Flat",
    "offset_rule": "Material at the offset",
    "flip_fixed": "Flip fixed side",
    "flattened": "Flattened",
    "bend_lines": "Show bend lines",
    "bounding_box": "Show bounding box",
    "grain": "Grain direction",
    **{f"length{k}": f"Length {k}" for k in range(2, 9)},
}

#: Labels and tips of the later tools (D547). Added with setdefault, so a key
#: another tool already labels keeps its text.
LATER_LABELS = {
    "tool_face": "Stop face of the tool body",  # TR279 (D2313)
    "remove_faces": "Faces to remove",
    "insert": "Insert point",
    "tool_angle": "Rotation",
    "mirror": "Mirror",
    "rib_ends": "Rib ends",  # TR283 (D2311)
    "drawn_cut": "Drawn cut out",
    "punch_radius": "Punch radius",  # TR77 (D2309)
    "die_radius": "Die radius",
    "corner_radius": "Corner radius",
    "bend_region": "Bend region",  # TR174 (D2308)
    "keep_body": "Keep the solid",  # TR171 (D2307)
    "rip_type": "Rip type",
    "draft": "Draft",  # TR77 (D1816)
    "tube_faces": "Tube faces",  # TR174 (D1813)
    "tube_angle": "Slit angle",
    "tube_offset": "Slit offset",
    "offset_start": "Start offset",
    "offset_end": "End offset",
    "fold_percent": "Fold progress (%)",
    "title": "Mark title",
    "sheet_length": "Sheet length",
    "sheet_width": "Sheet width",
    "limit": "Up to",
    "slot_length": "Slot length",
    "slot_width": "Slot width",
    "bridge": "Bridge",
    "edge_offset": "Edge offset",
    "skip_tabs": "Tabs to skip",
    "overlap_ratio": "Overlap ratio",
    "collect_all": "Collect all corners",
    "corner_kind": "Corners",
    "break_angle": "Break angle",
    "break_radius": "Break radius",
    "merge_faces": "Merge faces",
    "corner_trim": "Corner trim",
    "leave_out": "Faces to leave out",
    "bend_notches": "Bend notches",
    "notch_size": "Notch size",
    "all_corners": "Collect all corners",
    "relief_type": "Relief type",
    "corner_types": "Type per corner",
    "size_by": "Size by",
    "ratio": "Ratio to thickness",
    "size": "Size",
    "placement": "Placement",
    "profile_sketch": "Flange profile",
    "corner_relief": "Corner relief",
    "corner_relief_size": "Corner size",
    "hem_type": "Hem type",
    "corner_gap": "Corner gap",
    "offset": "Offset",
    "offset_from": "Measure offset",
    "faces": "Wall ends",
    "corner_type": "Corner type",
    "break_type": "Break type",
    "distance": "Distance",
    "flip": "Flip",
    "edge": "Tab edge",
    "face": "Face",
    "tab_count": "Tabs",
    "tab_length": "Tab length",
    "spacing": "Spacing",
    "clearance": "Clearance",
    "bends": "Bends",
    "all_bends": "All bends",
    "tool": "Form tool",
    "diameter": "Diameter",
    "width": "Width",
    "height": "Height",
}

TIPS = {
    "thickness": "Sheet thickness for the whole part.",
    "radius": "Inside radius of the bends.",
    "method": "How the flat length of each bend is worked out.",
    "k_factor": "Where the neutral layer lies, as a fraction of the thickness from the inside.",
    "allowance": "Bend allowance or bend deduction, as a length.",
    "relief_ratio": "Relief size as a fraction of the thickness, from 0.05 to 2.",
    "flip_side": "Thicken the sketch to the other side.",
    "symmetric": "Thicken half to each side of the sketch.",
    "edges": "Straight edges of flat faces of the sheet.",
    "length2": "Own length of the second picked edge.",
    "gap": "Space left between flanges that meet at a corner.",
    "offset_distance": "How far in from the picked edge the flange sits.",
    "propagate": "Also take every edge joined smoothly to a picked one.",
    "walls": "Pick a face on each of the two walls the bend joins.",
    "profile": "Round gives a smooth rib, Flat a straight one.",
    "rib_position": "How far the rib sits from the middle of the bend. 0 is the middle.",
    "flat_cutout": "Cut the rib's place out of the flat pattern; off leaves it whole.",
    "offset_rule": "Where the material goes at the offset place.",
    "trim_side_bends": "Shorten flanges that meet at a corner so they do not overlap.",
    "flip_fixed": "Keep the other side of the line fixed (first wall only).",
    "grain": "An edge of the first wall that sets the length direction of the flat size.",
}

LATER_TIPS = {
    "tool_face": (
        "The flat face of the tool body that sits on the sheet. Model the tool as its own "
        "body; it leaves the part when it is used."
    ),
    "remove_faces": "Faces of the tool body that leave holes in the formed sheet.",
    "insert": "A vertex of the tool body placed on the middle of each sketch line.",
    "tool_angle": "Turns the tool about the press on each line.",
    "mirror": "Mirrors the tool across each sketch line.",
    "rib_ends": "Round or square ends of the rib along each sketch line.",
    "drawn_cut": "Cut the top of the stamp away, so it is a drawn hole with a collar.",
    "punch_radius": "Inside round at the top of the stamp; 0 leaves it sharp.",
    "die_radius": "Round where the stamp leaves the wall; 0 leaves it sharp.",
    "corner_radius": "Rounds the corners of the outline seen from above; 0 keeps them.",
    "bend_region": (
        "Open leaves the corner between the two bends empty; Closed fills it where the "
        "bends cross, in the folded part only."
    ),
    "keep_body": "Keep the solid as its own body beside the sheet, to convert it again.",
    "rip_type": (
        "How walls meet at an edge that is not a bend: Overlap (the earlier wall covers "
        "the corner), Underlap (the later wall covers it), Open (neither, the corner is "
        "left open) or Butt (both meet where the corner is halved)."
    ),
    "draft": "Side angle of the stamp from square to the wall; 0 gives straight sides.",
    "tube_faces": "Round faces of a plain tube or cone: each is slit along its length.",
    "tube_angle": "Where the slit runs round the tube, from the face's own start.",
    "tube_offset": "Moves the slit sideways, square to its plane.",
    "merge_faces": "Join the faces of walls and bends in the flat pattern. Off shows where "
    "each bend region starts and ends.",
    "corner_trim": "Cut the square where two bend regions meet at a corner of the flat.",
    "leave_out": "Faces of flanges to leave out of the flat, with every wall bent from them.",
    "bend_notches": "Small notches at both ends of each bend line in the flat pattern, so "
    "the bend can be lined up on the press brake.",
    "corner_types": "One type per corner, in corner order, separated by commas. "
    "A blank keeps the relief type.",
    "placement": "Centred on the bend lines, or tangent to the bends at the corner.",
    "profile_sketch": "A closed sketch that shapes the flange: X runs along the edge from "
    "the start of the bend, Y up the flange as Length is measured.",
    "corner_relief": "Shape cut where two bends of one flange meet at a corner.",
    "corner_relief_size": "Diameter of a circular corner relief.",
    "hem_type": "Closed lies flat, open leaves a gap, teardrop leans back, rolled curls.",
    "corner_gap": "Space left between hems that meet at a corner.",
    "offset_from": "Which faces the jog offset is measured between.",
    "faces": "The narrow end faces of flange walls at the corners to close.",
    "spacing": "Tab centre to tab centre. Zero spreads the tabs over the edge.",
    "clearance": "Extra room around each tab in its slot.",
    "bends": "Edges of the solid that become bends.",
    "flip": "For edge rips: cut back the other wall.",
}

CHOICES = {
    "up_to": "Up to plane or face",
    "outside": "Outside corners",
    "inside": "Inside corners only",
    "triangle": "Triangle",
    "rectangle": "Rectangle",
    "bend_lines": "Centred on the bend lines",
    "value": "Value",
    "constant_width": "Constant width",
    "k_factor": "K-factor",
    "bend_allowance": "Bend allowance",
    "bend_deduction": "Bend deduction",
    "bend_table": "Bend table",
    "rectangular": "Rectangular",
    "obround": "Obround",
    "tear": "Tear",
    "ratio": "Ratio of thickness",
    "size": "Width and depth",
    "sketch_plane": "Sketch Plane",
    "surface": "Surface/Face/Plane",
    "vertex": "Vertex",
    "blind": "Blind",
    "mid_plane": "Mid Plane",
    "angle": "Typed angle",
    "perpendicular": "Perpendicular to face",
    "parallel": "Parallel to face",
    "outer_sharp": "Outer virtual sharp",
    "inner_sharp": "Inner virtual sharp",
    "tangent": "Bend tangent",
    "normal": "Square to the flange",
    "material_inside": "Material inside",
    "material_outside": "Material outside",
    "bend_outside": "Bend outside",
    "virtual_sharp": "Virtual sharp",
    "offset": "Offset",
    "centreline": "Bend centreline",
    "circular": "Circular",
    "closed": "Closed",
    "open": "Open",
    "teardrop": "Teardrop",
    "rolled": "Rolled",
    "same_face": "Face to same face",
    "inner_faces": "Between inside faces",
    "outer_faces": "Overall",
    "overlap": "Overlap",
    "underlap": "Underlap",
    "butt": "Butt",
    "chamfer": "Chamfer",
    "fillet": "Fillet",
    "dimple": "Dimple",
    "louvre": "Louvre",
    "rib": "Embossed rib",
    "round": "Round",
    "flat": "Flat",  # D2841: Gusset, Profile
    "square": "Square",
    "custom": "Own tool (a body)",
}

FLAT_SIZE = "Flat size"
FLAT_SIZE_TEXT = "{length} x {width}"
FLAT_SIZE_NONE = "Not available"
NEEDS_SHEET = "{tool} needs a sheet metal part. Add a Base Flange first."
NEW_SHEET = (
    "Set the values of the new sheet body, then click OK. Each sheet body has its own "
    "Sheet Metal folder and Flat Pattern."
)  # TR281 (D2312)
ALREADY_SHEET = (
    "{tool} cannot start here: the part is already sheet metal. "
    "Use Edge Flange or the other sheet metal tools to add to it."
)
NEEDS_FLAT = "There is no flat pattern to export. Fix the Flat Pattern first."
FLAT_ON = "Flat pattern shown."
FLAT_SUPPRESSED = "Flatten did nothing: the Flat Pattern is suppressed. Unsuppress it first."
FLAT_ROLLED_BACK = (
    "Flatten did nothing: the Flat Pattern is below the rollback bar. "
    "Move the bar to the end of the tree first."
)
FLAT_OFF = "Part shown folded."
FLATTEN_UNDO = "Flatten"
FOLD_UNDO = "Fold"
ADD_FOLDER_UNDO = "Add Sheet Metal Parameters"
ADD_FLAT_UNDO = "Add Flat Pattern"
BEND_TABLE_UNDO = "Load Bend Table"
BEND_TABLE_LOADED = "Loaded a bend table with {rows} rows."
BEND_TABLE_BAD = "The bend table could not be read: {error}"
BEND_TABLE_UNREADABLE = (
    "The bend table could not be read: {error}. Check the file and load it again."
)
FILTER_BEND_TABLE = "Bend tables (*.csv)"
FILTER_FLAT = "STEP (*.step *.stp);;DXF (*.dxf);;SVG (*.svg);;Quote data CSV (*.csv)"
#: The Sheet Metal Rules window (TR332, D1111).
RULES_TITLE = "Sheet Metal Rules"
RULES_APPLY = "Apply"
RULES_SAVE = "Save Current"
RULES_DELETE = "Delete"
RULES_LIBRARY = "Library File"
RULES_CLOSE = "Close"
RULES_FILE = "Rules in {name}"
RULES_NAME = "Rule name"
RULES_PICK = "Pick a rule in the list first."
RULES_NO_NAME = "Enter a name for the rule."
RULES_FILTER = "Sheet metal rules (*.json)"
RULES_UNDO = "Apply Rule {name}"
RULES_APPLIED = "Applied the rule {name} to the Sheet Metal parameters."
#: The Bend Table window (TR282, D1110).
BEND_LIST_TITLE = "Bend Table"
BEND_LIST_HINT = (
    "Pick a row to see the bend in the model. Type a new radius, allowance or step, then click OK."
)
BEND_LIST_COLUMNS = {
    "number": "No.",
    "feature": "Feature",
    "direction": "Direction",
    "angle": "Angle (deg)",
    "radius": "Radius (mm)",
    "allowance": "Allowance (mm)",
    "step": "Step",
}
BEND_LIST_DIRECTIONS = {"up": "Up", "down": "Down"}
# TR282 (D2310): rips in the Bend Table.
RIP_LIST_HINT = "Rips: pick a row to see the rip; the gap can be typed."
RIP_LIST_COLUMNS = {"number": "Rip", "feature": "Feature", "kind": "Kind", "gap": "Gap (mm)"}
RIP_LIST_KINDS = {
    "sketch": "Sketched",
    "edge": "Edge",
    "sketch_edge": "Sketched and edge",
    "tube": "Tube",
}
RIP_LIST_BAD = "Rip row {row}: enter a gap above zero."
BEND_LIST_BAD = "Row {row}: enter numbers of zero or more, and an allowance above zero."
BEND_LIST_NONE = "The part has no bends to list. Add a flange or a bend first."
BEND_LIST_FEATURE = "Edit Bend {n}"
BEND_LIST_UNDO = "Bend Table"
#: The Flat Pattern Output dialog (TR173, D1108).
FLAT_OUTPUT_TITLE = "Flat Pattern Output"
FLAT_OUTPUT_ITEMS = {
    "outline": "Outline",
    "bend_lines": "Bend lines",
    "marks": "Cross break and form marks",
    "box": "Bounding box",
}
FLAT_ORIGINS = {
    "part": "Part origin",
    "lower_left": "Lower left corner",
    "centre": "Centre of the outline",
}
FLAT_OUTPUT_ORIGIN = "Origin"
FLAT_OUTPUT_ROTATE = "Rotate"
FLAT_OUTPUT_FLIP_X = "Flip X direction"
FLAT_OUTPUT_FLIP_Y = "Flip Y direction"
FLAT_OUTPUT_UP = "Up bend colour"
FLAT_OUTPUT_DOWN = "Down bend colour"
FLAT_OUTPUT_COLOUR_TIP = "DXF colour number: 1 red, 2 yellow, 3 green, 4 cyan, 5 blue, 6 magenta."
FLAT_OUTPUT_PREVIEW = "Items to write (untick to leave one out)"
#: Quoting rows of the Flat Pattern panel (TR172, D1106).
QUOTE_LABELS = {
    "blank_area": "Blank area",
    "outer_cut_length": "Outer cut length",
    "inner_cut_length": "Inner cut length",
    "cut_outs": "Cut outs",
    "bends": "Bends",
}
EXPORT_FLAT_TITLE = "Export Flat Pattern"
EXPORT_FLAT_DONE = "Saved the flat pattern as {name}."
EXPORT_FLAT_FAILED = (
    "The flat pattern could not be saved: {error}. Check the folder and export again."
)
FIRST_SHEET = "Set the sheet values for the part, then press OK to draw the base flange."
GAUGE_TABLE_UNDO = "Load Gauge Table"
GAUGE_PICK_TITLE = "Gauge"
GAUGE_PICK_LABEL = "Gauge to use:"
GAUGE_NONE = "No gauge (use the typed thickness)"
GAUGE_LOADED = "Loaded a gauge table with {rows} gauges."
GAUGE_SET = "Using gauge {name}."
GAUGE_BAD = "The gauge table could not be read: {error}"
GAUGE_UNREADABLE = "The gauge table could not be read: {error}. Check the file and load it again."
FILTER_GAUGE_TABLE = "Gauge tables (*.csv)"
NO_UNFOLD = "Fold needs an Unfold above it. Add an Unfold first."

_strings.TOOLTIP_TEXT.update(TOOLTIP_TEXT)
_phase3.LABELS.update(LABELS)
_phase3.TIPS.update(TIPS)
for _key, _text in CHOICES.items():
    _phase3.CHOICES.setdefault(_key, _text)
for _key, _text in LATER_LABELS.items():
    _phase3.LABELS.setdefault(_key, _text)
for _key, _text in LATER_TIPS.items():
    _phase3.TIPS.setdefault(_key, _text)
_phase3.TYPE_NAMES.update(TYPE_NAMES)

# build123d script export (PLAN Phase 5) -------------------------------------------
EXPORT_BUILD123D = "build123d Script..."
FILTER_PYTHON = "Python scripts (*.py)"
BUILD123D_DONE = "Saved the build123d script {name}. Features it cannot make are comments."
BUILD123D_FAILED = (
    "The build123d script could not be saved: {error}. Choose another folder and try again."
)
