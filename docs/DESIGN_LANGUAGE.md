# Datum: FDCAD's design language

Owner request of 2026-11-10: redesign the UI, colours, logo and icons (DECISIONS D1034). This page says what the look is and why, so later work keeps it. It is FDCAD's own design. Nothing in it is copied or traced from another program (CLAUDE.md section 7).

A datum is the surface a machinist measures everything else from. The look follows that idea: the part is the subject, the window is the quiet, exact surface it sits on.

## 1. Principles

1. **The part comes first.** The 3D view is the largest and richest thing on screen. Panels are flat and quiet. Only one thing floats: the command tabs' card.
2. **Two colours carry meaning.** Cobalt means "this is what the tool adds or acts on". Ember means "this is what the tool takes away". Nothing else uses them.
3. **Solids look solid.** Icons are small lit parts, not wire drawings: a closed outline has a body.
4. **One step of spacing, two radii.** Every size is a multiple of the 4 px step. Controls have 6 px corners; panels, plates and popups have 10 px.
5. **Rules stay rules.** Every contrast limit of `docs/UI_POLISH_SPEC.md` still holds, in all four themes, and so does the 24 px smallest size for something to click.

## 2. Colour

All colours live in `src/fdcad/ui/themes/theme.py`. Widgets never write a colour themselves.

| Name | Light | Dark | Used for |
| --- | --- | --- | --- |
| Cobalt (`accent`) | `#1F54E6` | `#7FA6FF` | Focus, the chosen tab, the main button, new material in icons |
| Ember (`cut`) | `#CF5409` | `#FF9D5C` | Removed material in icons: cuts, holes, trims, deletes |
| Window | `#E9ECF1` | `#16181C` | The frame: menu bar, tab rows, status bar |
| Surface | `#F5F6F9` | `#1E2126` | Panels and the tree |
| Raised | `#FFFFFF` | `#292D34` | The command card, groups, buttons, popups |
| Ink (`text`) | `#14171C` | `#ECEEF2` | Text and icon lines |

1. The greys are cool, with a little blue in them, so cobalt sits in the same family and ember stands apart.
2. The view runs from a pale sky tone at the top to a deeper studio floor tone at the bottom. Selection, pre selection, sketch states and axis colours keep their meanings from before. The rules for what is drawn in the view are in section 7.
3. Beige and Stealth are the same system in warm paper and in black. They use the same cobalt and ember.
4. The brand colours (`BRAND` in `theme.py`) are the same in every theme: a deep cobalt tile from `#24388F` to `#0A1030`, white, and the ember of the mark.
5. A row has three fills besides the panel's: under the pointer (`hover`), selected (`selected`) and selected under the pointer (`pressed`, also the fill of a pressed button). Every text colour a row can have reads at 4.5:1 on each of them, so `pressed` is only a small step past `selected` in lightness and a stronger blue as well (D2840).

## 3. Shape and layout

1. **Command tabs.** The chosen tab is a raised pill. The tools sit on one rounded card that floats on the window colour. Main tools are large with the label under the icon. Small tools flow into balanced columns of at most four rows, each row 24 px, in the order `docs/RIBBON_SPEC.md` lists them. Each column fills from the top and the block of columns is centred beside the large tools.
2. **Left panel.** Flat, one colour from its tab row to the bottom. The chosen tab is a tinted pill.
3. **Document tabs.** The chosen part's tab joins the view under it, with a cobalt line on top.
4. **View toolbar.** A see through pill over the view.
5. **Windows.** Long pages scroll inside the window, so its buttons are always on screen.
6. **Panel headers.** Every panel that opens in the left panel has one header: the icon and the name, then OK and Cancel at equal width across the panel. OK is the main button. Both are words only (D2692). That is the property panel, the sketch panel, the Reference Geometry panels and the Section View panel (D2743, `fdcad/ui/property_panel/header.py`). Help and Pin, at the right of the name in the property panel, are 24 px icon buttons (D2701).
7. **Groups.** A group is a card with its semibold title inside, in a panel and in a window alike. A field icon has one cell the size of a small tool button, so fields share a left edge and icons sit level with them (D2692). A row leads with a word or with an icon, not both, and every lead of a panel sits in one column: as wide as the widest lead on show, 128 px at most. So every field of a panel starts at one x, in every group (D2742, `fdcad/ui/property_panel/columns.py`). In the left panel, which a tool's panel never makes wider than its default (D2791), a word of more than about 8 letters does not widen the column: in a group with such a word each drop down sits under its word at the width of the group, and a drop down with no room for its entry ends it with an ellipsis (D2800, D2801). A label is a word or two written for the user, never the name a field has in the code, and short enough to sit in that column (D2841). A note under a control takes a row when it has something to say and none before, so no group ends with a blank line (D2842).
8. **Message bars.** A card with a colour on its left edge and a mark for its kind. A warning has the warning colour. A notice has the neutral muted colour: green is kept for "this worked" and cobalt for what a tool acts on (D2700). The button that does what the message asks is outlined; Don't Show Again and the cross that closes the bar are flat (D2694, D2701).
9. **Empty states.** One line in the muted colour, centred in the place the content will take (D2693, D2695). A whole page that is empty (the start page, the left panel with no part) puts the line in a dashed outline. A list or table keeps its size and shows the line in its middle; a card shows it where its buttons will be. `fdcad/ui/empty_state.py` holds the three forms (D2702).
10. **Panels that float.** A panel that can leave the window (the node editor) has a title bar of FDCAD's own: the name in the title role on the window colour, then Float and Close as 24 px icon buttons. Float becomes Dock, with another drawing, while the panel floats. The bar takes no mouse press itself, so dragging it and double clicking it work as in any window (D2745).
11. **Tabs inside a panel.** A row of words that fills the width of the panel or of its group: muted, the chosen one in the text colour with a 2 px cobalt line under it. Fillet and Chamfer (Main, More, Favourites) and the Hole Tool (Type, Positions) use it. The pill is for the tab rows one level up, items 1 and 2 of this list (D2790, D2803).

## 4. Icons

Rules are checked by `src/fdcad/ui/icons/audit.py`; `tools/icon_sheet.py` draws the whole set for review.

1. A 24 by 24 grid, lines 1.5 wide with round ends, straight lines on the pixel grid. As before.
2. **Body tint.** A closed outline is filled lightly in its own line colour (12 percent for ink, 20 percent for an active shape). Dashed and half strength outlines stay empty: they are hidden or reference lines. `tools/icon_duotone.py` applies this to the whole set and is safe to run again.
3. **Light from the upper left.** On the main tools a block's left face is tinted lightly (8 percent) and its right face more (22 percent), so it reads as a lit solid. `tools/icon_heroes.py` holds these drawings.
4. **Cobalt adds, ember removes.** A tool's active part is drawn in `#ACCENT`. Tools that take material away use `#CUT` instead, so Extruded Boss and Extruded Cut can never be mixed up, and neither can their rows in the tree.
5. **Before and after.** Where it helps (Fillet, Chamfer), the shape from before the tool is a faint dashed line.
6. **Marks.** A warning is a triangle, an error a circle, a notice and a question a rounded square. Message bars, message windows, the tree and the Errors tab all use these four, so a kind of message has one shape everywhere (D2694, D2696).
7. **Sharp at every scale.** A picture put on a label is asked for at the screen's pixel ratio (D2698).
8. **One command, one picture.** A right click menu shows the icon a command has in the menu bar, the command tabs and the context toolbar. A command with no icon shows none, and every menu row keeps the icon column, so the text of all rows starts on one line (D2703, `fdcad/ui/menu_icons.py`).
9. **A word may become an icon** when the control is small, often seen and in a narrow place. The word stays as the accessible name and starts the tooltip, the target stays 24 px or more, and a state such as pinned changes the drawing as well as the colour (D2701).

## 5. The mark

The app icon is the letters F and D made the way FDCAD makes parts: a flat off white profile (`#FFFEFB` to `#F3EEE4`, faintly warm toward the foot, D1039) pushed back into an ember solid, on the cobalt tile. The two letters stand on two neighbouring faces of a cube that is not drawn, so the F is seen from the front left and the D from the front right, both from above. The F is its face and the cube's corner: it runs to the corner, and the end of its top arm lies on the D's face. The D starts where that end stops and stands against the back of the F. The D's side walls are a darker ember than the F's, so the F reads as standing in front, and the end of the F's top arm, the corner itself, is a bright ember that does not darken toward its foot, so it does not run into the D's side wall below it (D1036, D1037, D1038). `tools/make_brand.py` draws it from numbers, so it can be redrawn at any size. A bolder drawing is used at 16 to 32 px. The start picture and the installer use the same tile, mark and white name.

## 6. Type

The working UI keeps its four roles (caption 11, body 13, title 13 semibold, dialog title 15 semibold; `themes/typography.py`). One more role, display at 34 px, is only for the name FDCAD on the start picture.

## 7. The 3D view

The numbers live in `src/fdcad/ui/viewport/look.py` and are tested without a graphics card. `tools/view_review_shots.py` draws the view on a real screen for review (`docs/VIEW_REVIEW_2026-11-19.md`).

1. **True colours.** Every colour reaches the kernel as sRGB, so a part, a sketch and a plane have the colour the theme or the user gave them. The brightest face of a part in the isometric view is close to the part's own colour, and no face is brighter than it (D2760).
2. **Three lights.** A key light from the upper left, a soft fill from the lower right and some ambient light, all following the camera: top, front and side of a box are three clear shades in every standard view. No specular glint.
3. **Two line colours.** Edges drawn on faces use `edge`. Lines with nothing behind them (the outline round the part, wireframe, the seen lines of the hidden line styles) use `silhouette`, which reads against the view. Hidden edges are the same colour faded toward the view, and dashed (D654, D2761). Wireframe draws real edges only, the edges the shaded view draws on its faces: no curve of the kernel's across a hole or a fillet (D2823).
4. **Weights.** Edges 1 px, the outline 1.5 px, reference planes 1 px, the origin's axes 1.5 px. The highlight under the cursor is 2.5 px and a selection 3 px. Sketches shown in the view and reference curves are 2 px, twice an edge. Marks are heavier the more they matter: a lost pick 2 px, a line to pick from 3 px, what an error points at 4 px. All grow with the screen scale (D2765, D2766, D2824).
5. **Highlights are flat.** A highlighted face is a flat tint of its colour, a third see through, with its outline in the full colour. It is not lit, so the colour is the same on every face (D2764). The outline has a rim: a line 1 px wide on each side of it, white in the light themes and black in the dark ones. A part can have any colour, so the outline brings its own ground and reads on a red part as it does on the grey one (D2821).
6. **One typeface.** Text in the view is in the window's font. A value (a depth, a radius, a dimension) sits on a plate in the colour of the sketch editor's value plate and is drawn over everything else (D2762, D2763).
7. **One axis, one colour.** X, Y and Z have the theme's three axis colours in the corner triad, at the origin and in a sketch (D2766). The triad, its letters and the places to click on it grow with the screen scale together (D2822).
8. **Smoothing.** Four samples everywhere. Eight below 150 percent on a graphics card that tells its memory, where the four extra samples cost a view no more than a sixteenth of it: thin lines are a quarter to a third steadier there. A sample of a pixel costs 16 bytes (D2820).
9. **See-through amounts.** How see through a thing is says how much it matters now (0 is solid, 1 is not there). A sketch region: 0.85 idle, 0.70 under the cursor, 0.45 picked, 0.30 picked and under the cursor, each a step the eye sees in every theme. The feature preview and the graph ghost 0.70. The mirror image 0.65, with its edges. A reference plane 0.88. The numbers are checked with `look.seen_through`, which mixes colours as the kernel does, and `look.colour_gap` (D2760, D2825).
