# Round 12 report C: sketch

Branch `cloud/round12c`, rebased on `origin/phase7b-stage2` at `0b4e4310` (TR272). Decisions D1300 to D1317.

## Items done

| Item | Decision | Commit | Notes |
|---|---|---|---|
| TR37 Repair Sketch | D1300 | 17f94d5e | New tool under Check Sketch (dropdown). Find, Zoom to Next Fault, Fix, Fix All. |
| TR38 Sketch problem list | D1301 | 52ca9800 | Click the sketch status. Dangling, Invalid and No solution states; Diagnose, Repair All Dangling. |
| TR338 Solution jumps | D1302 | 5c571d60 | Status bar warning; Keep This Side and Remove Side Locks in the empty space menu. |
| TR108 Relation groups, Equal Length | D1303 | 953078db | Groups join; numbered tags; Equal on lines and arcs. |
| TR41 Ellipse and spline relations | D1304 | afc8e47a | Equal Curvature not built (recorded). |
| TR43 Spline handles | D1305 | c489b2a3 | Pin Handle, Reset Handle, Add Handle Line. |
| TR42 Spline edit tools | D1306 | c489b2a3 | Insert Spline Point, Fit Spline, Simplify Spline. |
| TR45 Baseline, ordinate, chamfer, path length | D1307 | c489b2a3 | |
| TR107 Sketch pattern options | D1308 | c489b2a3 | Count label already existed (D513). |
| TR231 Relations offered while drawing | D1309 | c489b2a3 | Per kind switches; Tab skips one click. |
| TR362 Weak automatic relations | D1310 | c489b2a3 | |
| TR342 Limits and Point on Segment | D1311 | c489b2a3 | Active set on top of the solver. |
| TR111 items 2 (part) and 4 | D1312 | c489b2a3 | PLAN line annotated, not ticked. |
| TR114 item 1 rectangle extras | D1313 | ecde84d5 | PLAN line annotated, not ticked. |
| TR115 items 3 and 4 (part) | D1314 | 7f21cf1f | PLAN line annotated, not ticked. |
| TR122 item 2 linked copies | D1315 | 6eb87a87 | TR122 now ticked. |
| TR341 item 3 | D1316 | 2d715349 | PLAN line annotated, not ticked. |
| TR48 fillet on arcs | D1317 | 0393a1ca | PLAN line annotated, not ticked. |

Note on commits: TR43, TR42, TR45, TR107, TR231, TR362, TR342 and TR111 share hunks in the tool registry, strings, context menu, CHANGELOG and the guide, so they went in as one commit (c489b2a3) instead of one per item. Each has its own DECISIONS entry, CHANGELOG line, guide text and test files.

## Items skipped or left open, and why

* TR48 rest: fillets with splines (splines are not solver curves, D278), chamfers on arcs, sizing by dragging the preview arc.
* TR339 Construction geometry after the sketch is closed: needs pickable sketch geometry in the 3D view and naming for features that pick it; that is viewport work in session F's area and more than the hour budget.
* TR53 rigid drag key: the brief says the key must be chosen; no key is settled in DECISIONS, so it waits for the owner.
* TR106 Close Sketch to Model, TR112 Drag without solving, TR116 picture extras, TR118 Convert Entities extras, TR232 temporary guide lines, TR234 sketch on a face without splitting it, TR238 dimension lock while dragging, TR34 sketch blocks: not reached in this session.
* TR121 Text extras: item 1 (explode text) needs kernel outline work run off the UI thread; not reached.
* TR111 items 1 and 3, TR114 item 2, TR115 items 1 and 2 and the rest of item 4, TR341 item 2: listed in their decisions as not built.
* TR38 addition (section 22 item 34) to name construction lines without dimensions as the cause of "not fully defined", and the faint image of a lost item (TR38 item 2): not built (D1301).

## Owner file items (FDEF_SPEC.md, SHORTCUTS.md not edited)

New optional sketch keys and values, all written only when used, so older files save unchanged and old files open:

* Sketch key `keep_sides`: map of `corner:<line>:<line>` or `arc:<id>` to +1 or -1 (TR338, D1302).
* Relation key `weak: true` (TR362, D1310).
* Relation type `on_segment` with entities [point, line] (TR342, D1311).
* Dimension key `limit`: `"min"` or `"max"` (TR342, D1311).
* Dimension type `path_length` with the chain's line and arc ids (TR45, D1307).
* Dimension `display` keys `style: "ordinate"` and `group: "<zero point id>:<axis>"` (TR45, D1307).

Preferences (not in the file): `sketch/auto_horizontal` and seven more `sketch/auto_<kind>` switches (TR231).

Keys for SHORTCUTS.md: Tab in the sketch canvas while a drawing tool is active skips the next click's automatic relations (TR231, D1309). No new default command keys; the new commands have none.

## Shared files changed

* `src/fdcad/ui/sketch_tools/registry.py`, `tool_text.py`, `src/fdcad/ui/input/commands.py`, `src/fdcad/ui/icons/NAMES.md`: seven new sketch tools (repair_sketch, insert_spline_point, fit_spline, simplify_spline, baseline_dimension, ordinate_dimension) and new icons (`sketch.*`, `relation.on_segment`).
* `src/fdcad/ui/command_tabs/tabs.py`: Check Sketch and Repair Sketch share a dropdown beside Relations; Smart Dimension is a dropdown with Baseline and Ordinate; the spline dropdown gets the three spline tools.
* `src/fdcad/ui/main_window/context_menu.py`: sketch menu items (Keep This Side, Remove Side Locks, Keep Relation, Pin Handle, Reset Handle, Add Handle Line, Path Length Dimension, Chamfer Dimension, Angle to Horizontal and Vertical, Relax Spline, the Limit submenu on dimensions).
* `src/fdcad/ui/main_window/status_bar.py` and `sketch_mode.py`: the sketch status label is clickable and opens the problem list; the list closes with the sketch.
* `src/fdcad/ui/strings.py`: new strings, all in marked blocks.
* `src/fdcad/core/sketch/solver.py`: ellipse and spline relations, Equal Length, path length, and the limit active set in `solve` and `drag`. `src/fdcad/core/sketch/model.py`: the keys above. `src/fdcad/core/document/paste.py` and `ui/sketch_tools/edit.py`: `keep_sides` in the sketch keys.
* `tests/ui/test_context_menus.py`: the dimension menu now lists Limit.
* `tests/ui/sweep_support.py`: unchanged. The problem list is a non modal dialog, which `close_popups` already closes after each step.

## Last full suite

After the rebase on `0b4e4310`, Linux, Qt offscreen: **5246 passed, 97 skipped, 1 xfailed, 2 failed** (12 min). Neither failure is in this session's code:

* `tests/core/test_message_next_steps.py::test_every_error_and_warning_says_what_to_do_next` flags two messages that came in with the base branch: `core/features/extrude_open.py:94` ("Redraw its ends." starts with a verb the checker does not know, from TR157) and `core/features/twist_lock.py:209` ("Model the box ...", from TR357). For the manager: fix the wording or add the verbs.
* `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory` uses Windows drive paths (`C:/b`) and fails on Linux on the base branch as well.

The full suite run before the rebase (after the first five items) had the same resources failure plus one theme test, which the Check and Repair Sketch dropdown fixed.
