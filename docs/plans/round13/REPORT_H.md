# Round 13 report: cloud H (fillet, chamfer, draft, shell, direct edit, checks, sheet metal)

Branch `cloud/round13h`, made from `origin/phase7b-stage2` at d5f429d7. Decisions D1800 to D1816.
The run stopped on the stop signal (`control/stop` was there before item 17 began). Everything finished is pushed.

## Items done

| Item | What was built | Decision | Commit |
|---|---|---|---|
| TR64 | Item 4 Select through faces (Fillet and Chamfer panels, view flag). Item 2 Round corners recorded as met, with a test. Items 1 and 3 left: the kernel has no setting. | D1800, D1801 | 3b8d38d2 |
| TR271 | Item 1 Limit failing areas: a fix that turns each failing edge into a Partial Edges fillet over the longest stretch that builds. TR271 done. | D1802 | 966ad476 |
| TR322 | Shell Wall rule Never thinner or Never thicker, with a measured check and warning. TR322 done. | D1803 | 68a201a9 |
| TR323 | Draft type Fixed Edge. TR323 done. | D1804 | de3c9ddc |
| TR259 | Reapply Fillets on Draft (Neutral Plane and Fixed Edge). Combine left, see D1806. | D1806 | de3c9ddc |
| TR147 | Item 3 in part: Dome direction vector. Constraint sketch and tapered steps left. | D1805 | 92215ee3 |
| TR262 | Gap fix: new Heal Edges feature, added by Geometry Check Fix on gaps and inexact edges. Smooth and square up fixes and the clip sphere left. | D1807 | bc13af95 |
| TR87 | Item 2: wall analysis target in Preferences and the hover reading. TR87 done. | D1808 | 6a17a9e4 (docs in bc13af95) |
| TR164 | Detailed preview ticks on Extrude and Rib. TR164 done. | D1809 | 713f5ad7 |
| TR60 | Split Line Silhouette (cylinders, cones square to the pull, spheres) and intersection with another body. TR60 done. | D1810 | a1a7d8ff |
| TR84 | Parting Line Split faces at the line (straddle cylinders, cones, spheres). TR84 done. | D1811 | 8202de93 |
| TR321 | Chamfer Corners: Patch or Mitre. Blend and setback left. | D1812 | c7a916b3 |
| TR394, TR63 | Not built: the fillet maker has no setback, transition or piece settings (checked). Recorded. | D1814 | c7a916b3 |
| TR268 | Item 2 Orient Body: Move and Copy Body mode Frame to frame. Items 1 and 3 left. | D1815 | 326a8c1c |
| TR174 | Item 4 Rip on tubes and cones (gap, angle, offset). Item 2's bend region choice still left (D1107). | D1813 | 14cac161 |
| TR77 | Stamp: closed sketch, depth, draft, reverse, outline marks in the flat pattern. Punch, die and corner radii left. | D1816 | 68702dcc |

Two lint and format commits follow (1083de98, c5baeb01).

## Items not started (stop signal)

TR266, TR166 (item 2), TR170 (rest), TR171, TR282 (rest), TR283 (item 1), TR279. TR281 needs an owner decision (it is marked so in the spec) and would be skipped anyway.

## Owner file items

FDEF_SPEC.md (not edited) needs these new params, refs and types:

- shell: `wall_rule` ("never_thinner", "never_thicker").
- draft: `draft_type` "fixed_edge" with `refs.fixed_edges`; `reapply_fillets`.
- dome: `refs.direction` (one item list or a dict).
- new type `heal_edges`: `tolerance` (length, optional).
- split_line: `method` "silhouette" with `refs.direction`; `refs.tool_body` for intersection.
- parting_line: `split_faces`.
- chamfer: `corner` ("patch", "mitre").
- rip: `refs.tube_faces`, `tube_angle`, `tube_offset`.
- move_copy_body: `mode` "frame" with `refs.from_frame` and `refs.to_frame`.
- new sheet metal type `stamp`: `depth`, `draft`, `reverse`, `refs.sketch`, `refs.sheet_metal`.

Not in the file: Select through faces and the Detailed preview ticks are session view state. The wall target is a preference (`printing/wall_target`).

Keys: one new command, `feature.stamp` (Sheet Metal tab, Forms group), with no default key. SHORTCUTS.md is unchanged.

## Shared files changed

- `ui/viewport/widget.py`: the `pick_through` flag and one call before the TR224 see through pick.
- `ui/main_window/window.py`: one fix action branch (`limit_failing`).
- `ui/property_panel/panel.py`: the Extrude Detailed preview tick, a class flag and the copy in `_changed`.
- `ui/strings.py`: `DRAFT_TYPES` "fixed_edge", `SPLIT_LINE_METHODS` "silhouette", `CHECK_FIX_TIP` text.
- `ui/strings_phase3.py`, `ui/strings_sheetmetal.py`: labels, tips and choices.
- `ui/input/commands.py`, `ui/sheet_metal/flow.py`, `ui/sheet_metal/forms.py`, `ui/icons/NAMES.md` (new icon `feature.stamp.svg`): the Stamp command.
- `ui/body_tools/forms.py`: Frame to frame fields.
- `ui/preferences/printing_page.py`, `ui/preferences/print_settings.py`: the wall target.
- `core/features/delete_face.py`: one import line that registers `heal_edges`.
- New UI text lives in a new module, `ui/strings_finish.py`, to keep merges small.

## Tests

- Last full suite run (after TR84, before TR321 to TR77): `uv run pytest -q -p no:cacheprovider --ignore=tests/ui/test_app_sweep.py` gave 4 failed, 5760 passed, 54 skipped, 1 xfailed. The same 4 fail on `origin/phase7b-stage2` without these changes: `test_schema_keys` (two cases, living_hinge_strip, owner FDEF items from round 12), `test_resources.py::test_shortages_list_each_disk_once_and_memory` and `test_sketch_preferences.py::test_preferences_dialog_sketch_page`.
- After that, the tests of every later item and the sheet metal, chamfer, body tools, icon, command and message checker tests passed. ruff and `mypy` strict on `fdcad/core` are clean for these changes. One line in `tests/core/features/test_interlock.py` is over the length limit; it came from round 12, not this branch.
- The full suite was not run again after the stop signal, so the last items are covered only by their own tests.
- App sweep: `test_app_sweep.py::test_every_command_on_a_part` hangs on the base branch too. It stops in `orientation_popup.show` at `menu.exec(...)` when the sweep runs `view.orientation` (TR210, D1601). The sweep's QMenu.exec patch does not catch it. With `view.orientation` added to the sweep's SKIP list (a local change, not committed), the two quick sweep tests passed (2 passed in 108 s) on this branch. The manager should fix the sweep or the popup.
