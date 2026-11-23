# Round 12 report A: sheet metal

Branch `cloud/round12a`. Decisions D1100 to D1113. `origin/phase7b-stage2` moved (to e647188e, TR357) while this ran; a rebase needed a force push, which was not allowed here, so it is merged in instead (ab667088). The merge result is the same tree as the rebase would give: two conflicts, `src/fdcad/ui/strings.py` (both tips kept) and `src/fdcad/core/equations/engine.py` (`sensor` and `flatten` both kept).

## Items done

| Item | What | Decision | Commit |
|---|---|---|---|
| TR165 | Sheet metal Tab (`sheet_tab`): closed sketch on a wall face adds a piece one sheet thick; Link to thickness on Extruded Boss | D1100 | 7ae15f6b |
| TR166 item 1 | Edge Flange profile sketch (`refs.profile_sketch`): narrower, wider, notched or shaped flanges | D1101 | d8d032fc |
| TR167 | Edit Bends (`edit_bends`): new radius and allowance for one, picked or all bends, also on converted and Insert Bends parts | D1102 | fed7519f |
| TR168 | Sheet metal Corner Relief (`sheet_corner_relief`): rectangular, circular, tear, obround, constant width; collect all or picked; ratio or value; on bend lines or tangent; one type per corner | D1103 | f3159022 |
| TR169 | Bend notches (triangle, circle, rectangle) in the flat pattern and its DXF | D1104 | abb07a73 |
| TR76 | Flat pattern options: Merge faces, Corner trim, Faces to leave out. Item 1 (No Bends) met by Unfold All + Fold, tested on Insert Bends; item 3 already met by the Start list, tested | D1105 | ac6865a9 |
| TR172 | Quoting data: blank area, outer and inner cut length, cut outs, bends, flat length and width; panel rows, equations (`blank_area@Flat Pattern` ...), CSV export | D1106 | ac6865a9 |
| TR174 items 1, 2 (part), 3, 5, 6, 7 | Hem own lengths and allowance; Closed Corner overlap ratio; Cross Break angle and radius; Break Corner collect all and inside corners; Tab and Slot edge offset and skipped tabs; flat larger than the sheet warning | D1107 | ac6865a9 |
| TR173 | Flat Pattern Output dialog: items, origin, rotate, flip X and Y, up and down bend colours (BEND_UP, BEND_DOWN layers), list to leave out single bend lines and marks | D1108 | ac6865a9 |
| TR370 | Extend Wall (`extend_wall`) by distance or up to a plane or face; Perforated Fold Line (`perforation`) | D1109 | ac6865a9 |
| TR282 item 2, item 1 in part | Bend Table window (highlight, radius and allowance per row as Edit Bends features, steps), bend order in DXF (BEND_ORDER text) and SVG titles | D1110 | ac6865a9 |
| TR332 | Sheet Metal Rules: named rules in a shared JSON library, Save Current, Delete, Library File, Apply (one undo step) | D1111 | b4b017be |
| TR283 item 2 | Fold progress (Flat Pattern `fold_percent`) and Flat Marks (`flat_marks`) | D1112 | 6e741eb8 |
| TR170 in part | Partial miter flange: start and end offsets | D1113 | 60df5863 |

Commit ac6865a9 holds six items in one commit, because the Flat Pattern module, the sheet metal forms and the sheet metal strings were edited for all of them while the five item full suite ran; their tests, docs, CHANGELOG lines and decisions are separate.

Every new feature keeps the sheet model, so Flatten keeps working, and each has a flatten test.

## Items skipped or left partly done, and why

* TR166 item 2: flanges on curved and tangent edge chains need walls that are not flat plates, which the sheet model (D333) does not have. Ending a flange at a picked point is Up to Vertex; several flange lengths at once is Length 2 to Length 8 (D337). Recorded in D1101.
* TR174 item 2 open or closed bend region, item 4 rip on hollow cylinders and cones, item 6 use inside patterns and mirrors: no curved walls or corner regions in the sheet model, and a pattern after a sheet metal feature is outside the sheet model. Recorded in D1107.
* TR173: sketches as an item (the flat drawing has no sketch geometry) and one file per body (waits for TR281). Recorded in D1108.
* TR282: rips in the table and turning a bend into a rip and back (rips are cuts, not model entities; a bend turned into a rip would leave its child wall unconnected). Recorded in D1110.
* TR170: trim side bends, own relief and allowance beyond Own Bend Values, arcs in the profile. Recorded in D1113.
* TR171 Convert to Sheet Metal extras: not started (time). Keeping the original body needs a multi body sheet result; rip types and rounded edges as bends need convert_sheet rework.
* TR281 Several sheet metal bodies: not started. Marked "owner decision" in the spec; it changes the one folder per part rule (D330) and the Base Flange first solid rule, so it needs the owner's call on how bodies own their folders.
* TR283 item 1, TR77 Stamp, TR279 Own forming tools: not started (time). They need new formed geometry (drawn shapes with draft and radii, a user part as a tool) in the sheet model's folded only adds.

## Owner file items (FDEF_SPEC, SHORTCUTS)

New feature types: `sheet_tab`, `edit_bends`, `sheet_corner_relief`, `extend_wall`, `perforation`, `flat_marks`.

New params and refs on existing types:

* `edge_flange`: ref `profile_sketch`.
* `flatten`: `bend_notches`, `notch_size`, `merge_faces`, `corner_trim`, ref `leave_out`, `sheet_length`, `sheet_width`, `bend_order`, `fold_percent`.
* `hem`: `length2` to `length8`, `method`, `k_factor`, `allowance`.
* `closed_corner`: `overlap_ratio`.
* `cross_break`: `break_angle`, `break_radius`.
* `break_corner`: `collect_all`, `corner_kind`.
* `tab_slot`: `edge_offset`, `skip_tabs`.
* `miter_flange`: `offset_start`, `offset_end`.
* `sheet_metal` (folder): `rule_name`.
* New type params: `sheet_corner_relief` (`all_corners`, `relief_type`, `corner_types`, `size_by`, `ratio`, `size`, `placement`, ref `bends`), `edit_bends` (`all_bends`, `radius`, `method`, `k_factor`, `allowance`, ref `bends`), `extend_wall` (`end_condition`, `distance`, refs `face`, `limit`), `perforation` (`slot_length`, `slot_width`, `bridge`, ref `sketch`), `flat_marks` (`title`, ref `sketch`), `sheet_tab` (ref `sketch`).

New commands, no default keys: `feature.sheet_tab`, `feature.edit_bends`, `feature.sheet_corner_relief`, `feature.extend_wall`, `feature.perforation`, `feature.flat_marks`, `feature.bend_list` (Bend Table), `feature.sheet_rules` (Sheet Metal Rules).

New settings key: `sheet_metal/rule_library`. New file: the rule library JSON (D1111).

## Shared files changed

* `src/fdcad/ui/property_panel/panel.py`: Link to thickness for bosses (small helper `_link_box`, `_link_thickness`).
* `src/fdcad/ui/strings.py`: the Link to thickness tooltip text (merged with the local session's `flip_side` tip during the rebase).
* `src/fdcad/ui/body_tools/form_widget.py`: a "sketch" field stores its pick under its own name; a "text" field shows its Field default as placeholder; `bend_notches` added to OMIT_NONE.
* `src/fdcad/core/equations/engine.py`: `MEASURED_VALUES["flatten"]` (merged beside the local session's `sensor`).
* `src/fdcad/ui/input/commands.py`, `src/fdcad/ui/icons/NAMES.md` and eight new icons.
* `tests/ui/sweep_support.py` not changed: the three new windows (Flat Pattern Output, Bend Table, Sheet Metal Rules) open with `QDialog.exec`, which the sweep already replaces.

## Test results

* Full suite before the rebase (after five items): 5146 passed, 97 skipped, 1 xfailed, 1 failed: `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory`, which fails the same way on `phase7b-stage2` without these changes (it expects Windows drive ordering).
* App sweep (`tests/ui/test_app_sweep.py`) after the main batch: 12 passed, 52 skipped (slow ones).
* Full suite on the final tree (the merge, ab667088): 5228 passed, 97 skipped, 1 xfailed, 2 failed. Neither failure comes from sheet metal:
  * `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory`, the pre-existing one above.
  * `tests/core/test_message_next_steps.py::test_every_error_and_warning_says_what_to_do_next` flags two messages from the local session's latest commits: `core/features/extrude_open.py:93` ("Redraw its ends.") and `core/features/twist_lock.py:209` ("Model the box round the lid's plug ..."): "redraw" and "model" are not next step words the checker knows. The sheet metal messages all pass it.
