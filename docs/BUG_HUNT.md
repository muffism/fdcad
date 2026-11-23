# Bug hunt for v1.0 (PLAN Phase 6, round 9s)

The owner asked for the Phase 6 bug hunt to run without a human tester (D438 stream 1). An automated sweep drives the app on the Qt offscreen platform (D490):

1. Opens every sample part and graph sample.
2. Runs every command id in `src/fdcad/ui/input/commands.py` with no selection, a face, an edge, a vertex, a sketch and a body selected, then presses Cancel or OK on what it opened (OK keeps the panel's defaults).
3. Runs every item of the view right click menu (empty space, face, edge, vertex, plane) and of the tree right click menu on every row.
4. Draws each shape on a fresh sketch, dimensions, trims, offsets and exits; runs every sketch command and every sketch right click item.
5. Opens every preference page, changes every field, then Cancel and OK.
6. Save, Save As each type (FDCAD part, STEP, STL, 3MF, and a name with no suffix), reopen.
7. Checks every command tab button and dropdown entry.

Each step must not raise, must finish within 30 s, and Undo then Redo must give back the same `.fdef` text.

Run it with:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/ui/test_app_sweep.py
```

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/ui/test_app_sweep.py --run-slow
```

The first runs the quick version (about 75 s). The second adds the full sweep over every sample (about 2 hours on 4 cores).

## Found and fixed

Ranked by severity: crashes and data loss first, then wrong geometry, then dead buttons and wrong messages.

| Id | Severity | What failed | Short repro | Fix and regression test |
|---|---|---|---|---|
| B3 | Crash | A tree refresh while a plane pick was armed passed every row change to the pick. The part row raised KeyError; a plane row could start the pick's next step while the tree was deleting its rows, which corrupted memory and crashed the process (segmentation fault in `FeatureTree.refresh`). | Open the plate sample. Right click Plate Sketch, Edit Sketch Plane. Leave it open, right click Holes, Roll Back to Here. | The pick ignores row changes while the tree refills and rows that are not features (D493). `test_tree_refresh_while_picking_a_plane` |
| B3a | Wrong result | Same cause: after a refresh the restored current row replaced the plane the user had chosen. | Select Top Plane in the tree, Edit Sketch Plane on a sketch, pick Front Plane, then anything that rebuilds. The pick shows Top Plane. | Same fix and test. |
| B2 | Data left behind | Cancel on the first Sheet Metal values kept the new Sheet Metal folder and still opened the Base Flange panel. | New part with a sketch. Base Flange. Cancel on the Sheet Metal panel. | The panel records OK or Cancel; Cancel undoes the folder (D492). `test_cancel_on_the_first_sheet_values_stops_base_flange` |
| B5 | Wrong message | Messages said what failed but not what to do: export failures, the five print checks, preview, regions, measure, reference geometry kernel failures, Combine with one body, Select Other on empty space, unreadable part files. | File, Export to a folder that cannot be written; or open a damaged `.fdef`. | Each now ends with a next step (D494). `test_error_message_steps.py` |
| B6 | Test failure | The startup memory budget failed on Linux (449 MB) because the kernel library maps about 245 MB of library files there. | `uv run pytest tests/perf/test_budgets.py -k startup` on Linux. | On Linux the test counts the memory the app allocates (D491). |
| B7 | Wrong message | About 300 messages (feature value checks, the sketch solver, file, configuration and design table messages) said what failed but not what to do. Was open item O1. | Give an extrude a depth of 0; add Coincident to one item. | Rewritten at their sources in round 9v (D550). `tests/core/test_message_next_steps.py` scans every message in the source. |
| B8 | Wrong message | Wrappers such as `VARIABLE_ERROR`, `OPEN_FAILED` and the favourites import wrapped reasons that ended with a full stop, so no fixed step could follow. Was open item O2. | Open a file you cannot read. | FDCAD reasons are complete messages shown last; outside reasons go through `strings.clause()` before a fixed step (D550). `tests/ui/test_error_message_steps.py` |

## Checked and not a bug

| What the sweep saw | Why it stays |
|---|---|
| Opening a feature panel and pressing Cancel, or Undo after OK, leaves `next_id` one higher in the file text. | Feature ids are never reused on purpose (D490). The sweep compares the file text without this counter. |
| Shell, the patterns, Mirror, the body tools, Rib, Lip and Groove, Flow and the deformations accept OK with nothing picked and add a feature with an error such as "Mirror 1: pick a plane in the view." | The feature stays in the tree with an error that names the missing pick, so the user can edit it. Other panels refuse OK until a pick is made. Both follow TOOL_SPEC T5; making them all refuse OK would be a behaviour change, recorded in IDEAS.md instead. |
| Offset Face adds a feature named Move Face. | Offset Face is Move Face in Offset mode (D230). |
| Sketch commands that need a selection (Offset, Mirror, Fillet, Chamfer, patterns) do nothing when the clicks miss. | They wait for a pick and say so in the status bar. |

## Open

None. O1 and O2 were closed in round 9v as B7 and B8.

## Round 10a

Phase 1 core workflow before v1.0: sketching, Extrude, Revolve and their cuts, the feature tree, undo and redo, Save, Save As, Open, recovery, the welcome screen and the Help menu. Four hunters drove the real main window offscreen (sketch, Extrude and Revolve, tree and undo, files and app shell); the lead merged their fixes and fixed the items marked L. Every fix has a regression test that fails without it.

Start of round: ruff, ruff format, mypy clean; pytest 3146 passed, 1 failed (`test_edges_pick_within_a_few_pixels` needs a display, fixed as L5), 75 skipped.

End of round: ruff, ruff format, mypy clean; pytest 3211 passed, 76 skipped; the full slow suite (`--run-slow`, every sample in the app sweep and the naming stress tests, 112 tests) passed.

### Found and fixed

| Id | Severity | What failed | Short repro | Fix and regression test |
|---|---|---|---|---|
| L1 | Data loss | Save and autosave left out the open sketch's edits; a new sketch was missing from the file, and the title showed no star. | Start a sketch, draw a rectangle, Ctrl+S, reopen. | Save closes the sketch as OK does; autosave writes a copy with the sketch (D590). `test_save_open_sketch.py` |
| F1 | Crash | A wrong typed value in the configurations block made Open raise TypeError with no message. | Open a file with `"overrides": 5`. | Reported as a damaged file. `test_damaged_configurations_give_a_file_error` |
| F3 | Data loss | Save As swapped the last dotted part for the suffix: "rev 1.2" saved as "rev 1.fdprt" and silently replaced that file. | Save As "rev 1.2". | The suffix is added; a different existing file is confirmed first (D597). `test_save_as_adds_the_suffix_to_a_dotted_name` |
| F10 | Data loss | A second FDCAD offered the first one's live autosaves as crash recovery and deleted them. | Run two copies with an unsaved part in the first. | Autosaves are held by lock files (D597). `test_recovery_leaves_the_autosaves_of_a_running_fdcad_alone` |
| F4 | Data loss risk | A recovered part opened as Untitled, so Save asked for a new name and the original stayed old. | Crash with an unsaved saved part, recover. | The recovered part keeps its file. `test_recovered_part_keeps_its_file` |
| F2 | Data access | Saved parts and exports were written with mode 0600 on macOS and Linux; saving over a shared file removed group access. | Save, then `ls -l`. | Normal permissions (D597). `tests/core/io/test_file_modes.py` |
| S1 | Data loss | Delete removed the sketch origin, its Fix and every relation to it. | Click the origin, Delete. | The origin and its Fix are kept (D596). `test_delete_keeps_the_sketch_origin_and_its_fix` |
| S6 | Data loss | Mirror with Copy off lost the shape's joins: the mirrored rectangle had four loose sides. | Mirror a rectangle, Copy off, drag a side. | The copies keep the relations a mirror keeps true (D596). `test_mirror_without_copy_keeps_the_joins_of_the_replaced_shape` |
| S8 | Data loss | Edit Sketch on another sketch opened it even when the open one could not close, dropping its changes. | Bad value in a dimension box, Edit Sketch on another sketch. | The open sketch stays open. `test_edit_another_sketch_keeps_the_open_one_when_its_value_is_wrong` |
| L2 | Data loss | Same as S8 when switching part tabs: the sketch stayed open under the other part. | Bad value in a dimension box, click another part's tab. | The tab goes back to the sketch's part (D592). `test_switching_parts_keeps_a_sketch_whose_value_is_wrong` |
| E7, T9 | Exception | OK after Undo had removed the open feature raised KeyError. | Add Extrude 1, edit it, Undo, OK. | Undo is off while a panel is open (D591); the panel also says the feature is gone. `test_ok_after_undo_removed_the_feature_does_not_raise`, `test_undo_is_off_while_a_feature_panel_is_open` |
| T10 | Exception | During a rebuild, a click or right click on the row of a deleted or undone feature raised KeyError. | Delete a feature on a large part, right click its row at once. | Rows refill after every undo change (D591). `test_rows_follow_the_document_before_the_rebuild_ends` |
| E1 | Wrong geometry | Mid Plane with a draft leaned only one half. | 20 x 20 square, Mid Plane 10, draft 5 degrees. | Both halves use the draft (D595). `test_mid_plane_draft_leans_both_halves` |
| E2 | Feature fails | Through All cut with an inward draft failed even at 2 degrees. | Square cut through a plate, inward draft 2 degrees. | The cut ends 1 mm past the part (D595). `test_through_all_cut_with_inward_draft` |
| E4 | Wrong geometry | Revolve Offset from Face larger than the turn to the face wrapped round to 350 degrees with no message. | Face 90 degrees away, offset 100. | Error that names the fix (D595). `test_offset_past_a_face_of_the_part_is_an_error` |
| T1 | Wrong result | Deleting the feature just above the rollback bar rolled the part to the end. | Roll back to the hole sketch, delete it. | The bar moves to the feature before (D591). `test_deleting_the_feature_above_the_bar_keeps_the_part_rolled_back` |
| T3 | Wrong geometry | Suppressing the feature just above the bar built every rolled back feature. | Roll back, suppress the feature above the bar. | The rebuild leaves out all rolled back features (D591). `test_rollback_holds_when_the_feature_above_the_bar_is_suppressed` |
| T12 | Wrong result | Dragging the feature above the bar took the bar with it. | Roll back, drag the feature above the bar higher. | The bar stays (D591). `test_moving_the_feature_above_the_bar_rolls_nothing_else_back` |
| T2 | Wrong geometry | Rename accepted another feature's name or id, or a name with `"` or `@`, so formulas pointed at the wrong feature. | Rename Cut 1 to an existing extrude's name. | The name is refused with a message (D591). `test_tree_refuses_a_name_another_feature_has`, `tests/core/document/test_names.py` |
| S2 | Wrong geometry | Angle dimensions took 0, negative, 180 and 400 degrees; the label disagreed with the lines. | Dimension two lines, type -30. | Refused with a message (D596). `test_angle_dimension_refuses_angles_the_lines_cannot_have` |
| S5 | Wrong geometry | Trim and Extend kept an arc's old arc length, so the radius changed. | Arc with an arc length dimension, trim it. | The arc length is dropped and listed (D596). `test_trimming_an_arc_drops_its_arc_length_and_keeps_its_radius` |
| S4 | Wrong message | A sketch the solver could not solve said "Fully defined". | Triangle sides 80, 25, 25. | Reports Over defined (D596). `test_a_sketch_that_cannot_be_solved_shows_as_over_defined` |
| E3 | Wrong pick | A turned off Direction 2 still took faces picked in the view. | Direction 2 Up to Face, untick, pick a face for From. | Only ends in use take picks. `test_hidden_direction_2_end_does_not_take_the_from_pick` |
| E6 | Value lost | Switching between Up to Face and Offset from Face dropped the face just picked. | Up to Face, pick, switch. | The pick is kept (D595). `test_switching_between_face_ends_keeps_the_picked_face` |
| L3 | Value lost | The sketch Dimension panel applied its value only on Enter; Tab dropped it. | Select a dimension, type in the panel, press Tab. | Applied on focus loss too (D593). `test_leaving_the_value_field_applies_the_typed_value` |
| E5 | Wrong default | Inch parts got 10 in offsets and a 1 in thin wall. | Inch part, From Offset. | Inch sized defaults (D595). `test_inch_part_defaults_are_inch_sized` |
| E8 | Confusing | A new Revolved Cut on a face started with Reverse pressed. | Sketch on a face, Revolved Cut. | Only Extruded Cut points into the part (D595). `test_new_cut_on_a_face_reverses_only_an_extrude` |
| T5 | Wrong message | A sketch on a face of a suppressed extrude said "missing reference f6/cap/end ... Reselect it." | Suppress an extrude with a sketch on its face. | Says to unsuppress. `test_face_of_a_suppressed_feature_says_unsuppress` |
| T4 | Missing message | A refused tree drag only changed the cursor. | Drag a sketch below its feature. | The reason shows in the status bar (D591). `test_a_refused_drag_says_why_in_the_status_bar` |
| S7 | Wrong message | Four trim, extend and convert notes had no next step. | Trim with a curve between no boundaries. | Each names a next step. `test_trim_and_extend_refusals_say_what_to_do_next` |
| S11 | Missing message | Tool panel fields (offset distance, pattern spacing) gave no feedback on unreadable text. | Type "abc" as the offset distance. | Red field, tip and status bar. `test_tool_panel_field_says_what_is_wrong_with_a_typed_value` |
| S10 | Confusing | Shape value fields stayed red after a good value. | Bad value, then a good one. | The error look clears. `test_shape_value_field_drops_its_error_once_a_good_value_is_applied` |
| S9 | Confusing | Dragging fully defined geometry added an empty undo step and made Cancel ask to discard. | Drag a fixed line. | No step when nothing moved. `test_dragging_fixed_geometry_leaves_no_undo_step` |
| S3 | Confusing | A click on a pattern shape's side skipped an instance mark beside it. | Linear pattern with 10 mm spacing of a 10 mm shape. | The nearer curve wins. `test_pattern_pick_on_a_side_wins_over_an_instance_mark_beside_it` |
| T6 | Selection | A row clicked after `select()` jumped back after the next rebuild. | Select a row, then open Appearance. | Fixed in `FeatureTree.select`. `test_a_row_clicked_after_select_stays_selected_after_a_rebuild` |
| T7 | Confusing | A double click opened the feature and left a rename editor open on its row. | Double click a feature, Cancel. | Double click only edits (D591). `test_double_click_edits_the_feature_without_a_name_editor` |
| T8 | Dead item | Rename on a shared sketch link row did nothing. | Right click a shared sketch link, Rename. | Edits the sketch's own row. `test_rename_from_a_shared_sketch_link_row_edits_the_sketch_name` |
| T11 | Minor | Up or Down on the bar at an end of the tree pulled the selection back to the bar later. | Bar at the top, press Up, click a row, rebuild. | Fixed. `test_up_at_the_top_does_not_pull_the_selection_back_to_the_bar` |
| L4 | Text cut off | Long feature names were cut off in the tree with no way to read them. | Rename a feature to a long name. | Full name as a tip (D594). `test_every_feature_row_shows_its_full_name_as_a_tip` |
| F5 | Recent files | `fdcad part.fdprt` stored a relative path, and the same file could open twice. | Open from the command line, then from Recent. | Full paths (D597). `test_a_relative_path_opens_once_and_is_remembered_in_full` |
| F8 | Recent files | `&` in a path showed as a shortcut key; a missing file stayed in Recent forever. | Folder "R&D"; delete a recent file. | Escaped; missing files are removed (D597). `test_recent_files_menu_shows_ampersands_and_drops_missing_files` |
| F6 | Text cut off | The welcome window had a fixed size, so text was cut at larger fonts. | 13 pt system font. | Scroll area. `test_welcome_text_is_never_cut_off` |
| F7 | Wrong title | The title bar kept the name of the last closed part. | Close the only part. | App name and version. `test_title_bar_forgets_a_closed_part` |
| F9 | Wrong message | Export during the first rebuild said the part is empty. | Open a large part, Export at once. | Says to wait for the rebuild. `test_export_during_the_first_rebuild_says_to_wait` |
| F11 | Wrong message | A value that cannot be saved told the user to choose another folder; a TypeError was not caught. | A formula that overflows to infinity, Save. | FDCAD's own reason is shown. `test_a_value_that_cannot_be_saved_names_the_fix_not_the_folder` |
| F12 | Broken link | User guide links to a heading opened the top of the page. | Help, User Guide, a link to a section. | Headings get anchors. `test_guide_links_to_a_heading_scroll_to_it` |
| F13 | Confusing | Save As and Export opened in the working folder, not the part's folder. | Save As on a saved part. | Starts in the part's folder (D597). `test_save_as_and_export_start_in_the_parts_folder` |
| L6 | Slow | The slow sweep failed on every sample, on the base commit too: Preferences OK took 75 to 90 s. Each Preferences open left a hidden dialog of about 300 widgets, and the sweep never let Qt delete closed widgets, so over 12000 piled up and each theme change restyled all of them. | Open Preferences many times, then OK; or run the slow sweep. | The dialog is deleted after it closes; the sweep delivers pending deletes after each step (D599). `test_preferences_leave_no_dialog_behind`; the slow sweep per sample now takes about 2 minutes instead of 12. |
| L5 | Test failure | The pick tolerance test failed on Linux without a display. | Full suite in the cloud container. | Skips without a display (D598). |

### Checked and not a bug

| What was checked | Result |
|---|---|
| Extrude volumes for Blind, Through All, Through All Both, Up to Next, Up to Vertex, Up to Face, Offset from Face, Up to Body, Mid Plane, Direction 2, From Offset, Cut Outside, thin types, caps and draft. | Match hand calculations. |
| Revolve volumes for Blind, Mid Plane, Through All, Direction 2, Up to Vertex, Up to Face, Offset from Face and Revolved Cut. | Match. |
| Every extrude and revolve in the samples and the showcase: open the panel, OK. | No change to the part; every end condition survives edit, undo, redo, save and reopen, with units and formulas. |
| "Created a separate body" on thin cuts. | Correct: a ring cut leaves loose plugs. |
| 80 random sketch runs of 40 steps over every draw tool, trim mode, extend, fillet, chamfer, offset, mirror, patterns, delete, construction, drags, dimensions, relations, undo and redo. | No crash, nothing left pointing at deleted items, data round trips. |
| Trim nearest on a piece with no crossings removes the whole curve. | Matches the spec. |
| Undo then Redo for suppress, rollback, rename, delete and move on every feature of five samples, with Undo during the rebuild. | Same file text, no missing rows. |
| Every right click item on every tree row. | Opens without error. |
| Every sample and fixture file opens; damaged, empty, binary and newer files give clear messages. | Fine. |
| Save As every type, unicode and spaces in names, the modified star, the close prompt, autosave clean up, offline help links, About and New Part dialogs at large fonts. | Fine. |
| `test_full_rebuild_of_each_sample[generated_200]` over its 3 s budget in the cloud container. | The same on the base commit; the container is slower than the target machines. |

### Open

| Id | What | Why it stays |
|---|---|---|
| O10a-1 | A cut that misses the part removes nothing, with no message. | A warning needs a volume check per cut against the performance budgets; recorded for after v1.0. Fixed later (D1086): a cut that removes no material warns. |
| O10a-2 | With Thin Feature on, Selected Regions picks are ignored. | Whether a thin wall follows only picked regions is a design choice. |
| O10a-3 | Ticking Direction 2 on a new 360 degree revolve gives an error at once. | The message says what to do; changing the default is a design choice. |
| O10a-4 | A linear sketch pattern of a fully defined rectangle leaves the copies under defined (they can turn). | D276 says copies are defined by the original; the solver has no translation relation, so this needs a design choice. |
| O10a-5 | Smart Dimension on a line 20 pixels or shorter picks an end point at its midpoint. | A tie in the point wins pick rule (D434). Minor. |
| O10a-6 | Escape after Smart Dimension picks a part edge leaves its fixed construction copy. | Minor; undo removes it. Fixed 2026-11-18 (D2648): Escape takes the copy away. |
| O10a-7 | Deleting a rolled back feature never asks about its sketch; the sketch is kept. | Low impact. |
| O10a-8 | A very large formula evaluates to infinity, which then blocks Save (with a correct message since F11) and autosave of that part. | The expression parser is outside this round's area; suggested fix: raise an expression error when the result is not finite. Fixed later (D723): a result that is not finite is an expression error. |
| O10a-10 | Equations (19 widgets), Design Table (32) and the section view panel (140) leave widgets behind on each open. | Outside this round's area and far smaller than the Preferences leak; same fix as D599. Fixed later (D637): each is freed, or at most one is kept. |
| O10a-9 | Damaged autosaves are skipped at every start but never deleted; several new parts are all called "Untitled" in the close prompt. | Minor. First half fixed later (D724): a damaged autosave is renamed `.damaged` and not tried again. Several parts all called Untitled: tabs showed the same name too. Fixed 2026-11-18 (D2682): new parts are Untitled, Untitled 2 and so on, in tabs and the close prompt. |

## Round 10b

Area: Phase 2 and 3 modelling features (Fillet, Chamfer, Shell, Draft and Draft Analysis, Rib, Hole Tool, threads, Dome, Mounting Boss, Sweep, Loft, Helix, patterns, Mirror, reference geometry), with weight on editing an early feature and rebuilding. Hunted with throwaway scripts through the rebuild engine and the property panels on the Qt offscreen platform, plus a sweep that changed every length of every sample by 10 percent up and down (no later feature broke). Regression tests: `tests/core/features/test_round10b.py` and `tests/ui/test_round10b_ui.py`.

Suite at the start: ruff, ruff format and mypy clean; pytest 3146 passed, 1 failed (R1 below), 75 skipped.

### Found and fixed

| Id | Severity | What failed | Short repro | Fix |
|---|---|---|---|---|
| A1 | Wrong geometry | Picking the second of two edge pieces with the same name rounded the first piece. | Notch across a top edge, fillet the right hand piece. | Resolve by snapshot among same name edges (D606). |
| A2 | Wrong geometry | A cut added before a fillet or chamfer that splits its edge left half the edge sharp, with no message. | Fillet a top edge, then insert a notch across it before the fillet. | Every piece of a split edge is rounded (D606). |
| B1 | Wrong geometry | Modelled threads that run out of the far end of a face cut nothing or the wrong material and reported OK; a tapped hole with a thread deeper than the plate lost the part's face names. | M6 tapped through hole in a 10 mm plate with Modeled thread. | Inside out sweeps turned the right way; a wrong cut now fails with a next step (D607). |
| A3 | Wrong geometry | Shell with a wall as thick as the part reported OK and gave back the solid part. | Shell a 10 mm plate, top removed, wall 12. | Fails: "the wall is as thick as the part" (D607). |
| C3 | Wrong geometry | Loft with both profiles on one plane, or a closed loft of two profiles, reported OK with no volume. | Two squares on Front, Loft. | Clear errors (D607). |
| P5 | Wrong geometry | Geometry pattern of a pattern left out the pattern's seed. | Row of 3 holes, pattern the row in Y with Geometry pattern. | Seeds of patterns are copied too (D604). |
| P6 | Wrong geometry | Sketch Pattern and Hole Tool used ellipse axis points and spline points and handles as positions. | Sketch with one point and a spline, Sketch Pattern. | `helper` points are left out (D605). |
| C2 | Values ignored | Reference plane, point and coordinate system values typed as formulas or variables kept their old values. | Plane offset `=gap`, change gap. | Kinds declared (D608). |
| A5 | Values ignored | "Fillet the rest" with Multiple radius gave the remaining edges the wrong radii, in the core and in the panel. | Radii 30, 1, 1; edge 1 fails; click the fix. | Per edge values follow their edge (D609). |
| A6 | Values ignored | A three distance vertex chamfer reopened with Equal ticked; OK made it equal. | Vertex chamfer 1, 2, 3; edit; OK. | Equal ticked only when stored (D609). |
| B6 | Values ignored | Reopening a thread with a size not in the table switched it to M1.6. | Thread size "D10x1.5"; edit; OK. | Size kept (D609). |
| A7 | Wrong result | Partial fillet over the whole edge (0 to 100 percent) failed. | Partial, percent, 0 to 100. | No split needed (D609). |
| P1 | Wrong message | Picks lost because an earlier feature failed or is suppressed said "pick them again". | Raise a pattern count so a copy falls off; a fillet on another copy. | Names the failed or suppressed feature (D600). |
| P2 | Wrong message | Circular pattern direction 2 angle 0 or negative gave "would not touch the part". | Direction 2, angle 0. | Same check as direction 1 (D602). |
| P3 | Wrong result | Linear pattern direction 2 parallel to direction 1 put copies on each other silently. | Both directions on Right Plane. | Clear error (D602). |
| P4 | Wrong message | Mirror copies that miss the part said "or change the spacing". | Mirror a boss about a side face. | Step fits the feature (D603). |
| C7 | Wrong message | A missing loft profile failed in the kernel (IndexError). | Profiles list with an empty entry. | "profile 2 is missing" (D607). |
| B3 | Wrong result | An edge dome on a face that is not convex added nothing and reported OK. | Dome, Continuous off, on an L shaped face. | Fails with "Tick Continuous dome." (D609). |
| B4 | Wrong message | Mounting Boss messages did not name the feature. | Boss draft 60 degrees. | Name added (D609). |
| R1 | Test failure | `test_edges_pick_within_a_few_pixels` failed on Linux without a display server. | Full suite in a Linux container. | Skips when the 3D view cannot be built (D601). |

### Checked and not a bug

| What was checked | Why it stays |
|---|---|
| Fillets, chamfers, shells, holes, threads, domes, bosses, ribs, sweeps and lofts after changing extrude depths, sketch sizes, suppressing or moving a cut. | References kept, volumes right, or a clear error. |
| Every length of every sample changed by 10 percent up and down. | No later feature broke. |
| Panels reopened for edit for every type in the area (about 40 setups). | Values round trip; only A6 and B6 did not. |
| Save and reopen of every case. | Same text and same volumes. |
| Zero, negative and too large values for radii, distances, angles, thickness, counts, pitches and turns. | Clear messages with a next step. |
| Pattern count lowered so a filleted copy no longer exists. | "picked items were lost. Pick them again" is right: the copy is gone. |
| Reference planes at 0, 180, 360 degrees, three collinear points, coincident axis points, parallel mid planes. | Correct or a clear error. |
| A Sketch Pattern point removed from the sketch shifts the instance numbers of the skip list. | Numbering by sketch order is documented (FDEF_SPEC 5.3.13). |

### Open

| Id | Severity | What fails | Notes |
|---|---|---|---|
| O3 | Wrong geometry | Modelled threads that run out of the far end of a face, including tapped holes with a thread deeper than a through hole, cannot be cut. They now fail with a clear message instead of a silent wrong result (D607). | Needs a kernel fix (trim the thread tool to the part first). Hard problem: hand to an Opus session. |
| O4 | Moves geometry | A sketch on a reference plane made from a face moves when that face grows: the plane's origin is the face's centre (`datum.py` `face_geo`), while a sketch on the face itself keeps the model origin (D74). | Fixing it shifts sketches in saved files, so it needs a stored option and an owner decision. |
| O5 | Wrong geometry | A variable fillet whose radius is larger than the faces allow can report OK with the fillet face running out of the part. | Needs a geometry check of new fillet faces against the part's box. |
| O6 | Wrong geometry | A sweep along a helix whose profile is wider than the pitch overlaps itself and reports OK. | A full self intersection check took over 2 minutes; a cheap pitch check for helix paths is the likely fix. Fixed 2026-11-18 (D2649): a round profile wider than the pitch is refused. |
| O7 | Values ignored | Sweep and Loft ignore Thin Feature Cap Ends; a circular profile sweep ignores Thin Feature. | Either build the caps or hide the option. Fixed later (D713): Cap ends is not offered for Sweep and Loft, and Thin Feature with a circular profile is refused with a message. |
| O8 | Wrong result | A Dome with Continuous on a top face that has a hole fails with "produced invalid geometry" (`solids._unify`). | Shared code; skip the unify when it breaks a valid shape. Checked 2026-11-18: it builds now; the face merge after the dome goes through the fallback of D704. |
| O9 | Missing check | Cosmetic and tapped hole threads longer than the face are stored and drawn as typed. | Clamp with a warning. Fixed 2026-11-18 (D2647): the Cosmetic Thread mark is cut to its face with a warning; tapped hole marks were already cut to the material depth. |
| O10 | Precision | Table values filled into inch parts are rounded to 4 digits (M5 tap drill 4.2012 mm). | `spec_form.number_text`. Fixed 2026-11-18 (D2643): the text reads back as the same length. |
| O11 | Panel | Sweep and Loft twist and end direction lists offer only the default planes; a stored face direction in a Loft is not restored. | |
| O12 | Wrong message | Wording only: a zero per edge fillet radius says "larger than the faces allow"; an asymmetric chamfer's "largest distance" scales both distances; a reference point at a negative distance says "longer than the edge". | Fixed 2026-11-18 (D2644): each names its own cause. |
| O13 | Showcase | `showcase/everything_part.fdprt` reports "touch only along an edge" warnings from its Revolve on, before and after this round. | Outside this area (Revolve). |
| O14 | Outside area | Seen by the hunt, not checked further: an extrude cut sketched on a top face without Reverse removes nothing and reports OK; a typed value "1e-3" says "Unknown unit 'e'". | For the session that owns Extrude and value parsing. Both fixed later: the cut warns (D1086), and 1e-3 is a number (D2620). |

## Round 10c

Area: bodies, direct editing and data exchange (multibody tools, Move, Offset and Delete Face, the deform tools, STEP and mesh import, STEP, STL and 3MF export, Save Bodies, Appearance, Section View, Measure, Print Estimate, hide, show and isolate). The real main window was driven on Qt offscreen with throwaway scripts over the samples and new parts, including edits after the fact, roll back, undo, redo, save and reopen. Choices are in D610 to D619.

Starting point: ruff, format and mypy clean; 3146 passed, 1 failed. The failure was `test_edges_pick_within_a_few_pixels`, which built the 3D view directly; on Linux offscreen the kernel's graphics driver needs a display server. It now skips there and still runs on macOS and Windows.

### Found and fixed

| Id | Severity | What failed | Short repro | Fix and regression test |
|---|---|---|---|---|
| R10c.1 | Wrong geometry | Move Face and Delete Face ran on every body at once: offsets toward another body failed, Up to Body never worked, overlapping bodies gave a false zero thickness warning. | Two blocks 5 mm apart, Offset Face on block A's side by 10 mm. | Edits run on the picked bodies only (D611). `test_direct_edits_change_only_the_picked_body` |
| R10c.2 | Wrong geometry | Ticks on by default could not be turned off: Merge result (Intersect), Uniform (Scale), Equal spacing (Circular Pattern). | Intersect, untick Merge result, OK: regions still merged. | Unticked flags are written as false (D610). `test_flags_on_by_default_can_be_turned_off` |
| R10c.3 | Wrong geometry | Changing Axis in a deform panel kept Start and End fitted to Z; bodies picked later kept the old triad. | Twist about X on a 10 mm bar: turned about 9 degrees instead of 90. | Planes refit to the new axis and picked bodies (D614). `test_a_new_axis_fits_the_trim_planes_to_the_body`, `test_picking_a_body_moves_the_triad_to_it` |
| R10c.4 | Wrong geometry | A Bend tighter than the body folded through itself with only a warning; Flow round a tight arc did the same and showed OK. | 10 mm bar, Bend radius 4; or Flow round a 2 mm arc. | Both are now errors with a next step (D615). `test_a_bend_tighter_than_the_body_is_an_error`, `test_flow_round_a_bend_tighter_than_the_body_is_an_error` |
| R10c.5 | Wrong geometry | Inch parts read the deform defaults as inches: tolerance 0.254 mm, stretch 254 mm, bend radius 50 in. | New inch part, Stretch. | Inch defaults (D614). `test_inch_parts_get_inch_defaults` |
| R10c.6 | Wrong geometry risk | Split kept its numbered list after the tools or bodies changed, so the kept numbers could pick the wrong bodies. | Split, Cut, change a tool, OK. | List and ticks cleared, Press Cut hint shown (D612). `test_split_cut_button_lists_the_pieces` |
| R10c.7 | Wrong geometry | OBJ with CRLF or CR line endings imported with "no triangles"; binary STL with padding was refused; bad numbers showed a kernel error; NaN corners left silent holes. | Import an OBJ saved on Windows. | Mesh reader fixed (D616). `tests/core/io/test_mesh_import.py` |
| R10c.8 | Value lost | STEP from File, Export dropped the cosmetic thread notes. | tapped_housing sample, Export STEP. | Notes written on both paths (D617). `test_step_keeps_thread_notes_with_or_without_colour` |
| R10c.9 | Value lost | Save Bodies with a body named CON, NUL, AUX, PRN, COMn or LPTn gave a name Windows cannot write. | Rename a body AUX, Save Bodies. | "_" added after the name (D613). `test_windows_device_names_are_not_used` |
| R10c.10 | Value lost | Export with a typed name and no suffix wrote a file with no suffix; Save As cut "v1.2 plate" to "v1.fdprt". | Export STL as `plate`. | Known suffixes replaced, others kept (D613). `test_export_adds_the_suffix_to_a_typed_name`, `test_save_as_keeps_a_dot_in_the_name` |
| R10c.11 | Value lost | Appearance, the section panel and Measure kept working on the part the user switched away from. | Open Appearance in part A, show part B, pick a swatch: part A changes. | Tools follow the shown part (D618). `tests/ui/test_view_tools_tab_change.py` |
| R10c.12 | Value lost | Print Estimate kept the old part's volume after a tab switch; a part still building never got one. | Open Print Estimate, switch parts. | Refreshes on tab change (D618). `test_estimate_follows_the_shown_part` |
| R10c.13 | Wrong value | Copy Appearance of a face with no colour of its own copied the part colour, not its body colour. | multibody_split_part, colour Body 2, Copy Appearance on its face. | Takes the drawn colour (D619). `test_copy_appearance_of_a_face_takes_its_body_colour` |
| R10c.14 | Wrong value | Measure perimeter counted a cylinder's seam twice and gave a sphere a perimeter. | Measure a cylinder side face. | Seams left out (D619). `test_perimeter_leaves_out_the_seam_of_a_round_face` |
| R10c.15 | UI | Intersect's region list never filled, so regions could not be excluded. | Two overlapping bodies, Intersect, pick both. | List fills on a worker thread (D612). `test_intersect_lists_regions_to_exclude` |
| R10c.16 | UI | Appearance over the section panel removed it while the section ran: arrow left, OK and Cancel gone. Same the other way round. | Section View, then Appearance, then close Appearance. | One side panel at a time (D618). `test_appearance_over_the_section_panel_closes_it_as_ok` |
| R10c.17 | UI | Isolating a hidden body gave an empty view while the status bar said it was isolating. | Select a face, H, then I. | Hidden bodies left out, clear message (D619). `test_isolate_leaves_out_hidden_bodies_and_one_body_message` |
| R10c.18 | UI | A closed part's section could come back on a new part (state keyed by a reused object id). | Section a part, close it, open a new part. | State forgotten on close (D618). `test_closing_a_part_forgets_its_section` |
| R10c.19 | UI | A new section was centred on every body, including hidden ones. | Hide a body, Section View. | Uses the shown bodies (D618). `test_new_section_cuts_through_the_shown_bodies` |
| R10c.20 | UI | Transform Handles from a body row used the body of a face still selected in the view; seeded body picks showed face names such as `f8/side/e5`. | Select a face of Body 1, right click Body 2, Transform Handles. | Row body wins, picks labelled by body (D612). `test_body_row_command_uses_that_body` |
| R10c.21 | UI | Another face of a picked body listed it twice. | Body tool, click two faces of Body 1. | Same body toggles (D612). `test_another_face_of_a_picked_body_toggles_it` |
| R10c.22 | UI | Colours in use and the tree's Appearances row showed internal face names. | Colour a face. | Listed by feature with a count (D619). `test_colours_in_use_name_faces_by_their_feature` |
| R10c.23 | UI | Each change of units, decimals or Show dX dY dZ added a repeat to the Measure history. | Measure, change units twice. | Options only redraw (D619). `test_units_and_decimals_do_not_add_history` |
| R10c.24 | Wrong message | Intersect on bodies that do not overlap said to include a region in an empty list; Combine Subtract with no main body said "pick a body". | Intersect two separate blocks. | Messages name what is missing. `test_messages_name_what_is_missing` |
| R10c.25 | Wrong message | Export of a part with only a reference mesh said the part was empty. | Open an STL, File, Export. | Says to tick Convert to Solid. `test_export_of_a_reference_mesh_says_to_convert_it` |
| R10c.26 | Wrong message | Section drag arrow label in bare millimetres in an inch part. | Inch part, Section View. | Label uses part units (D618). `test_drag_arrow_label_uses_the_part_units` |
| R10c.27 | Wrong message | Show All with one hidden body said "Showing 1 hidden bodies". | Hide one body, Show All. | "Showing the hidden body." `test_isolate_leaves_out_hidden_bodies_and_one_body_message` |

### Checked and not a bug

| What was tried | Why it stays |
|---|---|
| Export, reimport and volume for STEP, STL and 3MF on 8 samples, unicode and spaces in paths, INCH and M STEP files. | All within 0.05 percent; units read correctly. |
| Exports and Print Estimate include hidden bodies. | By design (D410). |
| A part with a failed feature exports the last good body. | No spec says otherwise; the error stays in the tree. |
| Save Bodies replaces a file of the same name. | Documented in D528. |
| Combine Subtract with tools that do not overlap removes the tool bodies. | Normal subtract behaviour. |
| Fill with Tangent on a box top loses about 2 mm3. | The new face must meet vertical walls smoothly. |
| Delete and Patch on a plain box face fails. | The neighbours cannot grow to close it; the message says so. |
| Colours carry across configurations. | D254 stores colours per part. |
| The section drag arrow points along the reference normal, not the rotated plane normal. | Offset moves the plane along the reference normal, so the arrow matches. |
| Twist of 3600 degrees seems to lose 7 percent of its volume. | The geometry is within the reported deviation; the volume figure is imprecise (open item below). |

### Open

| Id | What | Repro | Why not fixed |
|---|---|---|---|
| R10c.O1 | `volume_of` uses the kernel's default volume precision, which is imprecise on deformed spline bodies. Print Estimate shows it. | Twist a 10 x 10 x 100 mm bar 3600 degrees: 9268 mm3 against about 9850. | A tighter precision changes golden results and speed budgets across the app; needs measuring first (CLAUDE.md 5A.4). |
| R10c.O2 | Other body tool forms (Move Face distance, pattern spacing, Move and Copy Body) copy millimetre default text in inch parts. | Inch part, Move Face. | A general fix converts length defaults in `flow.new_feature`; outside this round's small fixes. Fixed 2026-11-18 (D2645): length defaults become round inch values. |
| R10c.O3 | Delete Face "Keep the faces that worked" still diagnoses on the whole multibody part. | Overlapping bodies, Delete Face that fails on one face. | No failing case found to test. |
| R10c.O4 | Editing a saved Combine or Delete Body labels a consumed body by its face name. | Edit Combine 1. | Labels read the final part; geometry is not affected. |
| R10c.O5 | No way to edit a section after OK: the command toggles it off. | Section View, OK, Section View. | Needs a product decision (for example Edit Section); scope is frozen. Recorded in IDEAS.md. |
| R10c.O6 | Copy or Paste Appearance with only edges or vertices selected uses the part. | Select an edge, Paste Appearance: the whole part changes. | D254 says the part is the target with no face; needs a decision. |
| R10c.O7 | Copy Appearance on a feature with no colour returns the part colour even when its body is coloured. | Colour Body 2, Copy Appearance on a feature in it. | A feature can span several bodies. |
| R10c.O8 | Section references are fixed copies: a moved reference plane leaves the section in place until it is turned off and on. | Section on Plane 1, change Plane 1's offset. | Behaviour change; recorded for later. Now IDEAS.md item 79 (2026-11-18). |
| R10c.O9 | 3MF files whose build items use components give "has no triangles to import". | Import a 3MF from a slicer that uses components. | Missing reader feature, not a bug; recorded in IDEAS.md. Fixed later (D715): components are read. |
| R10c.O10 | The slow sweep fails only on Preferences OK, on every sample in this area, and the step grows slower with each sample run in the same process: 73 s (flowed_strap), 170 s (imported_mesh_with_cut), 280 s (imported_step_with_features), 420 s (multibody_split_part), against a 30 s limit. Every other step of the six samples passes (about 14,500 steps), and the right click sweep passes on all six. The growth suggests the theme restyle cost rises with widgets left from earlier windows or panels. | `--run-slow tests/ui/test_app_sweep.py -k "every_command and (flowed_strap or imported_mesh_with_cut)"` | Fails the same way before this round; Preferences and themes are outside this area. Worth checking whether a long real session slows Preferences OK in the same way. Fixed later (D599, D637): closed dialogs are freed. |

## Round 10d

Bug hunt before v1.0 in sheet metal, the 3D Print tab, configurations, equations and variables, the node editor and curves. Driven with throwaway offscreen scripts on the samples and on parts built for the hunt (shelled box cut in two at mid height, two separate bodies), including edit after OK, undo and redo, save and reopen.

Suite at the start: ruff, ruff format and mypy clean; pytest 3,146 passed, 1 failed, 75 skipped. The failure, `test_edges_pick_within_a_few_pixels`, needs an X display for the 3D view and passes under `xvfb-run` (see Checked and not a bug).

### Found and fixed

| Id | Severity | What failed | Short repro | Fix and regression test |
|---|---|---|---|---|
| R10d.1 | Wrong result | A boss on one piece after Split or Split for Print joined the pieces back into one body. | Plate, Split for Print in two, Extrude a boss on one half: one body. | A boss fuses only with the bodies it meets (D620). `test_boss_on_one_piece_keeps_the_pieces_apart` |
| R10d.2 | Wrong message | After Split or Split for Print every later solid feature warned that bodies touch only along an edge (known issue). | Split a plate, then any cut across the seam. | Edges and corners where bodies meet face to face are not flagged; a true edge contact still is (D620). `test_cut_across_the_seam_does_not_warn`, `test_edge_contact_on_a_piece_still_warns` |
| R10d.3 | Missing option | Split for Print cut every body its planes crossed; it had no body picker (known issue). | Two bodies, Split for Print: both are cut. | Bodies to Cut group and `refs.bodies`; each body is cut on its own (D621). `test_split_for_print_cuts_only_the_picked_body`, `test_split_panel_picks_bodies_to_cut` |
| R10d.4 | Wrong message | Clicking an edge in the Split for Print panel said "Pick faces for the projection." | Split for Print, At Planes, click an edge. | Own message naming both uses of a face click (D621). `test_split_panel_picks_bodies_to_cut` |
| R10d.5 | Wrong result | Lip and Groove on the cut rim of a split enclosure failed with "produced invalid geometry". The grown rim outline was inside out, and the lip joined the two pieces. | Shell a box, Split for Print at mid height, Lip and Groove with the cut face as lip and groove rim. | Inside out outline rebuilt; lip on one piece, groove in the other, each only in its own body (D622). `test_lip_and_groove_on_the_cut_rim_of_a_split_enclosure` |
| R10d.6 | Wrong result | A tall Snap Hook or Mounting Boss next to the wall of a split enclosure joined the two pieces into one body without a warning. | Split enclosure, Snap Hook at the wall, body height 30. | Both join only the body they stand on (D622). `test_snap_hook_and_boss_against_the_wall_stay_in_their_piece` |
| R10d.7 | Wrong message | The build volume check measured the whole part after Split for Print, said it does not fit and told the user to use Split for Printing. | Open `split_with_pins`, Build Volume. | Each body is measured; the message counts bodies (D622). `test_each_body_is_checked_on_its_own`, `test_build_volume_message_counts_bodies` |
| R10d.8 | Wrong result | Lay Face Flat started with nothing selected kept waiting, so a face picked later for Fillet or any panel also set the print orientation and added an undo step. | Lay Face Flat with no selection, then Fillet and click a face. | The wait ends when a panel or sketch is open or the tab changes. `test_a_pick_for_another_tool_does_not_lay_a_face_flat` |
| R10d.9 | Wrong result | Snap Groove moved the cut body to the front of the part, so body colours and hidden bodies (stored by body number) moved to another body. | Split enclosure with a colour on body 2, Snap Groove into body 2. | Bodies keep their order. `test_snap_groove_keeps_the_body_order` |
| R10d.10 | Kernel failure | Snap Groove with Gap Height 0 failed in the geometry kernel. | Snap Groove, Gap Height 0. | Repeated outline corners are dropped. `test_snap_groove_with_no_gap_above_the_head` |
| R10d.11 | Wrong result | Snap Groove with a face of the hook's own body picked cut the hook's head off without a message. The code comment said the hook's body is never cut. | Enclosure sample (one body), Snap Groove with the top rim face picked. | Refused with "the picked body holds the snap hook ... Pick a face of the body the hook catches in, or split the part first." `test_snap_groove_refuses_the_hook_body` |
| R10d.12 | Slow, memory | Every Preferences open left the hidden dialog (about 285 widgets) alive under the main window, so each OK restyled more widgets. The slow app sweep failed on "Preferences, OK took 70 s" after a few thousand steps. | Open Preferences and press OK ten times: each OK is slower. | The dialog is deleted once closed. `test_closed_dialog_is_deleted` |
| R10d.13 | Blocked edit | The Variables tab refused every edit ("Unknown name") once one variable used a feature value, and every edit dropped all variable comments. | Variable `="depth@Extrude 1" * 2`, then change another variable in the Variables tab. | The tab solves with the whole part and keeps comments (D626). `test_edits_keep_comments_and_feature_value_formulas` |
| R10d.14 | Data loss | Renaming or deleting a variable lost or orphaned its values in other configurations; the panel still counted them and re-adding the old name brought them back. | Configure Width per configuration, rename Width to W. | Overrides and the design table column follow the rename, or are dropped on delete, in the same undo step (D626). `test_renamed_and_removed_variables_take_their_configured_values`, `test_renamed_or_deleted_variable_keeps_or_drops_its_configured_values`, `test_follow_variables_moves_swaps_and_drops_overrides_and_columns` |
| R10d.15 | Data loss | Renaming a row in the design table deleted the configuration and added a new one at the end with the active configuration's values (suppression lost, order changed); swapping two names did nothing. | Design table, rename a row. | Rows are renamed in place, through temporary names so swaps work (D626). `test_renaming_a_row_renames_its_configuration` |
| R10d.16 | Wrong result | Node inputs typed as formulas never followed variable changes, even after reopening. | Sphere radius `=R * 2`, change R. | Unwired formula inputs are worked out again with the current variables; the variables are part of the node's result key (D627). `test_input_formulas_follow_the_variables` |
| R10d.17 | Dead command | A pasted Add as Feature node got no graph body; deleting one left its graph body with an error whose advice could not work. | Node editor, copy and paste an Add as Feature node, or delete it. | Paste adds and delete removes the graph body, each in one undo step (D627). `test_pasted_and_deleted_add_as_feature_nodes_bring_and_take_their_bodies` |
| R10d.18 | Cut off | The node editor's search and settings column opened 76 px wide. | Open the node editor, select a node. | At least 230 logical pixels (D627). `test_settings_of_every_node_fit_without_cutting` |
| R10d.19 | Wrong result | Equations manager OK applied a variable name such as "My Var" that no formula can use. | Equations, add "My Var", OK. | OK refuses names that break the variable name rule (D626). `test_ok_refuses_a_variable_name_no_formula_can_use` |
| R10d.20 | Wrong message | Design table CSV files from decimal comma spreadsheets (semicolon or tab separated) were refused with "add a header row". | Import a semicolon separated CSV. | The separator is read from the header row (D627). `test_csv_with_semicolons_or_tabs_from_decimal_comma_spreadsheets` |
| R10d.21 | File content | Values of a deleted feature stayed in the saved configurations, forced schema 2 and the count was wrong. | Configure a feature value, delete the feature, save. | Left out of the file and the count; kept in memory for undo (D626). `test_values_of_a_deleted_feature_are_left_out_of_the_file` |
| R10d.22 | Confusing | After deleting Graph Body 1 the next Add as Feature node was named Graph Body 2 again, next to an existing Graph Body 2. | Two graph bodies, delete the first, add another. | Next free number (D627). `test_graph_body_names_stay_unique_after_a_delete` |
| R10d.23 | Wrong message | Graph errors showed ids and type names ("in node n2 (add_as_feature)"); a failed CSV export showed a raw OSError; the configurations rename message stayed after the old name was typed back. | Break a graph node; export a design table to a missing folder. | Nodes named by title, own export message, message cleared (D627). `test_graph_body_reports_graph_errors`, `test_export_to_a_missing_folder_says_what_to_do`, `test_in_place_rename_messages_clear_when_the_name_is_put_back` |
| R10d.24 | Wrong geometry | Array Along Curve copies that overlap each other gave wrong volumes and body counts (4 mm block, spacing 1: 3 bodies of 208 mm3 instead of 1 body of 112 mm3); a plate arrayed round its own contour added nothing. | Block 4 x 4 x 4, line path, spacing 1, count 4. | Each copy is its own kernel tool (D628). `test_overlapping_copies_fuse_into_one_body`, `test_copies_of_the_whole_part_along_its_own_contour` |
| R10d.25 | Failure | Contour and Projected Curve with a reference axis as the direction said "the direction pick was lost", although PHASE3_SPEC P3.6 allows an axis. | Contour Curves, direction a reference axis. | Axis direction and origin used (D629). `test_contour_along_a_reference_axis`, `test_contour_direction_that_is_not_a_plane_or_axis` |
| R10d.26 | Missing option | The Projected Curve panel could not take a plane or axis direction; the Contour list offered only the default planes, including planes below it in the tree; contours were missing from the sweep path and composite item lists. | Open the panels. | Shared direction list of planes and axes above the feature; contours offered as paths and items (D629). `test_direction_lists_offer_axes_and_only_earlier_planes`, `test_contour_curves_are_offered_as_paths_and_items` |
| R10d.27 | Missing message | Array Along Curve ignored skip numbers that change nothing (1, above the count, every copy); Projected Curve and array body picks dropped the "found by its position" warning; a solid feature as a path said "not a sketch". | Instances to skip "1". | Warnings with a next step; warning passed on; "not a sketch or a curve" (D628). `test_skip_numbers_that_do_nothing_are_reported`, `test_projected_face_found_by_position_warns` |
| R10d.28 | Cut off | The Contour Curves panel was wider than the dock (the empty list prompt was 330 px), and curve panel lists showed wrong prompts ("Choose a sketch with one circle" in Projected Curve). | Open Contour Curves. | Short prompt; each list says what it takes (D629). `test_contour_panel`, `test_empty_lists_prompt_for_what_they_hold` |
| R10d.29 | Wrong message | Flat Pattern warned when a plain cut, hole or fillet on a flat wall came after the last sheet metal feature (known issue). Planes, axes, points and sketches gave no warning in any test; a regression test locks that in. | Base Flange, Edge Flange, Extruded Cut through a wall, Flat Pattern. | Material removed since the last sheet feature is cut from each wall in its own frame and kept only when the folded volume matches the part; added material and cuts across bends still block, with a next step (D623). `tests/core/features/sheetmetal/test_flat_blockers.py`, `test_a_fillet_on_a_wall_edge_flattens` |
| R10d.30 | Dead command | Base Flange, Convert to Sheet Metal or Insert Bends on a part that is already sheet metal opened a panel and added a feature that always fails. | Sheet metal sample, Base Flange. | Refused with a status message and a next step (D625). `test_a_second_sheet_start_is_refused_with_a_next_step` |
| R10d.31 | Value lost | Unticking a flag that starts ticked (Show bend lines, Show bounding box, Trim side bends, also Merge, Uniform, Equal spacing in other shared forms) did not stick after OK or reopen. | Flat Pattern, untick Show bend lines, OK, reopen. | The flag stores false (D624). `test_unticked_flat_pattern_options_stay_off_after_ok_and_reopen` |
| R10d.32 | Wrong result | A saved feature with no value for a flag showed the new feature default, so OK changed the part (an Edge Flange saved without Trim opened with Trim ticked). | Open `folder_options.fdef`, edit the Edge Flange. | A saved feature shows the type's own default (D624). `test_a_saved_flange_without_trim_shows_it_unticked` |
| R10d.33 | Data loss | OK on a saved Edge Flange without changes dropped its own relief and own bend values; the volume changed. | `folder_options.fdef`, edit Edge Flange, OK. | The group tick starts on when the feature has values for its fields (D624). `test_own_relief_values_survive_ok_without_the_panel_tick` |
| R10d.34 | Wrong message | Flatten did nothing when the Flat Pattern was suppressed or rolled back, but still wrote an undo step. | Suppress Flat Pattern, Flatten. | Says why, leaves the part alone (D625). `test_flatten_says_why_when_the_flat_pattern_is_not_built` |
| R10d.35 | Wrong geometry | In a part in inches a new Sheet Metal folder and loaded gauges typed bare numbers, read as inches: a 25.4 mm sheet. | New part in inches, Base Flange. | Values typed with " mm" (D625). `test_sheet_values_stay_in_mm_in_a_part_in_inches` |
| R10d.36 | Wrong geometry | Edge Flange (and Hem) left a 0.25 mm3 loose cube at a corner between two trimmed side bends with a gap wider than the relief, as a second body with no warning. | 1 mm sheet, 1 mm radius, 1 mm gap. | The enclosed square is cleared (D625). `test_corner_reliefs_leave_no_loose_piece` |
| R10d.37 | Wrong message | Features below a failed Base Flange said "Add a Base Flange first". | Break the Base Flange. | Names the failed feature and says to fix it. `test_a_failed_base_flange_is_named_by_the_features_after_it` |
| R10d.38 | Cut off | Found in the final full run after the merge: with a theme stylesheet applied, the Arc node's settings needed 234 px in the 230 px settings column of R10d.18. | Dark Grey theme, node editor, add an Arc node. | The column grows to fit the selected node's settings once they are styled. `test_settings_fit_with_a_theme_stylesheet` |

### Checked and not a bug

| What was seen | Why it stays |
|---|---|
| `test_edges_pick_within_a_few_pixels` fails in the cloud container. | The 3D view needs an X display on Linux; it passes under `xvfb-run`. CI runs on Mac and Windows. |
| Lay Face Flat and the status bar right after selecting a face showed the selection text, not "orientation set". | Timing of the throwaway script: the selection's area measurement finished after the command. On screen the measurement is done before the click. |
| Configurations: switching, adding and copying on `configured_bolt_family` with undo, redo, save and reopen; design table bad cells; unit mixes and cycles in equations; Expression node bad formulas (parser only); graph samples round trip. | Behaved correctly with clear messages. |
| Curves: save and reopen of contour, projected, composite and array; undo, redo and edit after OK; a contour with tiny spacing hits the 500 section limit. | Behaved correctly. |
| Sheet metal: OK on an empty panel adds a feature with an error; no text cut off at 1280 by 800; Flatten undo and redo, flat DXF with a hole, every fixture saved and reopened. | App wide convention (round 9s) or correct. |
| Vent with a circle boundary and two ribs; Snap Groove into the other piece of a split enclosure; every print check command with nothing, a face or a body selected on three samples. | Volumes and messages correct. |

### Open

| Id | What | Why it is left |
|---|---|---|
| R10d.O1 | Closed Corner (and Tab and Slot in `rip_tab_cross.fdef`) lose their face reference when the folder thickness goes from 2 to 3 mm: the picked end face carries a relief face name after coplanar faces merge. | Topological naming work (CLAUDE.md 1A, Opus task). |
| R10d.O2 | Miter Flange errors after a thickness change when its profile sketch is not attached to the edge. | Expected for an unattached sketch. |
| R10d.O3 | Lip and Groove on a rim two pieces share puts the lip on the piece the stored face faces out of; there is no control to swap. Lay Face Flat turns all bodies together, so the overhang check of a split part looks at the pieces as modelled. | New controls (IDEAS.md item 6). |
| R10d.O4 | Renaming a variable does not rewrite formulas that use it; they show "Unknown variable". Ticking no configurations in Chosen Configurations silently undoes the edit. Expression node errors repeat "Fix the formula." | New behaviour (IDEAS.md item 7) or cosmetic. |
| R10d.O5 | Linear and circular patterns send their copies as one compound tool, so copies that overlap each other may fuse wrongly as Array Along Curve did (R10d.24). A Pipe along a closed projected loop with sharp 3D corners fails with "intersects itself" (mitred corners, D292). | Outside this round's area; not checked. |
| R10d.O6 | The About dialog is created with the main window as parent and never deleted, like Preferences was (R10d.12). | Small and rarely opened. Fixed later (D637): About is freed after it closes. |
| R10d.O7 | Slow tests not finished in the cloud container: the full slow app sweep for the sheet metal samples and the per sample perf budgets for them (stopped at the 30 minute limit on the shared machine). | Run on CI or a free machine. |

## Round 10e

Area: robustness and speed across the whole app (cloud session, 2026-10-31). The real main window was driven on the Qt offscreen platform with empty data and cache folders, with throwaway scripts for timing, memory, responsiveness, layout and damaged files. Ids start with E so they do not clash with the other round 10 sessions.

Baseline before any change: ruff, ruff format and mypy clean; `pytest -q` gave 3146 passed, 75 skipped and 1 failed (E1).

At the end: ruff, ruff format and mypy clean; `pytest -q` gave 3172 passed, 76 skipped, 0 failed. Slow tests (`--run-slow`) on a 4 core cloud runner, one test at a time: the 25 naming stress tests and the 25 command sweeps passed after E16 was fixed; the 25 right click sweeps passed on the final code after E17 was fixed. The slow set takes about 3 hours here when run in one process.

### Found and fixed

| Id | Severity | What failed | Short repro | Fix and regression test |
|---|---|---|---|---|
| E2 | Freeze | The window froze for 1.2 s to 3.3 s while a large part opened or rebuilt. The kernel keeps Python's GIL during each kernel call, so every Qt call the UI made from Python waited for the next boolean to end; the first paint of the new tab made hundreds of them. | Open `samples/generated_200.fdprt` and move the mouse over the command tabs. | The UI thread beats while a rebuild runs and the rebuild pauses between features when the UI has not had a turn (D631). Worst gap now about 0.2 s. `tests/perf/test_ui_responsive.py` |
| E3 | Data kept in memory | Every rebuild, feature preview, region pick, sketch outline, measure and body tool job stayed in memory with its document copy and the shapes it was given, until FDCAD quit: about 0.5 MB per rebuild of the 200 feature part. | Edit a value 30 times; memory grows each time. | Jobs start through `fdcad/ui/background.start_job`, so Python frees them (D633). `tests/ui/test_memory_release.py` |
| E4 | Data kept in memory | Closing a part kept its session, undo history, last rebuild with every shape and the closed tab: about 8 MB per open and close of the 200 feature part. | Open and close `generated_200.fdprt` ten times. | `DocumentSession.close()` frees them; `close_tab` calls it (D633). `tests/ui/test_memory_release.py` |
| E5 | Layout | The main window could not be narrower than 1330 px, wider than a 1280 px screen (a 1920 px laptop at 150 percent): the right side, with the command search, was off screen. | Make the window narrow. | Command tabs scroll sideways with a thin bar or the mouse wheel; smallest width is about 490 px (D632). `test_window_fits_a_small_screen_and_tabs_scroll` |
| E6 | Layout | Compact buttons fixed their width before the style sheet padding was known, so a narrow window cut "Swept Boss" to "Sw...ss". | Features tab in a 1280 px window. | The minimum width is measured each time (D632). `test_compact_labels_are_never_cut` |
| E7 | Look | Only Features, Sketch and Evaluate had the panel colour; on Bodies, 3D Print, Sheet Metal and Graph the selected tab did not join its panel. | Dark theme, click Bodies. | Every tab panel carries one style property (D632). `test_every_tab_has_the_panel_colour` |
| E8 | Layout | The first window was always 1400 x 900, partly off a 1280 x 720 screen. | Start FDCAD on a small laptop screen. | The first size fits the available screen (D635). `test_first_window_fits_a_small_screen` |
| E9 | Wrong message | A part file with a damaged value in a configuration raised a raw `TypeError`: no message. | Set a configuration's `suppressed` to `1.5` and open the file. | Any type error while reading becomes "The file is damaged ..." with the next step (D634). `tests/core/io/test_damaged_values.py` |
| E10 | Wrong state | A damaged sketch dimension value raised after the tab was added, so the part never rebuilt and no message showed. | Set a sketch dimension's value to an object and open the file. | The value is skipped (the sketch reports it) and the quick value refresh can no longer stop the rebuild (D634). `test_a_damaged_value_never_stops_the_rebuild`, `test_sketch_dimension_value_of_the_wrong_type` |
| E11 | Crash in the tree | `appearance`, `print_setup` or `embedded` that is not an object loaded, then broke the feature tree. | Set `appearance` to a string and open the file. | Reading rejects it as damaged (D634). `test_top_block_that_is_not_an_object` |
| E12 | Missing files | The node editor guide and the attractor plate tutorial open samples from the `graphs` folder, which the installed app did not have. | Installed app: File, Open, samples folder. | The spec ships `samples/graphs`, and the bundle check reports it missing (D636). `test_spec_ships_the_graph_samples_the_guide_opens`, `test_missing_graph_samples_are_reported` |
| E13 | Freeze | Closed dialogs (Preferences, New Part, About, Shortcuts, Text, insert table, configuration chooser, two question boxes) stayed alive. Preferences OK restyles every widget, so after a long session it took 70 s; the slow sweep failed on it. | Open and OK Preferences many times; each OK is slower. | Each dialog is deleted after use (D637). `test_closed_preferences_dialogs_are_freed` |
| E14 | Data kept in memory | Each opening of the Equations manager, Design Table, shortcut bar, view selector or snap popup made a new one and kept the old ones (156 widgets left after an 828 step sweep). | Press Q several times, or open Equations several times. | At most one of each stays (D637). `test_reopened_popups_and_managers_do_not_pile_up` |
| E15 | Slow | Preferences OK restyled the whole app twice even when the theme did not change. | Open Preferences, press OK. | Restyles only when the theme changed (D638). `test_preferences_ok_restyles_only_when_the_theme_changed` |
| E16 | Test failure | The slow sweep failed: Preferences OK took 70 s. The sweep never ran `deleteLater()`, so about 25,000 closed widgets piled up; the app's event loop does run them. | `pytest --run-slow "tests/ui/test_app_sweep.py::test_every_command_on_every_sample[bracket]"` | The sweep's `pump()` sends deferred deletes like the event loop (D638). |
| E17 | Crash | Segmentation fault in the slow right click sweep: Python's cyclic garbage collector ran inside the background rebuild thread and destroyed Qt objects there while the UI thread deleted widgets. | `pytest --run-slow -m slow tests/ui/test_app_sweep.py` (about 60 tests in). | Collection runs only on the UI thread from a timer (D639). `tests/ui/test_gc_guard.py` |
| E1 | Test failure | `test_edges_pick_within_a_few_pixels` built the real kernel viewport and failed on Linux with no X display. | `pytest tests/ui/test_drag_handles.py` in a cloud container. | Skips when the kernel cannot open a display connection; Windows and macOS still run it (D630). |

After E9 to E11 were fixed, 770 damaged files made from six samples (one value changed or removed at a time) opened in the window with no uncaught error.

### Checked and not a bug

| What was checked | Result |
|---|---|
| Full rebuild of `generated_200.fdprt` | About 2.0 s on the cloud runner (budget 2 s, test margin 3 s). 72 percent is the kernel boolean of each hole cut (`op.Build()` with fuzzy tolerance); no Python hot spot. Speeding it up would change geometry code, so it stays. |
| Full rebuild of `showcase/everything_part.fdprt` | About 1.2 s; slowest feature 0.32 s. Within budget. |
| Kernel work on the UI thread during long rebuilds | Every OCP call made on the UI thread while both large parts opened was logged: only one (turning on the kernel's parallel mode). |
| Every command in `src/fdcad/ui/input/commands.py` | Each has an action, a tooltip that starts with its name and a user guide mention. Five keyboard only commands (scroll tree to top and bottom, next and previous command tab, move confirmation corner) have no icon on purpose (`NO_ICON` in `tests/ui/test_icons.py`). |
| Every preference page in all four themes | Renders without cut text. The Printing page's density table shows two rows at the default dialog size and scrolls; the dialog can be made taller. |
| Every theme | Contrast is covered by `tests/ui/test_theme_contrast.py`; screenshots of every tab and preference page showed no unreadable text or icons. |
| Command tab groups and dropdowns | Balanced on every tab at 1920 px. Dropdown arrows of compact buttons sit at the right edge of their column, the same on every tab. |
| Windows installer `packaging/windows/fdcad.iss` | Registers `.fdprt` and `.fdef` to `FDCAD.Part` with icon, open command, `OpenWithProgids` and uninstall cleanup. |
| Mac bundle settings in `packaging/fdcad.spec` | Document type and exported type `org.fdcad.part` cover both `fdprt` and `fdef`; file open events reach the window (`_FileOpenFilter`). |
| Opening a part with a valid cache | Covered by budget 2; passes. |

### Open

| Id | What | Why it stays open |
|---|---|---|
| O3 | One long kernel call (a single boolean of 0.3 s, as in the showcase part) still holds the GIL for its whole length, so the window can pause that long. | The kernel bindings do not release the GIL; fixing it would need a separate process for rebuilds, which is outside the plan. Fixed later (D2600): long rebuilds run in a helper process. |

## Merge of rounds 10a to 10f (manager, 2026-10-31)

- R10b.W1 (open): on Windows a modelled thread that runs the whole length of a plain shaft is cut only partly by the kernel (about 160 mm3 of an expected 300 to 600). The D607 check catches it and the feature shows the clear thread error instead of a wrong shape. The test is marked as an expected failure on Windows only. It passes on Linux.
- Fixed: the D607 check rejected the turned shaft's correct thread on Windows, where the kernel's overlap of the helix comes back empty. It now checks only the removed volume in that case.
