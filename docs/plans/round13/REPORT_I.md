# Round 13 report: Cloud I (patterns, sweep and loft, holes, threads, fastening)

Branch `cloud/round13i`, made from `origin/phase7b-stage2` and merged with it again at the end (the manager's merge of J's work moved it). Decisions D1900 to D1925. The stop signal (`control/stop`) never appeared.

## Items done

| Item | What was built | Decision | Commit |
|---|---|---|---|
| TR59 item 3 | Copy values: one copy's own values by instance number (`instance_values`), and Copy Values on a copy's right click menu | D1900 | 2812ad80 |
| TR141 item 1 | Pattern Chain: mirror, linear, circular and scale steps in a typed order; TR141 done | D1901 | 2812ad80 |
| TR270 item 1 | Explode Pattern in the tree menu: one feature per copy (`only` key) | D1902 | eee1c749 |
| TR398 item 1 | Fill Pattern on cylinder faces, spacing along the surface or as seen from the front; TR398 done | D1903 | 220b6ac2 |
| TR399 items 1, 2 | Add to Pattern and the Follow Pattern feature; TR399 done | D1904 | 9b05bd29 |
| TR56 items 1, 2 | Sweep start tangency (Path Tangent) and Merge tangent faces; TR56 done (Tangent to Adjacent Faces left out, see D1905) | D1905 | 30e7735f |
| TR137 items 1, 2 | Profile part way along the path, one way, the other or both with its own twist; several profiles along one path; TR137 done | D1906, D1907 | 30e7735f |
| TR138 item 1 rest | Loft profiles from loops of model edges | D1908 | 30e7735f |
| TR139 item 2 | Show section for Sweep and Loft; TR139 done | D1909 | 30e7735f |
| TR396 item 1 | Sweep section values: profile dimensions as formulas of t; TR396 done | D1910 | 30e7735f |
| TR143 item 1 | Hole placement by two edges or concentric, no sketch; TR143 done | D1911 | 30e7735f |
| TR144 items 1, 3, 4 | Custom Stack holes, a start plane, user hole sizes from a file; TR144 done | D1912, D1913, D1914 | aa5dd483 |
| TR397 item 1 | Radial and on a point hole placement, holes along a slanted axis; TR397 done | D1915 | daad1675, ebd43444 |
| TR146 item 1 rest | Mounting Boss step, fin direction from a face | D1916 | 01a44ad3 |
| TR145 | Tapered modelled thread (Taper Angle); TR145 done | D1917 | 29bd7b14 |
| TR254 | Thread profile from a sketch, end finishes Square, Chamfer, Fade Out; TR254 done | D1918 | 2fd9db2d |
| TR412 | Fit table by hole diameter band, direction and nozzle, Fit from Table | D1919 | fc5f26ae |
| TR327 | User thread sizes for Thread and Cosmetic Thread (shared file with D1914, class column) | D1920 | 05b310ac |
| TR347 | Simplify threads while editing (preference and part key), Force Rebuild makes them real, export note | D1921 | 05b310ac |
| TR256 | Thread Relief for Thread and tapped holes, tapped hole Entry Chamfer | D1922 | 05b310ac |
| TR162 item 2 in part | Helix Closed Ends | D1923 | 05b310ac |
| TR136 item 2 | Loft Tangent to Faces and Curvature to Faces | D1924 | 05b310ac |
| TR148 | Several offset or angle planes, or points along a curve, in one command | D1925 | 05b310ac |

PLAN.md ticks: TR141, TR398, TR399, TR56, TR137, TR139, TR396, TR143, TR144, TR397, TR145, TR254, TR412, TR327, TR347, TR256, TR148 are ticked. TR59, TR270, TR138, TR146, TR162 and TR136 have their done parts noted on the line and stay open.

## Items or parts not done, and why

- TR142 item 1 (patterns of reference planes, axes and points): skipped. One pattern feature holding several datums would need every reference pick, the plane and axis display, visibility and the tree to learn a datum number (about 40 places in the UI). TR148 (D1925) covers repeated offset and angle planes and points along a curve as separate, formula linked features; circular copies of axes and points have no reference method to build from. Left for a decision on multi datum results.
- TR59 item 4 (Vary Sketch) and clicking instance markers: the pattern engine does not re-solve a seed's sketch per copy, and the view has no instance markers. Copy Values is reached from the copy's own right click menu instead (D1900).
- TR270 view only hiding and item 3 (box skip over markers): no instance markers, and a pattern's copies are faces of one solid drawn as one shape (D1902).
- TR138 items 2 and 3: the group picker needs a new chain editing widget; a cut by a solid tool body has no kernel sweep of a solid, and copies would leave scallops (D1908).
- TR146 items 2 and 3 (Lip and Groove extras, Vent per group fillet, draft and offset): not reached.
- TR162 item 1 (bolt, nut and washer from a standard size): J's D2003 added a nut and bolt sample in this round; a washer and sizing from the tables are not done. Ground flat spring ends are not in the helix curve (D1923 says to cut the swept spring).
- TR136 items 1 (several draggable connectors) and 3 (Add Loft Section): view dragging and converting a loft slice into an editable sketch were not reached.
- TR56 Tangent to Adjacent Faces for sweeps: the pipe shell has no mode for it (D1905).

## Owner file items (FDEF params and keys to add to FDEF_SPEC)

New feature types: `pattern_chain` (params `steps`, `spacing`, `instances`, `reverse`, `turns`, `angle`, `reverse_turn`, `scales`, `factor`; refs `direction`, `axis`, `plane`, `centre`) and `follow_pattern` (refs `pattern`; key `on`).

Every pattern of features: param `instance_values`. Pattern features: key `only` (an exploded copy).

Fill Pattern: `surface_spacing` ("mapped", "projected").

Sweep: `start_tangency` ("none", "path_tangent"), `merge_faces`, `sweep_direction` ("forward", "backward", "both"), `twist_angle2`, `twist_turns2`, `show_section`, `section_values`; refs `profiles` (more profiles along the path).

Loft: `show_section`; constraints "tangent" and "curvature" for `start_constraint` and `end_constraint`; profile refs of kind "loop" (`{"kind": "loop", "edges": [...]}`).

Hole: `hole_type` "custom" with `stack`; `place_by` ("points", "edges", "concentric", "radial", "point"), `place_distance1`, `place_distance2`, `radial_distance`, `radial_angle`, `thread_relief`, `thread_chamfer`; refs `place_edges`, `concentric`, `radial`, `at_point`, `hole_axis`, `start_plane`; the standard "user"; `diameter` is now optional in the type (custom holes have none).

Thread (`modeled_thread`): `taper_angle`, `form` "sketch" with refs `profile_sketch`, `end_finish` ("square", "chamfer", "fade"), `relief`.

Mounting Boss: `step_height`, `step_diameter`.

Helix: `ends` ("open", "closed"), `end_pitch`.

Document: `extra["simplify_threads"]` (true or false, the part's own setting).

Preferences (not in the file): `holes/user_sizes` (the user size file text), `printing/fit_table`, `rebuild/simplify_threads`.

No new keys in SHORTCUTS.md. New commands: `feature.pattern_chain` (Features tab, pattern group; no key).

## Shared files changed

- `src/fdcad/core/features/base.py`: `BuildContext.simplify_threads` (one field).
- `src/fdcad/core/rebuild/engine.py`: `simplify_threads` and `real_once` settings, `RebuildReport.simplified`, a cache key part for simplified threads.
- `src/fdcad/core/features/__init__.py`: registers `pattern_chain` and `follow_pattern`.
- `src/fdcad/ui/main_window/window.py`: the engine gets the simplify preference, Force Rebuild sets `real_once`, `export_warning` names simplified threads.
- `src/fdcad/ui/main_window/context_menu.py`: Copy Values on a pattern copy.
- `src/fdcad/ui/tree/feature_tree.py`: Explode Pattern and Add to Pattern menu items.
- `src/fdcad/ui/tree/row_icons.py`: Follow Pattern's tree icon.
- `src/fdcad/ui/preferences/settings.py`, `dialog.py`: Simplify threads while editing (General page).
- `src/fdcad/ui/command_tabs/tabs.py`, `input/commands.py`, `body_tools/flow.py`, `icons/NAMES.md`, new icon `feature.pattern_chain.svg`: the Pattern Chain command.
- `src/fdcad/ui/strings.py`, `strings_phase3.py`, `strings_phase4.py`, `strings_import.py`: labels and tips.
- `src/fdcad/ui/reference_geometry/panel.py`, `tool.py`: How many for planes and points.
- `tests/ui/test_ribbon_layout.py`: the Features tab now lists Pattern Chain.
- `tests/ui/sweep_support.py`: a temporary orientation popup patch was added and then removed again after J's D2005 fix; no net change.

## Tests

Pre-existing failures on `origin/phase7b-stage2` before this round's work (checked with the work stashed): `tests/core/io/test_schema_keys.py` (two, the `living_hinge_strip` sample's keys), `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory` and `tests/ui/test_sketch_preferences.py::test_preferences_dialog_sketch_page`. They are environment or owner file issues, not touched here.

Full suite before the merge (after TR254): 4 failed (the four above), 5808 passed, 112 skipped, 1 xfailed.

Last full suite (after the merge with `origin/phase7b-stage2`): 7 failed, 5935 passed, 121 skipped, 1 xfailed. The four above, plus three that came in with the merged J work and fail the same way on `origin/phase7b-stage2` itself: `test_schema_keys.py` for the `nut_and_bolt` sample (`features.params.form` not yet in FDEF_SPEC.md, an owner file) and `test_old_files.py` for `print_in_place_hinge` (its extrude uses the newer start condition keys). None comes from this branch's changes.
