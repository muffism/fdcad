"""User visible text for menus, selection, views, the tree and fields (TOOL_SPEC T8, T9, T14).

Kept apart from ``strings.py`` so parallel work on other panels does not clash.
Title case for commands, sentence case for messages (CLAUDE.md section 8).
"""

from __future__ import annotations

# Right click menus (T9) ---------------------------------------------------------------

SELECT = "Select"
ZOOM_TO_FIT = "Zoom to Fit"
PREVIOUS_VIEW = "Previous View"
VIEW_ORIENTATION = "View Orientation"
DISPLAY_STYLE = "Display Style"
RECENT_COMMANDS = "Recent Commands"
EXIT_SKETCH = "Exit Sketch"
DISCARD_CHANGES = "Discard Changes"
SMART_DIMENSION = "Smart Dimension"
SNAPPING = "Snapping"
END_CHAIN = "End Chain"
REVERSE_DIRECTION = "Reverse Direction"
NORMAL_TO = "Normal To"
HIDE = "Hide"
SHOW = "Show"
HIDE_SKETCH = "Hide Sketch"
SHOW_SKETCH = "Show Sketch"
RENAME = "Rename"
DELETE = "Delete"
SKETCH = "Sketch"
SELECT_OTHER = "Select Other"
# TR309 (D926)
MIRROR_IMAGE_ON = (
    "Mirror image about {name}, display only. Pick a plane in the tree first to use another."
)
MIRROR_IMAGE_OFF = "Mirror image hidden."
# TR93 (D915)
SELECT_PREVIOUS_NONE = "There is no earlier selection to bring back since the last rebuild."
INVERTED = "{count} items picked."
# TR303 (D943)
SIMILAR_TITLE = "Select Similar"
SIMILAR_HINT = (
    "Faces like the first picked face are picked. Choose Must match for the rules to use, "
    "and Except for a rule that takes faces out."
)
SIMILAR_RULES = {
    "kind_size": "Same kind and size",
    "parallel": "Parallel (planes and axes)",
    "area": "Same area (within 5%)",
}
SIMILAR_CHOICES = {"ignore": "Not used", "must": "Must match", "except": "Except"}
SIMILAR_MATCH = "Faces must match"
SIMILAR_ALL = "Every Must match rule"
SIMILAR_ANY = "Any Must match rule"
SIMILAR_NEEDS_FACE = "Select Similar needs a picked face. Pick a face first."
SIMILAR_NO_RULE = "No rule is set to Must match. Set at least one rule to Must match."
SIMILAR_FAILED = "The faces could not be compared. Rebuild the part and try again."
CONVERT_NOTHING = "Nothing is picked. Pick faces, edges or vertices first."
# TR94 (D944)
SETS_TITLE = "Selection Sets"
SETS_SAVE = "Save Selection Set"
SETS_NAME = "Name"
SETS_HINT = (
    "Pick a set to select what it holds now. A rule set picks again by its rule, so it "
    "follows changes to the part."
)
SETS_PICK = "Pick"
SETS_NEW_RULE = "New Rule Set"
SETS_COMBINE_TITLE = "Combine Sets"
SETS_DELETE = "Delete"
SETS_RULE = "Rule"
SETS_RULE_KINDS = {
    "feature": "Faces of a feature",
    "colour": "Faces of a colour",
    "edge_length": "Edges at least this long",
}
SETS_OPS = {"union": "Add", "subtract": "Take away", "intersect": "Keep shared"}
SETS_FIRST = "First set"
SETS_OP = "Combine by"
SETS_SECOND = "Second set"
SETS_ITEMS = "{count} picked items"
SETS_RULE_FEATURE = "faces of {name}"
SETS_RULE_COLOUR = "faces in {colour}"
SETS_RULE_LENGTH = "edges of {mm} mm or longer"
SETS_COMBINE = "{op}: {names}"
SETS_UNDO = "Save Selection Set"
SETS_DELETE_UNDO = "Delete Selection Set"
SETS_SAVED = 'Selection set "{name}" saved.'
SETS_SELF = "A combined set cannot use itself. Pick two other sets."
SETS_IN_USE = '"{name}" is used by {users}. Delete those sets first.'
SETS_NO_NAMES = "These picks have no stable names to save. Rebuild the part and pick again."
SETS_MISSING = (
    "{count} saved items are no longer in the part and were skipped. Save the set again "
    "to update it."
)
SETS_FAILED = "The selection set could not be worked out. Rebuild the part and try again."
SETS_NEED_TWO = "Combining needs two sets. Save another set first."
SELECT_MIDPOINT = "Select Midpoint"
GO_TO_FEATURE = "Go To Feature"  # TR200
CONSTRUCTION = "Construction Geometry"
ADD_RELATION = "Add Relation"
FIX = "Fix"
SELECT_CHAIN = "Select Chain"
EDIT_VALUE = "Edit Value"
MAKE_REFERENCE = "Make Reference"
MAKE_DRIVING = "Make Driving"
EDIT_FEATURE = "Edit Feature"
EDIT_SKETCH = "Edit Sketch"
REVOLVE = "Revolved Boss"
EXTRUDE = "Extruded Boss"
ROLL_BACK_HERE = "Roll Back to Here"
ROLL_FORWARD = "Roll Forward"
ROLL_PREVIOUS = "Roll to Previous"
ROLL_END = "Roll to End"
DELETE_ROLLED_BACK = "Delete Rolled Back Features"
LAST_TOOL = "Last Tool: {tool}"
NO_RECENT = "No commands yet"
MIDPOINT_SELECTED = "Midpoint of the edge selected at {point}."
SELECT_OTHER_EMPTY = "Nothing under the cursor to choose from. Point at an item and try again."

#: Display style names for the right click menu.
STYLE_NAMES = {
    "shaded_edges": "Shaded With Edges",
    "shaded": "Shaded",
    "hidden_lines": "Hidden Lines Removed",
    "hidden_lines_visible": "Hidden Lines Visible",
    "wireframe": "Wireframe",
}

#: Standard view names for the View Orientation submenu.
VIEW_NAMES = {
    "front": "Front",
    "back": "Back",
    "left": "Left",
    "right": "Right",
    "top": "Top",
    "bottom": "Bottom",
    "iso": "Isometric",
    "dimetric": "Dimetric",
    "trimetric": "Trimetric",
}

# Delete with the sketch (T9.10) -------------------------------------------------------

DELETE_TITLE = "Delete"
DELETE_KEEP_SKETCH = "Delete {name}. Also delete its sketch {sketch}?"
DELETE_ALSO_SKETCH = "Delete Sketch Too"
DELETE_KEEP = "Keep Sketch"

# Context toolbar (T8) -----------------------------------------------------------------

CONTEXT_TIPS = {
    "sketch": "Sketch",
    "normal_to": "Normal To",
    "edit": "Edit Feature",
    "edit_sketch": "Edit Sketch",
    "extrude": "Extruded Boss",
    "revolve": "Revolved Boss",
    "delete": "Delete",
    "construction": "Construction Geometry",
    "dimension": "Smart Dimension",
}

# Selection filters (T14.3.2) ------------------------------------------------------------

FILTER_BAR = "Selection Filter"
FILTERS_ON = "Filters on: only the chosen types select (F6 turns them off)"
FILTERS_OFF = "Filters off: everything selects (F6 turns them on)"
FILTER_CLEAR = "Clear All"
FILTER_ALL = "Select All"
#: A filter type the 3D view cannot pick (audit D11 item 2, D719).
FILTER_IN_TREE = "{name} are chosen in the feature tree, not in the 3D view. Click them there."
FILTER_NAMES = {
    "vertex": "Vertices",
    "edge": "Edges",
    "face": "Faces",
    "body": "Solid Bodies",
    "plane": "Planes",
    "axis": "Axes",
    "sketch": "Sketches",
    "segment": "Sketch Segments",
    "point": "Sketch Points",
    "dimension": "Dimensions",
}
FILTER_STATUS = "Selection filter: {names}"
FILTER_STATUS_NONE = "Selection filter off: everything selects."

# Views (T14.4) --------------------------------------------------------------------------

NORMAL_TO_SKETCH = (
    "The sketch already faces you, so it was fitted in the view. "
    "Close the sketch to turn the 3D view."
)
ZOOM_SELECTION_NOTHING = "Select faces, edges or sketch items first, then use Zoom to Selection."
SHOW_MENU = "Hide or Show"

# Feature tree (T14.5) -------------------------------------------------------------------

PART_PROBLEMS_TIP = "Click to list every error and warning of the part."
NO_PROBLEMS = "No warnings or errors."
DELETE_DEPENDENTS = (
    "Delete {name} and the features that use it: {names}? They are rolled back, "
    "so the part does not change now."
)
ROLLBACK_MENU = "Rollback Bar"
DROP_ON_FEATURE = "A feature can only be dropped on another feature. Drop it on a feature row."

# Value fields (T14.6) -------------------------------------------------------------------

EXPRESSION_TIP = (
    'Type a value or an expression starting with "=", for example =Width/2. '
    'Type ="Name" and press Enter to make a global variable from the value.'
)
SHOW_RESULT = "Show the result"
SHOW_EXPRESSION = "Show the expression"
VARIABLE_PRESS_ENTER = "Press Enter to make a global variable {name} from this value."
VARIABLE_BAD_NAME = (
    "{name} cannot be a variable name. Use letters, digits and underscores, starting with a letter."
)
VARIABLE_NO_VALUE = "Type a value first, then make the variable from it."
VARIABLE_TITLE = "New Global Variable"
VARIABLE_CONFIRM = "Make a global variable {name} = {value} and use it here?"

# Shortcut editor (T14.7) ----------------------------------------------------------------

SHORTCUT_COLUMNS = ["Category", "Command", "Shortcut", "Search Words"]
CATEGORY_ALL = "All"
#: Category names shown for command groups; Interface holds the commands of no menu.
CATEGORY_NAMES = {"Interface": "Other"}
PRESS_A_KEY = "Click here, then press the new key"
REMOVE_SHORTCUT = "Remove Shortcut"
RESET_DEFAULTS = "Reset to Defaults"
RESET_QUESTION = (
    "Reset only the shortcuts, or everything "
    "(shortcuts, search words, gestures and the shortcut bar)?"
)
RESET_SHORTCUTS_ONLY = "Shortcuts Only"
RESET_EVERYTHING = "All Input Settings"  # not theme, units or autosave (audit D3 item 16)
COPY_LIST = "Copy List"
KEY_IN_USE_TITLE = "Shortcut in Use"
KEY_IN_USE = "{key} is used by {names}. Move it to {command}?"

# Tree folders and comments (TR23) -------------------------------------------------

ADD_FOLDER = "Add to New Folder"
RENAME_FOLDER = "Rename Folder"
REMOVE_FOLDER = "Remove Folder"
COMMENT = "Comment..."
EDIT_COMMENT = "Edit Comment"
COMMENT_TITLE = "Comment"
COMMENT_PROMPT = "A short note for this feature. Leave it empty to remove the comment."

# Bodies a feature acts on (TR33) ---------------------------------------------------

BODIES_GROUP = "Bodies"
BODIES_ALL = "All bodies"
BODIES_SELECTED = "Selected bodies"
BODIES_TIP = "Which bodies this feature cuts or joins. Bodies not picked stay as they are."
BODIES_PICK_TIP = "Click any face of a body in the view to add the body."
BODY_PICK = "Body {index}"
BODIES_PICK_FACE = "Click a face of a body to add that body."
BODIES_NONE = "Pick one or more bodies, or choose All bodies."
# Ratio and difference relations (TR226, D870)
RELATION_VALUE_PROMPTS = {
    "length_ratio": "First length divided by the second:",
    "length_difference": "First length minus the second (mm):",
}
# Detach linked geometry (TR340, D885)
DETACH = "Detach from Model"
# Safe graphics (TR219, D2016)
SAFE_GRAPHICS_ON = {
    "flag": "Safe graphics: drawing in software, as asked with --safe-graphics.",
    "env": "Safe graphics: drawing in software, as asked by FDCAD_SAFE_GRAPHICS.",
    "setting": "Safe graphics: drawing in software. Turn it off in Preferences if the "
    "graphics driver works.",
    "crash": "Safe graphics: the last start did not finish, so this start draws in "
    "software. Tick Safe graphics in Preferences to keep it.",
}
PREF_SAFE_GRAPHICS = "Safe graphics (draw in software)"
PREF_SAFE_GRAPHICS_TIP = (
    "Draw without the graphics hardware, for computers whose graphics driver fails. "
    "Slower. Takes effect the next time FDCAD starts."
)
# Before and After (TR289, D2019)
COMPARE_TITLE = "Before and After"
COMPARE_NOTE = (
    "The part volume after each feature that changed in the last rebuild. Click a row "
    "to see that feature's part from before faintly over the part now."
)
COMPARE_NONE = "No feature changed volume in the last rebuild. Change a value, then look again."
COMPARE_COLUMNS = ("Feature", "Before (mm³)", "After (mm³)", "Change")
COMPARE_NO_PART = "No part is open. Open a part and change a value first."
# Shortcuts with an input method on (TR354, D2020)
SHORTCUTS_PAUSED = (
    "Single letter shortcuts are paused while the input method is composing. Turn the "
    "input method off, or switch it to direct input, to use them."
)

# TR329 (D2208): Pick in Volume.
PICK_VOLUME_TITLE = "Pick in Volume"
PICK_VOLUME_SHAPE = "Volume"
PICK_VOLUME_SHAPES = {"box": "Box", "cylinder": "Cylinder", "sphere": "Sphere"}
PICK_VOLUME_CENTRE = "Centre"
PICK_VOLUME_SIZE = "Size"
PICK_VOLUME_RADIUS = "Radius"
PICK_VOLUME_AXIS = "Cylinder axis"
PICK_VOLUME_MODE = "Pick what is"
PICK_VOLUME_MODES = {"inside": "Inside", "outside": "Outside", "touching": "Touching"}
PICK_VOLUME_KIND = "Pick"
PICK_VOLUME_KINDS = {"face": "Faces", "edge": "Edges", "vertex": "Vertices"}
PICK_VOLUME_WORKING = "Picking in the volume..."
PICK_VOLUME_DONE = "Picked {count} items in the volume."
PICK_VOLUME_NO_BODY = "Pick in Volume needs a part. Make a solid first."
PICK_VOLUME_FAILED = "The items in the volume could not be found. Change the volume and try again."
PICK_VOLUME_CHANGED = "The part changed while picking. Use Pick in Volume again."
