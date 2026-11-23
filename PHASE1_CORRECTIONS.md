# Phase 1 Corrections (owner testing, 2026-10-25)

Found by hand testing the Phase 1 Windows installer. Fix these on the `phase1` branch so every later phase gets them. The owner's overall verdict: the UI looks poor and needs a polish pass.

**Phases 2 to 7 are paused** until the owner signs off on these fixes. Later phase branches are then rebased on `phase1`. Free model workers do the simpler items. Claude reviews every change.

Status key: [ ] open, [~] with a worker, [x] fixed.

## Bugs (fix first)

- [x] **C1. A finished sketch is not shown.** After exiting a sketch, its curves do not appear in the 3D view.
  - Expected: a finished sketch shows its lines in the viewport, and hides when it is used by a feature (unless shown on purpose).
  - Look at: `ui/main_window/sketch_mode.py`, `ui/viewport/widget.py`, `ui/main_window/visibility.py`.
- [x] **C2. No preview while editing Extrude (and Revolve, and other features).**
  - Expected: while the property panel is open, the viewport shows a live, see-through preview that updates on every value change. OK commits it, Cancel removes it.
  - Look at: `ui/main_window/new_feature.py`, `ui/property_panel/panel.py`, `ui/viewport/`.

## Workflow

- [x] **C3. Origin and the default planes must not be editable like features.**
  - Expected: Origin, Front, Top and Right sit at the top of the tree. No edit, delete, suppress, reorder or rollback on them. Only show or hide, plus "Sketch" from the right-click menu.
  - Look at: `ui/tree/feature_tree.py`, and the matching commands in core.
- [x] **C4. Starting a sketch must ask where it goes.**
  - If a plane or flat face is already selected, the sketch starts on it.
  - If nothing is selected, show "Select a plane or flat face", highlight the three default planes in the viewport, and start the sketch on the one the user clicks (planes in the tree can also be clicked). Esc cancels.
  - Look at: `ui/main_window/sketch_mode.py`, `ui/main_window/actions.py`.

## UI look and layout

- [x] **C5. Every command needs an icon beside its name.** Line, centerline, corner rectangle, center rectangle, circle, each arc, point, the relations, smart dimension, extrude, revolve, and the rest.
  - Original SVG set made for FDCAD (PLAN section 8, item 7). No icons copied from other CAD tools.
  - One consistent style, readable at 16 and 24 px, with light and dark theme versions (or one icon set recoloured by the theme).
  - There is no icons folder yet. Add `src/fdcad/ui/icons/` and include it in packaging.
- [x] **C6. Group related tools into dropdowns.**
  - Rectangle: corner rectangle, center rectangle.
  - Arc: centerpoint arc, tangent arc, 3 point arc.
  - Line: line, centerline.
  - Later phases: Slot (straight, arc); Ellipse (ellipse, partial ellipse).
  - The button keeps the last tool used from its group, with a small arrow that opens the rest.
  - Look at: `ui/command_tabs/`, `ui/sketch_tools/tools.py`.
- [x] **C7. General polish pass.** Spacing, alignment, font sizes, theme colours, and Windows display scaling. Get screenshots from the owner before and after. Done on `cloud/polish` and `cloud/polish2` (round 2 after the reviewer's Windows run, D111); screenshots in `docs/screenshots/polish/`. Owner sign off on the installed build still needed.

- [x] **C8. Context toolbar on selection (D106).** See L9. Build after C3 and C4.

## UI overhaul plan (starts Thursday 2026-10-29, Claude does it)

Owner verdict on the 0.1.0-fix1 build: the UI is far from what the reference material shows. Do this as one overhaul, in order, checking each step with screenshots of the running app before giving the owner a build:

1. Original icon set (C5) for every sketch tool, feature, relation, tree row and view button, light and dark.
2. Command tabs rebuilt (L1, L2): big icons for main tools, compact icon plus label for the rest, dropdown groups, tooltips.
3. Property panel rebuilt (L3). Done on `cloud/panel-preview`, with the live preview and drag arrow (C2, L7).
4. Feature tree icons and viewport view toolbar (L4, L5), status bar (L6).
5. Workflow: live preview (C2), finished sketch shown (C1), sketch plane picking (C4), context toolbar (C8), cursor feedback (L8).
6. Polish pass (C7), then a build for the owner.

Only hand the owner a build when the look has visibly changed.

## Layout notes from the reference manuals (2026-10-25)

Familiar CAD conventions seen in `reference/` (local only). Follow the behaviour, never copy icons, names, colours or screenshots.

- **L1. Command tabs.** Main tools (Extrude, Revolve, Extruded Cut) are large: icon above the label. Secondary tools sit in small stacked rows of icon plus label, two or three per column. Grouped tools show a small arrow for the dropdown (see C6).
- **L2. Tooltips.** Bold tool name plus one sentence on what it does, for example "Extrude: extends a sketch in one or two directions to make a solid."
- **L3. Property panel.** Header with the feature name and OK and Cancel buttons at the top. Options in collapsible titled groups (From, Direction 1, Direction 2, Thin Feature). Each field has a small icon at its left. End condition is a dropdown, with a reverse direction button beside it. Direction 2 and Thin Feature are unchecked group boxes that expand when ticked.
- **L4. Feature tree.** Part name at the top, then a Solid Bodies folder, the three planes, Origin, then features. Every row has a type icon. A feature expands to show the sketch it uses. A draggable rollback bar sits under the last feature.
- **L5. View toolbar.** Small, semi transparent row of icons at the top centre of the viewport: zoom to fit, zoom to area, previous view, section view, standard views dropdown, display style dropdown.
- **L6. Status bar.** Units selector at the bottom right. Sketch status and cursor coordinates beside it.
- **L7. Feature preview (C2).** See-through preview in an accent colour, with the sketch still visible. Needs owner OK (see below): a drag arrow on the preview that changes the depth live.
- **L8. Cursor feedback.** While a sketch tool is active, the cursor shows a small copy of the tool's icon. Snap targets (midpoint, endpoint, centre) show a small marker by the cursor.
- **L9. Approved by the owner (D106), item C8.** A context toolbar: when a face, plane or feature is selected, a small floating row of icons appears by the cursor (Sketch, Extrude, Edit Feature, Hide, Normal To). It saves many clicks and fixes much of C4.

## Done means

- Each item above is fixed and checked by hand in the installed build.
- Tests are added where possible: tree locking (C3), sketch plane choice (C4), tool groups (C6).
- The owner signs off on before and after screenshots for C5 to C7.

## Workflow spec (2026-10-29)

The owner wants the tutorial workflow copied step by step. See `docs/WORKFLOW_SPEC.md` (items W1 to W8 and three acceptance tests). Extra tools used by the tutorials stay in Phases 2 and 3.

- [x] W1 sketch plane picking, W2 feature first, W3 sketching feedback, W4 dimension value box, W5 exit and tree (branch `cloud/workflow`, D110). Check the 3D view parts by hand: planes on hover, sketch lines, labels on the model.
- [x] Block test, Turned test and Box test run offscreen in `tests/ui/test_acceptance.py` (Box test on `cloud/phase1-finish`, with dimensions to part edges, D113).
- [x] W6 feature panel and preview: revolve drag handle (W6.4) and revolve axis picked as a straight part edge (W6.3), D112. Check the curved arrow and edge picking by hand on a GPU.
- [x] Remaining gaps (D114): animated turn to a new sketch (W1.3), model cursor coordinates in the status bar (L6), dropdowns remember their tool across restarts (C6), show and hide state saved in the file.
