---
name: fdcad-release
description: Use when building, packaging, signing or publishing FDCAD: local PyInstaller and installer builds, the Mac DMG, CI and release workflows, version tags and phase end pull requests.
---

# Building and releasing FDCAD

Read `PLAN.md` sections 12 and 13 and `CLAUDE.md` sections 4 and 9 first.

## 1. Files

1. `packaging/fdcad.spec`: PyInstaller one folder build (D43). Excludes the `vtk` and `matplotlib` Python packages (D60). Holds the Mac bundle settings and the `.fdef` document type.
2. `packaging/windows/fdcad.iss`: Inno Setup installer with the `.fdef` association and uninstaller. The AppId must never change (D61).
3. `packaging/macos/make_dmg.sh`: ad hoc signs `dist/FDCAD.app` with codesign and builds the DMG with hdiutil.
4. `.github/workflows/ci.yml`: tests on every push on Windows. macOS runs only on pull requests to `main` and manual runs while the repo is private (D35).
5. `.github/workflows/release.yml`: on a `v*` tag, builds both installers and creates the GitHub Release.

## 2. Local Windows build

1. `uv run pyinstaller packaging/fdcad.spec --noconfirm` gives `dist/FDCAD/FDCAD.exe`.
2. Compile the installer in PowerShell: `& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" /DAppVersion=X.Y.Z packaging\windows\fdcad.iss`. Output: `packaging/windows/Output/FDCAD-X.Y.Z-windows-x64-setup.exe`.
3. Smoke test without touching the owner's real install: run the setup with `/VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /DIR=<temp folder>`. Check that `HKCU:\Software\Classes\.fdef` is `FDCAD.Part`, open a `.fdef` file and confirm FDCAD starts. Then run `<temp folder>\unins000.exe /VERYSILENT` and confirm the folder and keys are gone.
4. Check budgets on the built exe: window visible in under 2 s, under 400 MB with an empty part.

## 3. Mac build (CI only)

1. Runner `macos-14` (Apple Silicon). Run `brew install eigen boost` before `uv sync`, because planegcs builds from source on Mac (D64).
2. PyInstaller gives `dist/FDCAD.app`. `bash packaging/macos/make_dmg.sh X.Y.Z` gives `dist/FDCAD-X.Y.Z-macos-arm64.dmg`.
3. The app must be ad hoc signed or it will not launch on Apple Silicon.
4. CI Mac runners have no GPU. The owner checks the viewport by hand on the MacBook Air M1.

## 4. Release steps

1. Set the same version in `pyproject.toml` and `src/fdcad/__init__.py`. Run `uv lock`.
2. Move `CHANGELOG.md` Unreleased items under `## [X.Y.Z]`. The release workflow uses that section as the release notes.
3. All checks pass: `uv run ruff format --check`, `uv run ruff check`, `uv run mypy`, `uv run pytest`.
4. Open the pull request from `phaseN` to `main` with the PLAN section 13 checklist filled in with what to try. Mac CI runs on it.
5. After the owner merges, tag `vX.Y.Z` on `main` and push the tag. Confirm the Release has both installers.

## 5. Rules

1. Releases are unsigned (no paid certificates). The README explains first launch on both systems.
2. Ship the license texts (`LICENSE`, `THIRD_PARTY_NOTICES.txt`, `SOURCE_OFFER.md`; written by `tools/third_party_notices.py`, D2860) in the bundle.
3. A new bundled dependency needs a `DECISIONS.md` entry with its license, which must be GPL v3 compatible.
4. Never push a tag or publish a release before the owner merges the phase pull request.
