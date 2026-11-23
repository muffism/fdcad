# FDCAD 1.0 release notes

Release date: to be set when the owner tags v1.0.0.

FDCAD 1.0 is the first complete release. It is a free, open source parametric part modeller for Windows (x64) and Mac (Apple Silicon), aimed at parts for 3D printing and general mechanical parts. You draw sketches, turn them into features, and change any value later; the part rebuilds from its feature tree.

FDCAD works fully offline. It sends nothing over the network and collects no usage data. Opening a part file never runs code.

This page sums up what 1.0 can do, area by area. `CHANGELOG.md` has the full list.

## Getting started

1. Windows: run `FDCAD-1.0.0-windows-x64-setup.exe`. It adds FDCAD to the Start menu, opens `.fdprt` part files (and older `.fdef` files) on a double click and has an uninstaller in Settings, Apps.
2. Mac: open `FDCAD-1.0.0-macos-arm64.dmg` and drag FDCAD into Applications. The app is signed ad hoc, so the first start needs a right click on the app and Open.
3. The first start shows a short welcome: how to start a sketch, the command tabs, the left panel and where Preferences and the themes are. Help, Welcome shows it again.
4. Help, Open User Guide opens the guide inside FDCAD. It has a page for each tool group and twelve tutorials built on the sample parts in File, Open Sample.
5. Help, Keyboard Shortcuts lists every command and its keys. Change the keys in Preferences, on the Shortcuts tab.

## Sketching

1. Lines, rectangles (corner, center, 3 point and parallelogram), circles, arcs, slots, polygons, splines, ellipses, points and text.
2. Relations and Smart Dimension, with a sketch that turns black when fully defined and shows conflicting items highlighted.
3. Trim, Extend, Offset, Mirror (also while drawing), sketch fillets and chamfers, and linear and circular sketch patterns.
4. Snaps to the sketch and to the part: corners, edges, midpoints and centres. Convert Entities copies part edges and curve features into the sketch.
5. Pictures in a sketch, scaled to a known length, to trace over.
6. Crossing curves split a sketch into regions. Pick the regions a feature uses, or let it use them all.

## Features

1. Extruded and revolved bosses and cuts with every common end condition, draft while extruding and thin walls.
2. Swept and lofted bosses and cuts.
3. Fillet, chamfer, shell, draft, move face, offset face and delete face.
4. Linear, circular, sketch driven and curve driven patterns, mirror, and arrays along a curve.
5. Values can be typed in the work area, right where the drag handle is, and every field takes units and formulas.

## Holes, threads and fastening

1. Hole Tool: simple, counterbore, countersink, tapped, heat set insert, hex nut trap and captive nut slot holes, in ISO metric and inch sizes, also as slots.
2. Modelled helical threads and cosmetic threads.
3. Mounting bosses, snap hooks and their grooves, lip and groove, vents, ribs, domes and wrap. The fastening tools can save favourite settings.

## Curves, bodies and deformation

1. Helix and spiral, projected and composite curves, contour curves and pipes.
2. Several bodies in one part: combine, intersect, split, move and copy, scale and delete. Bodies can be hidden or isolated.
3. Bend, twist, taper, stretch and flow along a curve. A result that is only approximate is marked as such.

## Reference geometry

Planes, axes, points and coordinate systems, with a panel that guesses the method from what you pick.

## Sheet metal

Base flange, edge flange, miter flange, hem, jog, sketched bend, closed and broken corners, rip, tab and slot, cross break, forming tools, convert to sheet metal and insert bends. Flatten shows the flat pattern, which exports to DXF, SVG or STEP. Bend allowance comes from a K factor, a bend allowance, a bend deduction or a bend table.

## 3D printing and checking the part

1. Printer profiles with build volume, nozzle, overhang angle, minimum wall and fit tolerance.
2. Overhang, wall thickness and draft analysis, geometry check, build volume check and a print weight estimate.
3. Split for Printing cuts a part to fit the printer, with pins or dovetail keys.
4. Open in Slicer sends the part to your slicer as 3MF.
5. Measure and Section View.

## Files

1. Parts are saved as `.fdprt` files. Parts saved as `.fdef` by earlier builds still open, and Save writes them as `.fdprt` from then on. Every file saved by an earlier FDCAD version opens in 1.0.
2. Export to STEP, STL, 3MF, DXF, SVG and a build123d script. Save As writes STEP, STL and 3MF directly.
3. Import STEP files as a base body, and STL, 3MF or OBJ meshes as reference bodies or solids.
4. Autosave and recovery after a crash.

## Equations, configurations and the node editor

1. Global variables and equations, with formulas in any value field. Renaming a feature updates the formulas that name it.
2. Configurations and design tables for families of parts.
3. A node editor (Graph tab) to build geometry or drive values with nodes, then turn the result into a feature with Add as Feature.

## Working in the app

1. Four colour themes, Beige, Light Gray (the default), Dark Grey and Stealth, or follow the system setting.
2. Mouse or trackpad navigation, editable shortcuts, mouse gestures and a shortcut bar with search.
3. Undo and redo for every change, including steps inside a sketch.
4. Errors and warnings say what failed and what to do next. Many come with one click fixes in the Errors tab. FDCAD never changes geometry to fix an error without asking.

## Known limits

1. Surface bodies are not part of FDCAD, so the Delete option of Delete Face stays greyed out.
2. A few fillet, chamfer and draft options the kernel cannot do reliably were left out. They are listed in `DECISIONS.md` (D529).
3. The Mac build is checked by the automated build only. Please report anything that looks wrong on a Mac.
4. The speed and memory budgets are tested in CI. Confirming them on the two baseline machines is part of the owner review (`docs/OWNER_REVIEW_1.0.md`).

## Thanks and licenses

FDCAD is licensed under the GNU General Public License, version 3 or later. It uses Open CASCADE Technology through OCP, planegcs, Qt for Python and NumPy, each under its own license. Help, About FDCAD lists them and shows their license texts.
