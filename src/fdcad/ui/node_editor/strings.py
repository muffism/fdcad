"""Text of the node editor (PLAN section 8 item 14: all UI strings in one place)."""

from __future__ import annotations

PANEL_TITLE = "Node Editor"
TAB_GRAPH = "Graph"
GROUP_GRAPH = "Graph"
GROUP_EDIT = "Edit"
GROUP_VIEW = "View"
NEW_GRAPH = "Graph 1"
SEARCH_PLACEHOLDER = "Search nodes"
NO_PART = "Open a part to use the node editor."
EMPTY_HINT = "Double click the canvas or press the Add Node key to add a node."
SETTINGS_TITLE = "Node settings"
NOTHING_SELECTED = "Select a node to see its settings."
RUN_ANYWAY = "Run Anyway"
GROUP_NAME = "Group"
COMMENT_TEXT = "Comment"
POSITION_ROW = "{graph} (node graph)"
POSITION_TIP = "{graph} runs here. It reads only features above this row."
STATUS_RUNNING = "Updating preview..."
STATUS_DONE = "Preview updated in {seconds:.2f} s."
STATUS_ERRORS = "{count} node(s) have errors. Hover a red node to see why."
STATUS_CANCELLED = "Preview cancelled."
TOO_MANY_NODES = "A graph can have at most {limit} nodes. Delete some nodes first."
GRAPH_ROW_ERROR = "{graph} failed: {error} Open it in the node editor to fix it."
PASTE_DAMAGED = "The copied nodes could not be read. Copy the nodes again, then paste."
WIRE_REFUSED = "Cannot wire these ports: {reason}"
POSITION_SET = "{graph} now runs after {feature}."
POSITION_NEEDS_FEATURE = "Select a feature in the feature tree first."
GRAPH_BODY_NAME = "Graph Body {n}"
# The title bar's two buttons (D2745). Each word is the accessible name and starts
# the tooltip.
TITLE_FLOAT = "Float"
TITLE_FLOAT_TIP = (
    "Float: put the node editor in a window of its own. "
    "A double click on the title bar does the same."
)
TITLE_DOCK = "Dock"
TITLE_DOCK_TIP = (
    "Dock: put the node editor back in the main window. "
    "Drag the title bar to dock it at another side."
)
TITLE_CLOSE = "Close"
TITLE_CLOSE_TIP = "Close: hide the node editor. Node Editor on the Graph tab shows it again."

# Undo step names.
UNDO_ADD_NODE = "Add {title} Node"
UNDO_DELETE = "Delete Nodes"
UNDO_MOVE = "Move Nodes"
UNDO_WIRE = "Connect Nodes"
UNDO_UNWIRE = "Disconnect Nodes"
UNDO_SETTING = "Change {title}"
UNDO_GROUP = "Group Nodes"
UNDO_UNGROUP = "Ungroup Nodes"
UNDO_PASTE = "Paste Nodes"
UNDO_POSITION = "Move Graph Position"
UNDO_NEW_GRAPH = "New Graph"
UNDO_RUN_ANYWAY = "Run Anyway"

#: Node categories in the add list, in this order.
CATEGORY_ORDER = (
    "Input",
    "Math",
    "List",
    "Point and Vector",
    "Curve",
    "Solid",
    "Pattern",
    "Output",
    "Display",
)
