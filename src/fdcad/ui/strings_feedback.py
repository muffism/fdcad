"""User visible text for messages, status bar feedback, window details and diagnostics.

UI_POLISH_SPEC U8, U9 and U10 (D673 to D679). Kept apart from ``strings.py`` so
parallel work on other panels does not clash. Title case for commands, sentence
case for messages, no dashes (CLAUDE.md section 8).
"""

from __future__ import annotations

# Error messages (U8.2) -------------------------------------------------------------------
ERROR_TITLE = "FDCAD"
COPY_DETAILS = "Copy Details"
COPY_DETAILS_TIP = "Copy the technical details, to paste into a bug report"
COPIED = "Copied"
UNEXPECTED = (
    "The last command stopped because of an internal error. Your open parts are not "
    "changed. Save your work. If it happens again, use Report Problem to send us a "
    "report. If the 3D view does not draw, tick Safe graphics in Preferences "
    "or start FDCAD with --safe-graphics."
)
UNEXPECTED_THREAD = (
    "A background task stopped because of an internal error. Your open parts are not "
    "changed. Save your work. If it happens again, send the log with a bug report."
)
OPEN_FAILED_CONTEXT = "Opening {path}"
SAVE_FAILED_CONTEXT = "Saving {path}"
READ_FAILED_CONTEXT = "Reading {path}"

# Confirmations of destructive steps (U8.5) -----------------------------------------------
UNSAVED = (
    "Save changes to {name} before closing? If you close without saving, the changes "
    "since the last save are lost."
)

# Status bar (U8.1, U8.4) -----------------------------------------------------------------
SAVED = "Saved {name}"
SAVING = "Saving {name}"
EXPORTING = "Exporting {name}"
OPENING = "Opening {name}"
CANCEL = "Cancel"
CANCEL_TIP = "Stop this task"

# Empty places (U8.3) -----------------------------------------------------------------------
NO_RECENT = "No recent files"
EMPTY_TREE = "Start a sketch on a plane: select Front, Top or Right, then click Sketch."
# Empty states of the left panel (D2702).
NO_PART_OPEN = "No part is open. Use New Part or Open to start."
NO_PART_VARIABLES = "No part is open. Use New Part or Open, then add variables here."
NO_VARIABLES = "No variables yet. Use Add Variable to make one."
NO_COMMAND_MATCH = 'No command matches "{text}". Try a shorter or different word.'

# Window (U9) -------------------------------------------------------------------------------
WINDOW_TITLE = "{name}[*] \N{MIDDLE DOT} FDCAD"
ABOUT_BUILD = "Built {date}"
ABOUT_BUILD_SOURCE = "Running from source"
ABOUT_LOGS = "Log folder: {path}"
OPEN_LOG_FOLDER_BUTTON = "Open Log Folder"

# Help, Diagnostics (U10.3) -----------------------------------------------------------------
DIAGNOSTICS = "&Diagnostics"
COPY_SYSTEM_INFO = "Copy &System Info"
OPEN_LOG_FOLDER = "Open &Log Folder"
SYSTEM_INFO_COPIED = "System info copied. Paste it into your bug report."
LOG_FOLDER_FAILED = "Could not open the log folder {path}. Open it in your file manager instead."

# Problem reports (D2871): FDCAD never sends anything; the user's mail app does ---------------
REPORT_PROBLEM = "Report Problem"
REPORT_PROBLEM_TIP = (
    "Save a problem report and open your mail app with a message to the FDCAD team. "
    "Nothing is sent until you press Send."
)
REPORT_A_PROBLEM = "&Report a Problem"
REPORT_READY = "Problem report saved and copied. Check the message in your mail app, then send it."
REPORT_FROM_HELP = "Reported from the Help menu"
REPORT_CLOSED = "FDCAD closed unexpectedly"
REPORT_NO_MAIL = (
    "FDCAD could not open a mail app. The problem report is saved at {path} and is on the "
    "clipboard. Use any mail service to send it to {address}."
)
REPORT_NO_MAIL_NO_FILE = (
    "FDCAD could not open a mail app or save the report. The problem report is on the "
    "clipboard. Use any mail service: paste it into an email to {address}."
)
REPORT_OPEN_FOLDER = "Open Folder"
REPORT_SUBJECT = "FDCAD {version} problem report"
REPORT_MAIL_ASK = "What were you doing when the problem happened?"
REPORT_MAIL_VERSION = "FDCAD: {version}"
REPORT_MAIL_OS = "OS: {os}"
REPORT_MAIL_PROBLEM = "Problem: {summary}"
REPORT_MAIL_SAVED = (
    "The full report is saved at {path} and is on the clipboard. Please attach the file "
    "or paste it below."
)
REPORT_MAIL_CLIPBOARD = "The full report is on the clipboard. Please paste it below."
REPORT_TITLE = "FDCAD problem report"
REPORT_MADE = "Made {time}. The login name is shown as <user> and the home folder as <home>."
REPORT_SYSTEM = "System"
REPORT_LOG = "Log: the last {count} lines of fdcad.log"
REPORT_LOG_EMPTY = "No log lines were found."
REPORT_CRASH = "Native crash: the last FDCAD session in crash.log"
REPORT_DETAILS = "Error details"
REPORT_NOTE = "Note"

# Developer overlay (U10.4) -----------------------------------------------------------------
PREF_DEV_OVERLAY = "Show frame and rebuild times in the view (for developers)"
PREF_DEV_OVERLAY_TIP = (
    "Shows how long the last frame and the last rebuild took, in the lower left corner "
    "of the 3D view."
)
OVERLAY = "Frame {frame} \N{MIDDLE DOT} Rebuild {rebuild}"
OVERLAY_NONE = "none yet"
