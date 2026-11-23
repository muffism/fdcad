"""Accessible names of the main areas of the window (UI polish spec U4.3, D665).

Screen readers announce these. Icon buttons and fields without a label take
their tooltip title instead (``themes.app_style.name_widget``).
"""

from __future__ import annotations

NAME_TREE = "Feature tree"
NAME_PROPERTY_PANEL = "Property panel"
NAME_SIDE_PANEL = "Side panel"
NAME_VARIABLES = "Variables"
NAME_ERRORS = "Errors"
NAME_VIEW = "3D view"
NAME_SKETCH = "Sketch editor"
NAME_DOCUMENTS = "Open parts"
NAME_VIEW_TOOLS = "View tools"
NAME_STATUS_BAR = "Status bar"
NAME_SEARCH = "Search tools"
NAME_QUICK_ACTIONS = "Quick actions"

# Describe Part and Large Controls (TR294, D2017)
DESCRIBE_TITLE = "Describe Part"
DESCRIBE_NAME = "Part {name}."
DESCRIBE_UNNAMED = "not saved yet"
DESCRIBE_EMPTY = "The part has no body yet."
DESCRIBE_BODIES = "Bodies: {count}."
DESCRIBE_SIZE = "Overall size {x} by {y} by {z} millimetres."
DESCRIBE_FEATURES = "{count} features, in order:"
DESCRIBE_SUPPRESSED = ", suppressed"
DESCRIBE_STATE = ", {state}"
DESCRIBE_NO_PART = "No part is open. Open or start a part to describe it."
PREF_LARGE_CONTROLS = "Large controls"
PREF_LARGE_CONTROLS_TIP = "Make command tab buttons and tree rows half as large again."
