# Phase 5 tool behaviour spec

Behaviour only, written by the manager on 2026-10-30 from the vendor's public online help (2027 pages), in our own words, with generic names (CLAUDE.md sections 7 and 10). Implementers build from this file and PLAN.md only. [Later] marks items outside PLAN.md Phase 5. The bend allowance formula below is standard engineering, not product specific.

Common rules: as PHASE2_SPEC.md.

## P5.1 Sheet metal parameters

1. A Sheet Metal folder at the top of the tree holds the part's defaults: thickness, inside bend radius, bend allowance method and value, relief type and size. Editing it updates every sheet metal feature that uses the defaults.
2. Bend allowance methods: K-factor (default 0.5 is too high for most work; use 0.44 as our default and record it in DECISIONS), Bend allowance (a length), Bend deduction (a length), Bend table (a CSV of thickness, radius and angle to allowance) [Later: bend calculation tables].
   - With a K-factor: bend allowance = pi x (R + K x T) x A / 180, where R is the inside radius, T the thickness, A the bend angle in degrees and K the position of the neutral layer as a fraction of the thickness from the inside face.
3. Relief types (added automatically where a bend meets an edge): Rectangular, Obround (both sized by a ratio of the thickness between 0.05 and 2.0, or by a width and depth), Tear (smallest possible: rip or extend; built as a fixed narrow slit, audit 2026-11-02 A item 32). Corner relief options (D540).
4. Gauge tables (thickness and radius picked from a named size list) (D542); material linked parameters [Later].

## P5.2 Base flange

1. From a sketch: a closed profile becomes a flat plate of the sheet thickness; an open profile (lines and arcs) is thickened into a bent wall, every sharp corner becoming a bend of the default radius.
2. The same From list as Extrude (TOOL_SPEC T5.1.2: sketch plane, flat face or plane, vertex, offset) and, for open profiles, Direction 1 and 2 with Blind, Up to Vertex, Up to Face, Offset from Face, Mid Plane.
3. Sheet parameters on the panel: thickness, Reverse (thicken to the other side), Symmetric (half each side), bend radius, bend allowance method and value, relief type and ratio. These become the part defaults when this is the first sheet metal feature. [Built differently: the thickness and relief live only in the Sheet Metal folder (P5.1), and Symmetric wins over Reverse when both are on; audit 2026-11-02 A items 25 and 32.]

## P5.3 Edge flange

1. Pick one or more straight edges of the sheet. Each gets a wall bent from that edge. Option: edit the flange profile sketch (to make a shaped wall). [Not built: see TUTORIAL_REVIEW_SPEC_2 TR166; audit 2026-11-02 A item 9.]
2. Bend radius (default or own), gap distance between neighbouring flanges.
3. Angle field; optionally pick a face so the flange stays perpendicular or parallel to it.
4. Length: Blind with a length measured from the outer virtual sharp, the inner virtual sharp, or the tangent point of the bend (bends over 90 degrees); Up to Vertex (end face through the vertex, or a plane parallel to the base through it); Reverse. Multi length: each picked edge gets its own length label in the view.
5. Flange position: material inside, material outside, bend outside, or virtual sharp aligned; trim side bends option.
6. Custom bend allowance and relief override per flange.

## P5.4 Sketched bend

1. Sketch a line on a flat face of the sheet. Pick the face that stays fixed [built without a fixed face pick: the parent wall stays fixed; audit 2026-11-02 A item 32]. Bend position relative to the line: bend centreline, material inside, material outside, bend outside. Bend angle with Reverse, radius (default or own), custom bend allowance.

## P5.5 Flatten and fold

1. A Flat Pattern feature is always last in the tree for a sheet metal part. Turning it on shows the part flat with bend lines (bend lines can be hidden); features added while it is on apply only to the flat state; features added while it is off go before it.
2. Flatten toggle in the Sheet Metal tab. Flattening uses the bend allowance of each bend, so the flat length is exact for the chosen method.
3. If the part cannot be flattened (it would overlap itself), a warning names the feature that causes it and highlights it.
4. Grain direction (an edge) sets the orientation of the flat bounding box shown in the panel (length x width).
5. Export of the flat pattern as STEP, DXF and SVG (PLAN), true scale, bend lines on their own layer, optional bounding box.
6. Unfold and fold of single bends to add cuts across a bend (D541).
7. PLAN limit: flatten and fold only for parts made from the sheet metal features; other parts show a message saying which feature blocks flattening. Cuts and holes that only remove material from flat walls do not block it (D700, D727).

## P5.6 Not in PLAN Phase 5 (record only)

Since built in later rounds: miter flange, hem, jog, closed and break corners, forming tools, tab and slot, cross breaks, rips, convert to sheet metal and insert bends (see the sheet metal user guide), and the gusset (D700). The list below is the original record.


Miter flange (D531), hem (D530), jog (D532), closed corner (D533), break corner (D534), forming tools (D545), tab and slot (D536), cross breaks (D539), rips (D535), convert solid to sheet metal (D537), insert bends (D538). Swept flange (D543) and lofted bend (D544) [Later]: left out, they need a sheet model with curved walls.
