# Phase 1 implementation plan (v0.1)

Order of work for `PLAN.md` Phase 1. The headless core comes first, so every piece is tested without the UI. Each milestone ends with all checks green and a commit on `phase1`. The `PLAN.md` items in brackets are ticked when their last part lands.

## M1. Units and expressions (`core/units`)
1. Lexer and parser for every form in `FDEF_SPEC.md` section 12: decimals, fractions, mixed numbers, feet and inches, arithmetic, `=` formulas with variables, functions and `pi`.
2. Values carry a dimension (length, angle, number). Dimension checks per section 12.3.
3. Evaluation returns millimetres or radians. Part unit applies to bare numbers outside formulas.
4. Variables: evaluation order, circular reference detection, clear errors.
5. Tests: a large table of input, part unit, field kind and expected value. [Unit and expression parser; Global variables (core half)]

## M2. Document and file format (`core/document`, `core/io`)
1. Typed document model: parameters (`expr` plus `value`), features, variables, configurations, appearance.
2. New document with Origin, Front (XY), Top (XZ) and Right (YZ). mm and inch templates.
3. `.fdef` read and write in canonical form, unknown keys preserved, newer schema refused with the spec message.
4. Migrations framework (`core/io/migrations`), schema 1.
5. Tests: round trip, canonical output, the spec's minimal example. [.fdef save and open (core half); Origin and default planes]

## M3. Sketch core (`core/sketch`)
1. Entities: point, line, circle, arc, construction flag. Permanent ids.
2. planegcs wrapper: relations, driving and driven dimensions, solve, degrees of freedom.
3. Status: under, fully and over defined, conflicting relations reported.
4. Sketch checks: open contours, duplicates, overlaps, self intersection.
5. Profiles: closed loops to OpenCascade faces with nested holes. [Relations; Smart dimension (core); Sketch status and diagnostics; sketch checks]

## M4. Features and naming (`core/features`, `core/naming`)
1. Feature interface: parameters, validation, execute, naming map.
2. Origin, plane, sketch, extrude (boss and cut; blind, through all, mid plane, two directions, reverse), revolve (one direction, mid plane, two directions, angle).
3. Topological naming per `PLAN.md` section 6, with snapshots and the resolution order.
4. Robustness: fuzzy booleans, zero thickness detection, unexpected bodies and body count, fix offers as data.
5. Tests: golden volumes, face and edge counts, naming stability. [Extrude; Revolve; Topological naming; Robustness foundations (core)]

## M5. Rebuild engine and cache (`core/rebuild`, `core/cache`)
1. Dependency graph from parameters, variables and references. Rebuild only affected features.
2. Worker with progress and cancel. Feature states OK, warning, error. No cascading collapse.
3. Per feature memory cache (capped, LRU) and disk cache in binary BRep, keyed as in `FDEF_SPEC.md` section 13.
4. Parallel kernel modes on. Rebuild statistics. [Rebuild engine; Local solid cache; Performance foundations (core)]

## M6. Export (`core/io`)
1. STEP AP214 and AP242. STL with deviation and angle. 3MF written in house: units, colours, multiple bodies.
2. Tests: STEP reimport volume, STL watertight, 3MF structure. [STEP, STL and 3MF export]

## M7. Application shell (`ui`)
1. Main window layout, command tabs, feature tree, property panel, status bar, light and dark themes, preferences.
2. Undo stack and command objects for every document change.
3. New Part dialog, save, save as, open, recent files, `.fdef` opened from the file manager (Windows argument, macOS file open event).
4. Autosave and recovery, local log file. [Main window layout; New Part dialog; Undo and redo; save and open (UI half); Autosave]

## M8. Sketcher UI (`ui/sketch_tools`)
1. Tools: line, centerline, rectangles, circle, arcs, point, construction toggle.
2. Inference: snaps, inference lines, automatic relations. Dragging at 60 updates per second.
3. Relations and smart dimension UI, status colours, conflict highlight. [Sketcher; Sketch inference; Smart dimension (UI)]

## M9. Viewport and input (`ui/viewport`, `ui/input`)
1. Selection: hover, filters, box, select other. Feature tree actions.
2. Standard views, normal to, zoom to fit, previous view, display styles, transparency.
3. Shortcuts, gestures and shortcut bar from `SHORTCUTS.md`, with editors. [Selection; Feature tree actions; Navigation; Shortcuts]

## M10. Errors panel, samples, budgets, release
1. Errors panel and confirmed one click fixes in the UI. Bodies folder.
2. Sample parts: plate with holes, turned shaft, bracket, generated 200 feature part. Golden results.
3. Performance and memory budgets as tests. Rebuild statistics panel.
4. Changelog, pull request with the owner checklist, v0.1.0. [Sample parts; remaining items]

## Delegation (DECISIONS D52)
Free model workers take the clearly specified, easy to check parts: test tables, sample part generators, boilerplate dialogs, docs. Claude keeps the parser core, naming, rebuild engine, solver wrapper, viewport and anything that needs debugging.
