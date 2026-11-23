# Contributing to FDCAD

Thank you for helping. Please read `PLAN.md`, `CLAUDE.md` and `DECISIONS.md` first. Scope is frozen until v1.0 (DECISIONS D48), so new feature ideas go to `IDEAS.md`.

## Setup

1. Install [uv](https://docs.astral.sh/uv/).
2. Run `uv sync` to create the environment from the lock file.
3. Run `uv run pre-commit install` to enable the commit hooks.

## Everyday commands

1. Run the app: `uv run fdcad`
2. Run the tests: `uv run pytest`
3. Format and lint: `uv run ruff format` and `uv run ruff check`
4. Type check: `uv run mypy`

## Rules in short

1. `fdcad.core` never imports Qt or anything from `fdcad.ui`.
2. Kernel calls never run on the UI thread.
3. Every document change goes through an undoable command.
4. Every new feature or fix comes with tests. A bug fix comes with a test that failed before the fix.
5. Do not add a dependency without a `DECISIONS.md` entry stating its license. It must be compatible with GPL v3.
6. Do not use commercial CAD product names in code, UI or docs. See `CLAUDE.md` section 7.
7. Write plain, short sentences. No em dashes or en dashes.

## Clean room

FDCAD follows the workflow of common part modellers without copying any of them.

1. Do not copy code, text, icons, screenshots or file formats from commercial CAD software or its documentation, and do not contribute work you made while looking at them.
2. Build from this repository and the specs in `docs/`. If a spec is missing something, open an issue that describes the behaviour you want in your own words.
3. Standard engineering data (thread sizes, hole dimensions) may be used when it is compiled from the published standards.

## Pull requests

Work happens on a branch, not on `main`. Keep commits small and working. CI must pass on Windows and macOS.

By contributing you agree that your work is released under GPL v3 or later.
