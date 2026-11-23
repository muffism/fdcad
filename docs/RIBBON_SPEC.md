# Command tab layout spec (R1 to R4)

Owner notes of 2026-10-30: "why is Draft under Shell?" and "the placement of features and the dropdown menu look a bit wonky". This spec fixes where the part modelling tools sit and how grouped buttons look. It is behaviour only (CLAUDE.md section 10). Icons, colours and the look of each button stay FDCAD's own.

## R1. Rule for what is visible

1. A tool that most parts use is never hidden inside another tool's dropdown. Draft, Shell, Rib, Mirror and the Hole Tool each get their own visible button.
2. A dropdown groups only close variants of one idea: Fillet with Chamfer; the pattern kinds; the thread and hole kinds; the reference geometry kinds; the curve kinds. Tools that only share a group heading (Shell and Draft, Rib and Wrap) are never put in one dropdown.
3. The button of a dropdown keeps running the tool it shows; the arrow opens the list. The shown tool changes to the last one used (as today, D435).

## R2. Features tab order, left to right

1. **Sketch**: Sketch, large.
2. **Add material**: Extruded Boss and Revolved Boss large; Swept Boss and Lofted Boss small, stacked in one column.
3. **Remove material**: Extruded Cut, Hole Tool and Revolved Cut large, the Hole Tool between the two cuts because a hole is the most common cut; Swept Cut and Lofted Cut small, stacked in one column. The Hole Tool button is a dropdown with Hole Tool, Modeled Thread and Cosmetic Thread.
4. **Modify**: Fillet large, a dropdown with Fillet and Chamfer. Next to it, Pattern large, a dropdown with Linear, Circular and Sketch patterns. [The curve pattern (Array Along Curve) is in the Curves dropdown only, item 5; audit 2026-11-02 D11 item 10.] Then a column of three small buttons: Rib, Draft, Shell. Then a column of three small buttons: Dome, Wrap, Mirror.
5. **Reference geometry and curves**: Reference Geometry large (dropdown: Plane, Axis, Point, Coordinate System) and Curves large (dropdown: Helix and Spiral, Projected, Composite, Contour, Pipe, Curve Array).
6. **Direct editing**: a column of small buttons: Move Face, Offset Face, Delete Face.

The Fasten group goes away (its tools moved into 3). Other tabs keep their tools; apply R1 and R3 to them too.

## R3. How grouped buttons look

1. Large button: icon on top, label under it (at most two lines, broken between words). On a large dropdown button the arrow sits centred under the last line of the label (R3B), inside the button, and the whole strip under the icon opens the list. The arrow never floats at a corner and never overlaps the label.
2. Small button in a stacked column: icon left, label right, and for a dropdown a small arrow right of the label, vertically centred on it.
3. All large buttons on a tab have the same height, the same icon size and their labels on the same baseline. A large button is as wide as its icon or its longest label line plus a fixed padding, so neighbours look even; no button is padded wider to fit its arrow.
4. Small buttons in one column line up on the left, with the same spacing between rows. A column of two is centred vertically in the group.
5. Group titles are centred under their group. Groups are separated by a thin divider with equal space on both sides.
6. The open list shows each tool's icon and name, one per row, in the order given in R2, with the shown tool marked.

## R3A. Change of 2026-11-10 (Datum look, DECISIONS D1034)

1. Small tools no longer sit in fixed columns of three. A group's small tools flow, in the order R2 lists them, into columns of at most four rows, so a group is as narrow as its tools allow and no tab grows taller than its large buttons. The columns are balanced: six tools make three and three (the two columns R2 names for Modify), five make three and two, eight make four and four.
2. Each column is filled from the top, and the block of columns is centred on the large buttons (R3.4 as before), so rows line up across columns.
3. Every row is 24 px tall or more.
4. The tools of a tab sit on one rounded card on the window colour, and the chosen tab is a raised pill.

## R3B. Change of 2026-11-19 (UI review item P10, DECISIONS D2744)

Owner decision on a point R3.1 left open: where the arrow goes when the label has one line.

1. The arrow of a large dropdown button sits under the last line its label has, at the same gap whether the label has one line or two. Under a one line label that is where the second line would be. Before, every arrow sat in one row under the room kept for two lines, so the arrow of a one line label hung a whole empty line below its word.
2. Unchanged: every large button keeps room for two lines, and labels still start on the same line (R3.3). The strip under the icon still opens the list (R3.1).
3. The arrows of one tab are therefore on up to two rows, one per label length. An arrow moves when its button shows another tool of its group whose label has the other length.

## R4. Checks

1. Tests read the Features tab and check the order and grouping in R2 (button ids per group, which are large, which are small, which are dropdowns).
2. A test checks that no command id from R1 item 1 is only reachable through another tool's dropdown.
3. A test lays out each tab at 1280 and 1920 pixels wide (offscreen) and checks that no two buttons overlap, every dropdown arrow lies inside its button and below or right of its label (for a large button: below the lines the label has, R3B), and large buttons share one height.
4. Screenshots of every tab in the light and dark themes go to `docs/screenshots/` for the owner.
