# Round 12 report: Local E (patterns, sweep and loft, holes and threads)

Branch `local/round12e`, decisions D1500 to D1520. Work stopped at about 75 percent of the 5 hour usage window, after 20 items or parts of items. `origin/phase7b-stage2` was merged in at the end (one conflict in PLAN.md, the TR270 and TR272 lines; both kept).

## Items done

| TR | What | Decision | Commit |
|---|---|---|---|
| TR366 | Per copy angles (Circular Pattern) and spacing laws for Array Along Curve. TR366 ticked. | D1500 | d023a2e0 |
| TR270 item 2 | Linear Pattern seed cell and grid rotation | D1501 | 5d036483 |
| TR398 items 2, 3 | Suppress Region for every pattern; Linear Pattern fill Spacing and overall size | D1502, D1503 | a32d8368 |
| TR56 items 3, 4 | Sweep twist by number of turns (whole turns on closed paths); Follow Curvature | D1504 | 2b6fbd75 |
| TR144 item 3 | Hole taper and Depth Includes Point | D1505 | 1f44839c |
| TR144 item 2 | Counterdrill hole type | D1506 | 960c1bd1 |
| TR393 | Thread class on tapped holes and modelled threads (hole list, allowance). TR393 ticked. | D1507 | e64d8d62 |
| TR397 item 2 | "count@Hole 1" for formulas (the sizes already were named values) | D1508 | 1b576e16 |
| TR139 item 1 | Sweep self crossing message names the tight bend | D1509 | 75660e8c, fix f4fdd8b7 |
| TR254 (part) | Trapezoidal, ACME, square, buttress and pipe 55 degree thread forms | D1510 | 06275588 |
| TR145 (part) | Tapered Pipe Tapped hole type, NPT and Rc sizes | D1511 | 2c1fa463 |
| TR141 item 2 | Patterns (and mirrors) of patterns of features | D1512 | a0cc4ca5 |
| TR59 item 1 | Increment spacing laws and Vary values (seed values grow per copy) | D1513 | fae68f4e |
| TR396 item 2 | Sweep orientations Normal to Face and Follow Second Path | D1514 | ef238df2 |
| TR137 item 3 | Sweep corners Mitre and Round | D1515 | 33699b09 |
| TR138 item 1 (part) | Sweep a flat model face as the profile | D1516 | 7f6800fd |
| TR146 item 1 (part) | Mounting Boss height up to a mating face and pin size from a mating edge | D1517 | fb11afda |
| TR324 | Size gradient on Fill Pattern cut shapes. TR324 ticked. | D1518 | 6c7908c2 |
| TR399 item 3 | Pattern check level Full or Fast | D1519 | 8c0f5bf9 |
| TR143 item 2 | Skip a hole position of an existing sketch by clicking | D1520 | cf149bec |

The PLAN.md lines of the partly done items say what is done and what is open.

## Items skipped and why

* TR142 item 1 (patterns of reference planes, axes and points): a feature result holds one datum; copies of datums need a change to the result model and to everything that picks datums. Too large for this round.
* TR136 (loft connectors and end constraints): connectors are dragged in the view (viewport work), and tangent or curvature to adjacent faces cannot be made with the guiding copy method the loft uses for its end constraints (D220); it needs a different loft builder.
* TR256 (thread relief and end chamfer): needs the undercut and chamfer sizes of the published thread run out standard, which I could not compile with confidence from what is in the repository; the clean room rules bar looking them up.
* TR327 (user thread tables): needs a table editor dialog, size list plumbing in three panels and a Repeat command; larger than the time left.
* TR347 (simplify threads while editing): export and print preparation must force a full rebuild with real threads; those flows belong to session B (printing and export) and the main window.
* TR412 (fit values by hole size and direction): the table lives in the printer profile (session B's area) and needs its editor.
* Open parts of partly done items: TR270 items 1 and 3 and view only hiding (viewport and tree commands), TR141 item 1 (pattern chains), TR399 items 1 and 2 (Add to Pattern), TR398 item 1 (curved face spacing), TR59 items 3 and 4 (per instance overrides, Vary Sketch), TR56 items 1 and 2 (tangency; for merging tangent faces, faces on one surface are already joined by the final unify, and faces on different surfaces cannot be one B-rep face without approximation), TR137 items 1 and 2, TR138 loft edge loops and items 2 and 3, TR139 item 2 (Show Sections), TR396 item 1 (section formulas along the path), TR143 item 1, TR397 item 1, TR144 items 1 and 4 and the start plane, TR145 tapered modelled thread, TR254 sketch profile and end finishes, TR146 boss step and items 2 and 3.

## FDEF owner items (new params and keys, not in FDEF_SPEC.md)

* Circular Pattern: `law1`, `law2` ("even", "angles", "increment"), `angles1`, `angles2` (text), `increment1`, `increment2` (angles).
* Linear Pattern: `law1`, `law2` gain "increment" with `increment1`, `increment2` (lengths); `seed_cell1`, `seed_cell2`; `rotate` (angle); `fill1`, `fill2` gain "fit".
* Every pattern (shared COMMON_PARAMS): `region_mode` with `refs.region`; `vary` (text); `check` ("full", "fast").
* Array Along Curve: `law`, `ratio`, `jitter`, `seed`, `fractions`.
* Fill Pattern: `gradient`, `size_end`, `refs.gradient_from`.
* Sweep: `twist` gains "turns" with `twist_turns`; `orientation` gains "curvature", "face" (`refs.orient_face`) and "second_path" (`refs.x_path`); `corners`; `profile_type` gains "face" with `refs.profile_face`.
* Hole: `hole_type` gains "counterdrill" (`cdrill_angle`) and "pipe_tapped"; `taper`, `taper_angle`, `point_in_depth`; `thread_class`; `data.skip_points`.
* Thread (modelled): `thread_class`; `form` gains "trapezoidal", "acme", "square", "buttress", "pipe".
* Mounting Boss: `height_clearance` with `refs.height_face`; `pin_clearance` with `refs.pin_edge`.
* No new shortcut keys.

## Shared files changed

* `src/fdcad/ui/body_tools/forms.py` and `form_widget.py` (pattern fields, the text field placeholder, the seed list offers patterns of features).
* `src/fdcad/ui/strings.py`, `strings_phase3.py`, `strings_phase4.py` (labels, tips, choices).
* `src/fdcad/ui/property_panel/forms/`: `sweep_form.py`, `hole_form.py`, `pipe_forms.py`, `thread_forms.py`, `fastening_forms.py`.
* `src/fdcad/core/equations/engine.py` (MEASURED_VALUES gets the hole count) and `src/fdcad/core/hole_table.py`.
* No new dialogs, so `tests/ui/sweep_support.py` is unchanged.

## Tests

Per the local rules only the tests of what I touched were run; the full suite is the manager's. Run and passing: the new and changed test files, the pattern, hole, sweep, thread, fill, loft, vent, lip and groove and mounting boss tests, the sample part tests, `tests/core/io`, `tests/docs`, the message checker tests and `tests/ui/test_app_sweep.py`, before the final merge and again after it.

After the merge: 263 passed, 52 skipped, 1 failed. The failure is `tests/core/test_message_next_steps.py::test_every_error_and_warning_says_what_to_do_next` on two messages that came in with the merge from `phase7b-stage2` (`core/features/extrude_open.py:94` "Redraw its ends." and `core/features/twist_lock.py:209` "Model the box round the lid's plug"): their next step verbs are not in the message checker's list. They are not in this branch's area, so they are left for the manager.
