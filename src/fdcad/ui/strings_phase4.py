"""User visible text for the Phase 4 panels (PHASE4_SPEC P4.1 to P4.8).

Kept apart from ``strings.py`` so parallel work on other panels does not clash.
Title case for commands and labels, sentence case for messages (CLAUDE.md section 8).
"""

from __future__ import annotations

GROUP_FASTEN = "Fasten"
GROUP_SHAPE = "Shape"
GROUP_TEXT = "Text"

# Favourites box (PHASE4_SPEC common rules) ----------------------------------------------

GROUP_FAVOURITES = "Favourites"
FAVOURITES_TIP = "Save the current settings under a name and use them again later."
FAV_SAVE = "Save"
FAV_APPLY = "Apply"
FAV_UPDATE = "Update"
FAV_DELETE = "Delete"
FAV_EXPORT = "Export"
FAV_IMPORT = "Import"
FAV_NONE = "No favourites yet"
FAV_NAME_TITLE = "Save Favourite"
FAV_NAME_PROMPT = "Name of the favourite:"
FAV_FILE_FILTER = "FDCAD favourites (*.json)"
FAV_IMPORTED = "{count} favourite(s) imported."
FAV_IMPORT_FAILED = "Import failed: {error}"
# TR326 (D947)
FAV_RENAME = "Rename"
FAV_RENAME_FAILED = "That name is empty or already used. Type another name."
FAV_DEFAULT = "New ones start with"
FAV_DEFAULT_TIP = (
    "What a new feature of this type starts with: the factory settings, the settings of the "
    "last one you made, or a favourite."
)
FAV_FACTORY = "Factory settings"
FAV_LAST_USED = "Last used"

# Hole Tool (P4.1) ------------------------------------------------------------------------

TAB_TYPE = "Type"
TAB_POSITIONS = "Positions"
GROUP_HOLE = "Hole"
HOLE_TYPES = {
    "simple": "Simple",
    "counterbore": "Counterbore",
    "countersink": "Countersink",
    "tapped": "Straight Tapped",
    "heat_set_insert": "Heat Set Insert",
    "self_tapping": "Self Tapping (Plastic)",
    "magnet": "Magnet Pocket",
    "dowel": "Dowel Pin",
    "bearing": "Bearing Seat",
    "counterdrill": "Counterdrill",  # TR144 (D1506)
    "pipe_tapped": "Tapered Pipe Tapped",  # TR145 (D1511)
    "custom": "Custom Stack",  # TR144 (D1912)
    "nut_trap": "Hex Nut Trap",
    "nut_slot": "Captive Nut Slot",
}
STANDARDS = {"iso": "ISO Metric", "ansi": "ANSI Inch", "user": "User Sizes"}  # D1914
FIT_TABLE = "Fit Table..."  # TR412 (D1919)
FIT_FROM_TABLE = "Fit from Table"
FIT_TABLE_PROMPT = (
    "One row per line: hole or outside, flat, upright or any, up to which diameter, the "
    "gap per side, and an optional nozzle size, such as: hole upright 6 0.25"
)
FIT_TABLE_SAVED = "Fit table saved with {count} rows."
FIT_TABLE_BAD = "The fit table could not be read: {why} Fix the line and save again."
FIT_UPRIGHT = "an upright hole"
FIT_FLAT = "a hole printed lying down"
FIT_ROW = (
    "Fit Tolerance {gap} mm per side from the table, for {way} up to {up_to} mm. FDCAD "
    "applies it to the model: turn off the slicer's own hole compensation, or set this to 0."
)
FIT_NO_ROW = (
    "No table row fits {way} of this size, so the printer's {gap} mm is used. Add a row "
    "with Fit Table."
)
LOAD_USER_SIZES = "Load User Sizes..."  # TR144 (D1914)
LOAD_USER_SIZES_TIP = (
    "Load your own hole sizes from a comma separated file with a header row: name and "
    "diameter, and optionally pitch, tap_drill, clearance_close, clearance_normal, "
    "clearance_loose, head_diameter, head_height, csk_diameter, nut_flats, nut_height "
    "(mm) and class (a thread class such as 6g). They show under the User Sizes standard "
    "in the Hole Tool and in the Thread and Cosmetic Thread size lists."
)
USER_SIZES_FILTER = "Size tables (*.csv *.txt)"
USER_SIZES_LOADED = "{count} user hole sizes loaded."
USER_SIZES_BAD = "The size file could not be read: {why} Fix the file and load it again."
PURPOSES = {"drill": "Drill Size", "tap_drill": "Tap Drill", "clearance": "Screw Clearance"}
FITS = {"close": "Close", "normal": "Normal", "loose": "Loose"}
PRINT_FITS = {"none": "None", "clearance": "Clearance", "slip": "Slip", "press": "Press"}
END_CONDITIONS = {
    "blind": "Blind",
    "through_all": "Through All",
    "up_to_next": "Up to Next",
    "up_to_vertex": "Up to Vertex",
    "up_to_face": "Up to Face",
}
BOTTOMS = {"flat": "Flat", "drill_point": "Drill Point"}
LABEL_TYPE = "Type"
LABEL_STANDARD = "Standard"
LABEL_PURPOSE = "Purpose"
LABEL_SIZE = "Size"
LABEL_CUSTOM_SIZE = "Custom size"
LABEL_FIT = "Fit"
LABEL_PRINT_FIT = "Print Fit"
LABEL_HEAD = "Head"  # TR253
CBORE_HEADS = {
    "socket": "Socket Head",
    "button": "Button Head",
    "low_head": "Low Head Socket",
    "pan": "Pan Head",
    "cheese": "Cheese Head",
    "washer": "Socket Head on Washer",
}
CSK_HEADS = {"flat": "Socket Flat Head", "recessed": "Cross Recessed Flat Head"}
DRILL_NAME = "Drill: {names}"
LABEL_PRINT_TOP = "Print Top"  # TR175
PRINT_TOPS = {"none": "Round", "teardrop": "Teardrop", "flat": "Flat Bridge"}
LABEL_PRINT_BRIDGE = "Head Down Bridge"  # TR176
PRINT_BRIDGES = {"none": "None", "sacrificial": "Sacrificial Layer", "stepped": "Stepped Layers"}
LABEL_BRIDGE_LAYER = "Layer Height"
LABEL_FIT_TOLERANCE = "Fit Tolerance"
LABEL_END = "End Condition"
LABEL_BOTTOM = "Bottom"
LABEL_DIAMETER = "Diameter"
LABEL_DEPTH = "Depth"
LABEL_TIP_ANGLE = "Drill Point Angle"
OPT_POINT_IN_DEPTH = "Depth Includes Point"  # TR144 (D1505)
LABEL_CDRILL_ANGLE = "Counterdrill Angle"  # TR144 (D1506)
LABEL_THREAD_CLASS = "Thread Class"  # TR393 (D1507)
NO_THREAD_CLASS = "None"


def thread_class_choices(internal: bool | None) -> tuple[tuple[str, str], ...]:
    """(value, label) pairs for the thread class list: internal, external or both."""
    from fdcad.core.features import thread_class as tc

    names: tuple[str, ...]
    if internal is None:
        names = tc.CLASSES
    elif internal:
        names = tc.METRIC_INTERNAL + tc.INCH_INTERNAL
    else:
        names = tc.METRIC_EXTERNAL + tc.INCH_EXTERNAL
    return (("none", NO_THREAD_CLASS), *((n, n) for n in names))


OPT_TAPER = "Taper"
LABEL_TAPER_ANGLE = "Taper Angle"
LABEL_CBORE_DIAMETER = "Counterbore Diameter"
LABEL_CBORE_DEPTH = "Counterbore Depth"
LABEL_CSK_DIAMETER = "Countersink Diameter"
LABEL_CSK_ANGLE = "Countersink Angle"
LABEL_THREAD_DEPTH = "Thread Depth"
LABEL_PITCH = "Pitch"
LABEL_THREAD_DIAMETER = "Thread Diameter"
LABEL_NUT_FLATS = "Nut Across Flats"
LABEL_NUT_HEIGHT = "Nut Height"
LABEL_NUT_ANGLE = "Nut Angle"
LABEL_SLOT_OFFSET = "Slot Offset"
LABEL_SLOT_LENGTH = "Slot Length"
GROUP_SLOT_HOLE = "Slot"
OPT_SLOT_HOLE = "Slot"
LABEL_SLOT_SPAN = "Slot Length"
LABEL_SLOT_SPAN_MODE = "Measured"
SLOT_SPAN_MODES = {"centre": "Centre to Centre", "overall": "Overall"}
LABEL_SLOT_ANGLE = "Slot Angle"
GROUP_OPTIONS = "Options"
OPT_HEAD_CLEARANCE = "Head Clearance"
OPT_NEAR_CSK = "Near Side Countersink"
OPT_FAR_CSK = "Far Side Countersink"
LABEL_NEAR_CSK_DIAMETER = "Near Side Diameter"
LABEL_NEAR_CSK_ANGLE = "Near Side Angle"
LABEL_FAR_CSK_DIAMETER = "Far Side Diameter"
LABEL_FAR_CSK_ANGLE = "Far Side Angle"
OPT_COSMETIC_THREAD = "Cosmetic Thread"
OPT_MODELED_THREAD = "Modelled Thread"
EDIT_INSERTS = "Edit Insert Table"
INSERT_TABLE_TITLE = "Heat Set Insert Table"
INSERT_COLUMNS = ("Size", "Hole Diameter (mm)", "Hole Depth (mm)")
INSERT_ADD = "Add Row"
INSERT_REMOVE = "Remove Row"
INSERT_RESET = "Restore Defaults"
INSERT_BAD_ROWS = (
    "Row(s) {rows} need a size name and a diameter and depth above zero. "
    "Fix the row, or remove it with Remove Row."
)
LABEL_FACE = "Face"
LABEL_UP_TO = "Up to Face"
LABEL_UP_TO_VERTEX = "Up to Vertex"
LABEL_POSITION_SKETCH = "Position Sketch"
OWN_POINTS = "Points Placed Here"
USE_POINTS = "Points"
USE_ENDS = "End Points"
USE_CENTRES = "Centres"
LABEL_STACK = "Elements"  # TR144 (D1912)
LABEL_START_PLANE = "Start plane"  # TR144 (D1913)
LABEL_PLACE_BY = "Place by"  # TR143 (D1911)
PLACE_BYS = {
    "points": "Points",
    "edges": "Distances from Two Edges",
    "concentric": "Concentric",
    "radial": "Distance and Angle from an Axis",  # TR397 (D1915)
    "point": "On a Point",
}
LABEL_RADIAL = "Axis"
LABEL_RADIAL_DISTANCE = "Distance from axis"
LABEL_RADIAL_ANGLE = "Angle"
LABEL_AT_POINT = "Point"
LABEL_HOLE_AXIS = "Hole axis"
LABEL_PLACE_EDGES = "Edges"
LABEL_PLACE_DISTANCE1 = "From edge 1"
LABEL_PLACE_DISTANCE2 = "From edge 2"
LABEL_CONCENTRIC = "Round edge or cylinder"
HOLE_PLACE_NEEDS_FACE = "Pick the face the hole starts on, then the edges to place it by."
POINT_ROW = "Point {k}"
REMOVE_POINT = "Remove Point"
HOLE_COUNT = "{count} hole(s)"
HOLE_PLACE_HINT = "Click on the face to place a hole at each click."
# TR189 (D935)
INSERT_MARGIN = "Depth margin"
INSERT_MARGIN_TIP = (
    "Extra depth added to each insert hole from the table, so melted plastic has room "
    "below the insert."
)
# Bolt circle (TR407, D913)
BOLT_LABEL = "Bolt Circle"
BOLT_PLACEHOLDER = "5x100"
BOLT_START_PLACEHOLDER = "Start angle"
BOLT_MAKE = "Make"
BOLT_TIP = (
    "Click the centre on the face, then type the hole count and circle diameter, "
    "such as 5x100, and an optional start angle. The clicked point becomes the centre."
)
BOLT_NEEDS_CENTRE = "Click the centre of the bolt circle on the face first."
HOLE_NEEDS_POINTS = "Place at least one hole on the Positions tab."
HOLE_NEEDS_FACE = "Pick the face for the holes on the Positions tab."
HOLE_UP_TO_NEEDS = "Pick the face where the holes stop."
HOLE_PICK_FACE = "Pick a face of the part."

TIPS = {
    "hole_type": "The kind of hole. Each kind is its own feature.",
    "standard": "The thread standard the sizes come from.",
    "purpose": "What the hole is for: a drill size, a tap drill or a screw clearance.",
    "size": "The screw or insert size. The values below are filled from the table.",
    "fit": "How loose a screw clearance hole is (ISO 273 fine, medium or coarse).",
    "print_fit": "Adds the printer's fit tolerance: Clearance twice, Slip once, Press none.",
    "cbore_head": "The screw head: fills the counterbore diameter and depth from its table.",
    "csk_head": "The countersunk head form: fills the countersink diameter from its table.",
    "print_top": "Gives a sideways hole a pointed or flat top toward the printer's up, so "
    "it prints without supports.",
    "print_bridge": "For a head printed facing down: leave a thin layer to drill out, or two "
    "stepped layers that print as bridges.",
    "bridge_layer": "One printed layer: use the printer profile's layer height.",
    "fit_tolerance": "The fit tolerance from the printer profile, per side.",
    "end": "Where the hole stops.",
    "bottom": "A flat bottom prints best. A drill point is shaped like a twist drill tip.",
    "diameter": "The hole diameter.",
    "depth": "How deep the hole goes from the face.",
    "head": "Values of the screw head bore.",
    "thread": "Thread length and pitch of a tapped hole.",
    "nut": "Size and turn of the hex nut.",
    "slot": "Where the slot sits below the face and how far it reaches.",
    "slot_hole": (
        "Makes a slot at each position so the part can slide. "
        "The length is between the end centres or over the whole slot."
    ),
    "options": "Extra shapes at the near and far ends of the hole.",
    "head_clearance": "Carries the head bore up above the face by this length.",
    "thread_class": "The thread's tolerance class, shown in the hole list. On a modelled "
    "thread its allowance (none for H, h, 3A and B classes) is added to the clearance.",
    "point_in_depth": "Ticked, the drill point's tip reaches the depth. Unticked, the "
    "straight wall does and the point goes below it.",
    "taper": "Narrows the whole hole wall toward the bottom by the taper angle, measured "
    "from the axis.",
    "near_csk": "A countersink where the hole starts.",
    "far_csk": "A countersink where a Through All hole comes out.",
    "cosmetic": "Shows the thread on the hole wall without modelling it.",
    "modeled": "Cuts a real helical thread that prints.",
    "inserts": "Change the insert hole sizes. They are kept in the preferences.",
    "face": "The face the holes start on, flat or curved.",
    "up_to": "The face where the holes stop.",
    "up_to_vertex": "The vertex whose level the holes stop at.",
    "sketch": "Use the points of an existing sketch, or place points here.",
    "use_points": "Count points that are on their own.",
    "use_ends": "Count end points of lines and arcs.",
    "use_centres": "Count centres of circles and arcs.",
    "start_plane": "Optional: a flat face whose plane the holes start on, in place of the "
    "face they are placed on, such as a plane below a curved or stepped top.",
    "radial": "A round or straight edge whose axis the distance and angle are measured from.",
    "radial_distance": "How far the hole's centre is from the axis, on the face.",
    "radial_angle": "The angle round the axis, from the face's X direction.",
    "at_point": "A vertex or sketch point: the hole's centre, seen straight onto the face.",
    "hole_axis": "Optional: a straight edge the holes run along, when they need not be "
    "square to the face.",
    "fit_table": "A printer's holes come out smaller upright than lying down, and small "
    "holes more than large ones. Fit Table keeps a gap per side by diameter band and "
    "direction (and nozzle); Fit from Table sets this hole's Fit Tolerance from it.",
    "stack": "The hole's elements from the face inward, each a kind, a diameter and a length "
    "(a countersink takes its angle): counterbore 10 3; countersink 8 90; straight 5 12. "
    "Kinds: straight, counterbore, tapped, countersink. Reorder them by editing the list.",
    "place_by": "Place one hole by its distances from two straight edges, or on the axis of "
    "a round edge or cylinder, with no sketch. Points places holes at sketch points.",
    "place_edges": "Two straight edges of the face, not parallel.",
    "place_distance": "How far the hole's centre is from the edge, measured on the face.",
    "concentric": "A round edge or a cylinder face: the hole goes on its axis.",
    "points": "The holes placed here. Type a position to move one.",
}

# Cosmetic and modelled threads (P4.2, P4.3) ------------------------------------------------

GROUP_THREAD = "Thread"
GROUP_THREAD_VALUES = "Thread Values"
LABEL_EDGE = "Start Edge"
LABEL_LENGTH = "Length"
LABEL_REVERSE = "Reverse"
THREAD_ENDS = {"blind": "Blind", "full": "Full Length"}
LABEL_OFFSET = "Start Offset"
LABEL_START_ANGLE = "Start Angle"
LABEL_REVOLUTIONS = "Revolutions"
LABEL_UP_TO_ITEM = "Up to Selection"
LABEL_KEEP_LENGTH = "Keep Thread Length"
LABEL_METHOD = "Method"
LABEL_HAND = "Hand"
LABEL_STARTS = "Starts"
MODELED_ENDS = {"blind": "Blind", "revolutions": "Revolutions", "up_to": "Up to Selection"}
METHODS = {"cut": "Cut Thread", "extrude": "Extrude Thread"}
HANDS = {"right": "Right Hand", "left": "Left Hand"}
GROUP_THREAD_PRINT = "Printing"  # TR178
LABEL_FORM = "Profile"
FORMS = {
    "iso": "Standard 60 Degree",
    "printable": "Printable 90 Degree",
    "round": "Round",
    "trapezoidal": "Metric Trapezoidal 30 Degree",  # TR254 (D1510)
    "acme": "ACME 29 Degree",
    "square": "Square",
    "buttress": "Buttress 7 and 45 Degree",
    "pipe": "Pipe 55 Degree",
    "sketch": "From a Sketch",  # TR254 (D1918)
}
END_FINISHES = {"square": "Square", "chamfer": "Chamfer", "fade": "Fade Out"}  # TR254 (D1918)
LABEL_END_FINISH = "End Finish"
LABEL_PROFILE_SKETCH = "Profile Sketch"
LABEL_LEAD_IN = "Lead In"
LABEL_TAPER_ANGLE = "Taper Angle"  # TR145 (D1917)
OPT_THREAD_RELIEF = "Thread Relief"  # TR256 (D1922)
OPT_THREAD_CHAMFER = "Entry Chamfer"
NOMINAL_NOTE = (
    "Thread profiles are nominal 60 degree V profiles. "
    "Check the fit on a test print before relying on them."
)
THREAD_TIPS = {
    "thread_class": "The thread's tolerance class: capital letters and B for holes, small "
    "letters and A for shafts. Its allowance (none for H, h, 3A and B) is added to the "
    "clearance unless a clearance is typed.",  # TR393 (D1507)
    "form": "Printable has 45 degree flanks that print without supports; Round is a coarse "
    "groove for caps and jars.",
    "thread_fit": "Adds clearance per side: half the fit's diameter change, from the printer's "
    "fit tolerance.",
    "end_finish": "How the thread ends: Square stops at full depth, Chamfer runs the depth "
    "out at 45 degrees, Fade Out runs it out over the last pitch. Not with a taper.",
    "profile_sketch": "A sketch with one closed region: its X runs along the axis and its Y "
    "is the depth into the material (cut) or the height off the face (extruded).",
    "thread_relief": "A run out groove where the thread ends, sized from the pitch (DIN 76-1): "
    "a shaft's is the diameter less 1.6 pitches across and 3 pitches long, a hole's the "
    "diameter plus 0.3 mm and 4 pitches long.",
    "thread_chamfer": "A 90 degree countersink at the hole's entry to 1.05 times the thread "
    "diameter, so the tap starts cleanly and no burr stands up.",
    "taper_angle": "A tapered thread: the half angle of its cone, 1.79 degrees for NPT and Rc "
    "pipe threads (1 in 16 on the diameter). A hole's thread narrows going in, a shaft's "
    "widens away from its end. 0 makes a straight thread.",
    "lead_in": "Cuts a 45 degree cone at the start so the thread does not start as a thin edge.",
    "offset": "Moves where the thread starts along the axis.",
    "start_angle": "Turns where the thread starts around the axis.",
    "revolutions": "How many turns the thread makes.",
    "up_to": "A vertex, flat face or plane where the thread stops.",
    "keep_length": "Keep the length when the start moves; off keeps the end in place.",
    "method": "Cut the thread into the face, or add it onto the face.",
    "hand": "Right hand threads tighten clockwise.",
    "starts": "Number of thread starts (1 to 4).",
    "edge": "The round edge of a hole or shaft where the thread starts.",
    "size": "The thread size. Diameter and pitch are filled from the standard table.",
    "diameter": "The major diameter of the thread.",
    "pitch": "The distance from one thread crest to the next.",
    "end": "How far the thread runs: a set length, or the whole round face.",
    "length": "The thread length from the start edge.",
    "reverse": "Run the thread the other way along the axis.",
}
# The Hole Tool's tapped holes take the same relief and chamfer (TR256, D1922).
TIPS.update({key: THREAD_TIPS[key] for key in ("thread_relief", "thread_chamfer")})

# Fastening features (P4.4) ------------------------------------------------------------------

GROUP_POSITION = "Position"
LABEL_POSITION = "Point or Round Edge"
LABEL_DIRECTION = "Direction"
GROUP_BOSS = "Boss"
BOSS_TYPES = {
    "screw_thread": "Screw Boss, Thread Side",
    "screw_head": "Screw Boss, Head Side",
    "pin": "Pin Boss, Pin",
    "pin_hole": "Pin Boss, Hole",
}
LABEL_BOSS_DIAMETER = "Boss Diameter"
LABEL_BOSS_HEIGHT = "Boss Height"
LABEL_DRAFT = "Draft"
LABEL_HOLE_DIAMETER = "Hole Diameter"
LABEL_HOLE_DEPTH = "Hole Depth"
LABEL_HEAD_DIAMETER = "Head Bore Diameter"
LABEL_HEAD_DEPTH = "Head Bore Depth"
LABEL_PIN_DIAMETER = "Pin Diameter"
LABEL_PIN_HEIGHT = "Pin Height"
LABEL_HEIGHT_FACE = "Up to Mating Face"  # TR146 (D1517)
LABEL_HEIGHT_CLEARANCE = "Gap to Mating Face"
LABEL_PIN_EDGE = "Pin Size from Edge"
LABEL_PIN_CLEARANCE = "Pin Clearance"
LABEL_STEP_HEIGHT = "Step Height"  # TR146 (D1916)
LABEL_STEP_DIAMETER = "Step Diameter"
GROUP_FINS = "Fins"
LABEL_FIN_COUNT = "Number of Fins"
LABEL_FIN_DIRECTION = "First Fin Along"
LABEL_FIN_ANGLE = "First Fin Angle"
LABEL_FIN_ANGLE2 = "Second Fin Angle"
LABEL_EQUAL = "Equally Spaced"
LABEL_FIN_LENGTH = "Fin Length"
LABEL_FIN_WIDTH = "Fin Width"
LABEL_FIN_HEIGHT = "Fin Height"
LABEL_CHAMFER_DISTANCE = "End Chamfer Distance"
LABEL_CHAMFER_ANGLE = "End Chamfer Angle"
LABEL_UP = "Up Direction"
LABEL_REVERSE_UP = "Reverse Up"
LABEL_HOOK_DIRECTION = "Hook Direction"
LABEL_HOOK_ANGLE = "Hook Angle"
LABEL_REVERSE_HOOK = "Reverse Hook"
LABEL_MATE_FACE = "Height From Face"
LABEL_BODY_HEIGHT = "Body Height"
GROUP_HOOK_DATA = "Hook Data"
LABEL_BASE_DEPTH = "Base Depth"
LABEL_TOP_DEPTH = "Top Depth"
LABEL_TOTAL_WIDTH = "Total Width"
LABEL_OVERHANG = "Overhang"
LABEL_HOOK_HEIGHT = "Hook Height"
LABEL_LIP_HEIGHT = "Lip Height"
LABEL_TOP_DRAFT = "Top Draft"
GROUP_GROOVE_PICKS = "Hook and Body"
LABEL_HOOK = "Snap Hook"
LABEL_GROOVE_BODY = "Body to Cut"
GROUP_GROOVE_DATA = "Groove Data"
LABEL_OFFSET_HEIGHT = "Offset Height"
LABEL_GAP_HEIGHT = "Gap Height"
LABEL_GROOVE_CLEARANCE = "Groove Clearance"
LABEL_GAP_CLEARANCE = "Gap Clearance"
LABEL_OFFSET_WIDTH = "Offset Width"
GROUP_LIP_PICKS = "Rims"
LABEL_LIP_FACES = "Lip Rim Faces"
LABEL_GROOVE_FACES = "Groove Rim Faces"
GROUP_LIP_SIZES = "Sizes"
LABEL_LIP_WIDTH = "Lip Width"
LABEL_LIP_DRAFT = "Lip Draft"
LABEL_LINK = "Link Matched Values"
LABEL_SPACING = "Spacing"
LABEL_GAP = "Gap"
LABEL_GROOVE_WIDTH = "Groove Width"
LABEL_GROOVE_HEIGHT = "Groove Height"
LABEL_GROOVE_DRAFT = "Groove Draft"
GROUP_VENT_SKETCH = "Vent Sketch"
LABEL_SKETCH = "Sketch"
VENT_COLUMNS = ("Curve", "Role")
VENT_ROLES = {
    "none": "Not Used",
    "boundary": "Boundary",
    "ribs": "Rib",
    "spars": "Spar",
    "fill": "Fill In Boundary",
}
GROUP_VENT_VALUES = "Ribs, Spars and Fill"
LABEL_RIB_WIDTH = "Rib Width"
LABEL_RIB_DEPTH = "Rib Depth"
LABEL_RIB_OFFSET = "Rib Offset"
LABEL_SPAR_WIDTH = "Spar Width"
LABEL_SPAR_DEPTH = "Spar Depth"
LABEL_SPAR_OFFSET = "Spar Offset"
LABEL_FILL_DEPTH = "Fill Depth"
LABEL_FILL_OFFSET = "Fill Offset"
GROUP_VENT_SHAPE = "Draft and Fillet"  # TR146 item 3 (D2406)
LABEL_LIP_EDGES = "Lip Rim Edges"  # TR146 item 2 (D2407)
LABEL_GROOVE_EDGES = "Groove Rim Edges"
LABEL_JUMP_GAPS = "Jump Gaps"
LABEL_FOLLOW_WALL = "Follow Wall Draft"
LABEL_RIB_DRAFT = "Rib Draft"
LABEL_RIB_FILLET = "Rib Fillet"
LABEL_SPAR_DRAFT = "Spar Draft"
LABEL_SPAR_FILLET = "Spar Fillet"
LABEL_FILL_DRAFT = "Fill Draft"
LABEL_FILL_FILLET = "Fill Fillet"
VENT_AREA = "Total area {total}, open area {open} ({percent} percent)."
VENT_AREA_NONE = "The areas show once the vent has a boundary."
VENT_NEEDS_BOUNDARY = "Give at least one closed set of sketch curves the Boundary role."
FASTEN_TIPS = {
    "face": "The face the feature stands on, flat or curved. Click on it to set the position.",
    "position": "A vertex or round edge to place the feature at. Leave empty to type a position.",
    "pos": "The position in model coordinates, set by clicking on the face.",
    "direction": "A plane, flat face or straight edge for the direction (default: face normal).",
    "boss_type": "Screw boss with a hole or a head bore, or pin boss with a pin or a pin hole.",
    "boss": "Size of the boss.",
    "draft": "Lean of the side walls, so the part comes off the bed and prints cleanly.",
    "hole": "The screw hole from the top of the boss.",
    "pin": "The pin on top of the boss, or the hole it fits in.",
    "step": "A narrower collar on top of the boss, for example to locate it in the mating "
    "part's hole. 0 makes none. The hole or pin starts on top of it.",
    "mating": "Click the face of the mating part the boss reaches up to, less the gap, and "
    "the round edge of the hole or pin it fits, less or plus the clearance.",
    "fins": "Fins brace the boss against the face. 0 for none.",
    "fin_direction": "A straight edge that the first fin points along.",
    "fin_angle": "Turn of the fin about the boss axis.",
    "equal": "Space the fins evenly round the boss; off uses the second fin angle as the step.",
    "chamfer": "Cuts the top outer corner of each fin.",
    "up": "A plane, flat face or straight edge for the up direction. Default: square to the face.",
    "hook_dir": "The way the hook lip points.",
    "mate": "Take the body height from a face, or type it.",
    "hook": "Sizes of the hook beam and lip.",
    "groove_hook": "The snap hook the groove is for.",
    "groove_body": "A face of the body the groove is cut in.",
    "groove": "Room round the hook head in the groove.",
    "rims": "Flat rim faces round an opening. The lip stands up, the groove is cut in.",
    "lip": "Size of the lip and the groove along the inner edge of the rim.",
    "link": "Groove width is lip width plus spacing, depth is lip height plus gap, same draft.",
    "vent_sketch": "The sketch with the vent curves, on or parallel to the face.",
    "vent_face": "The flat face the vent goes through.",
    "vent_roles": "Give each sketch curve a role: boundary, rib, spar or fill in boundary.",
    "vent_values": "Width, depth and offset below the face of the ribs, spars and fill.",
    "rim_edges": "Click an edge round the opening instead of the rim face; the flat rim it "
    "is on is used.",
    "jump_gaps": "Notches in the opening narrower than this, where ribs meet the wall at the "
    "rim, are crossed straight. 0 follows every notch.",
    "follow_wall": "Lean the lip and groove walls with the part's wall, so a drafted wall "
    "keeps its draft.",
    "vent_shape": "Draft narrows each group's bars going into the wall; the fillet rounds "
    "their outer edges. 0 leaves them square.",
}

# Rib, Dome, Wrap (P4.5 to P4.7) --------------------------------------------------------------

GROUP_RIB = "Rib"
LABEL_THICKNESS = "Thickness"
LABEL_SIDE = "Thickness Side"
RIB_SIDES = {"first": "First Side", "both": "Both Sides", "second": "Second Side"}
RIB_DIRECTIONS = {"parallel": "Parallel to Sketch", "normal": "Normal to Sketch"}
RIB_EXTENDS = {"linear": "Linear", "natural": "Natural"}
RIB_DRAFT_AT = {"sketch": "At Sketch Plane", "wall": "At Wall"}  # TR75 (D2112)
LABEL_DRAFT_AT = "Thickness"
LABEL_PULL = "Pull Direction"
LABEL_FLIP = "Flip Material Side"
LABEL_EXTEND = "Ends"
LABEL_USE_DRAFT = "Draft"
LABEL_DRAFT_OUTWARD = "Draft Outward"
LABEL_BODY = "Body"
GROUP_DOME = "Dome"
LABEL_FACES = "Faces"
LABEL_DISTANCE = "Distance"
LABEL_ELLIPTICAL = "Elliptical Dome"
LABEL_CONTINUOUS = "Continuous Dome"
GROUP_WRAP = "Wrap"
LABEL_FACE_TO_WRAP = "Face to Wrap On"
WRAP_TYPES = {"emboss": "Emboss", "deboss": "Deboss", "scribe": "Scribe"}
LABEL_WRAP_METHOD = "Method"
WRAP_METHODS = {
    "analytical": "Analytical",
    "spline": "Spline Surface",
    "project": "Project",  # TR156 (D2113)
}
SHAPE_TIPS = {
    "wrap_sketch": "A sketch of closed contours on a plane that touches the face.",
    "wrap_face": "A cylindrical or flat face to wrap the sketch on (any face for Spline Surface).",
    "wrap_method": (
        "Analytical keeps lengths exactly on cylinders and flat faces; the sketch must touch "
        "the face. Spline Surface works on any face from the point nearest the sketch origin, "
        "but cannot wrap all the way round."
    ),
    "wrap_type": "Emboss raises the contours, Deboss sinks them, Scribe only marks the face.",
    "wrap_thickness": "How far the contours are raised or sunk.",
    "wrap_reverse": "Wrap the sketch the other way round the cylinder.",
    "dome_faces": "Flat faces to dome.",
    "distance": "Dome height at the middle of the face. 0 on a round face meets the side tangent.",
    "dome_reverse": "Sink the dome into the part (concave).",
    "elliptical": "Round faces get a half ellipsoid instead of a spherical cap.",
    "continuous": "Polygon faces get one smooth surface; off, the dome rises from each edge.",
    "rib_sketch": "An open sketch: lines and arcs joined end to end.",
    "thickness": "The rib wall thickness.",
    "side": "Which side of the sketch curve the thickness lies on.",
    "rib_direction": "Grow in the sketch plane or straight out of it, until it meets the part.",
    "flip": "Grow toward the other side of the sketch curve.",
    "extend": "Linear: ends go straight on. Natural: an arc at an end keeps curving.",
    "rib_draft": "Lean the rib walls so it gets thinner as it grows (one straight line only).",
    "rib_draft_at": "Where the rib has the thickness typed: on the sketch plane, or where "
    "it meets the wall.",
    "wrap_pull": "Optional: pick a line, edge or plane. The raised or sunk walls run along "
    "it instead of square to the face.",
    "body": "In a part with several bodies, a face of the body the rib joins.",
}

# Sketch text (P4.8) --------------------------------------------------------------------------

TEXT_TITLE = "Sketch Text"
TEXT_ITEM = "Text Item"
TEXT_NEW = "New Text"
TEXT_TEXT = "Text"
TEXT_FONT = "Font"
TEXT_HEIGHT = "Height"
TEXT_BOLD = "Bold"
TEXT_ITALIC = "Italic"
TEXT_CURVE = "Along"
TEXT_NO_CURVE = "Straight From a Point"
TEXT_LINE = "Line"
TEXT_ARC = "Arc"
TEXT_CIRCLE = "Circle"  # TR230 (D976)
TEXT_SPLINE = "Spline"
TEXT_OFFSET = "Start Offset"
TEXT_OFFSET_TIP = (
    "How far along the curve the text starts, in mm, after the alignment. On a circle, "
    "Centre puts the text on top."
)
TEXT_ANGLE = "Angle"
TEXT_ALIGN = "Alignment"
TEXT_ALIGNS = {"left": "Left", "center": "Centre", "right": "Right", "full": "Full"}
TEXT_BOX = "Text Box Width"
TEXT_WIDTH = "Width Factor"
TEXT_SPACING = "Spacing"
TEXT_CHAR_ANGLE = "Rotate Each Character"
TEXT_FLIP_H = "Flip Horizontal"
TEXT_FLIP_V = "Flip Vertical"
TEXT_STENCIL = "Stencil"  # TR297 item 3 (D802)
TEXT_STENCIL_TIP = (
    "Leaves a bridge across the inside of letters such as O and A, so the middle stays "
    "joined when the text is cut through a sheet."
)
TEXT_BRIDGE = "Bridge width"
TEXT_BRIDGE_TIP = "How wide each stencil bridge is. 0: 12 percent of the text height."
# TR121 item 2 (D2202): styles for the characters selected in the text box.
TEXT_STYLE_ROW = "Selected characters"
TEXT_STYLE_BOLD = "Bold"
TEXT_STYLE_ITALIC = "Italic"
TEXT_STYLE_TURN = "Turn"
TEXT_STYLE_CLEAR = "Clear Styles"
TEXT_STYLE_TIP = (
    "Select characters in the text box, then make them bold or italic, or turn them by "
    "the angle beside Turn."
)
TEXT_DELETE = "Delete Text"
TEXT_NEEDS_SKETCH = "Open a sketch first, then add text to it."
TEXT_TIPS = {
    "pick": "Add a new text, or pick one of the sketch's texts to change it.",
    "text": "The text to write.",
    "font": "An installed font.",
    "curve": "Write along a sketch line, arc, circle or spline, or straight from the X and Y "
    "point.",
    "box": "Width of the text box used by the alignment (0 for none).",
}

#: One sentence tooltips of the Phase 4 commands (merged into ``strings.TOOLTIP_TEXT``).
COMMAND_TIPS = {
    "feature.hole": "Make holes of one type and size at points on a face.",
    "feature.cosmetic_thread": "Mark a thread on a hole or shaft without modelling it.",
    "feature.modeled_thread": "Model a real helical thread on a hole or shaft.",
    "feature.mounting_boss": "Add a boss for a screw or pin, with fins.",
    "feature.snap_hook": "Add a cantilever snap hook.",
    "feature.snap_groove": "Cut the groove a snap hook catches in.",
    "feature.lip_groove": "Add a lip on one rim and a groove in the other.",
    "feature.vent": "Cut a vent with ribs and spars from a sketch.",
    "feature.rib": "Add a wall from an open sketch that grows until it meets the part.",
    "feature.dome": "Raise flat faces into domes, or sink them.",
    "feature.corner_relief": "Relieve inside corners so a round milling tool can reach them.",
    "feature.wrap": "Emboss, deboss or scribe a sketch on a cylindrical or flat face.",
    "sketch.text": "Add text to the sketch, to extrude, cut or wrap like any closed profile.",
}

# Corner Relief (TR244, D785) ----------------------------------------------------------

GROUP_RELIEF = "Corner Relief"
LABEL_RELIEF_TYPE = "Relief"
RELIEF_TYPES = {"dogbone": "Dogbone", "t_bone": "T-Bone", "fillet": "Corner Fillet"}
LABEL_TOOL_DIAMETER = "Tool Diameter"
LABEL_RELIEF_CLEARANCE = "Clearance"
LABEL_RELIEF_FLIP = "Other Wall"
LABEL_RELIEF_EDGES = "Corner Edges"
LABEL_RELIEF_FEATURE = "All Corners Of"
RELIEF_TIPS = {
    "relief_type": "Dogbone cuts along the corner's diagonal, T-Bone into one wall, Corner "
    "Fillet rounds the corner to the tool.",
    "tool_diameter": "The milling tool's diameter. Type a variable to share it.",
    "clearance": "Added to the relief radius so the tool does not rub.",
    "flip": "A T-Bone cuts into the other wall.",
    "edges": "Pick inside corner edges, or choose a feature below.",
    "feature": "Every inside upright corner of this cut.",
}
# Self tapping holes (TR255, D840)
SELF_TAP_TABLE_TITLE = "Self Tapping Hole Sizes"
# Magnet pockets (TR179, D869)
GROUP_MAGNET = "Magnet"
LABEL_MAGNET_LENGTH = "Block length"
LABEL_MAGNET_SKIN = "Closed skin"
OPT_MAGNET_RELIEF = "Relief slots"
TIPS["magnet"] = (
    "Diameter is the magnet's diameter, or a block's width; depth is its thickness. "
    "Block length 0 makes a round pocket. Relief slots let air and glue out."
)
TIPS["magnet_skin"] = (
    "Leave this much material over the pocket so it is closed. Pause the print at that "
    "layer and drop the magnet in. 0 leaves the pocket open."
)
# Dowel holes (TR252, D872)
LABEL_DOWEL_FIT = "Pin fit"
DOWEL_FITS = {"press": "Press", "slip": "Slip"}
TIPS["dowel_fit"] = (
    "Press: the hole is the pin's nominal size, so the slightly over size pin grips. "
    "Slip: the hole is 0.02 mm larger so the pin slides in. For printed parts add a "
    "Print Fit as well."
)
# Bearing seats (TR251, D873)
GROUP_BEARING = "Bearing"
LABEL_BEARING_WIDTH = "Bearing width"
OPT_BEARING_GROOVE = "Retaining ring groove"
TIPS["bearing"] = (
    "The seat holds the bearing's outer ring; the smaller hole below leaves a shoulder "
    "for the ring to sit on while the inner ring turns freely. Diameter is that hole."
)
TIPS["bearing_groove"] = (
    "Cut a groove for an internal retaining ring above the bearing. The seat gets "
    "deeper by the groove and a 0.5 mm land."
)
# Hole size carry over setting (TR66, D892)
CARRY_SIZE = "Keep size when the type changes"
TIPS["carry_size"] = (
    "On: a new hole type starts with the size you had. Off: each hole type starts with "
    "the size you last used for it. Remembered for every part."
)
