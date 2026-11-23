# Round 12 report: Cloud D (fillet, chamfer, draft, shell, direct edit)

Branch `cloud/round12d`, rebased on `origin/phase7b-stage2` at 63ca7962. Decisions D1400 to D1421.

## Items done

Ticked in PLAN.md (done in full):

| TR | Title | Decision | Commit |
|---|---|---|---|
| TR131 | Fillet and chamfer without tangent propagation | D1400 | c48fcc5b, 48473b46 |
| TR62 | Fillet methods and profiles | D1402 | 0b69406d |
| TR133 | Variable fillet point positions | D1403 | 553b2236 |
| TR132 | Change existing fillets and drafts | D1404 | 2d66cc61 |
| TR346 | Fillet failure help | D1405 | 39e0fe23 |
| TR278 | Skip one face as a fix | D1406 | 072e77a3 |
| TR320 | Fillet rules | D1408 | 0c5e1193 |
| TR29 | Face fillet with a hold line | D1409 | 58017b2b |
| TR260 | Remove and change fillets on imported bodies | D1410 | 00255bbd |
| TR130 | Replace Face (flat targets) | D1412 | 0c0c5921, ccbd6ee8, 201e1459 |
| TR267 | Push and pull by sign | D1413 | ebff64f6 |

Done in part (PLAN.md line notes what is done and what is open):

| TR | Done | Decision | Commit | Open |
|---|---|---|---|---|
| TR64 | item 5: partial edge ends by a picked vertex or plane | D1401 | 463005da | items 1 to 4 (see below) |
| TR271 | items 2 and 3: edges to keep, limiting plane | D1407 | a3db82ca, 30e56ce5 | item 1, limit failing areas |
| TR322 | Shell Both Sides | D1411 | 6b36e1e4 | Never Thinner or Never Thicker |
| TR60 | Split Line by projection and by a plane | D1414 | e1dbcc7d | Silhouette, intersection with a body |
| TR84 | Parting line curve, closed loop and gaps | D1415 | d7e5cbd4 | splitting straddle faces (needs Silhouette) |
| TR87 | items 1 and 3: new check classes, Symmetry Check | D1416 | 7e3991dc | item 2, wall thickness target and hover |
| TR262 | new classes, sliver and duplicate Fix, Ignore, Next and Back | D1416 | 7e3991dc | gap, smooth and square up fixes, clip sphere |
| TR164 | detailed preview in core and on Draft | D1417 | 0a713058 | Extrude and Rib panel ticks (shared panel files) |
| TR147 | item 1: allow reduced angle | D1418 | 978ff1fa | tapered or square steps, item 3 (dome) |
| TR323 | second angle below the neutral plane, relative angles | D1419 | de933db2, 756f8937 | Fixed Edge type |
| TR259 | Reapply Fillets on Move Face and Delete Face | D1420 | 3b84db28 | Draft and Combine |
| TR394 | item 3 recorded as met by the vertex chamfer | D1421 | 191e6632 | items 1 and 2 |

579b796f fixes the wording of three new messages for the next step checker.

## Items skipped and why

- TR63 Setback fillet at corners: the OpenCascade fillet has no setback control at a vertex, and the corner patch is made by the kernel. A setback corner needs partial rounds that stop short of the vertex and a new filling surface; not attempted.
- TR321 Chamfer corners (chamfer, mitre or blend corner, setback): the kernel's chamfer makes its own corner and has no setting for the corner kind.
- TR266 Lasting face relations on bodies with no history: a relation store and a solver that holds relations during later Move Face edits is a large new subsystem; not started in this round.
- TR268 Place bodies by picks: not started (a mate solver for Move and Copy Body, frame mapping for Orient Body, and handle pivot and axis choices, which are viewport work).
- TR64 items 1 to 4: Keep Features, Round Corners and Overflow are kernel limits recorded in D213; Select Through Faces is viewport selection (session F's area).
- Open parts listed above: each one's reason is in its decision entry.

## Owner file items (FDEF_SPEC.md and SHORTCUTS.md were not edited)

New feature types:

- `remove_fillets` (D1410): params `min_radius`, `max_radius`, `new_radius` (lengths), `use_range`, `resize` (booleans); refs `faces`.
- `replace_face` (D1412): refs `faces`, `target` (a reference, or a list of one).
- `push_pull` (D1413): params `distance` (signed length), `symmetric`; refs `faces`, `sketch`, `to_face` (a reference or a list of one).
- `split_line` (D1414): params `method` ("projection", "intersection"), `reverse`, `both`; refs `faces`, `sketch`, `direction`, `plane` (a reference or a list of one).
- `parting_line` (D1415, a curve feature): param `reverse`; refs `direction`.

New params and refs on existing types:

- fillet: `tangent_propagation` (D1400, written only when false); `partial` "reference" with refs `partial_ends` (D1401); `method` ("radius", "asymmetric", "chord", and "hold_line" for face fillets), `profile` ("circular", "conic", "curvature", "elliptic"), `distance2`, `rho`, `reverse` (D1402, D1409); `vp_<j>` (D1403); refs `keep_edges`, `limit_plane`, param `limit_flip` (D1407); `auto_edges` items with `rule`, `feature`, `axis`, `exclude`, `radius`, and params `rule_radius_<n>` (D1408); refs `hold_lines` (D1409).
- chamfer: `tangent_propagation` (D1400); `partial` "reference" with refs `partial_ends` (D1401).
- shell: refs `skipped_faces` (D1406); param `both_sides` (D1411).
- draft: `allow_reduced` (D1418); `neutral_split` with `angle2`, and `angle_mode` ("absolute", "relative") (D1419).
- move_face and delete_face: `reapply_fillets` (D1420).
- New fix action `add_refs` (D1406) and `split_fillet` (D1405).

Keys: no new keyboard shortcuts.

## Shared files changed

- `src/fdcad/ui/main_window/context_menu.py`: view menu items on faces (Change Fillet Edge, Replace Face, Push Pull, Split Line, Parting Line).
- `src/fdcad/ui/main_window/window.py`: `FIX_ACTIONS` gets `add_refs`; `apply_fix` handles `split_fillet`.
- `src/fdcad/ui/tree/feature_tree.py`: tree menu items Change Fillets, Change Drafts, Reset Skipped Faces.
- `src/fdcad/ui/property_panel/forms/base.py`: labels and keys for fillet rule items.
- `src/fdcad/ui/body_tools/forms.py`, `src/fdcad/ui/strings_phase3.py`: Reapply fillets tick on Move Face and Delete Face.
- `src/fdcad/ui/print_tools/geometry_check.py`: Geometry Check limits, Fix, Ignore, Next, Back, Symmetry Check.
- `src/fdcad/core/features/preview.py`: detailed preview.
- `src/fdcad/ui/strings.py`: new strings, each block marked with its TR and decision.
- New feature types register from `fillet.py` and `delete_face.py`, and new panel forms from `fillet_form.py`, so `core/features/__init__.py` and `forms/__init__.py` were not edited. No ribbon commands or icons were added; the new tools open from the view and tree menus.

## Tests

- Last full suite on the rebased branch (`uv run pytest -q -p no:cacheprovider`, Linux, Qt offscreen): 1 failed, 5345 passed, 97 skipped, 1 xfailed. The one failure is `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory`, from the cloud machine's disk and memory, and it fails the same way on the base branch.
- The baseline before any change had 2 failures from the environment: `tests/core/test_resources.py::test_shortages_list_each_disk_once_and_memory` (disk and memory check on the cloud box) and `tests/ui/test_print_tools_install.py::test_tools_install_in_a_fresh_process` (a fresh process install). Neither touches this round's code.
- The app sweep and the next step message checks pass.

Mac and Windows CI were not run from this session (D35); the manager's merge runs them.
