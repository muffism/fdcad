# Workflow spec (Phase 1 UI overhaul)

The owner wants FDCAD to work the way the common university CAD tutorials teach part modelling: same order of steps, same places to click, same feedback. This file describes that workflow in our own words. The tutorials themselves are kept locally in `reference/` (not in git) and must never be copied: no text, names, icons or screenshots (CLAUDE.md section 7).

Scope decision (owner, 2026-10-29): Phase 1 copies the workflow and look for sketch, extrude and revolve. Tools the tutorials also use (trim, sketch fillet, fillet, chamfer, shell, hole tool, section view, up to face, material, mirror, patterns) stay in Phases 2 and 3 and are built the same way when they come.

Each item says what the user does and what FDCAD must show. IDs (W1...) are used in commits and in `PHASE1_CORRECTIONS.md`.

## Acceptance tests

Phase 1 is done when both of these can be followed click by click without a surprise:

All values below are our own test values.

- **Block test**: new part, sketch a corner rectangle on Top from the origin, dimension 40 x 80, extrude blind 25; preselect the top face, start Extrude, sketch two circles of diameter 18 placed by dimensions, exit, extrude blind 8 with merge; start Extruded Cut, pick one boss's top face, circle snapped to the boss centre, diameter 12, exit, blind 6; start Extruded Cut on the bottom face, circle diameter 8, Through All.
- **Turned test**: start Revolve with nothing selected, pick Front, draw a vertical 200 line from the origin, then lines, a centerpoint arc and a 3 point arc to close a profile beside it (no trim yet), add a vertical relation between two points with Ctrl click and the property panel, exit, pick the 200 line as the axis, 360 degrees, OK.
- **Box test**: sketch on a preselected Front plane, rectangle 120 x 70, double click the 70 and change it to 75, extrude 40 by dragging the handle, then by typing; sketch a circle on a face, dimension it to two edges, Extruded Cut Through All.

## W1. Starting a sketch (C4)

1. **Sketch** with a plane or flat face selected: the sketch opens on it at once.
2. **Sketch** with nothing selected: the three default planes appear in the viewport, a status message says "Select a plane or flat face", and the cursor shows a small sketch mark. Hovering a plane highlights its border. Clicking a plane (in the viewport or the tree) or a flat face opens the sketch. Esc cancels.
3. Opening a sketch turns the view normal to the sketch plane (animated) and switches the command tabs to the Sketch tab.

## W2. Feature first workflow (new)

1. **Extrude**, **Extruded Cut**, **Revolve** or **Revolved Cut** with a finished, unused sketch selected: the feature's property panel opens at once with a preview.
2. With a plane or flat face selected, or nothing selected: FDCAD starts a sketch for that feature (picking a plane as in W1.2 if needed). When the user exits the sketch, the feature's property panel opens on that sketch with a preview. Cancelling the feature keeps the sketch.
3. With nothing selected but exactly one finished, unused sketch in the part, the feature uses it (like pressing Extrude right after Exit Sketch).
4. When the feature panel opens, the view turns to an isometric-like angle (trimetric) so the depth can be seen, unless the user has rotated the view since leaving the sketch.

## W3. Sketching feedback

1. Clicking a sketch tool's button again, pressing Esc, clicking OK in the panel, picking another tool, or clicking **Select** ends the current tool.
2. The cursor shows a small copy of the active tool's icon (L8). Hovering the origin, endpoints, midpoints and centres shows a snap marker; hovering a circle's edge reveals its centre so it can be snapped to (needed by the block test).
3. Automatic relations show as small tags beside the geometry (hover gives the relation name). A menu entry in View shows or hides the tags.
4. Colours: under defined blue, fully defined black (white in dark theme), over defined red. The status bar shows Under Defined / Fully Defined / Over Defined.
5. Ctrl click two or more entities: the property panel lists relations that fit them (horizontal, vertical, coincident, equal...). Clicking one adds it.

## W4. Dimensions

1. **Smart Dimension**: click an entity (or two), then click where the text goes. A small value box opens right there, with the current value selected, plus OK and cancel buttons and a rebuild arrow. Enter accepts. The sketch resizes at once.
2. Double clicking any dimension (in a sketch, or on a selected feature) opens the same value box.
3. Values accept expressions and units (section 7 of PLAN).

## W5. Exiting a sketch and the tree

1. The confirmation corner (top right of the viewport) shows a sketch mark while a sketch is open: clicking it exits and keeps the changes; a red X beside it exits and discards them.
2. After exit, the sketch appears in the tree as Sketch 1, Sketch 2... and its curves stay visible in the viewport (C1).
3. When a feature uses a sketch, the sketch moves under the feature in the tree (expand arrow) and is hidden in the viewport. Right click the feature: Edit Sketch, Edit Feature.
4. Clicking a feature in the viewport or tree shows its sketch and feature dimensions on the model; double click one to change it (W4.2) and the part rebuilds.

## W6. Feature panel (L3) and preview (C2, L7)

1. Panel header: feature icon and name, OK, Cancel. Groups: From (where needed), Direction 1, Direction 2 (tick box, collapsed), Thin Feature later.
2. Direction 1: reverse direction button, end condition dropdown (Blind, Through All, Mid Plane for Phase 1), depth or angle field with icon, merge result tick box for bosses after the first body.
3. Revolve: axis of revolution field. If the sketch has exactly one centerline it is chosen automatically, otherwise the user clicks a sketch line or an edge.
4. Preview: see-through accent coloured solid that updates on every change, with the sketch still visible. A drag handle (arrow) at the end of the preview changes the depth live and shows the value beside it. The active direction's handle is the accent colour; the other direction's is grey.
5. Finishing: OK in the panel, OK in the confirmation corner, Enter, or right click in the viewport (right click gives a small menu whose first item is OK). Cancel or Esc removes the preview.
6. After OK the new feature appears in the tree (generic names with a space and a number: Extrude 1, Cut 1, Revolve 1, Revolve Cut 1).

## W7. Navigation (Guide tutorial)

1. Mouse: wheel zoom at the cursor, middle drag rotate, Ctrl middle drag pan, Shift middle drag zoom, Alt middle drag roll.
2. Keys: arrows rotate in steps, Ctrl arrows pan, Shift arrows rotate 90 degrees, Alt left or right rolls. Space or Ctrl+Space opens the view selector. F9 toggles the left panel.
3. View toolbar at the top centre of the viewport (L5): zoom to fit, zoom to area, previous view, standard views dropdown, display style dropdown. Section view button arrives in Phase 2.
4. Command tabs can be shown or hidden from a right click menu on the tab bar.

## W8. Look (C5 to C7, L1 to L6)

As in `PHASE1_CORRECTIONS.md`: original icons on every command, tree row and view button; large icon buttons for main features; compact rows for the rest; grouped tools with dropdown arrows; tooltips with a bold name and one sentence; status bar with sketch status, cursor coordinates and unit selector.
