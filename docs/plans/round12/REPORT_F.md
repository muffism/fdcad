# Round 12 report: Local F (view, display, selection, mouse and UI)

Branch `local/round12f`, head 4e83e0de, from `phase7b-stage2` at 7dad52c0. Stopped at 82 percent of the 5 hour usage window. Written by the manager from the agent's final report (the agent could not write files at the end).

## Items done

| TR | Decision | Commit | What |
|---|---|---|---|
| TR210 | D1600, D1601 | 0740c0a9 | Corner triad axis clicks (look along it, again for the other side, Shift for a quarter turn); View > Orientation popup, no default key. Item 3 already worked. |
| TR212 | D1602 | 0740c0a9 | Preferences > View: smooth edges shown, dashed or removed; hidden edges dashed or solid; highlight all edges of the feature picked in the tree. |
| TR355 | D1603 | 0740c0a9 | Section zones to cut with two or three planes; chosen bodies see through with a slider. |
| TR213 (part) | D1604 | 0740c0a9 | A section saved with the part and in saved views. Not done: which bodies are cut, tree folder with handles, Measure on cut faces. |
| TR214 | D1605 | aa3ff4cf | View > Display Quality 1 to 10 per part; lighter drawing while turning parts over 1500 faces. |
| TR216 | D1606 | 1cc8c664 | Display Mode and Transparency on Solid Bodies rows (right click). Hidden lines per body left out (a whole view mode in the kernel). |
| TR88 | D1608 | d4ff814a | View > Display States: save, apply, delete, link to a configuration. |
| TR211 | D1607 | 58d80965 | Zoom Out (no key), double middle click fits; wheel direction, zoom about pointer or centre, arrow step, turn speed, fit on standard views. |
| TR312 | D1609 | f72b1729 | Three middle button presets. |
| TR224 | D1610 | b263b174 | Item 1 pick through see through bodies (Shift picks them); item 4 Before and After slider in previews. |
| TR221 | D1611 | 4e83e0de | Collapse All (no key); status bar shows hovered edge length and radius, or the angle to the picked flat face. |
| TR380 (part) | D1612 | 4e83e0de | Item 1 trackpad rotate, smart zoom, swipe. Not done: item 4 taskbar progress. |

## Skipped or not reached

- TR100 Up direction: needs a decision on how planes and sketch axes change (D67).
- TR223 3D mouse: needs a new dependency and a licence check.
- Not reached (usage): TR329, TR218 item 2, TR222, TR291, TR293, TR294 items 2 and 3, TR354, TR289, TR98, TR219.

## Owner file items

- FDEF: `appearance.section`, `views[].section` (TR213), `appearance.display_quality` (TR214), `appearance.body_display` (TR216), `appearance.display_states` (TR88).
- SHORTCUTS.md keys to choose: `view.orientation`, `view.zoom_out`, `tree.collapse_all`. New commands without keys: `view.display_quality`, `view.display_states`.

## Shared files changed

`ui/main_window/window.py`, `ui/viewport/widget.py`, `ui/input/commands.py`, `ui/strings.py`, `ui/icons/NAMES.md` and icons, `ui/preferences/dialog.py` (new View tab; values in `preferences/view_options.py`), `ui/tree/feature_tree.py`, `ui/main_window/body_display.py`, `ui/equations/config_panel.py`, `ui/session.py`, `tests/ui/test_body_display.py`.

## Tests

Tests of touched areas passed. `tests/ui/test_app_sweep.py` stalled twice for over 15 minutes in the undercut analysis (waiting on the kernel lock); not confirmed whether `phase7b-stage2` has the same hang. The manager's full run must check this.
