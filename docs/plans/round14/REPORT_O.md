# Round 14 report: cloud O (view, section, file commands, help, UI)

Branch `cloud/round14o`, made from `origin/phase7b-stage2` at 01d6e2b5. Decisions D2500 to D2508. The stop signal was checked before each item and was never set. All seven items in the brief are done.

## Items done

| Item | What was built | Decision | Commit |
|---|---|---|---|
| TR213 Section view extras | Choose the bodies a section cuts (Bodies Cut list, saved as `whole` in the section data) | D2500 | 7c93bcd9 |
| TR213 | Section Planes folder in the feature tree; each plane gets an offset arrow and X and Y rotation rings in the 3D view; Edit Section and Turn Off Section on the folder menu. Also fixed: reopening the panel with two or three planes raised an error | D2501 | cd25ec7c |
| TR213 | Measure on cut faces: real cut faces are built on the worker and drawn nearly see through and pickable over the caps (line ticked) | D2502 | 07786298, 66a28cac |
| TR199 item 1 | Curvature Colors command (Evaluate tab, Curves group): faces coloured by largest, mean or Gaussian curvature, with a colour scale and the value under the cursor (line ticked) | D2503 | e0eb06b0, 2a23b5f9 |
| TR218 item 2 | Start page over the empty document area: recent parts as pictures, pins, Remove from List, Show in Folder; each save keeps a 128 px picture in the part file and in a cache folder (line ticked; drag to open already existed, D765) | D2504 | 9d392702, 06c8a2d9 |
| TR291 item 2 | Help, Lessons and a Start Lessons button on the welcome: two lessons whose steps tick when the part shows them, with Resume Later and Start Over (line ticked) | D2505 | 1da78173 |
| TR380 item 4 | Taskbar progress on Windows (ITaskbarList3 through ctypes) and a percentage badge on the Mac Dock icon (Objective-C runtime through ctypes), driven by the status bar progress for rebuilds, exports and the slicer hand off. No new dependency. Line stays unticked only for the F1 key, an owner item | D2506 | 98cb3313 |
| TR98 Freeze bar | Freeze Up to Here, Move Freeze Bar Above Here and Unfreeze All; frozen features keep their last result on a rebuild and cannot be edited (line ticked) | D2507 | 02477d3a, d9e7a667 |
| TR222 Custom command tabs and a simple mode | Right click a button: Add to My Commands, Remove from My Commands, Hide Button; tab menu: Show Hidden Buttons and Simple Mode (line ticked) | D2508 | d9e7a667 |

## Items skipped

None. Not built, and recorded in the decisions:

- TR98: the freeze bar cannot be dragged with the mouse or the arrow keys. The menu commands move it (D2507).
- TR218: Show in Folder opens the folder but does not select the file, because selecting it needs platform code (D2504).
- TR199: one colour per face, not per mesh point. Per point colours would need a Python loop over mesh nodes, which CLAUDE.md 5A forbids. Faces that are not planes, cylinders or spheres are sampled on a fixed 5 by 5 grid (D2503).
- TR380 item 4: the Windows and Mac taskbar calls cannot run in CI. They need a check by hand on both platforms (D2506).

## Owner file items

New top level FDEF keys for FDEF_SPEC.md. Both are kept in `Document.extra`, so older versions keep them and the file reader did not change:

- `thumbnail`: a base64 PNG picture of the part, written only after a save that had a 3D view (D2504).
- `freeze_bar`: the id of the last frozen feature, written only while something is frozen (D2507).

New key inside the saved section data (`appearance.section`): `whole`, a list of body indices the section leaves uncut (D2500).

New settings, not part data: `files/pinned`, `help/lessons`, `help/lesson_current`, `appearance/custom_commands`, `appearance/hidden_buttons`, `appearance/simple_mode`.

No new shortcut keys. New commands: `evaluate.curvature_colors` (no default key).

## Shared files changed (small changes)

- `src/fdcad/ui/main_window/window.py`: installs Curvature Colors, the start page and the tab customizer; adds the picture before save; adds the freeze guard in `edit_feature`; adds two type annotations.
- `src/fdcad/ui/tree/feature_tree.py`: Section Planes folder rows and menu, freeze bar row and menu items, and a `section_requested` signal.
- `src/fdcad/ui/viewport/widget.py`: `set_section_whole`, `set_section_faces`, and section faces following the selection filters in `_activate`.
- `src/fdcad/core/rebuild/engine.py`: frozen results are kept and reused (`frozen_results`).
- `src/fdcad/ui/preferences/settings.py`: pinned files, custom commands, hidden buttons and simple mode.
- `src/fdcad/ui/main_window/feedback.py`: drives the taskbar progress.
- `src/fdcad/ui/command_tabs/tabs.py`: Curvature Colors added to the Curves group.
- `src/fdcad/ui/input/commands.py`, `src/fdcad/ui/strings_import.py`, `src/fdcad/ui/icons/NAMES.md`, plus a new original icon `evaluate.curvature_colors.svg`.
- `src/fdcad/ui/help/__init__.py`, `src/fdcad/ui/help/welcome.py`: Lessons menu entry and the welcome button.
- `src/fdcad/ui/print_tools/slicer.py`: the slicer hand off reports progress.
- Tests updated for the new menu entries: `tests/ui/test_help.py` and `tests/ui/test_command_tabs.py`.

`tests/ui/sweep_support.py` did not need a change: no new modal dialogs. The lessons, Curvature Colors and start page are non modal windows or widgets.

## Last full suite result

`uv run pytest -q -p no:cacheprovider` on Linux (offscreen), after the last commit: 6240 passed, 2 failed, 121 skipped, 3 xfailed in 17 minutes. Both failures are explained below. The new and touched tests, the app sweep and the message checkers all pass.

Linux notes: `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory` also fails on the untouched base branch on Linux. It uses Windows drive paths. `tests/perf/test_budgets.py::test_200_feature_part_memory` measures the memory of the whole test process: it fails only late in a full run and passes when run alone.
