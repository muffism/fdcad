# Testing and building FDCAD on a Mac

These are the steps the macOS jobs in `.github/workflows/ci.yml` and `release.yml` run, for a
Claude Code session (or a person) on the owner's Mac when CI cannot run. Read `CLAUDE.md` first:
its rules apply here too.

## What you need

1. A Mac with Apple Silicon (M1 or later) and macOS 14 or later. Intel Macs are not a target.
2. The Xcode command line tools: `xcode-select --install`.
3. Homebrew (https://brew.sh), then `brew install eigen boost git gh`.
4. uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then open a new terminal.
5. `gh auth login`, so a branch can be pushed.

## Get the code

```bash
git clone https://github.com/muffism/fdcad.git
cd fdcad
git checkout main
uv python install 3.13
uv sync --locked
```

planegcs has no prebuilt Mac package, so `uv sync` compiles it from source against Eigen from
Homebrew (CLAUDE.md section 9 item 2). That takes a few minutes the first time. If it fails, stop
and report the error: that is a dependency question for the owner (CLAUDE.md section 2 item 1).

## Check

Run these in order. Use `export QT_QPA_PLATFORM=offscreen` for the tests.

1. `uv run ruff format --check`
2. `uv run ruff check`
3. `uv run mypy`
4. `uv run pytest`: the default suite, about 6,800 tests.
5. `uv run pytest --run-slow tests/perf`: the speed budgets.
6. If time allows: `uv run pytest --run-slow --ignore=tests/ui/test_app_sweep.py`, then the
   app sweep `uv run pytest --run-slow tests/ui/test_app_sweep.py`. The sweep takes hours; run it
   in a few parallel shards with `-k`.

Some tests are marked as Windows or macOS only, or expect a known kernel difference (an xfail).
Those are fine.

## Build

```bash
uv run pyinstaller packaging/fdcad.spec --noconfirm
bash packaging/smoke_test.sh dist/FDCAD.app/Contents/MacOS/FDCAD
bash packaging/macos/make_dmg.sh 1.0.0-dev-$(date +%Y-%m-%d)
```

`make_dmg.sh` signs the app ad hoc (`codesign --sign -`), without which it does not start on Apple
Silicon (CLAUDE.md section 9 item 3), and writes `dist/FDCAD-<version>-macos-arm64.dmg`.

Then open the DMG, drag FDCAD to Applications, start it once by right clicking it and choosing
Open (an ad hoc signed app needs that the first time), open a sample from File, Samples, and check
that the 3D view draws, a sketch opens and a feature builds. The smoke test cannot check the 3D
view, because it runs without a screen.

## When something fails on the Mac only

1. Find the cause and fix it there, with a test that fails before the fix (CLAUDE.md section 6
   item 3). Keep Mac specific code small (section 9 item 6).
2. Record each fix in `DECISIONS.md` with the next free number and the format already used, and
   add a line to `CHANGELOG.md`.
3. Commit on a branch named `mac-fixes` and push it: `git push -u origin mac-fixes`. Do not push
   to `main`. The Windows session merges it after running the Windows suite.

## Report

Say what passed and what failed in each step above, what was fixed and on which commits, the
speed budget times next to their limits, and where the DMG is.
