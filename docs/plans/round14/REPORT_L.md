# Round 14 report: cloud L (sketch)

Branch `cloud/round14l`, from `origin/phase7b-stage2` (01d6e2b5; it did not move during the session). Decisions D2200 to D2209. No stop signal was seen.

## Items done

| Item | What was built | Decision | Commit | PLAN.md |
|---|---|---|---|---|
| TR111 | Symmetric angle about a centerline: half angle with the text on the line's side, full angle across the centerline | D2200 | 7bb7e863 | unticked: arrow flip not built (sketch dimensions draw no arrowheads, D1708) |
| TR115 | Spline length dimension that drives the spline (solver midpoint helpers plus a chord and polygon length estimate); Path Length takes splines | D2201 | 860c0cb0 | ticked (degree and weights do not apply, D278, D1314) |
| TR121 | Bold, italic and turn per character (style runs); `{copy}` text field that numbers pattern copies | D2202, D2203 | a97e4c47 | ticked |
| TR151 | Slices round a reference axis; section view kept as a Section Cut feature | D2204, D2205 | 060cb7ed, 96019424, 74d556a3 | ticked |
| TR7 | 3D relations for 3D line points (Along X, Y, Z, Coincident, Fix, 3D Length) solved by a small numpy solver, and ties from 3D lines to plane sketch points | D2206 | 4b106efb | unticked: drawing in the 3D view with Tab to switch planes, and relations between two plane sketch parts |
| TR395 | An extrude depth arrow Alt snapped to a vertex becomes Up to Vertex, so it follows the point | D2207 | 267ab36d | unticked: fillet, chamfer and hole position values have nothing that could follow a point |
| TR329 | Pick in Volume (box, cylinder, sphere; inside, outside, touching), Paint Selection, Pick Bodies, Faces or Edges Only | D2208 | 5cb760ec | unticked: sizing the volume with handles in the 3D view (typed sizes instead) |
| TR293 | Click then click handles with arrow nudges, Enter and Escape; arrow nudges of picked sketch items; Tab to the next sketch point; tree Move Up and Move Down | D2209 | d45ab5d1 | unticked: placing a sketch dimension label by click then click |

## Items skipped

None skipped. The parts left out of each item are in the table and in their decisions.

## Owner file items

FDEF keys (FDEF_SPEC.md not edited):

1. Sketch dimension key `symmetric: true` on an `angle` dimension (D2200), written only when set.
2. Sketch `path_length` dimensions may now name splines (D2201). No new key.
3. Sketch text key `styles`: a list of runs `{start, end, bold?, italic?, angle?}` (D2202), written only when there are runs.
4. Sketch text field `{copy}` (D2203). No new key.
5. New feature type `section_cut` (Section Cut, D2205): no refs, no params, data key `zones`: a list of zones, each a list of `{origin: [x, y, z], normal: [x, y, z]}`.
6. 3D sketch data key `relations` (D2206): a list of `{type, points, value?, at?}`, with type `along_x`, `along_y`, `along_z`, `coincident`, `fixed` or `length`, and points `"k.i"` (3D line point) or `"Pk:eN"` (plane sketch part point).
7. Reference plane features made by Slice Body round an axis use the existing `angle` method (D2204). No new key.

Keys: none added to SHORTCUTS.md. New commands have no default key: `select.only_bodies`, `select.only_faces`, `select.only_edges`, `select.paint`, `select.in_volume` (D2208). The sketch uses arrow keys (nudge, with no tool active) and Tab (next point, while a point is picked), which SHORTCUTS.md leaves free there (D2209).

## Shared files changed

1. `src/fdcad/core/features/patterns.py`: a small `{copy}` hook beside the vary code (D2203). Cloud N's area.
2. `src/fdcad/core/features/base.py`: `BuildContext.copy_number` (D2203).
3. `src/fdcad/core/features/__init__.py`: registers `section_cut`.
4. `src/fdcad/ui/section/panel.py`, `src/fdcad/ui/section/tool.py`, `src/fdcad/ui/section/strings_section.py`: the Save as Cut Feature button (D2205). Cloud O's area.
5. `src/fdcad/ui/viewport/widget.py`: `handle_snapped` signal (D2207), paint pick (D2208), click then click handles (D2209).
6. `src/fdcad/ui/viewport/preview.py`, `src/fdcad/ui/property_panel/panel.py`: vertex link for depth arrows (D2207).
7. `src/fdcad/ui/main_window/window.py`: Selection menu entries and handlers (D2208).
8. `src/fdcad/ui/input/commands.py`, `src/fdcad/ui/input/selection_rules.py`, `src/fdcad/ui/icons/NAMES.md` and five new icons plus `feature.section_cut.svg`.
9. `src/fdcad/ui/tree/feature_tree.py`: Move Up and Move Down (D2209).
10. `src/fdcad/ui/strings.py`, `strings_extra.py`, `strings_phase3.py`, `strings_phase4.py`: new texts.

## Tests

1. Full suite after five items (TR111 to TR7): 6219 passed, 2 failed, 121 skipped, 3 xfailed. The two failures are environmental: `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory` fails the same way on the base branch in this container, and `tests/perf/test_budgets.py::test_200_feature_part_memory` passes when run alone (memory was high only under the full run).
2. Last full suite, after all eight items: 6234 passed, 2 failed, 121 skipped, 3 xfailed. The failures are the same two environmental ones as above (the memory budget measured 1759 MB under the full run and passes alone).

## Notes for the manager

1. The cloud container needed `libegl1` installed to import PySide6 (`apt-get install libegl1`). The repository needs no change for it.
2. `tests/core/features/test_edge_profile.py` has a ruff RUF007 warning from an earlier round; not touched.
