"""UI text of the Phase 2 print and evaluate tools (PLAN 8 item 14: strings in one place)."""

from __future__ import annotations

# DXF and SVG export ---------------------------------------------------------------------
FILTER_DXF = "DXF drawing (*.dxf)"
FILTER_SVG = "SVG drawing (*.svg)"
FLAT_NOTHING = (
    "Pick one flat face in the 3D view or a sketch in the feature tree, then export again."
)
FLAT_NOT_BUILT = "The sketch {name} has not been built. Rebuild the part and export again."
FLAT_DONE = "Exported {name} at true scale in {units}."
#: Sketch text and curves the drawing could not hold (spec 2 section 20 item 21, D715).
FLAT_LEFT_OUT = (
    "{n} sketch item{s} (text, or a curve that could not be made) left out. "
    "Draw them as lines, arcs or splines to include them."
)
FLAT_FAILED = "Export failed: {reason}. Rebuild the part, then export again."

# Open in slicer -------------------------------------------------------------------------
SLICER_NOTHING = "There is no part to send to the slicer. Add a feature first."
SLICER_STARTED = "Opened {name} in {slicer}."
SLICER_FAILED = (
    "Could not open the slicer: {reason}. Open the exported 3MF file in the slicer yourself."
)
SLICER_DEFAULT_APP = "the default app for 3MF files"

# Print orientation ----------------------------------------------------------------------
ORIENT_PICK = "Pick a flat face to lay on the printer bed."
ORIENT_NOT_FLAT = "The picked item is not a flat face. Pick a flat face to lay on the bed."
ORIENT_NO_NAME = "The picked face has no stable name. Rebuild the part and pick it again."
ORIENT_SET = "Print orientation set: the picked face lies on the bed. The model is unchanged."
ORIENT_CLEARED = "Print orientation cleared: the part prints as modelled."
ORIENT_LOST = "{reason} The part is exported as modelled."
# File, Export, Bodies (spec 2 section 20 item 13, D714).
BODIES_TITLE = "Export Bodies"
BODIES_FOLDER = "Choose the folder for the body files"
BODIES_FORMAT = "Write each body as:"
BODIES_PART = "Part"
BODIES_NOTHING = "There is no part to export. Open or build a part first."
BODIES_WAIT = (
    "The part is not fully rebuilt. Wait for the rebuild or press Ctrl+B, then export again."
)
BODIES_ONE = "The part has one body. Use Export STL or Export 3MF to save it."
BODIES_DONE = "Saved {n} body files in {folder}."
BODIES_FAILED = "Export Bodies failed: {reason} Check the folder, then export again."
UNDO_ORIENT = "Set Print Orientation"
UNDO_CLEAR_ORIENT = "Clear Print Orientation"

# Build volume ---------------------------------------------------------------------------
VOLUME_IN_ZONES = (
    "{count} bodies reach into a keep out zone of this printer. Move them on the bed in the "
    "slicer, or change the zones in Preferences, Printing."
)  # TR413 (D992)
VOLUME_TOO_TALL = (
    "{count} bodies are taller than the print head clearance, so they cannot all print one "
    "at a time. Print them together, or only one tall body last."
)
PREF_KEEP_OUT = "Keep out zones"
PREF_KEEP_OUT_TIP = (
    "Bed areas to keep clear, such as clips or a purge area: x0 y0 x1 y1 in mm from the bed's "
    "front left corner. Separate zones with a semicolon."
)
PREF_HEAD_CLEARANCE = "Head clearance"
PREF_HEAD_CLEARANCE_TIP = (
    "Height under the print head's gantry, for printing parts one at a time. 0 when not set."
)
LAYERS_SHOWN = "{layers} layers of {height} mm, drawn across the build direction."  # TR315
LAYERS_EVERY = "Every {step}th layer is drawn, to keep the view quick."
LAYERS_NOTHING = "The part has no body to show layers on. Add a feature first."
VOLUME_FITS = "The part fits {printer}: {size} in a {volume} build volume."
VOLUME_TOO_BIG = (
    "The part does not fit {printer}: {size} in a {volume} build volume ({axes} too large). "
    "Lay another face flat, scale the part or use Split for Printing."
)
VOLUME_BODIES_FIT = (
    "Each of the {bodies} bodies fits {printer}: the largest is {size} in a {volume} build volume."
)
VOLUME_BODIES_TOO_BIG = (
    "Bodies too large for {printer}: {too_big} of {bodies}. The largest is {size} in a "
    "{volume} build volume ({axes} too large). Lay another face flat, scale the part or "
    "use Split for Printing on those bodies."
)
VOLUME_NOTHING = "There is no part to check. Add a feature first."
VOLUME_FAILED = "Build volume check failed: {reason}. Rebuild the part and check again."

# Overhang -------------------------------------------------------------------------------
OVERHANG_NONE = "No face overhangs more than {angle} degrees from the build direction."
OVERHANG_FOUND = "Overhang above {angle} degrees: {full} (red), {partial} in part (orange)."
OVERHANG_NOTHING = "There is no part to analyse. Add a feature first."
OVERHANG_FAILED = "Overhang analysis failed: {reason}. Rebuild the part and run it again."

# Wall thickness (PLAN Phase 4, D414) ----------------------------------------------------
WALL_NONE = "No wall is thinner than {wall} mm, the printer's minimum wall."
WALL_FOUND = (
    "Walls thinner than {wall} mm: {full} (purple), {partial} in part (pink). "
    "Thinnest wall found: {thinnest} mm."
)
WALL_NOTHING = "There is no part to analyse. Add a feature first."
WALL_FAILED = "Wall thickness analysis failed: {reason}. Rebuild the part and run it again."

# Print estimate -------------------------------------------------------------------------
ESTIMATE_INFILL = "Infill"  # TR187 (D988)
ESTIMATE_INFILL_TIP = (
    "The slicer's infill percent. 100 % gives the solid part estimate; less counts the walls "
    "as solid and the rest at this percent."
)
ESTIMATE_WALLS = "Walls"
ESTIMATE_WALLS_TIP = "How many wall lines the slicer prints round every surface."
ESTIMATE_TITLE = "Print Estimate"
ESTIMATE_MATERIAL = "Material"
ESTIMATE_DENSITY = "Density"
ESTIMATE_VOLUME = "Volume"
ESTIMATE_WEIGHT = "Weight"
ESTIMATE_BODIES = "Bodies"
ESTIMATE_NOTE = (
    "Solid part estimate: the part is taken as fully solid. "
    "The slicer gives the real figure with its walls and infill."
)
ESTIMATE_NOTHING = "There is no body to measure. Add a feature first."
ESTIMATE_WORKING = "Working out the volume..."
ESTIMATE_FAILED = "Print estimate failed: {reason}. Rebuild the part and run it again."

# Geometry check -------------------------------------------------------------------------
CHECK_TITLE = "Geometry Check"
CHECK_RUN = "Check Again"
CHECK_CLEAN = "No problems found in {bodies}."
CHECK_FOUND = "{count} problems found. Click one to highlight it."
CHECK_WORKING = "Checking the geometry..."
CHECK_NOTHING = "There is no body to check. Add a feature first."
CHECK_FAILED = "Geometry check failed: {reason}. Rebuild the part and run it again."
CHECK_SLIVER_LABEL = "Sliver width below"
CHECK_EDGE_LABEL = "Tiny edge below"

# Preferences ----------------------------------------------------------------------------
TAB_PRINTING = "Printing"
PREF_PROFILE = "Printer profile"
PREF_ADD = "Add"
PREF_REMOVE = "Remove"
PREF_NAME = "Name"
PREF_BED_X = "Build volume X"
PREF_BED_Y = "Build volume Y"
PREF_BED_Z = "Build volume Z"
PREF_NOZZLE = "Nozzle"
PREF_OVERHANG = "Overhang angle"
PREF_MIN_WALL = "Minimum wall"
PREF_FIT = "Fit tolerance"
PREF_SLICER = "Slicer"
PREF_SLICER_BROWSE = "Browse..."
PREF_SLICER_EMPTY = "Default app for 3MF files"
PREF_MATERIALS = "Material densities (g/cm³)"
PREF_MATERIAL_RESET = "Reset Densities"
NEW_PROFILE = "New printer"

TOOLTIPS = {
    "file.export_dxf": "Save the picked flat face or sketch as a DXF drawing at true scale.",
    "file.export_svg": "Save the picked flat face or sketch as an SVG drawing at true scale.",
    "print.suggest_orientation": "Rank the ways to lay the part on the bed by overhang, "
    "height and fit, and lay the chosen face flat.",
    "print.fit_calibration": "Open a test plate of pins and holes with stepped, labelled gaps.",
    "print.keep_fit": "Keep the gap that fitted as the printer's fit value.",
    "print.coating": "Set a coating thickness that STL and 3MF exports take off every face, "
    "so the coated part ends at its size.",
    "evaluate.cups_islands": "Find hollows open to the bed that trap air or resin, and "
    "points that start printing in mid air.",
    "print.arrange": "Lay the bodies out on the bed with a spacing, clear of no print zones.",
    "evaluate.layer_fit": "List heights and walls that are not a whole number of layers or "
    "line widths of the printer.",
    "print.height_changes": "Add pauses, colour changes and setting changes at heights, "
    "written to the 3MF file for the slicer.",
    "file.export_section": "Save the cut at a plane or the outline along an axis as DXF or "
    "SVG, with layers for cutting and engraving.",
    "file.export_bodies": (
        "Save each body of the part to its own file, for example the pieces of a split."
    ),
    "print.open_slicer": "Send the part to the slicer of the active printer profile as 3MF.",
    "print.lay_flat": "Pick a flat face to lay on the printer bed. Only exports change.",
    "print.clear_orientation": "Print the part as modelled again.",
    "evaluate.build_volume": "Show the printer bed and build volume and check that the part fits.",
    "evaluate.overhang": "Colour faces that overhang more than the printer can print unsupported.",
    "evaluate.wall_thickness": "Colour faces on walls thinner than the printer profile minimum.",
    "evaluate.print_estimate": "Volume and print weight of the bodies, as a solid part estimate.",
    "evaluate.geometry_check": "Find invalid faces, sliver faces, tiny edges and gaps.",
    "evaluate.draft_analysis": "Colour faces by their draft from a direction of pull.",
}

# Draft analysis (D522) ------------------------------------------------------------------
DRAFT_TITLE = "Draft Analysis"
DRAFT_DIRECTION = "Direction of pull"
DRAFT_USE_FACE = "Use Selected Face"
DRAFT_PICKED_FACE = "Selected face"
DRAFT_REVERSE = "Reverse"
DRAFT_MIN_ANGLE = "Minimum angle (degrees)"
DRAFT_GROUP_TEXT = {
    "positive": "Positive draft",
    "negative": "Negative draft",
    "needs": "Needs draft",
    "straddle": "Straddle",
}
DRAFT_LEGEND = "{group}: {faces}"
DRAFT_DONE = (
    "Draft from {direction} at {angle} degrees: {positive} positive, {negative} negative, "
    "{needs} need draft, {straddle} straddle."
)
DRAFT_NOTHING = "There is no part to analyse. Add a feature first."
DRAFT_NO_DIRECTION = "Pick a plane or a flat face for the direction of pull."
DRAFT_NOT_FLAT = "Select one flat face in the 3D view, then click Use Selected Face."
DRAFT_FAILED = "Draft analysis failed: {reason}. Rebuild the part and run it again."
DRAFT_TIPS = {
    "direction": "The direction the part is pulled out of the mould: a plane's normal.",
    "use_face": "Use the normal of the flat face selected in the 3D view as the direction.",
    "reverse": "Pull the other way: positive and negative draft swap.",
    "min_angle": "Faces with less draft than this need draft.",
}

# Bed Edge Chamfer (TR177, D779) -----------------------------------------------------------

BED_CHAMFER_TITLE = "Bed Edge Chamfer"
BED_CHAMFER_PROMPT = "Chamfer every edge of the face on the bed by (mm):"
BED_CHAMFER_PICK = (
    "No face is on the bed. Use Lay Face Flat, or pick the bottom face, then choose Bed Edge "
    "Chamfer again."
)
BED_CHAMFER_DONE = "Added {name} on every edge of the face on the bed."
# Printer process and limits (TR295 item 2, D801)
PREF_PROCESS = "Process"
PREF_PROCESSES = {"fdm": "FDM (filament)", "resin": "Resin", "powder": "Powder"}
PREF_LAYER = "Layer height"
PREF_MIN_HOLE = "Smallest round hole"
PREF_MAX_BRIDGE = "Longest bridge"
# Scale to Fit Printer (TR185, D828)
FIT_SET = (
    "Print exports are scaled to {percent}% and turned {angle} degrees to fit the printer. "
    "The part is unchanged; use Save Print Scale as Feature to keep the size."
)
FIT_ALREADY = "The part already fits the printer. Nothing to change."
FIT_CLEARED = "Print exports are full size again."
FIT_FAILED = "The fit could not be worked out: {reason}. Check the part and the printer."
FIT_NOTHING_TO_SAVE = "There is no print scale to save. Run Scale to Fit Printer first."
FIT_SAVED = "{name} keeps the print scale in the part."
TOOLTIPS.update(
    {
        "print.scale_to_fit": "Turns and, if needed, shrinks print exports to fit the printer.",
        "print.clear_fit": "Prints at full size again, turned as modelled.",
        "print.save_fit": "Adds a Scale feature with the print scale, so the part keeps it.",
    }
)
# Fix overhangs from the analysis (TR410, D909)
OVERHANG_FIX_TITLE = "Fix Overhangs"
OVERHANG_FIX_PROMPT = "Chamfer size (mm). 45 degree chamfers print without support:"
OVERHANG_FIX_NONE = "No flat face hangs over thin air in this print orientation."
OVERHANG_FIX_DONE = "Added {name} on {n} downward faces. Edit or undo it as usual."
OVERHANG_ROUNDED = "{n} of them are fillets: a chamfer prints better there."

#: Section and Outline export (TR300, D1204).
SECTION_EXPORT_TITLE = "Export Section and Outline"
SECTION_MODES = {"section": "Section at a plane", "outline": "Outline seen along the axis"}
SECTION_VIEWS = {"top": "Top (XY)", "front": "Front (XZ)", "right": "Right (YZ)"}
SECTION_SOURCE = "Source"
SECTION_PLANE = "Plane"
SECTION_OFFSET = "Offset"
SECTION_OFFSET_TIP = "How far the cut plane is from the origin, along the plane's normal."
SECTION_KERF = "Kerf or tool offset"
SECTION_KERF_TIP = (
    "Grows each shape by this much in the drawing (shrinks it when negative), "
    "for the width of a laser cut or a cutter."
)
SECTION_SCALE = "Scale"
SECTION_USE = "Use"
SECTION_USES = {"cut": "Cut", "engrave": "Engrave", "ignore": "Ignore"}
SECTION_FILTER = "DXF drawing (*.dxf);;SVG drawing (*.svg)"
SECTION_NOTHING = "There is nothing to draw. Add a feature that makes a solid first."
SECTION_DONE = "Exported {name}: {count} lines and arcs on the CUT and ENGRAVE layers."

#: Per body print settings (TR383, D1207).
BODY_SETTINGS = "Print Settings..."
BODY_SETTINGS_TITLE = "Print Settings: {name}"
BODY_SETTINGS_UNDO = "Change Body Print Settings"
BODY_SETTING_LABELS = {
    "layer_height": "Layer height",
    "walls": "Wall count",
    "infill": "Infill density",
    "pattern": "Infill pattern",
    "supports": "Supports",
    "extruder": "Extruder",
}
INFILL_PATTERNS = {
    "grid": "Grid",
    "gyroid": "Gyroid",
    "cubic": "Cubic",
    "lines": "Lines",
    "honeycomb": "Honeycomb",
}
SUPPORTS_ON = "On"
SUPPORTS_OFF = "Off"
BODY_SETTINGS_NOTE = (
    "Ticked settings are written to the 3MF file for the slicer; the others come from the "
    "slicer's profile. FDCAD does not also change the shape for what the slicer "
    "compensates, such as hole shrink or first layer spread."
)

#: Settings by height (TR384, D1208).
HEIGHTS_TITLE = "Settings by Height"
HEIGHTS_NOTE = (
    "Heights are above the print bed. A pause lets you drop in magnets or nuts; a colour "
    "change swaps the filament; a setting holds from its height up to the next change of "
    "the same setting. Bambu Studio, OrcaSlicer and PrusaSlicer read them from the 3MF "
    "file; Cura and plain 3MF do not."
)
HEIGHTS_COLUMNS = ["Height", "Change", "Setting", "Value", "Note"]
HEIGHT_KINDS = {"pause": "Pause", "colour": "Colour change", "setting": "Setting change"}
HEIGHT_SETTINGS = {"layer_height": "Layer height (mm)", "infill": "Infill (%)", "walls": "Walls"}
HEIGHTS_ADD = "Add"
HEIGHTS_REMOVE = "Remove"
HEIGHTS_UNDO = "Change Settings by Height"
HEIGHTS_DONE = "Settings by height: {count} changes kept for the slicer."
HEIGHTS_NO_PART = "There is no part open. Open a part first."

#: Layer Fit Check (TR187 item 1, D1209).
LAYER_FIT_TITLE = "Layer Fit Check"
LAYER_FIT_HEAD = (
    "Sizes that are not a whole number of {layer} mm layers or {line} mm lines. The slicer "
    "rounds them, so they print a little off. Change the size to the whole value if it matters."
)
LAYER_FIT_NONE = (
    "Layer fit: every height is whole {layer} mm layers and every wall whole {line} mm lines."
)
LAYER_FIT_FOUND = "Layer fit: {count} sizes are not whole layers or lines."
LAYER_FIT_MORE = "and {count} more"
LAYER_FIT_NOTHING = "There is nothing to check. Add a feature that makes a solid first."
LAYER_FIT_FAILED = "Layer fit check failed: {reason}. Rebuild the part, then check again."

#: Suggest Orientation and Arrange on Bed (TR301, D1210).
SUGGEST_TITLE = "Suggest Orientation"
SUGGEST_PROMPT = "Ways to lay the part on the bed, best first. Pick one and click Apply."
SUGGEST_ROW = (
    "{down} face down: overhang {overhang} mm², {islands} islands, height {height} mm, {fits}"
)
SUGGEST_FITS = "fits"
SUGGEST_TOO_BIG = "too big for the printer"
SUGGEST_NOTHING = "There is nothing to place. Add a feature that makes a solid first."
SUGGEST_NO_FLAT = (
    "The part has no flat face to lay on the bed. Add a flat face, or print it as modelled."
)
SUGGEST_FAILED = "Suggest Orientation failed: {reason}. Rebuild the part, then try again."
ARRANGE_TITLE = "Arrange on Bed"
ARRANGE_PROMPT = "Spacing between bodies (mm):"
ARRANGE_ONE = "The part has one body, so there is nothing to arrange. Split it or add bodies first."
ARRANGE_NO_FIT = (
    "The bodies do not fit on the {x:g} x {y:g} mm bed. "
    "Enter a smaller spacing or split them over two prints."
)
ARRANGE_DONE = "Arranged on the bed: {count} bodies moved, {spacing} mm apart."
ARRANGE_FAILED = "Arrange on Bed failed: {reason}. Rebuild the part, then try again."
ARRANGE_UNDO = "Arrange on Bed"

#: Suction Cups and Islands (TR409, D1213).
CUPS_TITLE = "Suction Cups and Islands"
CUPS_FOUND = (
    "{cups} suction cups (deepest {deepest} mm) and {islands} floating islands as the part "
    "lies on the bed, marked in the view. Add drain holes to cups, or turn the part."
)
CUPS_NONE = "No suction cups or floating islands as the part lies on the bed."
CUPS_DRAIN = "Add Drain Holes"
CUPS_ORIENT = "Suggest Orientation"
CUPS_NOTHING = "There is nothing to check. Add a feature that makes a solid first."
CUPS_FAILED = "Suction cup check failed: {reason}. Rebuild the part, then check again."

#: Coating Allowance (TR307, D1214).
COATING_TITLE = "Coating Allowance"
COATING_PROMPT = "Coating thickness on every face (mm, 0 for none):"
COATING_UNDO = "Change Coating Allowance"
COATING_SET = "Coating allowance {coat} mm: STL and 3MF exports take it off every face."
COATING_OFF = "No coating allowance: exports keep the modelled size."
COATING_APPLIED = "Coating allowance of {coat} mm taken off every face."

#: Code Tag (TR311, D1215).
CODE_TAG_TITLE = "Code Tag"
CODE_TAG_TEXT = "Text"
CODE_TAG_MODULE = "Module size"
CODE_TAG_PLACEHOLDER = "A part number, a web address or a note"
CODE_TAG_SIZE = "The tag is {size} mm square. Leave a light border of 4 modules round it."
CODE_TAG_EMPTY = "Enter the text for the code."
CODE_TAG_TOO_LONG = "The text is too long for a code tag. Enter at most 213 letters."

#: Fit calibration (TR358, D2000).
CALIBRATION_TITLE = "Fit Calibration"
CALIBRATION_NOTE = (
    "Makes a test plate with one pin and a row of holes. The gap per side grows by the step "
    "from hole to hole, and each hole is labelled with its gap. Print it, then use Keep "
    "Measured Fit with the gap of the tightest hole the pin turns in."
)
CALIBRATION_START = "First gap"
CALIBRATION_STEP = "Step"
CALIBRATION_COUNT = "Holes"
CALIBRATION_PART = "Fit Calibration"
CALIBRATION_MADE = "Fit calibration plate with {count} holes opened as a new part."
KEEP_FIT_TITLE = "Keep Measured Fit"
KEEP_FIT_PROMPT = "Gap of the tightest hole the pin turned in, for {name} (mm):"
KEEP_FIT_DONE = "Fit value {gap} mm kept for {name}. Parts that use fit_tolerance@Printer rebuild."
