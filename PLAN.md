# FDCAD Build Plan

FDCAD is an open source parametric part modeler for macOS and Windows. Its workflow is familiar to engineers who use mainstream feature based CAD tools. Parts are saved as native `.fdef` files (open JSON format) and exported as STEP and STL.

Read this file together with `CLAUDE.md` (rules), `DECISIONS.md` (decision log), `FDEF_SPEC.md` (file format) and `SHORTCUTS.md` (input mapping). Scope is frozen; new ideas go to `IDEAS.md` (DECISIONS D48).

## 1. Product summary

1. **Name:** FDCAD ("Fully Defined CAD"). Native file extension `.fdef`.
2. **License:** GPL v3 or later.
3. **Platforms:** macOS on Apple Silicon (arm64), Windows x64. No Intel Mac build. No Linux release (Linux may work from source but is not tested).
4. **Distribution:** GitHub Releases only. Unsigned. Mac gets a DMG, Windows gets an installer.
5. **Native format:** `.fdef`, plain JSON, open published schema.
6. **Export:** STEP (AP214 default, AP242 option), STL and 3MF for 3D printing, DXF and SVG of flat faces and sketches for laser cutting and CNC. Colours are carried in STEP and 3MF.
7. **Import:** STEP, as a non editable base body that features can be added on top of. Meshes (STL, 3MF, OBJ) as reference bodies.

## 2. Scope

### In scope
1. Part modeling (single part per document, multibody allowed).
2. Sketching with constraints and dimensions.
3. Solid features: extrude, revolve, sweep, loft (boss and cut), fillet, chamfer, shell, draft, rib, dome, wrap.
4. Patterns and mirror; multibody operations.
5. Reference geometry and curves.
6. Hole Tool with cosmetic threads.
7. Equations, global variables, configurations, design tables.
8. Basic sheet metal: base flange, edge flange, sketched bend, simple flatten.
9. Measure and section view.
10. build123d Python script export.
11. Curve driven and deformation tools: pipe, array along curve, flow along curve, twist, bend, taper, stretch, transform handles, contour curves, curvature graph.
12. Node editor for algorithmic design (Phase 7): nodes drive variables and feature parameters, and generate geometry that is added to the feature tree as a feature.
13. 3D printing and prototyping tools: 3MF export, DXF and SVG export, open in slicer, fit presets, insert and nut hole types, modeled threads, fastening features, direct face editing, overhang and wall thickness analysis, build volume check, split for printing, scale, sketch picture, mesh import, volume and print weight estimate.

### Out of scope
Surface modelling of any kind (surface bodies and every surface tool; the Phase 8 surfacing approved on 2026-11-04, DECISIONS D850, was taken back out by the owner on 2026-11-08, DECISIONS D1028), mass properties as a user feature (the only exception is the volume and print weight estimate), assemblies, drawings, weldments, sheet metal edge cases (complex flatten, forming tools, lofted bends), web or browser version, Intel Mac build, script nodes or any code execution from a file.

## 3. Technology stack

1. **Language:** Python 3.13.
2. **UI:** PySide6 (Qt 6).
3. **Geometry kernel:** OpenCascade via OCP (PyPI package `cadquery_ocp`).
4. **Sketch solver:** planegcs (FreeCAD's 2D constraint solver, Python bindings, PyPI package `planegcs`). Prebuilt for Windows. Compiled from source on the Mac build (needs a C++ compiler and Eigen from Homebrew).
5. **Viewport:** OpenCascade's own viewer (V3d and AIS) embedded in a Qt widget.
6. **Tooling:** `uv` for environments and the lock file, `ruff` for formatting and linting, `mypy` for type checking (strict for `core`), `pytest` with the `pytest_qt` plugin for UI tests.
7. **Packaging:** PyInstaller. Mac DMG built with `hdiutil` and ad hoc signed with `codesign`. Windows installer built with Inno Setup.
8. **CI:** GitHub Actions on Apple Silicon Mac and Windows runners.
9. **Development machine:** the owner's Windows x64 PC, running Claude Code. Mac builds and Mac tests run only in CI.
10. **Repository:** private on GitHub until the owner makes it public. Copyright holder: Muffism.

Pin exact versions of every dependency in Phase 0 and record them in `DECISIONS.md`.

## 4. Repository layout

```
fdcad/
  app.py                 entry point
  core/                  modeling engine, never imports Qt
    document/            document, feature tree, variables, configurations
    features/            one module per feature type
    sketch/              sketch entities, relations, planegcs wrapper
    naming/              persistent face, edge and vertex names
    rebuild/             rebuild engine, error and warning states
    units/               unit and expression parser
    io/                  fdef read and write, migrations, STEP, STL, build123d export
    cache/               local solid cache
    deform/              NURBS based deformation (flow, twist, bend, taper, stretch)
    graph/               node graph engine and node library (Phase 7)
  ui/                    PySide6 user interface
    main_window/
    viewport/            OpenCascade viewer widget, selection, highlighting
    tree/                feature tree and rollback bar
    property_panel/
    command_tabs/
    sketch_tools/
    commands/            undoable command objects
    input/               shortcuts, gestures, shortcut bar
    themes/              light and dark
    preferences/
    node_editor/         node editor panel (Phase 7)
  resources/             icons (original SVG set), templates, app icon
tests/
  core/
  ui/
  fixtures/              sample parts, also used as tutorials
docs/
  user_guide/
packaging/
  macos/
  windows/
.github/workflows/
README.md  CHANGELOG.md  CONTRIBUTING.md  LICENSE  THIRD_PARTY_NOTICES.md
PLAN.md  CLAUDE.md  DECISIONS.md  FDEF_SPEC.md  SHORTCUTS.md  IDEAS.md
```

## 5. Architecture rules

1. **Engine and UI are separate.** `core` never imports Qt. Every feature can be built and tested headless.
2. **Every feature implements one interface:** parameter definitions, validation, and an execute step that takes the incoming solid and returns the new solid plus a naming map (which faces and edges it created, modified or deleted).
3. **Every user action is a command object** on an undo stack. Nothing changes the document outside a command.
4. **Rebuilds run in a background worker** with progress and cancel. The UI thread never runs kernel operations. Rebuild starts from the earliest changed feature only.
5. **Internal units:** lengths in millimetres, angles in radians. The text the user typed is always stored next to the computed value.
6. **The sketch solver sits behind a thin wrapper** in `core/sketch`, so it can be swapped without touching anything else.
7. **Feature states:** OK, warning (yellow, a reference resolved through the position fallback), error (red, failed or missing reference). An error stops that feature only; later independent features still build where possible.

## 5A. Geometry robustness

Kernel failures cannot be eliminated, but they must be rare, clearly explained and easy to fix.

1. **Tolerant booleans:** all booleans use a small fuzzy tolerance (default 0.00001 mm) so nearly coincident faces and rounding gaps from unit conversion are handled cleanly. Patterns of touching instances use the glue option.
2. **Zero thickness detection:** after every boolean, check for edges or vertices shared by separate bodies or non manifold edges. Highlight them and explain in plain words.
3. **Unexpected bodies:** merge is on by default. When a feature creates a separate body the user did not ask for, show a warning with options to keep it or undo. The feature tree has a bodies folder and the status bar shows the body count.
4. **Pre checks:** before running, show the largest fillet radius each selected edge allows, and the face whose curvature makes a shell or offset thickness impossible.
5. **Pinpointing:** when a multi edge fillet or chamfer fails, retry edge by edge to find the failing edges, then offer to apply the feature to the rest.
6. **One click fixes, always confirmed:** suggested fixes (for example add 0.01 mm to the dimension that caused zero thickness, reduce a radius to the allowed maximum, skip failing edges) are offered as buttons. Geometry never changes without the user's click.
7. **Errors panel:** lists every warning and error with the highlighted geometry, cause, suggested fixes and a link to the feature.
8. **No cascading collapse:** a failed feature is skipped; later independent features still build.
9. **Sketch checks:** open contours, duplicate or overlapping entities and self intersecting profiles are flagged in the sketch before a feature uses it.
10. **Geometry check tool:** finds invalid faces, sliver faces, tiny edges and gaps on any body, including imported ones.

## 6. Topological naming

1. Sketch entities have permanent IDs that are never reused.
2. Faces are named by origin, for example `f5/cap/start`, `f5/cap/end`, `f5/side/e3` (side face swept from sketch entity e3).
3. OpenCascade operation history (Generated, Modified, IsDeleted) carries names through later features. Split faces get stable suffixes ordered by geometry.
4. Edges are named by their two neighbouring faces. Vertices by their three or more neighbouring faces.
5. Every stored reference also keeps a position snapshot: type, midpoint, direction, length or area, and neighbouring face normals.
6. Resolution order: name first. If the name fails, use the snapshot to find one clear geometric match and mark the feature yellow. If there is no confident match, mark the feature red with "missing reference" and ask the user to reselect. Never guess silently.
7. Face colours attach to face names, so they survive rebuilds.

## 7. Units and expressions

1. Each part has a unit system, chosen in the New Part dialog: millimetres or inches. Preferences set which one is preselected. The status bar shows the current unit; clicking it changes the display unit only, never the geometry.
2. Accepted length units: `mm`, `cm`, `m`, `in`, `ft`, and the `"` and `'` symbols for inches and feet.
3. Accepted forms: `20`, `20mm`, `20 in`, `2/3in`, `7/8 mm`, `1 3/4in`, `1' 3"`, `20mm + 1/4in`, `=Width/2`, `=(Width + 5mm)*2`.
4. A number without a unit uses the part's unit.
5. Angles: degrees by default, `deg` and `rad` suffixes accepted, for example `30`, `30deg`, `0.5rad`.
6. Global variables are referenced by name after `=`. Circular references are an error shown in the equations manager.
7. Every field shows the typed text when editing and the evaluated value otherwise.

## 8. User interface

1. **Top:** menu bar (File, Edit, View, Insert, Tools, Help) and command tabs: Features, Sketch, Sheet Metal (Phase 5), Evaluate (measure, section view, printability checks, volume and weight), Graph (Phase 7).
2. **Left panel tabs:** feature tree with rollback bar; property panel (takes over while a feature or sketch is being edited, with OK and Cancel); configurations and variables.
3. **Centre:** viewport with a small view toolbar (standard views, display style, section view), XYZ triad bottom left, OK and Cancel corner top right while editing.
4. **Bottom status bar:** sketch status, cursor coordinates, unit selector.
5. **Sketch colours:** blue under defined, black fully defined (white in dark theme), red over defined.
6. **Themes:** light and dark, plus "follow system".
7. **Icons:** original SVG set made for FDCAD. App icon is an original design.
8. **Documents:** multiple parts open as tabs.
9. **Navigation:** mouse: middle drag rotate, Ctrl and middle drag pan, wheel zoom. Mac trackpad: two finger drag rotate, Shift and two finger drag pan, pinch zoom. Both selectable in preferences.
10. **Shortcuts, gestures and shortcut bar:** see `SHORTCUTS.md`. All customizable in preferences.
11. **Selection:** hover highlight, filters for faces, edges and vertices, box selection, select other.
12. **Feature tree actions:** rename, drag to reorder (blocked if it would break a dependency), suppress and unsuppress, rollback, edit feature, edit sketch, delete with dependency warning, parent and child view.
13. **Display precision:** 0 to 8 decimal places per unit, default 2 for mm and 3 for inches. Values are always stored and computed at full precision; the setting changes display only.
14. **Language:** English only for now. All UI strings live in one module so translation can be added later.
15. **Fonts:** bundled fonts under the SIL Open Font License for sketch text, plus the system's installed fonts.
16. **Preferences:** default units, theme, autosave interval, navigation scheme, shortcut editor, gesture editor, update check (off by default), printer profiles (build volume, fit tolerance, overhang angle, minimum wall thickness, slicer application) and material densities. Default profile: generic printer with a 220 x 220 x 250 mm build volume; the slicer is the system's default app for 3MF files.
17. **Terminology:** generic names only. See the trademark rules in `CLAUDE.md`.
18. **Node editor (Phase 7):** a dockable panel beside the viewport, one graph per part, opened from the Graph command tab.

## 9. Phases

Work strictly in order. Each phase ends with a GitHub release and a review by the owner. Tick items as they are completed.

### Phase 0: Skeleton release (v0.0.1)
Goal: prove the riskiest technical pieces before writing features.

* [x] Developer tooling (for building FDCAD, not shipped in the app):
  1. Owner step, once: in Claude Code run `/plugin marketplace add anthropics/skills`, then `/plugin install example-skills@anthropic-agent-skills` (provides `skill-creator` and `frontend-design`).
  2. Copy these skills from obra/superpowers (MIT) into `.claude/skills`, keeping its license notice: `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `writing-plans`, `executing-plans`. Do not add `brainstorming` (it asks the owner questions before any work) or `subagent-driven-development` (a fresh subagent and review per task uses many tokens).
  3. Install rtk on the Windows PC (`winget install rtk-ai.rtk`) and enable its Claude Code hook so command output (tests, git, builds) is compressed before Claude reads it.
  4. Install Claude Code Usage Monitor (`uv tool install claude-monitor`) for the owner to watch usage.
  5. Use `skill-creator` to write three project skills in `.claude/skills`: `fdcad-feature` (adding a feature: interface, naming map, tests, golden results), `fdcad-qt-ui` (layout, spacing, themes, icons, sketch colours, trademark terms), `fdcad-release` (build, sign, package, publish). Keep them current as later phases change the code.
* [x] Repository structure, LICENSE (GPL v3 or later), README, CHANGELOG, CONTRIBUTING, THIRD_PARTY_NOTICES (OpenCascade LGPL 2.1 with exception, planegcs LGPL 2.1 or later, PySide6 LGPL 3, Python PSF).
* [x] `uv` project with Python 3.13 and pinned dependencies. Lock file committed.
* [x] `ruff`, `mypy` and `pytest` configured. Git commit hooks run format and lint.
* [x] planegcs installs on Windows from the prebuilt package and compiles from source on the Mac runner.
* [x] Empty main window with an OpenCascade viewport embedded in Qt that renders and rotates a test cube on both OSes, including Retina and high DPI scaling.
* [x] PyInstaller builds a standalone app on both OSes.
* [x] Mac: DMG, ad hoc signed, launches on Apple Silicon. `.fdef` registered as a document type.
* [x] Windows: Inno Setup installer, `.fdef` file association, uninstaller.
* [x] GitHub Actions: tests on every push; release workflow on version tags builds both installers and attaches them to a GitHub Release.
* [x] Owner manual check: install the test build on the owner's Windows PC and MacBook Air M1 and confirm the cube renders, rotates and scales correctly. CI cannot do this because its Mac runners have no GPU.
* [x] README section explaining first launch of an unsigned app (Mac: System Settings, Privacy and Security, Open Anyway. Windows: More info, Run anyway).

### Phase 1: Foundation (v0.1)
Goal: a usable modeler for prismatic and turned parts.

* [x] Main window layout, command tabs, feature tree, property panel, status bar, light and dark themes, preferences dialog.
* [x] New Part dialog with unit choice; mm and inch templates.
* [x] Unit and expression parser (section 7) with a full test table.
* [x] Global variables (basic list in the variables tab; full equations manager in Phase 4).
* [x] `.fdef` save, save as, open, recent files, migrations framework (schema version 1).
* [x] Local solid cache (see `FDEF_SPEC.md`).
* [x] Origin and default planes: Front (XY), Top (XZ), Right (YZ).
* [x] Sketcher on planes and planar faces: line, centerline, corner rectangle, center rectangle, circle, centerpoint arc, tangent arc, 3 point arc, point, construction toggle.
* [x] Relations: horizontal, vertical, coincident, collinear, parallel, perpendicular, tangent, concentric, equal, midpoint, symmetric, fixed.
* [x] Smart dimension: linear, horizontal, vertical, angular, radius, diameter.
* [x] Sketch inference: snaps (endpoints, midpoints, centres, intersections, quadrants), inference lines, automatic relations.
* [x] Sketch status and diagnostics: under, fully and over defined; highlight conflicting relations.
* [x] Extrude (boss and cut): blind, through all, mid plane, two directions, reverse direction.
* [x] Revolve (boss and cut): one direction, mid plane, two directions, angle.
* [x] Rebuild engine with background worker, progress and cancel; feature states OK, warning, error.
* [x] Topological naming (section 6) for all Phase 1 features.
* [x] Geometry robustness foundations (section 5A, items 1, 2, 3, 6, 7, 8, 9): tolerant booleans, zero thickness detection, unexpected body warnings with the bodies folder and body count, confirmed one click fixes, errors panel, no cascading collapse, sketch checks.
* [x] Undo and redo for every action.
* [x] Selection system: hover highlight, filters, box selection, select other.
* [x] Context toolbar on selection (D106, added by the owner during Phase 1 corrections).
* [x] Feature tree actions (section 8, item 12).
* [x] Navigation for mouse and trackpad; standard views; normal to; zoom to fit; previous view; display styles (shaded with edges, shaded, hidden lines removed, wireframe); transparency toggle.
* [x] Shortcuts, gestures and shortcut bar from `SHORTCUTS.md`, with editors in preferences.
* [x] STEP export (AP214 default, AP242 option), STL export with deviation and angle settings, and 3MF export (written in house: units, colours, multiple bodies, same mesh settings as STL).
* [x] Autosave every 5 minutes to a recovery folder; recovery prompt after a crash; local log file.
* [x] Performance foundations (section 11): dependency based rebuild, per feature cache, parallel kernel modes, incremental meshing, lazy startup, one folder packaging, binary cache, rebuild statistics panel, and the budgets running as tests.
* [x] Sample parts: plate with holes, turned shaft, bracket, and a generated 200 feature part for performance tests.

### Phase 2: Core modeling (v0.2)
* [x] Extrude additions: up to vertex, up to face, offset from face, draft while extruding, thin feature.
* [x] Sweep (boss and cut): profile along path, with twist and guide options limited to what OpenCascade supports reliably. (Guide curves left out, DECISIONS D219.)
* [x] Loft (boss and cut): multiple profiles, optional guide curves, start and end tangency. (Guide curves left out: the kernel has no reliable guide support, DECISIONS D220.)
* [x] Fillet: constant radius, variable radius. Chamfer: distance and distance, angle and distance, vertex chamfer.
* [x] Robustness additions (section 5A, items 4, 5, 10): fillet and shell pre checks, edge by edge pinpointing with partial results, geometry check tool in the Evaluate tab.
* [x] Shell: faces to remove, inward or outward, per face thickness.
* [x] Draft: neutral plane method.
* [x] Reference geometry: plane (offset, angle, three points, normal to curve, mid plane), axis, point, coordinate system.
* [x] Sketch tools: offset, trim, extend, mirror, convert entities, sketch fillet, sketch chamfer, linear and circular sketch pattern, spline, straight and arc slots, polygon, ellipse, partial ellipse.
* [x] Measure tool: distance, angle, radius, length, area of selected entities.
* [x] Section view along any plane or planar face.
* [x] Part colour and face colours, copy and paste appearance; colours written to STEP and 3MF.
* [x] DXF and SVG export of a selected planar face or sketch, true scale, in the part's units.
* [x] Open in slicer: export 3MF to a temporary file and open it in the slicer set in the printer profile.
* [x] Overhang analysis: colour faces steeper than the profile's overhang angle from the build direction.
* [x] Build volume check: show the printer bed and volume in the viewport, warn when the part does not fit, and set the print orientation by picking a face to lay flat. Orientation affects export only, never the model.
* [x] Volume and print weight estimate in the Evaluate tab: volume of selected bodies times material density (editable presets for PLA, PETG, ABS, ASA, TPU and resin). Labelled as a solid part estimate; the slicer gives the real figure.
* [x] Sketch picture: insert an image into a sketch, scale it by two points and a known distance, adjust transparency. The image is embedded in the `.fdef`.
* [x] Sample parts: enclosure with shell and fillets, lofted handle, swept spring.

### Phase 3: Patterns, bodies, import (v0.3)
* [x] Linear pattern (one and two directions), circular pattern, sketch driven pattern; instances to skip.
* [x] Mirror features and bodies.
* [x] Multibody: combine (add, subtract, common), intersect, split, move and copy body, delete and keep body.
* [x] Isolate, hide and show bodies, show hovered body, show all hidden.
* [x] STEP import as a base body: shape healing on import, colours preserved, embedded in the `.fdef`.
* [x] Curves: helix and spiral, projected curve, composite curve.
* [x] Pipe: solid along a curve or edge chain, outer diameter, optional inner diameter for a hollow pipe, cap ends.
* [x] Array along curve: count or spacing, orient to curve or keep orientation, applies to bodies or features.
* [x] Transform handles: interactive move, rotate and scale arrows on a selected body; the result is written to the tree as a move and copy body feature with editable values.
* [x] Contour curves: planar sections of a body at a set spacing along a direction, created as reference curves usable in sketches and features.
* [x] Curvature graph: display only overlay for curves and edges, with scale and density controls.
* [x] Direct editing: offset face, move face, delete face (with healing). Works on native and imported bodies; each is a feature in the tree.
* [x] Split for printing: cut a body into pieces that fit the printer's build volume, by planes or automatically, with optional alignment pins or dovetail keys at a set clearance.
* [x] Scale feature: uniform or per axis, about the origin or a point.
* [x] Mesh import (STL, 3MF, OBJ) as a reference body: display, measure, section, use as a boolean tool, convert to a faceted solid. Warn above 100,000 triangles. The original mesh file is embedded in the `.fdef`.
* [x] Sample parts: patterned flange, multibody split part, imported STEP with added features, piped frame, chain of links arrayed along a curve, large part split for printing with pins, imported mesh with a cut.

### Phase 4: Productivity (v0.4)
* [x] Hole Tool: simple, counterbore, countersink, tapped; ISO metric and ANSI inch size tables (compiled from published standard dimensions); placed on sketch points.
* [x] Cosmetic threads: displayed on the face, stored as metadata, not modeled.
* [x] Hole Tool additions for printing: heat set insert holes (common published insert sizes, editable table), hex nut traps and captive nut slots, and modeled threads (real helical geometry that prints) as an option for tapped holes and for cylindrical faces.
* [x] Fit presets: clearance, slip and press, applied to holes and to offset face, using the fit tolerance from the active printer profile. (DECISIONS D311, D413.)
* [x] Fastening features: mounting boss, snap hook and groove, lip and groove, vent.
* [x] Wall thickness analysis: colour regions thinner than the profile's minimum wall thickness.
* [x] Equations manager: list, edit, evaluate, detect circular references.
* [x] Configurations: create, switch, per configuration parameter overrides and suppression.
* [x] Design tables: built in table editor stored inside the `.fdef`, with CSV import and export.
* [x] Rib, dome, wrap (emboss, deboss, scribe on cylindrical and planar faces).
* [x] Sketch text (for engraving and embossing).
* [x] Deformation features (in `fdcad/core/deform`): flow along curve, twist, bend, taper, stretch. Method: convert the body to NURBS, deform the control points, rebuild and validate the solid. Each feature has a tolerance setting, shows a warning when the result is approximate, and an error when the result is not a valid solid.
* [x] Sample parts: configured bolt family, tapped housing, twisted bar, part flowed along a curve, printable enclosure with bosses, snap hooks, inserts and a lip.

### Phase 5: Extras (v0.5)
* [x] Sheet metal parameters: thickness, bend radius, K factor, relief type.
* [x] Base flange, edge flange, sketched bend.
* [x] Simple flatten and fold for parts made only from these features; export the flat pattern as STEP, DXF and SVG.
* [x] build123d Python script export (one way). Unsupported items are written as comments.
* [x] Sample parts: sheet metal bracket and its flat pattern.

### Phase 6: Hardening (v1.0)
* [x] Naming stress tests: random upstream edits on all sample parts, checking every downstream reference.
* [ ] Full performance and memory pass against section 11: profile every sample part, fix the slowest steps, confirm every budget on both baseline machines. Profiling, fixes and budget tests done (docs/PERFORMANCE_REPORT.md, D432); confirming the budgets on the two baseline machines is left for the owner review.
* [x] Complete user guide with the sample parts as tutorials.
* [x] Fix all open bugs labelled for v1.0. Bug hunt in docs/BUG_HUNT.md (round 9s); its open items O1 and O2 closed in round 9v (D550).
* [x] Final `.fdef` schema review; migration tests from every earlier schema version.

### Phase 7: Node editor (v1.1)
Goal: algorithmic design inside FDCAD. Built only after v1.0 is released.

* [x] Graph engine in `fdcad/core/graph` (no Qt): typed ports (number, length, angle, boolean, point, vector, plane, curve, body, list), directed graph with cycle detection, lazy evaluation that recomputes only nodes downstream of a change, runs in the background worker with cancel, error state per node.
* [x] Node editor panel: add nodes from a searchable list, wire ports, group and comment nodes, copy and paste, zoom and pan, live preview of geometry in the viewport as a ghost. Every graph edit is an undoable command.
* [x] Input nodes: number slider (min, max, step), value field (accepts the full expression syntax), boolean toggle, point, read variable, read feature parameter, model reference (face, edge, curve or body by persistent name, with the same snapshot fallback as features).
* [x] Math nodes: arithmetic, trigonometry, range, series, remap, seeded random, and an expression node that uses the safe expression parser only.
* [x] List nodes: item, length, reverse, sort, shift, cull by pattern, flatten, and nested lists up to two levels.
* [x] Point and vector nodes: construct, deconstruct, distance, closest point, point grid, divide curve, populate a region with seeded random points.
* [x] Curve nodes: line, polyline, arc, circle, interpolated curve, planar offset.
* [x] Solid nodes: box, cylinder, sphere, extrude planar curve, pipe, boolean union, difference and intersection, move, rotate, scale, mirror, array.
* [x] Pattern nodes: attractor (scale or spacing by distance to points or curves), 2D Voronoi cells inside a boundary, strut lattice (cubic and octet) inside a bounding body.
* [x] Output nodes: set variable and set feature parameter (drive existing features and trigger a rebuild); add as feature (creates a `graph_body` feature in the tree as a new body, or added to or subtracted from an existing body).
* [x] Cycle rule: a graph has a position in the feature tree. It may read model geometry only from features above that position. A feature above that position that uses a graph driven variable or parameter is an error with a clear message.
* [x] Performance guard: graphs up to 500 nodes; preview updates in under 1 s for the sample graphs; a warning before running booleans on more than 200 bodies.
* [x] Sample graphs: plate with an attractor driven hole pattern, Voronoi cut panel, slider driven bracket, lattice filled block.

### Phase 7A: Tutorial review items (v1.2)
Goal: the behaviour common CAD lessons use that FDCAD lacked, found by the 2026-11-02 tutorial review and approved by the owner the same day (D683). Each item is specified in `docs/TUTORIAL_REVIEW_SPEC.md`; its test rows are in `docs/TEST_PLAN.md` section 17. Build in this order: High, then Medium, then Low, then the large items last.

High:
* [x] TR1 Move, Copy, Rotate, Scale and Stretch sketch entities.
* [x] TR3 Copy and paste in a sketch, and pasting a whole sketch onto a plane or face.
* [x] TR9 Copy and paste features onto a face.
* [x] TR13 Hidden Lines Visible display style.

Medium:
* [x] TR2 Split Entities.
* [x] TR4 Midpoint Line.
* [x] TR5 Insert a DXF file into a sketch.
* [x] TR11 Replace an imported body with a new file.
* [x] TR12 Sheet metal gusset and normal cut.
* [x] TR14 Dimetric and trimetric views, and saved views.
* [x] TR16 Split the view into two or four views.
* [x] TR17 Temporary axes.
* [x] TR22 Keys to go to the next and previous open part (keys in D683).
* [x] TR23 Tree folders and feature comments.
* [x] TR24 Save image of the view.
* [x] TR30 Sheet metal: cut linked to thickness, edge flange offset, miter flange propagate.
* [x] TR32 Named dimensions and Show All Dimensions.
* [x] TR33 Bodies a cut or boss acts on.

Low:
* [x] TR6 Intersection curves and silhouette entities.
* [x] TR8 Shift click for Nearest or Farthest while dimensioning.
* [x] TR10 Offset plane by Ctrl and drag.
* [x] TR15 Perspective view.
* [x] TR18 Zebra stripes.
* [x] TR19 Lasso selection.
* [x] TR20 Selection breadcrumbs.
* [x] TR21 Per body transparency.
* [x] TR25 Equations to and from a text file.
* [x] TR26 Measure in two units.
* [x] TR27 Compare two bodies.
* [x] TR28 Conic and equation curves.
* [x] TR29 Face fillet with a hold line.

Large (last):
* [x] TR7 3D sketch, starting with the plane sketch form (several planes in one sketch), then free 3D lines and splines (plane sketch parts copied in and typed 3D lines and splines done: D1719; Along X, Y, Z, coincident, fix and 3D lengths for 3D line points, and ties from 3D lines to plane sketch points, done: D2206; open: drawing in place with Tab to switch planes, and relations between two plane sketch parts). Rest moved to IDEAS.md (D1029).
* [x] TR31 IGES import with joining into a solid, and Heal for imported bodies (no surface building tools: those stay out of scope).
* [x] TR34 Sketch blocks (D1717).

### Phase 7B: Defects from the 2026-11-02 audit, then tutorial review 2 items (v1.3)
Goal: first fix the defects in existing features found by the 2026-11-02 audit (`docs/AUDIT_2026-11-02.md` and `docs/TUTORIAL_REVIEW_SPEC_2.md` sections 19 to 21), then build the behaviour in `docs/TUTORIAL_REVIEW_SPEC_2.md` (TR35 to TR420), approved by the owner on 2026-11-02 including every item marked for an owner decision (D750). Read each item with its additions (spec sections 22 to 24) and the merge and conflict notes (section 27); merged items are built once under the first number. Commands added by these items have no default keys unless the item names one (D750 item 4). Every command name in the spec is a working name: the implementer picks FDCAD's own label and records it. Start with `docs/PHASE7B_BRIEF.md`.

Stage 1, defects (audit "Read first" list first, then the rest by severity):
* [x] Topological naming: check names resolved through split suffixes, fallback names and imported face indexes against the stored position snapshot, so a changed face order gives a warning or a lost reference, never a silent wrong pick (audit E item 13, PLAN.md section 6 item 6). Add the hard cases as naming tests.
* [x] Changing the part units never changes geometry (audit D3 item 1).
* [x] Twisted sweep accuracy, face merge fallback, fillet crash guard, result sanity checks (spec section 19, audit E items 1 and 2).
* [x] Spline and ellipse curves in sweep, pipe, thin and rib paths, and in sketch tools that drop them silently (spec section 20 item 2, audit D2).
* [x] Paste into another part drops or remaps references (audit D3 item 3).
* [x] Damaged and hostile files: 3MF parser, decompression limits, recursion and number limits on open (audit D12).
* [x] Quit with several unsaved parts, cancelled rebuild status and export of partial bodies (audit D3 items 4 and 12).
* [x] Edge flanges in mirrors and patterns, and the contradicting messages (audit E item 7).
* [x] The rest of spec section 20 and the audit's High and Medium items, section by section.
* [x] Docs fixes: user guide, tutorials, SHORTCUTS.md (Ctrl+Shift+S and unbound default keys), FDEF_SPEC.md and PHASE5_SPEC.md where the audit found the document wrong.
* [x] Robustness tests from spec section 21.
* [x] Low audit items.

Stage 2, High:
* [x] TR35 Fully Define Sketch.
* [x] TR36 Check Sketch for Feature.
* [x] TR55 Guide curves for Sweep and Loft.
* [x] TR57 Fill Pattern.
* [x] TR79 Mass Properties.
* [x] TR125 Repair lost references.
* [x] TR150 Interference and gap check between bodies.
* [x] TR175 Support free hole tops.
* [x] TR176 Bridging under counterbores.
* [x] TR177 Bed edge chamfer.
* [x] TR178 Printable thread profile and fit.
* [x] TR182 Mesh export options.
* [x] TR244 Machining corner relief.
* [x] TR253 More screw heads and thread series.
* [x] TR261 Merge faces and remove extra edges.
* [x] TR263 Rules for Move Face.
* [x] TR264 How neighbours follow a moved face.
* [x] TR265 Set a size on a face.
* [x] TR284 Enclosed cavities.
* [x] TR286 Model health report.
* [x] TR287 Change test.
* [x] TR288 Show the cause of an error.
* [x] TR292 Status without colour alone.
* [x] TR295 Manufacturing check.
* [x] TR296 Milling checks.
* [x] TR297 Sheet metal and laser checks.
* [x] TR337 Signed distances in sketches.
* [x] TR375 Mac Redo key.
* [x] TR376 Mac menu roles and Window menu.
* [x] TR377 Drop files on the window.
* [x] TR378 System contrast themes on Windows.
* [x] TR381 3MF that slicers understand.
* [x] TR382 Body roles for printing.

Stage 3, Medium:
* [x] TR37 Repair Sketch.
* [x] TR38 Sketch problem list.
* [x] TR39 Select regions and chains in a sketch.
* [x] TR40 Merge relation.
* [x] TR41 Relations on ellipses and splines.
* [x] TR42 Spline edit tools.
* [x] TR43 Spline handles.
* [x] TR45 Baseline, ordinate, chamfer and path length dimensions.
* [x] TR48 Sketch fillet and chamfer on more curves (fillet on line and arc, and arc and arc corners done: D1317; splines, chamfers on arcs and drag sizing done: D1700 to D1702).
* [x] TR49 Derived sketch.
* [x] TR56 Sweep tangency and merge options (items 3 and 4 done: D1504; items 1 and 2 done: D1905, Tangent to Adjacent Faces left out).
* [x] TR58 Table Driven Pattern.
* [x] TR59 Varying pattern instances (items 1 and 3 done: D1513, D1900; clicking instance markers done: D2400; item 4 Vary Sketch not built: the pattern engine moves the seed's solid, it does not solve the seed's sketch again per copy, D2400). Rest moved to IDEAS.md (D1029).
* [x] TR60 Split Line (Projection and Intersection with a plane done: D1414; Silhouette and intersection with a body open). (Silhouette for cylinders, cones and spheres, and intersection with a body done: D1810)
* [x] TR61 Curve through points.
* [x] TR62 Fillet methods and profiles.
* [x] TR63 Setback fillet at corners. (not built: the kernel has no setback or transition setting, D1814) Rest moved to IDEAS.md (D1029).
* [x] TR65 Thin feature auto fillet.
* [x] TR67 More Deform modes (Deform Point, Curve to Curve and Surface Push done: D2412).
* [x] TR69 Bounding Box.
* [x] TR71 Insert Part (D2420).
* [x] TR72 Library features (item 1 in part, save to a library file and insert on a plane or face, done: D2115; several features per file, asking for each attached face, hidden internal dimensions and item 3 link or dissolve not built: they need a placement model beyond paste, D2422). Rest moved to IDEAS.md (D1029).
* [x] TR76 Sheet metal: flat pattern options.
* [x] TR78 Part material.
* [x] TR82 Custom properties.
* [x] TR83 Undercut analysis.
* [x] TR84 Parting Line (the line, closed loop and gaps done: D1415; splitting straddle faces open, it needs Split Line Silhouette). (splitting straddle faces done: D1811)
* [x] TR92 Select Loop and Select Tangent.
* [x] TR95 Tree filter box.
* [x] TR97 Save a Copy.
* [x] TR101 Pierce relation.
* [x] TR102 Snap to grid, length steps and angle steps.
* [x] TR103 Segment a curve.
* [x] TR104 Replace Entity.
* [x] TR105 Corner point at rounded corners.
* [x] TR107 Sketch pattern options.
* [x] TR108 Relation groups and equal length of any curves.
* [x] TR109 Turn a relation or dimension off.
* [x] TR110 Dimension preview on selection.
* [x] TR113 Cut away the model in front of the sketch plane.
* [x] TR117 Insert SVG into a sketch.
* [x] TR126 Esc stops a rebuild or a long calculation.
* [x] TR127 Primitive solids.
* [x] TR128 Combine options.
* [x] TR129 Offset Body.
* [x] TR130 Replace Face.
* [x] TR131 Fillet and chamfer without tangent propagation.
* [x] TR132 Change existing fillets and drafts.
* [x] TR133 Variable fillet point positions.
* [x] TR135 Loft to a point.
* [x] TR136 Loft connectors and end constraints (item 2 done: D1924; item 1 several connectors with Reset done, dragging them in the view not built: D2403; item 3 done: D2404). Rest moved to IDEAS.md (D1029).
* [x] TR137 Sweep with a profile part way along the path, and several profiles (items 1, 2 and 3 done: D1906, D1907, D1515).
* [x] TR139 Better sweep and loft errors (items 1 and 2 done: D1509, D1909).
* [x] TR140 Symmetric linear pattern.
* [x] TR141 Pattern chains and patterns of patterns (item 2 done: D1512; item 1 done: D1901).
* [x] TR143 Hole placement without a sketch (items 1 and 2 done: D1911, D1520).
* [x] TR144 More hole shapes (items 1 to 4 done: D1912, D1506, D1505, D1913, D1914).
* [x] TR146 Fastening feature extras (item 1 done: D1517, D1916; item 3 done: D2406; item 2 done: D2407).
* [x] TR148 Several planes or points in one command (D1925).
* [x] TR154 Linked body copy (D2417).
* [x] TR161 Gear profile.
* [x] TR163 Surface texture and knurl. (item 1, knurl, done: D2015; item 2, texture from an image, waits for the owner decision the spec asks for) Rest moved to IDEAS.md (D1029).
* [x] TR165 Sheet metal Tab.
* [x] TR166 Edge flange profile and edge choices. (item 1 done: D1101) (not built: flanges on curved and tangent edge chains, the sheet model has flat walls only; the picked end point and several lengths are met, D2305) Rest moved to IDEAS.md (D1029).
* [x] TR167 Edit Bends.
* [x] TR168 Corner Relief feature.
* [x] TR169 Bend notches.
* [x] TR171 Convert to Sheet Metal extras. (keep the body and rip types done: D2307; not built: rip sketches, a gap and overlap ratio per rip, rounded edges as bends, D2307) Rest moved to IDEAS.md (D1029).
* [x] TR172 Flat pattern data for quoting.
* [x] TR173 Flat pattern DXF output options.
* [x] TR179 Magnet pocket.
* [x] TR180 Print fit tolerance as a variable.
* [x] TR181 Split for Printing connectors (magnet pockets, screws with nut pockets and a glue gap done: D1211; draft on keys and the cut along a sketch path done: D2002).
* [x] TR184 Multi colour inlays.
* [x] TR185 Scale to fit the printer.
* [x] TR186 Mesh repair and reduce.
* [x] TR188 Printing sample parts (fit test plate, living hinge strip and storage bin done: D1217; the nut and bolt, the print in place hinge and the bin's base grid done: D2003).
* [x] TR190 Measured values in formulas.
* [x] TR191 Saved measurements.
* [x] TR194 Equation editor comfort.
* [x] TR195 Linked child configurations.
* [x] TR196 Export each configuration.
* [x] TR200 Tree follows the selection.
* [x] TR201 Delete with a list of dependents.
* [x] TR202 Errors list as a table.
* [x] TR206 Property panel behaviour.
* [x] TR207 Right click to move on.
* [x] TR208 Undo list.
* [x] TR209 Rotate about a picked item.
* [x] TR210 Axis triad clicks and an orientation popup. (D1600, D1601; the popup's key is an owner item)
* [x] TR212 Edge display options. (D1602)
* [x] TR213 Section view extras. (save with the part and in a saved view: D1604; choosing the bodies cut: D2500; the tree folder with handles and rings: D2501; Measure on cut faces: D2502)
* [x] TR214 Display quality. (D1605)
* [x] TR215 Hide and show by type.
* [x] TR217 Part templates.
* [x] TR219 Safe start without graphics hardware.
* [x] TR225 Slot along picked curves.
* [x] TR226 Ratio and difference relations.
* [x] TR227 Round All Corners.
* [x] TR231 Control of relations offered while drawing.
* [x] TR239 Extrude in a picked direction.
* [x] TR240 Extrude with twist and end scale.
* [x] TR241 Sweep with scale along the path.
* [x] TR242 Different depths per region in one extrude.
* [x] TR243 Edge profiles.
* [x] TR245 Lightening pockets.
* [x] TR246 Finger joints between plates.
* [x] TR247 Shaft and bore shapes.
* [x] TR248 Keyways and keyseats.
* [x] TR249 Retaining ring grooves.
* [x] TR250 O ring groove.
* [x] TR251 Bearing seat.
* [x] TR252 Dowel holes and a fit helper.
* [x] TR254 More thread forms (trapezoidal, ACME, square, buttress and pipe done: D1510; sketch profile and end finishes done: D1918).
* [x] TR255 Hole for self tapping screws.
* [x] TR257 Airfoil profile.
* [x] TR259 Rebuild fillets after a direct edit (Move Face and Delete Face done: D1420; Draft and Combine open). (Draft done: D1806; Combine done: D2302)
* [x] TR260 Remove and change fillets on imported bodies.
* [x] TR262 Geometry Check with fixes (sliver and duplicate fix, Ignore, Next and Back, the new classes done: D1416; gap, smooth and square up fixes and the clip sphere open). (gap fix done: D1807; smooth and square up fixes and the clip box done: D2303)
* [x] TR266 Lasting face relations on bodies with no history (D2418).
* [x] TR267 Push and pull by sign.
* [x] TR268 Place bodies by picks. (item 2 done: D1815; item 1 relations done: D2415; item 3 handle pivot and axes done: D2416)
* [x] TR269 Lock a body.
* [x] TR271 Fillet: limit failing areas, edges to keep, limiting plane (items 2 and 3 done: D1407; item 1 open). (item 1 done: D1802)
* [x] TR273 Goal seek and value sweep.
* [x] TR274 Variables with allowed values.
* [x] TR275 Tick boxes as formulas.
* [x] TR276 Pause rebuilds.
* [x] TR277 Replace a reference everywhere.
* [x] TR278 Skip one face as a fix.
* [x] TR279 Own forming tools. (own tool from a body done: D2313; not built: the tool library, D2313) Rest moved to IDEAS.md (D1029).
* [x] TR280 Bodies to linked part files (D2421).
* [x] TR281 Several sheet metal bodies. (done: D2312)
* [x] TR282 Bend table and bend order. (item 1 in part, item 2 done: D1110) (rips in the table done: D2310; not built: turning a bend into a rip and back, D2310) Rest moved to IDEAS.md (D1029).
* [x] TR289 Before and after comparison.
* [x] TR290 Result line after each command.
* [x] TR291 Help where it is needed. (items 1 and 3, hints, panel help and What's New: D2018; item 2, first run lessons that check the result: D2505)
* [x] TR293 Work without dragging. (click then click handles with arrow nudges, sketch nudges, Tab to the next sketch point, tree Move Up and Move Down done: D2209; not built: placing a sketch dimension label by click then click) Rest moved to IDEAS.md (D1029).
* [x] TR298 Moulding checks.
* [x] TR299 Printing checks.
* [x] TR300 Section and outline export.
* [x] TR301 Arrange on the bed and suggest an orientation.
* [x] TR302 Export and import options.
* [x] TR303 Select Similar.
* [x] TR317 Tangent circles and two point circle.
* [x] TR318 Blend curve.
* [x] TR319 Turned outline.
* [x] TR320 Fillet rules.
* [x] TR323 More draft options (second angle and absolute or relative done: D1419; Fixed Edge type open). (Fixed Edge done: D1804)
* [x] TR324 Size gradient pattern on a face.
* [x] TR325 Landing pad on a sloped wall.
* [x] TR326 Presets for any panel.
* [x] TR327 User thread tables (D1920).
* [x] TR328 Seed and boundary pick.
* [x] TR331 Configuration rules and test values.
* [x] TR332 Sheet metal rule library.
* [x] TR338 Warn when a sketch jumps to another solution.
* [x] TR339 Construction geometry after the sketch is closed (D1703).
* [x] TR340 Detach linked geometry.
* [x] TR343 Move the part origin (D2419).
* [x] TR344 Fit offset on a boss or cut.
* [x] TR345 Counts of zero and one.
* [x] TR346 Fillet failure help.
* [x] TR347 Simplify threads while editing (D1921; the part setting has no panel yet).
* [x] TR348 Timing pulley and belt profiles.
* [x] TR349 Thickness at a point.
* [x] TR351 Find typed values that should be linked.
* [x] TR352 Mark results that did not rebuild.
* [x] TR355 Section view zones and transparency. (D1603)
* [x] TR359 Expected value checks.
* [x] TR363 Cable tie channels.
* [x] TR364 Half lap joints between crossing plates.
* [x] TR365 Pattern at model points.
* [x] TR368 Batch export over variable values.
* [x] TR379 Recent files in the system (done but the Windows jump list New Part task: D948). Rest moved to IDEAS.md (D1029).
* [x] TR383 Per body print settings.
* [x] TR384 Settings by height.
* [x] TR385 Slicer target choice.
* [x] TR386 Read slicer 3MF files.
* [x] TR387 Switch a feature between boss and cut.
* [x] TR391 Offset corner style.
* [x] TR394 Fillet pieces and transitions (item 3 met by the vertex chamfer: D1421; items 1 and 2 open). (not built: the kernel has no setback or transition setting, D1814) Rest moved to IDEAS.md (D1029).
* [x] TR395 Snap a value to a point. (depth arrows follow a snapped vertex: D2207; not built: snapping fillet, chamfer and hole position values, which have no end condition to follow a point) Rest moved to IDEAS.md (D1029).
* [x] TR396 Section sizes along a sweep (items 1 and 2 done: D1910, D1514).
* [x] TR397 Radial hole placement and hole values in formulas (items 1 and 2 done: D1915, D1508).
* [x] TR398 Patterns on curved faces and by region (items 2 and 3 done: D1503, D1502; item 1 done for cylinder faces: D1903).
* [x] TR399 Patterns that follow other patterns (item 3 check level done: D1519; items 1 and 2 done: D1904).
* [x] TR400 Partial success for multi item tools.
* [x] TR401 Joint helpers between touching bodies.
* [x] TR402 Living hinge patterns.
* [x] TR403 Crush ribs.
* [x] TR404 Hinge generator.
* [x] TR405 Seats on curved faces.
* [x] TR409 Suction cups and floating islands.
* [x] TR410 Fix overhangs from the analysis.
* [x] TR411 Overlapping bodies on export.
* [x] TR412 Fit values by hole size and direction (D1919).
* [x] TR416 Add relations to existing geometry.
* [x] TR417 Text and yes or no variables.

Stage 4, Low:
* [x] TR44 Spline analysis aids.
* [x] TR46 Dimension tolerance and display.
* [x] TR47 Trim: keep the pieces as construction.
* [x] TR50 Move, rotate and scale a whole sketch.
* [x] TR51 Sketch from a picked edge.
* [x] TR52 Parabola and Jog Line.
* [x] TR53 Sketch drag keys (group drag done: D973; the rigid drag key needs a key chosen). Rest moved to IDEAS.md (D1029).
* [x] TR54 Text linked to a value.
* [x] TR64 Small fillet and chamfer options (items 5 and 6 done: D1012, D1401, D997; items 1 to 4 open). (item 4 done: D1800; item 2 met: D1801; items 1 and 3 left, the kernel has no setting) (not built: Keep Features and Overflow, the kernel has no setting, D2300) Rest moved to IDEAS.md (D1029).
* [x] TR66 Hole Tool size carry over setting.
* [x] TR68 Indent.
* [x] TR70 Select bodies by size.
* [x] TR73 Mirror Part to a new file.
* [x] TR74 More plane methods.
* [x] TR75 Rib and wrap small options (items 1 and 2, rib draft at the wall and wrap pull direction, done: D2112; item 3 single line fonts not built: it needs a stroke font and Wrap scribing open curves, D2413). Rest moved to IDEAS.md (D1029).
* [x] TR77 Sheet metal stamp. (depth, draft and the flat outline done: D1816; punch, die and corner radii done: D2309)
* [x] TR80 Centre of mass and mass overrides.
* [x] TR81 Section properties.
* [x] TR85 Mould Cavity.
* [x] TR86 Sensors.
* [x] TR87 More geometry check classes (items 1 and 3 done: D1416; item 2, the wall thickness target and hover reading, open). (item 2 done: D1808)
* [x] TR88 Display states. (D1608)
* [x] TR89 More expression functions.
* [x] TR90 Design table extras.
* [x] TR91 Deleting a feature and its equations.
* [x] TR93 Select Previous and Invert.
* [x] TR94 Selection sets.
* [x] TR96 Parent and child arrows.
* [x] TR98 Freeze bar (D2507).
* [x] TR99 Isolate display choices.
* [x] TR100 Up direction for new parts. Rest moved to IDEAS.md (D1029).
* [x] TR106 Close Sketch to Model (D1704).
* [x] TR111 Dimension placement details (item 5, many dimensions to reference and the reference mode, done: D965; item 4 and the angle to an axis of item 2 done: D1312; item 1 and the hidden lines of item 3 done: D1707, D1708; the symmetric angle about a centerline done: D2200; not built: arrow flip, since sketch dimensions draw no arrowheads, D1708, D2200). Rest moved to IDEAS.md (D1029).
* [x] TR112 Drag without solving (D1716).
* [x] TR114 Rectangle and polygon extras (item 3, ellipse construction axes, done: D967; item 1 done: D1313; item 2 done: D1709).
* [x] TR115 Line, arc and spline small options (item 3 and Relax Spline of item 4 done: D1314; Fit Spline converts a chain: D1306; items 1 and 2 done: D1710; the spline length dimension done: D2201; degree and weights do not apply to FDCAD's cubic splines with handles, D278, D1314).
* [x] TR116 Sketch picture extras (item 1, see-through colour, done: D977; item 2, trace, done: D1711).
* [x] TR118 Convert Entities extras (D1712).
* [x] TR119 Keep proportions on the first dimension.
* [x] TR120 Leaving a sketch.
* [x] TR121 Text extras (item 1, Explode Text, done: D1713; per character bold, italic and rotation done: D2202; pattern counting numbers done: D2203).
* [x] TR122 Merge sketches and linked copies (item 1, Merge Into Sketch, done: D986; item 2 done: D1315).
* [x] TR123 Sketch on hover with a tool active.
* [x] TR124 Swap axis relations.
* [x] TR134 Change a chamfer to a fillet and back.
* [x] TR138 More inputs for sweeps and lofts (item 1 done: D1516, D1908; item 3 done: D2405; item 2 group picker not built: it needs a chain editing widget with trim and extend, D2405). Rest moved to IDEAS.md (D1029).
* [x] TR142 Pattern small options (items 2 to 5 done: D1016, D962, D1015; item 1 patterns of reference geometry done: D2402).
* [x] TR145 Tapered threads (Hole Tool done: D1511; Thread done: D1917).
* [x] TR147 Draft, shell and dome small options (item 2, Shell Check Walls, done: D998; item 1 reduced angle done: D1418; tapered or square steps and item 3 open). (dome direction vector done: D1805; constraint sketch done: D2301; not built: tapered or square steps, D2301) Rest moved to IDEAS.md (D1029).
* [x] TR149 Offsets with rotations for reference geometry.
* [x] TR151 Slices and saved sections (item 1, parallel slices, done: D1718; slices round an axis done: D2204; item 2, a section view turned into a cut body feature, done: D2205).
* [x] TR152 Named faces and edges.
* [x] TR153 Body folders and body history.
* [x] TR155 Move a feature to another body.
* [x] TR156 Project onto a curved face.
* [x] TR157 Cut with an open sketch.
* [x] TR158 Remove history from a body.
* [x] TR159 Purge unused and delete below the bar.
* [x] TR160 Copy values and edit by rule.
* [x] TR162 Fastener and spring shapes (item 2 closed ends done: D1923; ground ends done: D2408; item 1 hex fastener sample done: D2409).
* [x] TR164 Show new and changed faces in a preview (core and Draft done: D1417; the Extrude and Rib panel ticks open). (Extrude and Rib ticks done: D1809)
* [x] TR170 Miter flange extras. (start and end offset done: D1113) (arcs in the profile and own relief done: D2306; not built: trim side bends, D2306) Rest moved to IDEAS.md (D1029).
* [x] TR174 Sheet metal small options. (items 1, 3, 5, 6, 7 and item 2 in part done: D1107) (item 4 done: D1813; the bend region choice of item 2 done: D2308)
* [x] TR183 3MF names and metadata.
* [x] TR187 Layer aware sizes and infill weight.
* [x] TR189 Small printing helpers.
* [x] TR192 Measure free points.
* [x] TR193 Linked values.
* [x] TR197 More values per configuration.
* [x] TR198 Table functions and lookups.
* [x] TR199 Curvature and deviation display (item 2, deviation along an edge: D996; item 1, curvature colours on faces with a scale and readout: D2503).
* [x] TR203 Message bars and hidden messages.
* [x] TR204 Recent commands in a sketch.
* [x] TR205 Menu access keys.
* [x] TR211 Zoom keys and mouse settings. (D1607; the Zoom Out key is an owner item)
* [x] TR216 Display mode per body. (D1606)
* [x] TR218 File commands and start page (items 1 and 3, file commands, last parts and older copies: D961; item 2, the start page and the picture in the part file: D2504).
* [x] TR220 Low memory and disk warnings.
* [x] TR221 Small tree and status options (item 1 but the Collapse All key, done: D963; item 2 is the TR23 comment; Collapse All command and item 3: D1611; the Collapse All key is an owner item).
* [x] TR222 Custom command tabs and a simple mode (D2508).
* [x] TR223 3D mouse. Rest moved to IDEAS.md (D1029).
* [x] TR224 Selection small options (items 2 and 3 done: D934, D1004; items 1 and 4: D1610).
* [x] TR228 Triangle, trapezoid and other shapes.
* [x] TR229 Convex hull (sketch; the part bridge is in IDEAS.md).
* [x] TR230 Text along any curve.
* [x] TR232 Temporary guide lines (D1714).
* [x] TR233 Colour per sketch.
* [x] TR234 Sketch on a face without splitting it (already met by design, no tick needed: D1715).
* [x] TR235 Show formulas on dimensions (the comment on hover is in IDEAS.md).
* [x] TR236 Step a dimension through a range.
* [x] TR237 Explain a relation.
* [x] TR238 Sketch settings (crossing and fork marks and the polar grid done: D987, D1014; dimension lock while dragging done: D1706).
* [x] TR256 Thread relief and end chamfer (D1922).
* [x] TR258 Roof and grow by a shape (item 1 roof done: D2414; item 2 grow by a sphere is Offset Body Rounded, D825; other shapes not built, D2414).
* [x] TR270 Pattern explode and small pattern options (item 1 done: D1902; item 2 seed cell and rotate done: D1501; item 3 box skip done: D2401; view only hiding not built: the copies are faces of one solid that the view draws as one shape, D2401). Rest moved to IDEAS.md (D1029).
* [x] TR272 Thin feature joined at its ends.
* [x] TR283 Sheet metal forms as features, and fold progress. (item 2 done: D1112; item 1 done: D2311)
* [x] TR285 Rib network.
* [x] TR294 Motion, screen readers and target size (item 1, Reduce Motion follows the system, done: D975; items 2 and 3 done: D2017, without live change events from the 3D view).
* [x] TR304 Copy configuration inputs.
* [x] TR305 Incremental save.
* [x] TR306 Mean dimensions.
* [x] TR307 Coating allowance.
* [x] TR308 Group identical bodies.
* [x] TR309 Mirror image display.
* [x] TR310 Variable names.
* [x] TR311 Code tag generator.
* [x] TR312 Mouse presets. (D1609)
* [x] TR313 Pick size settings.
* [x] TR314 Repeat with the same tool.
* [x] TR315 Layer preview.
* [x] TR316 Hole and thread list.
* [x] TR321 Chamfer corners. (mitre corner done: D1812; blend done: D2304; not built: setback, the kernel has no setting, D1814) Rest moved to IDEAS.md (D1029).
* [x] TR322 Shell both sides and minimum thickness (Both Sides done: D1411; Never Thinner or Never Thicker open). (Never Thinner and Never Thicker done: D1803)
* [x] TR329 More pick tools. (pick in a box, cylinder or sphere by typed sizes, paint pick and the one type switch done: D2208; not built: sizing the volume with handles in the 3D view) Rest moved to IDEAS.md (D1029).
* [x] TR330 Engraved marks.
* [x] TR333 Set the current view as front or home.
* [x] TR334 Extrude picks the operation.
* [x] TR335 Show more sketch items.
* [x] TR336 3D print export preview (OBJ done: D995; the mesh preview and refining by largest edge length done: D1200; refining by aspect ratio done: D2001).
* [x] TR341 Small sketch display aids (items 1, 4 and 5 done: D964, D1013; item 3 done: D1316; item 2 done: D1705).
* [x] TR342 Limits and segment relations.
* [x] TR350 Number display.
* [x] TR353 Point where a line meets a curved face.
* [x] TR354 Shortcuts with an input method on.
* [x] TR356 View only open.
* [x] TR357 Twist lock joint.
* [x] TR358 Guided calibration print.
* [x] TR360 Plane halfway between any two faces.
* [x] TR361 Diameter mode stays on in revolve sketches.
* [x] TR362 Weak automatic relations.
* [x] TR366 Pattern spacing laws.
* [x] TR367 Standard profiles.
* [x] TR369 More export formats.
* [x] TR370 Sheet metal small additions.
* [x] TR371 Small body tools.
* [x] TR372 Shake test for sketches.
* [x] TR373 Array Along Curve orientation and offsets.
* [x] TR374 Hyperbola and three expression curves.
* [x] TR380 Platform small items (items 2, 3 and 5 done: D1002, D934, D1003; item 1: D1612; item 4, taskbar and Dock progress: D2506; F1 key is an owner item). Rest moved to IDEAS.md (D1029).
* [x] TR388 Fill cavities and simplify.
* [x] TR389 Sketch layers.
* [x] TR390 Lattice fill as a feature.
* [x] TR392 Part notes.
* [x] TR393 Thread class on holes and threads.
* [x] TR406 Hose barbs and luer fittings.
* [x] TR407 Bolt circle shorthand.
* [x] TR408 Hobby small items (item 4, tool pocket, done: D1008; item 1, transition spiral, done: D2010; item 2 stone setting done: D2410; item 3 sprue tree and kit frame done: D2411).
* [x] TR413 Printer limits.
* [x] TR414 Material interlock and base pad.
* [x] TR415 Turn style and points from a file.
* [x] TR418 Dimension to midpoints.
* [x] TR419 Hide construction and group sketch items.
* [x] TR420 Edge angle display and plane display (D929).

### Phase 7C: Preview look (v1.3.1)

Owner request on 2026-11-09 (D1031). Spec: `docs/PREVIEW_SPEC.md`.

* [x] PV1 to PV8: every feature preview drawn as a see-through overlay of the added or removed material over the unchanged part. Done: D1032.

Done when: the Phase 7B done criteria hold and the owner has tried the Extrude, Cut, Fillet, Chamfer and Shell previews.

### Phase 7D: Workspace room and portable FDCAD (v1.3.2)

Owner request on 2026-11-10 (D1033).

* [x] Shorter command tabs, a narrower tree panel with a stacked filter, and no spare Untitled tab after opening a part. Done: D1033.
* [x] A start picture while the window loads. Done: D1033.
* [x] Portable mode, a single file `FDCAD-portable.exe` and a portable folder for Windows. Done: D1033.
* [x] Crash guard: a part that closed FDCAD while rebuilding opens stopped before that feature, and kernel faults are written to `crash.log`. Done: D1035.
* [x] The Datum look (`docs/DESIGN_LANGUAGE.md`): new colours in all four themes, the command card, new icon rules with a cut colour, a new app icon and start picture. Done: D1034.

Done when: the Phase 7C done criteria hold and the owner has started the portable build from a folder outside the user profile.

### Phase 8: Surfacing (removed)
Taken out of scope by the owner on 2026-11-08 (DECISIONS D1028). Nothing in it is built. `docs/SURFACE_SPEC.md` is kept as history only. Assemblies and drawings stay out of scope too.

## 10. Testing strategy

1. **Unit tests** for the expression parser (large table of inputs and expected millimetre values), solver wrapper, every feature, naming, and file read and write.
2. **Golden part tests:** every sample part rebuilds and is compared against stored results: volume (relative difference below 1 part per million), face count, edge count, and optimal bounding box (within 0.0001 mm). Volume is computed internally for testing only; it is not a user feature.
3. **Naming stability tests:** change upstream dimensions on sample parts; all downstream references must resolve to the same faces.
4. **Round trip tests:** save and reopen gives an identical document; STEP export and reimport gives matching volume; STL export is watertight.
5. **Migration tests:** files from every earlier schema version open correctly.
6. **UI smoke tests** with `pytest_qt` on the Qt offscreen platform: open app, create sketch, extrude, save, reopen. The real viewport is checked by hand in each owner review because CI runners have no GPU.
7. **Failure case library:** sample parts that deliberately trigger each known failure (bodies touching at an edge or a point, oversized fillet, impossible shell, open sketch contour, unit rounding gap). Each test checks that the right message, highlight and fix appear, and that the fix works.
8. **Deformation tests:** each deformation sample part produces a valid solid; volume and bounding box match golden results within a tolerance stated per test.
9. **Export tests:** 3MF files reimport with matching volume and colours and pass the 3MF core specification checks; DXF and SVG outputs match golden files.
10. **Graph tests:** every node has unit tests; sample graphs give identical results on every run (random nodes are seeded); cycle detection and the cycle rule have dedicated tests.
11. **CI:** while the repository is private, Windows tests run on every push, and Mac tests and builds run only on pull requests to `main`, version tags and manual runs, because Mac runner minutes cost about ten times Linux minutes and the free monthly allowance is limited. Once the repository is public, both run on every push.
12. **Performance and memory tests:** the budgets in section 11 run as automated tests on Windows CI, with a margin for slower runners, and fail the build when exceeded.

## 11. Performance and memory

Speed and low memory use are first class requirements from Phase 1, not a final polish step.

### 11.1 Baseline machines
1. Apple Silicon Mac: the owner's MacBook Air M1 (2020), a fanless base model that throttles under sustained load. Budgets assume 8 GB RAM.
2. Mid range Windows laptop: 4 cores, 16 GB RAM, integrated graphics.

### 11.2 Budgets
1. Startup: window visible in under 2 s; ready to work in under 5 s.
2. Open a sample part with a valid cache: under 2 s.
3. Edit one dimension near the end of a 200 feature tree: rebuild in under 0.5 s.
4. Full rebuild of each sample part: under 2 s.
5. Sketch dragging: solver keeps up at 60 updates per second for sketches up to 200 entities.
6. Viewport: 60 fps target, never below 30 fps, on a 200 feature part.
7. Memory: under 400 MB with an empty part; under 1.5 GB with a 200 feature part open.
8. No leaks: opening, rebuilding and closing a sample part 50 times grows memory by less than 50 MB.

### 11.3 Speed techniques
1. **Dependency based rebuild:** track which features depend on which values and references; rebuild only the features affected by a change, not everything after it.
2. **Per feature solid cache** in memory, backed by the disk cache, so rebuilds start from the nearest unchanged result.
3. **OpenCascade parallel modes on:** parallel booleans, parallel meshing and parallel shape checks.
4. **Batch kernel work:** one fillet operation for all selected edges; patterns combine all instances into one compound and run a single boolean instead of one boolean per instance.
5. **Incremental meshing:** only faces that changed are meshed again; mesh fineness scales with model size.
6. **No Python loops over geometry:** triangles, vertices and points move between the kernel, numpy and the GPU as whole arrays.
7. **Solver scope:** while dragging, solve only the connected group of entities being moved.
8. **Lazy startup:** show the window first, import the kernel and heavy modules in the background.
9. **Packaging for speed:** PyInstaller one folder builds, not single file builds, which unpack to a temporary folder on every launch.
10. **Binary cache format:** the disk cache uses OpenCascade's binary BRep format, which loads much faster than the text format.
11. **Throttled interaction:** hover highlighting and live previews are rate limited and cancelled when superseded.

### 11.4 Memory techniques
1. **Capped in memory cache:** intermediate solids are kept up to 25 percent of system RAM or 2 GB, whichever is smaller, least recently used first out, with the rest on disk.
2. **Undo stores commands, not solids:** undo replays parameter changes and reuses the cache.
3. **Instancing for display:** pattern and array instances share one mesh with different placements in the viewport.
4. **Lazy embedded data:** embedded STEP, meshes and images are decoded only when needed and the encoded text is released after loading.
5. **Imported meshes stay meshes** (compact float32 arrays) unless the user converts them to solids.
6. **Clean release:** closing a part frees its shapes, meshes and caches; tests check that memory returns close to its starting level.
7. **One display mesh quality at a time:** export meshes (STL, 3MF) are generated on demand and freed afterwards.

### 11.5 Tooling
1. Built in rebuild statistics panel: time per feature, slowest features first, current memory use.
2. Profiling with the `py_spy` sampling profiler and Python's `tracemalloc` during development (not shipped in the app).
3. Rule: measure before optimising, and add a regression test for every fix.

## 12. Release process

1. Semantic versions. Phase numbers map to minor versions (Phase 1 is v0.1.0).
2. Work for each phase happens on a branch named `phaseN`. At the end of the phase a pull request is opened; merging it is the owner's review step.
3. A version tag triggers the release workflow: builds the Mac DMG and Windows installer, attaches them to a GitHub Release, and uses the matching `CHANGELOG.md` section as release notes.
4. Each release includes a short demo checklist for the owner (section 13).

## 13. Owner review checklist (per phase)

1. Download and install the release on Mac and on Windows.
2. Open each new sample part; confirm it looks right.
3. Try the phase's headline features once by hand.
4. Edit one upstream dimension; confirm downstream features follow.
5. Save, close, reopen; export STEP and open it in another CAD tool.
6. Merge the pull request, or reply with issues.

## 14. Risk register

1. **OpenCascade viewer embedding in Qt on macOS.** Proven in Phase 0. If it cannot be made reliable, stop and ask the owner (fallback candidate: VTK).
2. **Packaging OCP with PyInstaller.** Proven in Phase 0.
3. **planegcs on Mac.** Compiled in CI in Phase 0. If it fails, stop and ask.
4. **Fillet and boolean failures in OpenCascade.** Catch every kernel exception, show a clear feature error, never crash.
5. **Topological naming edge cases.** Covered by the stress tests and the position fallback.
6. **Small single maintainer dependencies (planegcs, OCP).** Isolated behind wrappers; versions pinned.
7. **Deformation accuracy.** NURBS conversion can produce approximate or invalid solids on complex parts. Validate every result, warn when approximate, error when invalid, never pass a broken solid downstream.
8. **Node editor performance.** Large Voronoi, lattice or boolean graphs can be slow. Enforce the performance guard, run in the background, allow cancel.
9. **Mesh import performance.** Large meshes are slow as faceted solids. Warn above 100,000 triangles and keep meshes as display only references unless converted.
10. **Modeled threads and lattices.** Helical threads and many booleans are kernel heavy. Validate results and keep them optional.
