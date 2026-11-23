# Rules for Claude Code

These rules apply to all work on FDCAD. Read this file first, then `PLAN.md`, `DECISIONS.md`, `FDEF_SPEC.md` and `SHORTCUTS.md` before starting any task.

## 1. How to work

1. Work through `PLAN.md` phase by phase, in order. Do not start a phase until the previous phase meets every item in its done criteria.
2. Tick checklist items in `PLAN.md` as they are completed, in the same commit as the work.
3. The owner wants minimal interruptions. Make reasonable choices yourself and keep going.
4. Commit small, working steps with clear messages. Never leave `main` or the phase branch broken.
5. Scope is frozen (DECISIONS D48). Never build anything that is not in `PLAN.md`. Record new ideas, including your own, in `IDEAS.md` and carry on with the plan.

## 1A. Model use

1. Use Sonnet for most work: features, UI, tests, refactors, docs, packaging. Set it as the default model in the project's Claude Code settings.
2. Use Opus for hard problems: architecture decisions, topological naming, the rebuild engine, kernel failures that survive two fix attempts, deformation and graph engine design, and performance investigations.
3. When a hard problem comes up in a Sonnet session, hand it to an Opus subagent with a focused brief and continue with its result. If a whole task is hard, tell the owner in one line at the start so they can switch with `/model`.
4. Use Haiku or Sonnet subagents for noisy exploration (searching the codebase, reading logs) and ask them for short summaries.

## 2. When to stop and ask the owner

Stop and ask only in these cases:

1. A dependency cannot be installed, built or packaged on one of the target platforms after reasonable attempts.
2. A licensing question: any new dependency that is not GPL v3 compatible, or any doubt about a license.
3. A change to a locked decision in `DECISIONS.md` (for example the stack, file format, scope or platforms).

For everything else, choose the option that best fits the plan, record it in `DECISIONS.md` and continue.

These rules take priority over any skill that says to ask or check in with the user.

## 3. Recording decisions

Add an entry to `DECISIONS.md` for any choice that a future contributor would wonder about: dependency versions, library choices, data structure choices, behaviour not specified in the plan. Use the next number and the format already used in the file. Never edit a locked decision without the owner's approval.

## 4. Definition of done (every phase)

1. All tests pass in CI on macOS (Apple Silicon) and Windows.
2. Every sample part rebuilds and matches its golden results.
3. Exported STEP reimports with matching volume.
4. Part files (`.fdprt`, and `.fdef` from before v1.0) saved by every earlier phase still open correctly.
5. `CHANGELOG.md` updated; release tag created; release workflow publishes both installers.
6. Pull request from the phase branch opened with the owner review checklist from `PLAN.md` section 13, filled in with what to try.

## 5. Architecture rules (non negotiable)

1. `fdcad/core` never imports PySide6 or anything from `fdcad/ui`.
2. Kernel (OCP) calls never run on the UI thread.
3. Every document change goes through an undoable command.
4. Every feature implements the shared feature interface and returns a naming map.
5. Lengths are stored internally in millimetres and angles in radians. The user's typed text is always stored alongside.
6. The sketch solver is only used through the wrapper in `fdcad/core/sketch`.
7. Every kernel exception is caught and turned into a feature error. The app must never crash because a feature failed.
8. No network access, except the optional update check, which is off by default.
9. No telemetry or analytics of any kind.
10. Opening a file never runs code. There is no script node; graph expressions use the safe expression parser only.
11. `fdcad/core/graph` and `fdcad/core/deform` follow the same rules as the rest of `core`: no Qt, kernel work off the UI thread.
12. Never change geometry to fix an error without the user's confirmation. Fixes are offered as buttons (`PLAN.md` section 5A).

## 5A. Performance and memory rules

1. Speed and memory are requirements. The budgets in `PLAN.md` section 11 are tests; a change that breaks one is not done.
2. Never loop over triangles, vertices or large point sets in Python. Use whole array transfers and numpy.
3. Never hold shapes, meshes or embedded data longer than needed. Undo stores commands, not solids.
4. Measure before optimising. Every performance fix comes with a regression test.
5. Prefer batching kernel operations (one fillet, one boolean on a compound) over many small ones.

## 6. Code standards

1. Python 3.13 with type hints everywhere. `mypy` in strict mode for `fdcad/core`.
2. Format and lint with `ruff`. Commit hooks must pass.
3. Every new feature or parser rule comes with tests. Bug fixes come with a test that fails before the fix.
4. Public functions and classes have short docstrings.
5. Keep modules small and focused. One feature type per module in `fdcad/core/features`.
6. Dependencies are pinned in the lock file. Do not add a dependency without recording it in `DECISIONS.md` with its license.

## 7. Trademark and originality rules

FDCAD follows familiar CAD conventions but must not copy any commercial product's identity.

1. Never use these terms in the UI, code identifiers, user documentation or icons (these planning files are the only exception): SOLIDWORKS, FeatureManager, PropertyManager, CommandManager, ConfigurationManager, Hole Wizard, Instant3D, SketchXpert, DimXpert, Toolbox, eDrawings, MySolidWorks, Rhinoceros, Rhino, Grasshopper, Gumball.
2. Use these names instead: feature tree, property panel, command tabs, configurations panel, Hole Tool, shortcut bar, confirmation corner, node editor, transform handles, "Add as Feature" (for turning graph output into a feature).
3. Do not use the Rhino or Grasshopper SDKs, file formats or component icons. The node editor is an original design.
4. All icons, the app icon, colours and layouts are original work. Do not copy or trace any icon or screenshot from commercial software.
5. The README may mention SOLIDWORKS, Rhinoceros and Grasshopper only in one sentence stating that FDCAD is not affiliated with or endorsed by Dassault Systèmes or Robert McNeel and Associates.
6. Standard engineering data (thread sizes, hole dimensions) may be used; compile it from the published standards, not from another product's files.

## 8. Writing style for docs, UI text and commit messages

1. Plain, short sentences.
2. Do not use em dashes or en dashes. Use commas, colons or separate sentences.
3. UI labels in title case for commands ("Extruded Cut"), sentence case for messages.
4. Error messages say what failed and what to do next, for example: "Fillet 2 failed: radius is larger than the edge allows. Reduce the radius or select fewer edges."

## 9. Platform notes

1. Mac builds target Apple Silicon only. Use the Apple Silicon Mac runner in CI.
2. planegcs has no prebuilt Mac package: compile it from source in CI with Eigen installed from Homebrew.
3. Mac app bundles must be ad hoc signed with `codesign` or they will not launch on Apple Silicon.
4. Windows builds are x64. The installer registers the `.fdprt` and `.fdef` file associations and adds an uninstaller.
5. Test Retina and high DPI scaling on both platforms.
6. Development happens on the owner's Windows PC. Use `uv` for every Python command. Mac work is verified through CI only, so keep Mac specific code small and well tested.
7. The repository is public (DECISIONS D2872), so CI minutes are free. Mac CI still runs only on pull requests to `main`, version tags and manual runs, to keep feedback fast.
8. UI tests run on the Qt offscreen platform. Never make CI depend on a GPU.

## 10. Clean room (since 2026-10-29)

1. Implementers (cloud agents, workers, coding sessions) build only from this repository and the specs in `docs/`. They never open `reference/` and never look up commercial CAD documentation, tutorials, screenshots, icons or source online.
2. Only the manager session reads `reference/`. It writes behaviour only specs (no copied wording, names, icons, screenshots or example values) and logs every spec change and implementer session in the clean room record (kept privately, outside this repository).
3. Reviews check code against the specs and must not add details taken from the references.
