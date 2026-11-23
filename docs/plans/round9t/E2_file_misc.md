# Round 9t group E2: file options and misc (D527, D528)

Status: built. This note matches the code on the E2 branch.

## a. DECISIONS entries

D527: Keep separate body in the file, and formulas follow a feature rename (IDEAS.md items 1 and 3, approved in D438; changes D76 and D390 item 7). (1) The optional common feature key `keep_separate_body: true` (FDEF_SPEC 5.1 item 9, section 15 item 6) records that the user kept the separate body a feature made. It is written only when true, so it is an optional addition to schema 1: older files open and save byte for byte the same, and older readers keep it as an unknown key (FDEF_SPEC 14 item 4). Fixture `tests/fixtures/schema1/keep_separate_body.fdef` covers it. (2) The fix button "Keep separate body" in the Errors tab now sets the key with one undoable command (`SetKeepSeparateBody`, undo text "Keep Separate Body: <feature>") instead of hiding the warning for the session only. While the key is set the rebuild drops that feature's `separate_body` warning (after the cache, in the rebuild engine), so the Errors tab and the feature tree no longer show it in warning colour. The key is left out of the rebuild cache key, so setting or clearing it rebuilds no feature. (3) The feature's right click menu shows "Warn About Separate Bodies" while the key is set; it clears the key with one undoable command and the warning comes back. (4) Renaming a feature or sketch (tree rename, one undoable `RenameFeature`) also rewrites every formula that names it: quoted names `"<value>@<old name>"` become `"<value>@<new name>"` in feature values, sketch dimensions, global variables, suppression formulas, configuration overrides, design table cells and graph node formulas (value parameters and the Formula node's `formula` setting). Only whole names match: the text after the last `@`, without surrounding spaces, must equal the old name exactly, so renaming "Extrude 1" never touches "Extrude 10", and the id form `"depth@f6"` is left alone. The parser has no unquoted form for these names (`@` and spaces are not name characters), so only quoted names are rewritten; plain values (no `=`) are never touched. Comments are keyed by the value name without the feature name, so they need no change. (5) A formula the tokenizer cannot read (for example a missing closing quote) is left as typed; a new name holding a double quote cannot be quoted, so formulas are then left as typed. (6) The rewrite is pure Python in `core/equations/rename.py` (`rename_rewrite` returns edited copies; the part is not changed). The command stores the old and new copies of only what changed, so undo restores the old name and every rewritten formula, and redo puts them back.
Status: Default
Reason: The owner approved both ideas (D438); an optional key keeps old files unchanged, and rewriting quoted names only touches exact matches.

D528: Split saves bodies to separate files, and Wrap gets the Spline surface method (PHASE3_SPEC P3.4 item 3, PHASE4_SPEC P4.7 item 2). (1) Split: after Cut, each row of the body list can be renamed with a double click; the row text is the file name. A row left as "Body k" saves as "<part> body k" (the part's file name, or "Part" before it is saved). Below the list a format box (FDCAD Part, STEP, STL, 3MF) and a "Save Bodies" button (enabled after Cut) write each ticked body to its own file in a folder the user picks. FDCAD Part writes a new `.fdef` part whose only feature is an Imported STEP body (D290) holding that body, so it opens and can be edited directly; STEP, STL and 3MF use the export writers with default mesh settings. Characters not allowed in file names become `_`, names used twice get " 2", " 3", and files of the same name are replaced. The pieces are made again and written on a worker thread (`core/io/save_bodies.py`); the part is not changed, no undo step is added and nothing is stored in the file (renaming a row does not change the feature either). The result shows under the buttons: "Saved 2 files to <folder>." or the error, which names the body that failed. (2) Wrap: optional key `method: "spline"` (default `"analytical"`, not written; FDEF_SPEC 5.3.31 item 4). The Spline surface method works on any single face and the sketch plane need not touch it: the sketch origin is projected onto the nearest point of the face (on its boundary when that is nearest) to get (u0, v0); the sketch's x and y directions are turned into the face's tangent plane there (lengths kept, the side that keeps the sketch readable) and written in the tangent directions dS/du and dS/dv (least squares). That gives one fixed affine map from sketch coordinates to face parameters, so lengths along the face match the sketch near that point and follow the face's parameters further away; it is exact on flat faces and cylinders. Each sketch curve is made a B-spline in the sketch plane and its poles are moved by the map (exact, also for rational splines), giving curves on the face; holes are kept. Emboss and deboss make the wrapped faces thick along the face normal: a prism on flat faces, the kernel's simple thicken on curved faces with the side picked from where the result's centre lies against the face's outward normal. Scribe splits the faces as before. Reverse is hidden and not used with this method. (3) Messages: a sketch that leaves the face (checked at 24 points along each curve, with periodic faces taken round) or would wrap all the way round a closed face: "Wrap 1: the sketch runs off the face. Move it or make it smaller."; a point where the face has no tangent plane: "Wrap 1: the sketch origin does not project onto the face. Move the sketch."; a sketch plane square to the face: "Wrap 1: the sketch plane is seen edge on from the face. Sketch on a plane that faces it.". (4) The panel's Method box (Analytical, Spline Surface) sits above the face pick. Left out: the optional pull direction for emboss and deboss (as D322).
Status: Default
Reason: Writing pieces through the existing STEP import and export code adds no new file format, and an affine map into the face parameters is exact on planes and cylinders and kernel friendly elsewhere.

## b. CHANGELOG (Added)

- "Keep separate body" is now saved in the part, and the feature's right click menu has Warn About Separate Bodies to show the warning again. Renaming a feature or sketch also renames it in every formula that uses it, such as `"depth@Extrude 1"`.
- Split can save the kept bodies to separate files (FDCAD part, STEP, STL or 3MF), and Wrap has a Spline Surface method that works on any face.

## c. User guide

Page that describes the Errors tab (`docs/user_guide/` errors or robustness page):
- "Keep separate body" is saved with the part, so the warning stays hidden after you reopen it. To see the warning again, right click the feature and choose Warn About Separate Bodies.

Equations page:
- When you rename a feature or sketch, formulas that use its values follow the new name. For example `"depth@Extrude 1"` becomes `"depth@Base"`. Undo puts both back. Names that only start the same, such as "Extrude 10", are not changed.

Multibody page, Split section:
- After Cut, double click a body in the list to type its file name.
- Pick a format and click Save Bodies to write each ticked body to its own file in a folder you choose.
- An FDCAD Part file opens as an imported body you can edit with the direct editing tools.
- Saving does not change your part.

Wrap section (Phase 4 features page):
- Method Analytical keeps lengths exactly on cylinders and flat faces. The sketch plane must touch the face.
- Method Spline Surface works on any face. The sketch origin goes to the nearest point of the face, and lengths match the sketch near that point.
- With Spline Surface the sketch must stay on the face. It cannot wrap all the way round.

## d. Left out

- Wrap pull direction for emboss and deboss (as D322): material always grows square to the face.
- Split file names are not stored in the part: saving is a one off action and the part stays as it was.
