# Round 13 report: Cloud J (printing, export, generators, view and UI)

Branch `cloud/round13j`, decisions D2000 to D2020. Written 2026-11-07. The stop signal never appeared. The manager has already fast forwarded `phase7b-stage2` to `c3493b1d` (TR404).

## Items done

| Item | Decision | Commit | Notes |
|---|---|---|---|
| TR358 Guided calibration print | D2000 | c865bee6 (on 285a19f6) | Continues round 12's work in progress (it was going to be D1218). One plate with a variable for each gap, not one configuration per step. No shrink compensation exists to keep away from fit features. |
| TR336 Refine by aspect ratio | D2001 | eae93d6c | Flat flips that lower the worse ratio, plus splits of long edges that cannot be flipped, with no longest edge rule. Flat faces and cylinder sides meet the limit. Caps on end circles can stay above it. |
| TR181 Split connectors | D2002 | c30a1263 | Along Sketch cut mode, and `key_draft` for tapered dovetail keys. A glue gap is refused in sketch mode. |
| TR188 Printing samples | D2003 | eee03815, 81ce1b08 | Samples `nut_and_bolt`, `print_in_place_hinge` and `bin_base_grid`, with tutorials and golden results. They use no keys newer than the samples allow (see below). |
| TR390 Lattice fill | D2004 | 75f0db0c | Gyroid and diamond use numpy marching tetrahedra and are sewn into faceted solids, so they are heavy and capped. Honeycomb is exact. |
| (fix) Orientation popup | D2005 | 75f0db0c | With PySide6 6.12, the sweep's `QMenu.exec` stand in no longer applies, so the popup hung `test_every_command_on_a_part`. It now uses `popup()`. |
| TR330 Engraved marks | D2006 | 98b76cca | Mark feature, with depth 0 or a small depth. Marks on a sheet metal part's fixed wall go to a MARKS layer in the flat DXF and SVG. Marks on bent walls are left out. |
| TR348 Timing pulleys, root fillet | D2007 | 21d1dab8 | GT2, GT3, HTD 3M and 5M, MXL, XL, T2.5 and T5. A Root fillet radius makes true tangent arcs; Automatic keeps D866. |
| TR404 Hinge generator | D2008 | c3493b1d | Pin or print in place forms, with cones, a clearance and detents. The cone angle defaults to 45 degrees, because the core cannot read the printer profile. |
| TR405 Seats on curved faces | D2009 | 81ce1b08 | `face_seats`: seed body copies on a UV grid, turned to the face normal. |
| TR408 item 1 Transition spiral | D2010 | b9a75c68 | Clothoid curve feature. Items 2 and 3 are still open; the PLAN line stays unticked. |
| TR243 Edge profiles | D2011 | f4b5d15b | Round over, cove, rabbet, chamfer with flat and ogee, swept with round corners. No sketch profiles and no addition mode. |
| TR245 Lightening pockets | D2012 | e282f40d | Triangle pockets between ribs, with a border, rounded corners and a depth or through cut. |
| TR325 Landing pad | D2013 | 06a501ff | Raise or Press, with an optional cup wall. No draft and no clearance. |
| TR401 Joint helpers | D2014 | f2d45345 | Groove, rabbet, mortise and tenon, and dowels. The lower priority kinds are not built. |
| TR163 item 1 Knurl | D2015 | 8b4a3d5c | Straight and diamond. Item 2 (image texture) waits for the owner, as the spec says; the PLAN line stays unticked. |
| TR219 Safe start | D2016 | 54f776ba | `--safe-graphics`, `FDCAD_SAFE_GRAPHICS`, a Preferences tick, and automatic after a start that did not finish. **Owner:** check on Windows that VTK draws with Qt's software OpenGL. |
| TR294 items 2 and 3 | D2017 | 4349af32 | Describe Part and Large controls. The 3D view sends no live screen reader change events. |
| TR291 items 1 and 3 | D2018 | 02485f1a | Panel help button, first time hints and What's New. CHANGELOG.md now ships in the bundle. Item 2 (lessons) is open. |
| TR289 Before and after | D2019 | 0c6f8d24 | Opens on a command, not after every change. The session keeps the previous report. |
| TR354 Shortcuts with an input method on | D2020 | 5480ccb8 | Shortcuts work by key position through a fallback, and the status bar says when they are paused. Not tried with a real input method. |

## Items skipped and why

- **TR222 Custom command tabs, TR98 Freeze bar:** the spec marks both as owner decisions, and DECISIONS does not settle them.
- **TR163 item 2 (texture from an image):** owner decision, as the spec says.
- **TR213 Section view extras (the rest):** choosing which bodies are cut needs one drawing per body in the viewport (D1604). The tree folder with handles and rings, and Measure on cut faces, also need viewport work that did not fit this round.
- **TR329 More pick tools, TR293 Work without dragging, TR199 item 1 (face curvature colours):** viewport interaction work. Not started, for lack of time.
- **TR218 item 2 (start page with thumbnails):** not started. A stored thumbnail would also be a new FDEF key.
- **TR380 item 4 (taskbar and Dock progress):** not started. Qt 6 has no API for it: Windows needs COM through ctypes, and the Mac needs pyobjc (a new dependency).
- **TR408 items 2 and 3, TR291 item 2:** not started, for lack of time.

## Owner file items (FDEF_SPEC, SHORTCUTS)

- Feature types and params:
  - `lattice_fill`: `lattice`, `cell`, `wall`, `skin`, `refs.bodies`.
  - `mark`: `depth`, `refs.sketch`.
  - `hinge`: `knuckles`, `knuckle_diameter`, `clearance`, `form`, `pin_diameter`, `pin_cone_angle`, `detents`, `refs.edge`.
  - `face_seats`: `count_u`, `count_v`, `sink`, `operation`, `refs.on_face`, `refs.seed`.
  - `transition_spiral`: `spiral_length`, `end_radius`, `hand`, `refs.sketch`.
  - `edge_profile`: `router_profile`, `profile_size`, `profile_depth`, `refs.loop_face`, `refs.edges`.
  - `lightening_pockets`: `border`, `web`, `cell`, `corner_radius`, `pocket_depth`, `refs.plate_face`.
  - `landing_pad`: `pad_mode`, `cup_wall`, `refs.wall_face`, `refs.sketch`.
  - `joint_helper`: `joint`, `depth`, `joint_clearance`, `shoulder`, `dowel_diameter`, `refs.bodies`.
  - `knurl`: `knurl_pattern`, `knurl_pitch`, `knurl_depth`, `refs.round_face`.
- `split_for_print`: mode value `sketch`, ref `path`, param `key_draft`.
- Print setup: `mesh_export.max_aspect`.
- `modeled_thread.form` (D782) is not in FDEF_SPEC, so the nut and bolt sample leaves it out. `test_schema_keys` already fails for `living_hinge_strip` on `phase7b-stage2`, which also needs spec keys.
- New commands with no default keys: `view.describe_part` and `view.before_after`. No SHORTCUTS.md changes.
- QSettings keys: `view/safe_graphics`, `view/large_controls`, `help/hints_seen`, `help/hints_off`.

## Shared files changed

- `ui/input/commands.py`, `ui/command_tabs/tabs.py` (the 3D Print group, and Transition Spiral beside Helix), and `ui/icons/NAMES.md` with new icons.
- `ui/body_tools/flow.py`, `forms.py` and `strings_phase3.py`. Two existing tooltip texts were made general: `cell` and `depth`.
- `ui/main_window/window.py`: the Describe Part and Before and After actions, Large controls, and the panel help hookup.
- `ui/property_panel/panel.py` (help button and hint), `ui/session.py` (`previous_report`), `app.py` (safe graphics, key position filter), `ui/preferences/dialog.py` and `settings.py`.
- `ui/main_window/orientation_popup.py`, `ui/help/__init__.py`, `ui/help/paths.py`, `packaging/fdcad.spec` (ships CHANGELOG.md).
- `core/features/sheetmetal/export.py`, `flat_output.py` and `flat_pattern.py` (MARKS layer), `core/sketch/gear.py`, and `samples/builder.py` (`hexagon`, `edge_ref`).
- `samples/parts_phase4.py`: golden tolerance for `nut_and_bolt`.
- Tests: `tests/ui/test_ribbon_layout.py` (expects Transition Spiral) and `tests/conftest.py` (calibration dialog stand in).

## Test results

Full suite on this branch (last run, below). Failures that also happen on `origin/phase7b-stage2` without my changes, checked in a clean worktree:

- `tests/core/io/test_schema_keys.py` for `living_hinge_strip` (2 tests): FDEF_SPEC owner keys.
- `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory`
- `tests/ui/test_sketch_preferences.py::test_preferences_dialog_sketch_page`

`tests/ui/test_print_tools_install.py` failed once in a full run and passes alone.

Last full suite (after D2020): 8 failed, 5899 passed, 121 skipped, 1 xfailed, in 15 min. Three of the failures were mine: `test_help` (the Help menu now has What's New), `test_view_look` (the Before and After colour now comes from the theme DATA) and `test_body_tools` split save (the hints write the test settings file into the same temporary folder, so the test now counts .fdprt files only). I fixed those three and their files pass. `tests/perf/test_budgets.py::test_200_feature_part_memory` failed in the full run and passes alone: the manager should watch it on CI. One thing that could matter there is that the session now keeps the previous rebuild report (D2019). The other four are the failures listed above that already happen on `phase7b-stage2`.
