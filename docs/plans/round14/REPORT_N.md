# Round 14, cloud N: report

Branch `cloud/round14n`, made from `origin/phase7b-stage2` (01d6e2b5, which did not move during the round). Decisions D2400 to D2422. The stop signal (`control/stop`) was checked before every item and was never set.

## Items done

| Item | What was built | Decision | Commit |
|---|---|---|---|
| TR59 | Numbered instance markers on pattern copies in the view; clicking one starts that copy's Copy values entry. Vary Sketch is not built. | D2400 | 7a31105a, e1ed9048 |
| TR270 | A box dragged over instance markers adds those copies to Instances to Skip; Ctrl brings them back. Hiding copies in the view only is not built. | D2401 | fd10b02a |
| TR142 | Linear and Circular Pattern copy one reference plane, axis, point or coordinate system. Explode Pattern turns each copy into a usable reference. Line ticked. | D2402 | 68325588 |
| TR136 | Item 1: several connectors per loft profile (match_k) with Reset. Item 3: Add Loft Section from the tree menu. Dragging connectors in the view is not built. | D2403, D2404 | 08731b77 |
| TR138 | Item 3: Swept Cut with a solid tool body, exact for straight moves. Item 2 (group picker) is not built. | D2405 | a6232c25 |
| TR146 | Item 3: Vent draft and fillet for each element group. Item 2: Lip and Groove picks the rim by edges, Jump Gaps, Follow Wall Draft. Line ticked. | D2406, D2407 | 89b0f69b |
| TR162 | Sweep Ground ends. New sample `hex_fasteners` (an M6 bolt, nut and washer sized from the screw and washer tables) with a tutorial. Line ticked. | D2408, D2409 | 3a68cfd0, b51b7d27, 0a01166f |
| TR408 | Item 2: Stone Setting. Item 3: Sprue Tree, with tree and kit frame layouts. Line ticked. | D2410, D2411 | 3a68cfd0 |
| TR75 | Item 3 (single line fonts) is not built. | D2413 | e16fc5fc |
| TR67 | Deform Point, Deform Curve to Curve and Surface Push. Line ticked. | D2412 | e16fc5fc |
| TR258 | Roof: an equal slope roof over any closed outline, with an optional flat top. Grow by a sphere is the existing Offset Body Rounded. Line ticked. | D2414 | e75d7761 |
| TR268 | Item 1: Move and Copy Body by relations, solved together. Item 3: transform handle pivot and axes. Line ticked. | D2415, D2416 | 260aeb11, eae5443a |
| TR154 | Linked Body Copy, built after the rest of the part, with Break Link in the tree menu. Line ticked. | D2417 | ed299415 |
| TR266 | Face Relation (coplanar, offset, concentric, parallel, perpendicular, equal radius, fixed), held by later Move Face features. Line ticked. | D2418 | b51b7d27 |
| TR343 | Move Part Origin (tree menu on Origin). The origin and main planes move; other geometry stays where it is. Line ticked. | D2419 | b51b7d27 |
| TR71 | Insert Part: bodies of another part, linked to its file, with reference sketches and planes, Break Link and a self insert guard. Line ticked. | D2420 | b51b7d27 |
| TR72 | Nothing new. The rest of the item is recorded as not built. | D2422 | b51b7d27 |
| TR280 | Tools, Bodies to Part Files: linked parts (each holds an Insert Part of one body), FDCAD parts, STEP, STL or 3MF. Line ticked. | D2421 | b51b7d27, last commit (icon) |

The six new commands' icons (roof, stone setting, sprue tree, the three local deform modes) plus face relation, linked copy and insert part are drawn for FDCAD and listed in `icons/NAMES.md`.

## Not built, and why

- TR59 item 4, Vary Sketch: the pattern engine moves the seed's solid. It never solves the seed's sketch again for each copy (D2400).
- TR270, hiding copies in the view only: a pattern's copies are faces of one solid, and the view draws that solid as one shape (D2401).
- TR136, dragging connectors in the view: the view has no vertex handles on sketch profiles. Typed vertex numbers do the same job (D2403).
- TR138 item 2, the group picker that joins chains with trim and extend: it needs a new chain editing widget (D2405).
- TR75 item 3, single line fonts: this needs a stroke font, plus open curves carried through text layout, display, export and Wrap (D2413).
- TR258, grow by shapes other than a sphere: the kernel has no Minkowski sum (D2414).
- TR72, the rest (several features per file, asking for each attached face, hidden internal dimensions, link or dissolve): this needs a placement model beyond Paste (D2422).
- A `ground_spring` sample was built, then left out. Its keys (`ends`, `end_pitch` and `ground_ends`) are not in FDEF_SPEC.md, and the schema keys test only lets samples write keys the spec lists (D2409).

## FDEF owner items (new keys and types for FDEF_SPEC.md)

- New feature types:
  - `stone_setting`: `seat_face`, `seat_point`, `stone_diameter`, `girdle_depth`, `pavilion_angle`, `prongs`, `prong_diameter`, `prong_height`.
  - `sprue_tree`: `feed_points`, `cup`, `layout` (tree or kit_frame), `cup_diameter`, `cup_height`, `sprue_diameter`, `gate_diameter`, `margin`.
  - `roof`: `sketch`, `slope`, `max_height`, `operation`.
  - `deform_point`: `point`, `direction`, `fixed`, `distance`, `radius`, `stiffness`.
  - `deform_curve`: `initial`, `target`, `fixed`, `radius`.
  - `surface_push`: `point`, `direction`, `tool`, `depth`, `tool_x`, `tool_y`, `reach`.
  - `linked_copy`: `bodies`, `place` (offset or on_frame), `dx`..`rz`, `frame`, `data.link`.
  - `face_relation`: `relation`, `faces`.
  - `insert_part`: `part_file`, `link`, `keep_bodies`, `with_sketches`, `with_planes`, `place`, `dx`..`rz`, `frame`, `embedded`.
- New keys on existing types:
  - `loft`: `match_<k>`.
  - `sweep`: `profile_type` "body" with `refs.tool_body`, and `ground_ends`.
  - `vent`: `rib_draft`, `spar_draft`, `fill_draft`, `rib_fillet`, `spar_fillet`, `fill_fillet`.
  - `lip_groove`: `lip_edges`, `groove_edges`, `jump_gaps`, `follow_wall`.
  - `move_copy_body`: `mode` "relations" with `rel_from`, `rel_to` and `relations`, plus `pivot` (body_centre or picked) with `pivot_point`, and `handle_axes` (model or plane_axes) with `handle_plane`.
  - `origin`: `ox`, `oy`, `oz`, `rx`, `ry`, `rz`.
- Linear and Circular Pattern take a reference feature as `refs.features`. No new key.
- No new keyboard shortcuts.

## Shared files changed

- `src/fdcad/core/rebuild/engine.py`: one line. Linked copies, and the features that use them, are built last (`deferred_order`, D2417). `core/features/preview.py` `body_before` uses the same order. The preview's `PreviewGeometry` also gets a `markers` field (D2400).
- `src/fdcad/ui/viewport/widget.py`: a `markers_boxed` signal and `markers_in` (D2401). `ui/viewport/preview.py` and `value_labels.py` route marker clicks and boxes.
- `src/fdcad/ui/command_tabs/tabs.py`: new commands added as dropdowns, so no group grew wider. The pairs are Dome with Roof, Move and Copy Body with Linked Body Copy, and Merge Faces with Face Relation. Import gets Insert Part, Deform gets a local modes dropdown, and the 3D Print dropdown gets Stone Setting and Sprue Tree. `tests/ui/test_ribbon_layout.py` was updated to match.
- `src/fdcad/ui/tree/feature_tree.py`: new menu items: Add Loft Section, Break Link (linked copy and insert part) and Move Part Origin.
- `src/fdcad/ui/main_window/window.py` (pattern datum drawing) and `plane_pick.py` (exploded plane copies). `ui/equations/install.py` registers the Tools command.
- `src/fdcad/ui/strings.py`, `strings_phase3.py`, `strings_phase4.py`, `input/commands.py`, `body_tools/forms.py`, `body_tools/flow.py`, `body_tools/deform_forms.py`, `tree/row_icons.py`.
- Sample `samples/hex_fasteners.fdprt` and its entry in `tests/golden/samples.json`. No other sample changed.

## Last full suite

`uv run pytest -q -p no:cacheprovider`, Linux offscreen, at commit 0a01166f: 6297 passed, 3 failed, 124 skipped, 3 xfailed (17 min 38 s).

- `tests/ui/test_icons.py::test_every_visible_command_has_an_icon`: the new Tools command had no icon. It was fixed in the last commit; `tests/ui/test_icons.py` and `tests/ui/test_icon_audit.py` pass after the fix (499 passed).

The other two failures come from the test environment, not the code:

- `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory` also fails on the untouched base branch here. It expects Windows style disk paths.
- `tests/perf/test_budgets.py::test_200_feature_part_memory` passes when run alone. It fails only late in a full run on this Linux container, after the process has grown (about 1.8 GB against a 1.5 GB budget).
