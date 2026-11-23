"""User visible text for the Help menu and the first run welcome (D551 to D554).

Kept apart from ``strings.py`` so parallel work on other panels does not clash.
Title case for commands, sentence case for messages (CLAUDE.md section 8).
"""

from __future__ import annotations

# Help menu -------------------------------------------------------------------------------

WELCOME = "&Welcome"
USER_GUIDE = "Open &User Guide"
SHORTCUTS = "&Keyboard Shortcuts"
ABOUT = "&About FDCAD"
WHATS_NEW = "&What's New"  # TR291 item 3 (D2018)
WHATS_NEW_TITLE = "What's New"
WHATS_NEW_MISSING = "The list of changes was not found. Reinstall FDCAD to get it back."
PANEL_HELP = "Help"  # the button's name for screen readers; it shows an icon (D2701)
PANEL_HELP_TIP = "Help: open the user guide at this tool's page (F1)."  # TR291 item 1
HINT_SHOW_ME = "Show Me"
HINT_TURN_OFF = "Turn off hints"

# About box -------------------------------------------------------------------------------

ABOUT_TITLE = "About FDCAD"
ABOUT_HEADING = "FDCAD {version}"
ABOUT_SUMMARY = "Open source parametric part modeler for 3D printing and general parts."
ABOUT_LICENSE = (
    "FDCAD is free software, licensed under the GNU General Public License, "
    "version 3 or later (GPL v3). It comes with no warranty."
)
#: FDCAD's own copyright line, the same as the installer and the Mac app (D2866).
ABOUT_COPYRIGHT = "Copyright (C) 2026 the FDCAD contributors"
#: A link on the About tab that opens the notices on the Licenses tab (D2867).
ABOUT_NOTICES_LINK = (
    "FDCAD includes third party components under their own licenses. Read the "
    '<a href="notices">third party notices</a> and the '
    '<a href="offer">source offer</a>.'
)
#: The one sentence CLAUDE.md 7.5 allows, the same as the README (D553).
NOT_AFFILIATED = (
    "FDCAD is not affiliated with or endorsed by Dassault Systèmes or Robert McNeel and "
    "Associates; SOLIDWORKS, Rhinoceros and Grasshopper are their trademarks."
)
ABOUT_TAB = "About"
LICENSES_TAB = "Licenses"
LICENSE_DOCS = {
    "license": "FDCAD license (GPL v3)",
    "notices": "Third party notices",
    "offer": "Source offer",
    "lgpl21": "GNU LGPL 2.1",
    "lgpl3": "GNU LGPL 3",
}
LICENSE_MISSING = (
    "The file {name} is not in this installation. Reinstall FDCAD to restore it, "
    "or read the license texts in the source repository."
)
CLOSE = "Close"

# User guide ------------------------------------------------------------------------------

GUIDE_TITLE = "FDCAD User Guide"
GUIDE_HOME = "Contents"
GUIDE_BACK = "Back"
GUIDE_FORWARD = "Forward"
GUIDE_MISSING = "The user guide was not found in this installation. Reinstall FDCAD to restore it."
GUIDE_EXTERNAL = (
    "FDCAD does not open web pages. Copy the address into your browser to read it: {url}"
)

# Keyboard shortcuts ----------------------------------------------------------------------

SHORTCUTS_TITLE = "Keyboard Shortcuts"
SHORTCUTS_FILTER = "Type to filter by command or key"
SHORTCUTS_COLUMNS = ("Command", "Group", "Keys")
SHORTCUTS_NOTE = (
    "These are the keys in use now, with your changes. Change them in Preferences, "
    "on the Shortcuts tab."
)
SHORTCUTS_MAC_NOTE = "On a Mac, Ctrl is shown as Cmd and Meta as Control."
SHORTCUTS_EDIT = "Change Shortcuts"

# First run welcome -----------------------------------------------------------------------

WELCOME_TITLE = "Welcome to FDCAD"
WELCOME_INTRO = (
    "FDCAD builds a part from sketches and features. Any value can be changed later, "
    "and the part rebuilds from its feature tree."
)
#: (heading, text) pairs shown as short sections in the welcome.
WELCOME_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "Start a sketch",
        "Click Sketch on the Features tab, or press S. Click one of the three planes or a "
        "flat face. Draw with Line (L), Corner Rectangle or Circle, add dimensions with "
        "Smart Dimension (D), then click Exit Sketch in the top right corner. Extruded "
        "Boss turns the sketch into a solid.",
    ),
    (
        "The command tabs",
        "The tabs at the top hold the tools: Features, Sketch, Bodies, 3D Print, Sheet "
        "Metal, Evaluate and Graph. Hover a button to read what it does and its key. A "
        "button with a small arrow holds more tools.",
    ),
    (
        "The left panel",
        "The icons down the left side switch the left panel between the Feature Tree, "
        "Properties, Variables, Errors and Configurations. Hover an icon to see its name. "
        "The Errors icon shows how many errors the part has.",
    ),
    (
        "Preferences and themes",
        "Tools, Preferences (Ctrl+,) holds units, keys, mouse or trackpad navigation, "
        "autosave and the colour theme: Beige, Light Gray, Dark Grey, Stealth or Follow "
        "system.",
    ),
    (
        "The user guide",
        "Help, Open User Guide shows the guide inside FDCAD, with tutorials built on the "
        "sample parts in File, Open Sample. It needs no internet connection.",
    ),
)
WELCOME_AGAIN = "Show this again from Help, Welcome."
WELCOME_OPEN_GUIDE = "Open User Guide"
WELCOME_START = "Start Modeling"
