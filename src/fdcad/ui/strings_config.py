"""UI text for equations, configurations and design tables (PHASE4_SPEC P4.10)."""

# Equations manager -------------------------------------------------------------------

EQUATIONS_TITLE = "Equations"
EQ_HEADERS = ["Name", "Value / Equation", "", "Evaluates To", "Comments"]
EQ_SECTIONS = {
    "variable": "Global Variables",
    "feature": "Feature Values",
    "equation": "Equations",
}
EQ_ADD = {
    "variable": "Add global variable",
    "feature": "Add suppression or tick box (reverse@Extrude 1)",
    "equation": "Add equation",
}
EQ_DELETE = "Delete Row"
EQ_OK_MARK = "✓"
EQ_BAD_MARK = "✗"
EQ_SUPPRESSED = "Suppressed"
EQ_UNSUPPRESSED = "Unsuppressed"
EQ_HELP = (
    "Type a name and press Enter; the value starts with =. Use numbers with units, other "
    "names in quotes, functions ({functions}), comparisons and if(condition, then, else). "
    "Double click a dimension in the view to use it."
)
EQ_PICKED = 'Added "{name}" to the equation.'
EQ_NOT_APPLIED = "Equations not applied: {message}"
EQ_UNDO = "Edit Equations"
# Equations text file (TR25, D749).
EQ_EXPORT = "Export..."
EQ_EXPORT_TIP = "Saves every variable and equation to a text file."
EQ_IMPORT = "Import..."
EQ_IMPORT_TIP = "Reads variables and equations from a text file into the manager."
EQ_LINK = "Link..."
EQ_LINK_TIP = "Links a text file that is read again when the part opens and on Rebuild."
EQ_UNLINK = "Remove Link"
EQ_UNLINK_TIP = "The part stops reading the linked file. The values stay as they are."
EQ_LINK_NONE = "Linked file: none"
EQ_LINKED = "Linked file: {name}"
EQ_FILE_FILTER = "Text files (*.txt);;All files (*)"
EQ_EXPORT_TITLE = "Export Equations"
EQ_IMPORT_TITLE = "Import Equations"
EQ_LINK_TITLE = "Link Equations File"
EQ_EXPORTED = "Saved the equations to {name}."
EQ_EXPORT_FAILED = (
    "Equations not saved: {reason}. Check the folder and file name, then export again."
)
EQ_IMPORTED = "Read {count} changed rows from {name}. Press OK to apply them."
EQ_IMPORT_SKIPPED = (
    " Left out {count} rows the part does not have ({names}). Check the names in the file."
)
EQ_FILE_UNREADABLE = "{name} not read: {reason}. Check the file, then import again."
EQ_LINK_READ = "Read {count} changed values from {name}."
# Extrude picks the operation (TR334, D2110).
AUTO_OPERATION = "Pick operation from where it sits"
AUTO_OPERATION_TIP = (
    "Boss, Cut or New Body is chosen on each rebuild: mostly inside the part cuts, "
    "touching the part joins, apart from it makes a new body."
)
AUTO_ALTERNATE = "Alternate solution"
AUTO_ALTERNATE_TIP = "Take the other choice: a cut becomes a boss, a boss or new body a cut."
AUTO_CHOSEN = "Chosen: {op}"
AUTO_NAMES = {"boss": "Boss", "cut": "Cut", "new_body": "New Body"}
# Partial success (TR400, D2109).
FIX_HOLES_SKIPPED = (
    "{count} holes skipped. Click a skipped point in the Hole panel to cut it again."
)
# Seed and boundary pick (TR328, D2108).
SEED_PICK = "Select Faces Between"
SEED_PICK_DONE = "{n} faces selected between the picked boundary."
SEED_PICK_FAILED = "No faces selected: {reason}"
# Move a feature to another body (TR155, D2107).
MOVE_BODY = "Move to Body..."
MOVE_BODY_TITLE = "Move to Body"
MOVE_BODY_PROMPT = "Body the feature acts on:"
MOVE_BODY_UNDO = "Move {name} to Another Body"
MOVE_BODY_DONE = "{name} now acts on {body} only. Use Undo to put it back."
# Body folders (TR153, D2106).
BODY_FOLDER_MOVE = "Move to Folder..."
BODY_FOLDER_TITLE = "Body Folder"
BODY_FOLDER_PROMPT = "Folder name (leave empty to take the body out of its folder):"
BODY_FOLDER_UNDO = "Body Folder"
BODY_FOLDER_ACTIONS = {
    "hide": "Hide Bodies",
    "show": "Show Bodies",
    "colour": "Colour...",
    "delete": "Delete Bodies",
    "rename": "Rename Folder...",
    "remove": "Remove Folder",
}
BODY_FOLDER_DELETED = (
    "Delete Body added for {count} bodies of {folder}. Use Undo to bring them back."
)
BODY_FOLDER_NO_DELETE = "These bodies cannot be picked for Delete Body. Use Delete Body on them."
# Library feature files (TR72, D2115).
LIBRARY_SAVE = "Save as Library Feature..."
LIBRARY_INSERT = "Insert Library Feature"
LIBRARY_FILTER = "FDCAD library features (*.fdlib)"
LIBRARY_SAVED = "Saved {name}. Use Tools, Insert Library Feature to put it in a part."
LIBRARY_SAVE_FAILED = "The library feature could not be saved: {reason}. Choose another folder."
LIBRARY_READ_FAILED = "The library feature could not be read: {reason}. Choose another file."
LIBRARY_WHAT = "Select a sketch, or a feature made from a sketch, to save as a library feature."
# Named faces and edges (TR152, D2105).
NAMED_TITLE = "Name This Item"
NAMED_PROMPT = "Name (letters, digits, spaces and underscores):"
NAMED_NO_REF = "This item has no lasting name to keep. Pick a face or edge of a feature."
NAMED_SET = "Named {name}. Find it in Tools, Named Items."
NAMED_UNDO = "Name Item"
NAMED_LIST_TITLE = "Named Items"
NAMED_HELP = (
    "Click a name to pick its item in the 3D view. Custom property formulas can use "
    '"area@name" for a face and "length@name" for an edge.'
)
NAMED_ROW = "{name} ({kind})"
NAMED_EMPTY = "No named items yet. Right click a face or edge and choose Name This Item."
NAMED_LOST = "{name} cannot be found: {reason}"
NAMED_PICK = "Click a named face or edge in the list first."
NAMED_RENAME = "Rename"
NAMED_REMOVE = "Remove Name"
# Text and yes or no variables, and groups (TR417, D2104).
VAR_TYPE = "Type..."
VAR_TYPE_TIP = "Make the chosen variables numbers, text or yes or no."
VAR_TYPES = {"": "Number", "text": "Text", "yes_no": "Yes or No"}
VAR_TYPE_PROMPT = "Type of {names}:"
VAR_TYPE_SET = "Type set to {type}. Click OK to keep it."
VAR_GROUP = "Group..."
VAR_GROUP_TIP = "Put the chosen variables in a group, so the list keeps them together."
VAR_GROUP_PROMPT = "Group of {names} (leave empty for none):"
VAR_GROUP_SET = "Group set: {group}. Click OK to keep it."
VAR_GROUP_SHOWN = "Group: {group}"
VAR_NO_GROUP = "none"
VAR_PICK = "Click a global variable first, then use this button."
# Variables read from a CSV table (TR198, D2102).
CSV_LOOKUP = "Read from CSV..."
CSV_LOOKUP_TIP = (
    "Read the chosen variable from a CSV table by row label or row number and column. "
    "It is read again when the part opens and on Rebuild."
)
CSV_LOOKUP_TITLE = "CSV Table for {name}"
CSV_LOOKUP_FILTER = "CSV files (*.csv *.txt);;All files (*)"
CSV_LOOKUP_ROW = "Row: a label from the first column, or a row number (1 is the first row):"
CSV_LOOKUP_COLUMN = "Column: the column's header:"
CSV_LOOKUP_SET = "{name} is now read from the CSV table: {value}. Click OK to keep it."
CSV_LOOKUP_STOPPED = (
    "{name} keeps its value and is no longer read from a file. Click OK to keep it."
)
CSV_LOOKUP_BAD = "{name} cannot be read: {reason}"
CSV_LOOKUP_NEW = "Click OK to add the variable first, then use Read from CSV again."
CSV_LOOKUP_READ = "Read {count} changed values from CSV tables."
CSV_LOOKUP_FAILED = (
    "{count} values could not be read from CSV tables and keep their values ({first}). "
    "Check the files."
)
CSV_LOOKUP_UNDO = "Read CSV Values"
EQ_LINK_SAME = "{name} has no changes."
EQ_LINK_FAILED = (
    "Equations file {name} not read: {reason}. "
    "Check the file, or remove the link in the equations manager."
)
EQ_LINK_UNDO_READ = "Read Equations File"
EQ_FOLDER = "Equations"
EQ_FOLDER_ROW = "{name} = {value}"
EQ_FOLDER_TIP = "Global variables. Double click to open the equations manager."

# Configurations ----------------------------------------------------------------------

TAB_CONFIGURATIONS = "Configurations"
CONFIG_ADD = "Add Configuration"
CONFIG_RENAME = "Rename"
CONFIG_DELETE = "Delete"
CONFIG_ACTIVATE = "Show Configuration"
CONFIG_TABLE = "Design Table"
CONFIG_NEW_NAME = "Configuration {n}"
CONFIG_ACTIVE = "{name} (active)"
CONFIG_NAME_PROMPT = "Configuration name:"
CONFIG_OVERRIDES = "{count} configured value(s)"
CONFIG_UNDO_ADD = "Add Configuration {name}"
CONFIG_UNDO_RENAME = "Rename Configuration {name}"
CONFIG_UNDO_DELETE = "Delete Configuration {name}"
CONFIG_UNDO_SWITCH = "Show Configuration {name}"
# TR197 (D2101): preview without switching, and colours per configuration.
CONFIG_PREVIEW = "Preview"
CONFIG_PREVIEW_TITLE = "Preview of {name}"
CONFIG_PREVIEW_BUILDING = "Building {name}. The part itself does not change."
CONFIG_PREVIEW_READY = "{name}, built on a copy. Use Show Configuration to make it active."
CONFIG_PREVIEW_FAILED = (
    "{name}, built on a copy: {n} feature(s) failed in it. "
    "Use Show Configuration to make it active and fix them."
)
CONFIG_PREVIEW_NONE = (
    "{name} has no solid to show. Use Show Configuration to make it active and check its features."
)
CONFIG_PREVIEW_ERROR = "{name} could not be built: {reason}. Use Show Configuration to check it."
CONFIG_PREVIEW_PICK = "Pick a configuration in the list first."
CONFIG_COLOURS = "Colours by Configuration"
CONFIG_COLOURS_BUTTON = "Own Colours"
CONFIG_COLOURS_TIP = (
    "Colours by Configuration: keep face, feature and body colours for each configuration."
)
CONFIG_COLOURS_ON = (
    "Face, feature and body colours are now kept for each configuration. "
    "Pick colours while a configuration is shown to change only that one."
)
CONFIG_COLOURS_OFF = (
    "Every configuration now uses the colours shown. "
    "Turn on Colours by Configuration to set them apart again."
)
CONFIG_UNDO_COLOURS = "Colours by Configuration"
CONFIG_UNDO_SCOPED = "Change {path} in {scope}"
CONFIG_SCOPE_MENU = "Configurations"
CONFIG_SCOPE = {
    "this": "This Configuration",
    "all": "All Configurations",
    "chosen": "Chosen Configurations...",
}
CONFIG_SCOPE_TIP = "Applies to: {scope}"
CONFIG_CHOOSE_TITLE = "Chosen Configurations"
CONFIG_SUPPRESS_THIS = "Suppress in This Configuration"
CONFIG_UNSUPPRESS_THIS = "Unsuppress in This Configuration"

# Design tables -----------------------------------------------------------------------

TABLE_SUMMARY = (
    "{column}: {count} values. Sum {total}, average {average}, smallest {smallest}, "
    "largest {largest}."
)  # TR198 (D966)
TABLE_SUMMARY_NONE = "Click a cell of a number column to see its sum, average and range."
TABLE_ADD_VALUES = "Add Values..."  # TR90 (D969)
TABLE_DESCRIPTION_HEADER = "Description"  # TR90 item 1 (D2100)
TABLE_THEME_HEADER = "Theme"  # TR331 (D2103)
TABLE_RULES = "Rules and Themes..."
TABLE_APPLY_RULES = "Apply Rules"
TABLE_TRY = "Try Row"
TABLE_UNDO_RULES = "Apply Rules"
TABLE_RULES_APPLIED = "Rules changed {count} value(s). Click OK to keep the table as shown."
TABLE_TRY_TITLE = "Trial of {name}"
TABLE_TRY_STARTED = "Building the values of {name} on a copy. No configuration is added."
TABLE_TRY_EMPTY = "Add a row first, then use Try Row."
RULES_TITLE = "Rules and Themes"
RULES_TAB = "Rules"
THEMES_TAB = "Themes"
RULES_HEADERS = ["On", "If", "Test", "Value", "Then", "Choices"]
THEMES_HEADERS = ["Theme", "Sets", "To"]
RULES_HELP = (
    "If the first value passes the test, the Then value must be one of the choices, "
    "separated by commas; otherwise it is set to the first choice. Rules run from the "
    "top. Untick On to turn a rule off."
)
THEMES_HELP = (
    "A theme sets several values at once. Give each row a theme name, a value and what "
    "to set it to. Pick a theme in the design table's Theme column."
)
RULES_ADD = "Add Rule"
THEMES_ADD = "Add Value"
RULES_DELETE = "Delete"
RULES_UP = "Move Up"
RULES_DOWN = "Move Down"
RULES_UNDO = "Rules and Themes"
TABLE_COLOR_HEADER = "Part Colour"
TABLE_PROPERTY_HEADER = "{name} (property)"
TABLE_VALUES_PROMPT = (
    "Tick the values to add as columns. Variables and values set by a formula start ticked."
)
TABLE_VALUES_ADDED = "{count} columns added. Type each configuration's values, then click OK."
TABLE_TITLE = "Design Table"
TABLE_CONFIG_HEADER = "Configuration"
TABLE_ADD_ROW = "Add Row"
TABLE_DELETE_ROW = "Delete Row"
TABLE_ADD_COLUMN = "Add Column"
TABLE_DELETE_COLUMN = "Delete Column"
TABLE_IMPORT = "Import CSV..."
TABLE_EXPORT = "Export CSV..."
# TR304 (D930)
TABLE_COPY = "Copy Table"
TABLE_PASTE = "Paste Table"
TABLE_COPIED = (
    "The table is on the clipboard. Paste it into a spreadsheet or another part's Design Table."
)
TABLE_PASTED = "The pasted table is shown. Click OK to apply it."
TABLE_PASTE_EMPTY = "The clipboard has no table. Copy a table or spreadsheet cells first."
TABLE_REMOVE = "Remove Table"
TABLE_COLUMN_PROMPT = "Parameter:"
TABLE_CSV_FILTER = "CSV files (*.csv)"
TABLE_UNDO = "Edit Design Table"
#: Apply would delete configurations the table no longer lists (audit D3 item 11, D724).
TABLE_DELETES = (
    "OK deletes these configurations, which the table no longer lists: {names}. Delete them?"
)
TABLE_UNDO_REMOVE = "Remove Design Table"
TABLE_NOT_APPLIED = "Design table not applied: {message}"
TABLE_CSV_UNREADABLE = (
    "Design table not applied: the CSV file cannot be read ({reason}). "
    "Save it again as CSV text and import it again."
)
TABLE_EXPORTED = "Design table exported to {path}."
TABLE_EXPORT_FAILED = (
    "Design table not exported: the CSV file cannot be written ({reason}). "
    "Choose another folder or file name and export again."
)
TABLE_HELP = (
    "Rows are configurations; columns are values such as var.Width, f6.depth or "
    "f9.suppressed. Suppression is S or U. Leave a cell empty to keep that value as it is."
)
# Equations manager comfort (TR194, D830)
EQ_FILTER = "Filter rows"
EQ_DISABLE = "Disable"
EQ_DISABLE_TIP = (
    "Keeps the selected equations but stops using them, or uses them again when all are disabled."
)
EQ_DISABLE_PICK = "Select equation rows to disable or enable."
EQ_DISABLED = "Disabled"
EQ_SORT = "Sort"
EQ_SORT_TIP = "Sorts the rows of each section by name."
EQ_REPLACE = "Replace Name"
EQ_REPLACE_TIP = "Replaces a name the row uses that no longer exists, such as a deleted feature."
EQ_REPLACE_PICK = "Select the row that uses the missing name first."
EQ_REPLACE_NONE = "Every name this row uses exists. Nothing to replace."
EQ_REPLACE_ASK = 'Replace "{name}" with:'
EQ_REPLACED = '"{old}" replaced with "{new}".'
# Linked child configurations (TR195, D868)
CONFIG_ADD_LINKED = "Add Linked"
CONFIG_LINKED = "(linked to {parent}, {n} own values)"
# Variables with allowed values (TR274, D906)
EQ_ALLOWED = "Allowed Values"
EQ_ALLOWED_TIP = "Limit the chosen variable to a list of values or a range."
EQ_ALLOWED_PROMPT = (
    "Allowed values of {name}: a list such as 10, 20, 30, or a range such as 5..50. "
    "Leave empty to allow any value."
)
EQ_ALLOWED_PICK = "Click a global variable first, then press Allowed Values."
EQ_ALLOWED_SET = "Allowed values of {name} set. Press OK to keep them."
