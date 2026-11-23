# Round 14 report: cloud M (fillet, chamfer, draft, shell, checks, sheet metal)

Branch `cloud/round14m`, made from `origin/phase7b-stage2` at 01d6e2b5 (it did not move during the run, so no rebase was needed). Decisions D2300 to D2313. The stop signal was checked before every item and was never there. All 14 items of the brief were worked through in order and everything is pushed.

## Items done

| Item | What was built | Decision | Commit |
|---|---|---|---|
| TR64 | Items 1 (Keep Features) and 3 (Overflow) rechecked against the fillet maker: no setting. Recorded, line left open with a "not built" note. | D2300 | b3c07271 |
| TR147 | Dome Profile sketch: a closed outline in sketch coordinates (X out from the middle, Y up) turned about the face's middle and trimmed to the face. Tapered or square steps for Step Draft not built (reason in D2301). Line left open. | D2301 | 336bc4ef |
| TR259 | Reapply Fillets on Combine (Add, Subtract, Common): rounds touching another picked body are removed, the combine runs, and the edge pieces are rounded again. TR259 ticked. | D2302 | 10a132b8 |
| TR262 | New finding kind Nearly square; Fix for nearly smooth and nearly square edges between flat faces (a Move Face rotate about the edge, worked out in the background); Clip around each finding (a six plane clip box, the viewer only clips with planes). TR262 ticked. | D2303 | ab6d4b70 |
| TR321 | Chamfer corner Blend: the corner triangle replaced by a filling face tangent to the bevels along its edges. Setback still not possible (kernel). Line left open. | D2304 | 886e134f |
| TR166 | Item 2: flanges on curved edges not possible in the flat wall sheet model; the picked end point and several lengths are already met. Recorded, line left open. | D2305 | e9c6ba1d |
| TR170 | Miter Flange: tangent arcs in the profile become bends with the arc's radius; Own Relief at offset ends. Trim side bends not built. Line left open. | D2306 | 7662eb31 |
| TR171 | Convert to Sheet Metal: Keep the solid, and Rip type (Overlap, Underlap, Open, Butt). Rip sketches, per rip values and rounded edges as bends not built. Line left open. | D2307 | 7662eb31 |
| TR174 | Closed Corner bend region Open or Closed (the vault where the two bends cross, folded part only). TR174 ticked. | D2308 | 02821d94 |
| TR77 | Stamp Punch, Die and Corner radii. TR77 ticked. | D2309 | c85cbf97 |
| TR282 | Bend Table lists the Rip features with an editable gap; picking a row highlights the rip. Turning a bend into a rip not built. Line left open. | D2310 | 24fa1e65 |
| TR283 | Item 1: Stamp takes several outlines and a Drawn cut out; the rib (a bead along each line) gets square ends. TR283 ticked. | D2311 | ecdf80e3 |
| TR281 | Several sheet metal bodies (owner approved in D750): one folder per sheet, each with its own values and Flat Pattern, mixed with solid bodies. TR281 ticked. | D2312 | 734ba991 |
| TR279 | Forming Tool Own tool: the shape of a body of the part, with stop face, faces to remove, insert point, rotation and mirror; the tool body leaves the part. The tool library is not built (needs an owner choice on where tool files live). Line left open. | D2313 | 1958c8aa |

TR170 and TR171 share one commit (7662eb31): their changes touched the same shared files in one working tree.

## Items skipped or left in part, and why

* TR64 items 1 and 3, TR321 setback: the kernel's fillet and chamfer makers have no such settings (D2300, D1814).
* TR147 tapered or square steps: FDCAD's Step Draft cannot pick a parting line with steps in it at all; it needs a new draft method (D2301).
* TR166 item 2 curved edges: the sheet model has flat walls only (D2305).
* TR170 trim side bends (D2306); TR171 rip sketches, per rip gap and type, rounded edges as bends (D2307); TR282 bend to rip and back (D2310).
* TR279 tool library: needs an owner choice on where tool files live and how the rebuild reads them (D2313).
* TR281 limits: Bend Table and Export Flat Pattern use the first Flat Pattern only (D2312).

## Owner file items (FDEF params and keys)

New params or keys, all optional, none written for the default:

* dome: `refs.profile_sketch`.
* combine: `reapply_fillets`.
* chamfer: `corner` value `"blend"`.
* miter_flange: `relief`, `relief_by`, `relief_ratio`, `relief_width`, `relief_depth`.
* convert_sheet: `keep_body`, `rip_type` (`overlap`, `underlap`, `open`, `butt`).
* closed_corner: `bend_region` (`open`, `closed`).
* stamp: `punch_radius`, `die_radius`, `corner_radius`, `drawn_cut`.
* form_tool: `rib_ends` (`round`, `square`), `tool` value `"custom"`, `refs.tool_face`, `refs.remove_faces`, `refs.insert`, `tool_angle`, `mirror`.
* flatten: `refs.sheet_metal` (names the sheet a Flat Pattern flattens when a part has several).
* Several Sheet Metal folders per part are now valid (D2312 amends D330).

Move Face features made by Geometry Check Fix use existing keys only. No new keys or shortcuts (SHORTCUTS.md unchanged).

## Shared files changed

* `src/fdcad/core/rebuild/engine.py`: after a sheet metal feature runs, the part's other bodies are put back beside its sheet (`with_other_bodies`); the flat only rule below a Flat Pattern (D339) now holds per Sheet Metal folder. Small, but every rebuild goes through it.
* `src/fdcad/core/features/sheetmetal/common.py`: `latest_sheet` filters by folder and only blocks on a feature that changed the sheet's own solid.
* `src/fdcad/ui/sheet_metal/flow.py`: starting a second sheet adds a folder; other tools take the folder of the picked sheet; one Flat Pattern per folder; rip rows in the Bend Table.
* `src/fdcad/ui/print_tools/geometry_check.py` and `src/fdcad/ui/strings.py`: Geometry Check limit, Fix and clip box.
* `src/fdcad/ui/body_tools/forms.py`: Combine's Reapply fillets tick.
* `src/fdcad/ui/property_panel/forms/shape_forms.py`, `chamfer_form.py`: Dome profile sketch box, Chamfer Blend.
* No change to the main window, ribbon, tool registry or sweep support; no new dialogs (the Bend Table window got a second table).

## Tests

* Each item: tests of what it touched, the two message checker tests and the `tests/ui -k sweep` tests (24 passed, 64 skipped each time).
* Full suite after TR281 (before TR279): 6222 passed, 2 failed, 121 skipped, 3 xfailed. Final full suite: see the last line below.
* The two failures also fail on the untouched base branch in this Linux container: `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory` (Windows style paths) and `tests/perf/test_budgets.py::test_200_feature_part_memory` (memory budget on this machine). Neither touches this round's code.
* Pre existing ruff findings in test files from other rounds (8, for example `test_edge_profile.py`, `test_orient_body.py`) were left alone.

Last full suite result (after TR279, at 1958c8aa): 6226 passed, 2 failed (the two environment failures above), 121 skipped, 3 xfailed, in 15 min 26 s.
