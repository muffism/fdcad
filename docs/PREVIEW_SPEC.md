# Preview look spec (PV1 to PV8)

Written by the manager on 2026-11-09 from the owner's request: feature previews (Extrude, Fillet, Chamfer and the rest) should look like the overlay style common in CAD tools. Behaviour only. Colours, widths and values are FDCAD's own. Decision D1031. Replaces the finished part look of D583 for the Full preview.

## PV1 One look for every feature preview

1. While a feature's panel is open, the part keeps its normal look: opaque, in its own colours, with its usual edges and silhouette. It is never hidden or made see-through by the preview.
2. The preview shows only what the feature changes, drawn over the part as a see-through shaded solid in the one preview colour (FDCAD's accent colour, light and dark theme), with its edges as thin lines in the same colour.
3. Every feature that has a preview uses this look: Extrude, Revolve, Sweep, Loft, Rib, Hole, Fillet, Chamfer, Shell, Draft, Move Face, Dome, patterns, mirror and the rest. Drag arrows, rulers, callouts and value labels stay as they are.

## PV2 Added and removed material

1. A feature that adds material (a boss extrude, a revolve, a rib, a round on an inside corner) shows the added volume.
2. A feature that removes material (a cut, a hole, a round or chamfer on an outside edge, a shell's removed inside) shows the removed volume.
3. Removed material lies inside the part, so the preview is never hidden by the part's own faces: it always shows, drawn over the part. The preview's own faces still hide each other, so it reads as one solid.

## PV3 Fillet, Chamfer, Shell, Draft and Move Face

1. Full: over the unchanged part, the faces the feature makes (the round faces of a fillet, the angled faces of a chamfer, the inner faces of a shell, the drafted faces of a draft) are drawn see-through in the preview colour, with their edges. The sharp edge or old face stays visible underneath, so the user sees the old and new shape together.
2. Lines (owner's description, 2026-11-09): every Fillet and Chamfer face in the Full preview also draws, in the preview colour and drawn over the part like the rest of the preview: (a) its two long edges, where the new face meets the two neighbouring faces (the top and bottom edge of the round or chamfer), and (b) cross lines that join those two edges across the face, spaced along its length: arcs for a round (the radius seen in section), straight lines for a chamfer. Each face has both end lines plus evenly spaced lines between them (about one every few millimetres on screen, at least 3 and at most 40 per face, so long edges are not crowded). Shell, Draft and Move Face draw only the edges of their faces.
3. Move Face keeps its three colours (moved, held, stretched faces, D798) in the same overlay style.
4. Partial (D585) and None are unchanged.
5. The Extrude and Rib Detailed preview (TR164) uses the same overlay: added faces in the preview colour, changed faces in the second colour, over the unchanged part.

## PV4 No stripes

Preview faces that lie on or very close to the part's faces must not fight the part for depth (diagonal stripes or blotches on curved faces, the problem that led to D583). Pull the preview toward the camera with a depth offset, as the Extrude preview already does, or use another method that gives the same clean result. Test it on curved faces (a fillet on a cylinder edge, a draft on a round face).

## PV5 Picking through the preview

The preview is never picked. The part's edges and faces under it can still be hovered and clicked while the panel is open (Fillet and Chamfer add edges this way).

## PV6 Before and after slider

The before and after slider (TR224 item 4) stays. At After it shows the overlay of PV1 to PV3; moving it toward Before fades the overlay out until only the unchanged part shows.

## PV7 Speed

The overlay must not be slower than the current preview. Build the preview shapes off the UI thread as now (PLAN 11, throttled interaction). Do not mesh the whole result if only the new faces are drawn.

## PV8 Tests

1. Unit tests for each kind (an added volume, a removed volume, a Fillet Full, a Chamfer Full, a Shell, a Draft, Move Face): the part stays opaque and not ghosted, the overlay is see-through in the preview colour, and it is drawn so the part cannot hide it.
2. The old tests of the finished part look (D583) are updated to the new look.
