---
name: fdcad-feature
description: Use when adding or changing an FDCAD modeling feature type (extrude, revolve, fillet, pattern and so on), its parameters, naming map, file storage or tests. Covers the feature interface, topological naming, units, errors and golden results.
---

# Adding an FDCAD feature

Read `PLAN.md` sections 5, 5A, 6, 7 and 10 and `FDEF_SPEC.md` sections 3, 5, 7, 8 and 15 before starting. Many items below are planned for Phase 1; follow the plan where the code does not exist yet.

## 1. Where the code goes

1. One module per feature type in `src/fdcad/core/features/<type>.py`.
2. `fdcad.core` never imports PySide6 or `fdcad.ui`. `tests/core/test_core_has_no_qt.py` enforces this.
3. Kernel (OCP) work runs in the rebuild worker, never on the UI thread.
4. Sketch solving goes only through the wrapper in `src/fdcad/core/sketch`.
5. Type hints everywhere. `mypy` is strict for `fdcad.core`.

## 2. The feature interface (PLAN 5.2)

Every feature provides:
1. Parameter definitions: name, kind (length, angle, count, choice, reference), default, limits.
2. Validation: rejects bad input before any kernel call, with a clear message.
3. Execute: takes the incoming solid and the resolved references, returns the new solid plus a naming map.
4. Naming map: which faces, edges and vertices it created, modified and deleted, with names from section 3.
5. The face roles it creates, documented in the module docstring (FDEF_SPEC 8.5).

## 3. Topological naming (PLAN 6, FDEF_SPEC 7 and 8)

1. Faces: `<feature>/<role>` or `<feature>/<role>/<source>`, for example `f6/cap/end`, `f6/side/e3`.
2. Use OpenCascade history (Generated, Modified, IsDeleted) to carry names through the operation.
3. Split faces get `#1`, `#2` suffixes ordered by centroid X, then Y, then Z.
4. Edges: `edge(<face>|<face>)`. Vertices: `vertex(<face>|<face>|<face>)`. Names sorted alphabetically.
5. Every stored reference keeps a snapshot. Resolve by name first, then by one clear snapshot match (warning). No confident match is an error. Never pick between equally good matches.
6. Sketch entity ids are permanent and never reused.

## 4. Units and parameters (PLAN 7, FDEF_SPEC 3)

1. Store lengths in mm and angles in radians.
2. Store every parameter as `{ "expr": <typed text>, "value": <internal value> }`.
3. Evaluate expressions only with the safe expression parser in `src/fdcad/core/units`. Never use `eval`.

## 5. Errors and robustness (PLAN 5A)

1. Catch every kernel exception and turn it into a feature error. The app must never crash.
2. States: OK, warning (reference resolved through the snapshot fallback), error (failed or missing reference).
3. A failed feature is skipped. Later independent features still build.
4. Booleans use the fuzzy tolerance from DECISIONS D47 (0.00001 mm). Check for zero thickness and unexpected bodies after each boolean.
5. Messages say what failed and what to do next: "Fillet 2 failed: radius is larger than the edge allows. Reduce the radius or select fewer edges."
6. Fixes are offered as buttons the user confirms. Never change geometry automatically.
7. Batch kernel work: one fillet for all edges, one boolean on a compound for patterns.

## 6. UI and undo

1. Creating or editing the feature goes through an undoable command in `src/fdcad/ui/commands`.
2. Undo stores commands and parameters, never solids.
3. Property panel and tree work follows the `fdcad-qt-ui` skill.

## 7. File format (FDEF_SPEC 5, 14, 15)

1. Add the type string and its params and refs to `FDEF_SPEC.md` section 5.3.
2. Save in canonical form: keys in spec order, floats to 12 significant digits, unknown keys preserved.
3. A change that is not backward compatible raises `schema` and adds `migrate_N_to_M` in `src/fdcad/core/io/migrations` with tests.

## 8. Tests (PLAN 10)

Write the failing test first (see the `test-driven-development` skill).
1. Unit tests for parameters, validation and execute.
2. Golden results for each sample part that uses the feature: volume within 1 part per million, face count, edge count, optimal bounding box within 0.0001 mm.
3. Naming stability: change an upstream dimension, and downstream references resolve to the same faces.
4. Round trip: save and reopen gives an identical document. STEP export reimports with matching volume.
5. Failure cases: each known failure gives the right message, highlight and fix, and the fix works.
6. Performance budgets from PLAN 11.2 still pass.

## 9. Done checklist

1. `uv run ruff format`, `uv run ruff check`, `uv run mypy` and `uv run pytest` all pass.
2. The `PLAN.md` item is ticked in the same commit.
3. Non obvious choices have a `DECISIONS.md` entry.
4. New ideas go to `IDEAS.md`, not into the code (D48).
